from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx

from imi.universe.models import (
    InstrumentProfile,
)

IDX_COMPANY_PROFILES_ENDPOINT = (
    "https://www.idx.id/"
    "primary/ListedCompany/"
    "GetCompanyProfiles"
)

IDX_COMPANY_PROFILES_PAGE = (
    "https://www.idx.id/en/"
    "listed-companies/company-profiles/"
)


IDX_SECTOR_INDEX_MAP = {
    # Indonesian IDX-IC names
    "energi": "IDXENERGY",
    "barang baku": "IDXBASIC",
    "perindustrian": "IDXINDUST",
    "barang konsumen primer": "IDXNONCYC",
    "barang konsumen non-primer": "IDXCYCLIC",
    "kesehatan": "IDXHEALTH",
    "keuangan": "IDXFINANCE",
    "properti & real estat": "IDXPROPERT",
    "teknologi": "IDXTECHNO",
    "infrastruktur": "IDXINFRA",
    "transportasi & logistik": "IDXTRANS",

    # English aliases
    "energy": "IDXENERGY",
    "basic materials": "IDXBASIC",
    "industrials": "IDXINDUST",
    "consumer non-cyclicals": "IDXNONCYC",
    "consumer cyclicals": "IDXCYCLIC",
    "healthcare": "IDXHEALTH",
    "financials": "IDXFINANCE",
    "properties & real estate": "IDXPROPERT",
    "technology": "IDXTECHNO",
    "infrastructures": "IDXINFRA",
    "transportation & logistic": "IDXTRANS",
}


class IDXCompanyProfilesError(
    RuntimeError
):
    pass


@dataclass(frozen=True, slots=True)
class IDXCompanyProfilesResult:
    profiles: list[InstrumentProfile]
    raw_count: int
    provider_total: int | None


def _pick(
    row: dict[str, Any],
    *keys: str,
) -> Any:
    lowered = {
        str(key).lower(): value
        for key, value in row.items()
    }

    for key in keys:
        value = lowered.get(
            key.lower()
        )

        if value not in (
            None,
            "",
        ):
            return value

    return None


def _parse_date(
    value: Any,
) -> date | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    text_value = str(value).strip()

    if not text_value:
        return None

    if text_value.startswith(
        "/Date("
    ):
        digits = "".join(
            character
            for character in text_value
            if (
                character.isdigit()
                or character == "-"
            )
        )

        if digits:
            milliseconds = int(digits)

            return datetime.fromtimestamp(
                milliseconds / 1000,
                tz=UTC,
            ).date()

    iso_candidate = (
        text_value.replace(
            "Z",
            "+00:00",
        )
    )

    try:
        return datetime.fromisoformat(
            iso_candidate
        ).date()
    except ValueError:
        pass

    formats = (
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
    )

    for format_string in formats:
        try:
            return (
            datetime.strptime(
                text_value,
                format_string,
            )
            .replace(tzinfo=UTC)
            .date()
        )
        except ValueError:
            continue

    raise ValueError(
        "Unsupported IDX date: "
        f"{text_value}"
    )


def _normalize_sector(
    value: Any,
) -> str | None:
    if value is None:
        return None

    key = " ".join(
        str(value)
        .strip()
        .lower()
        .split()
    )

    return IDX_SECTOR_INDEX_MAP.get(
        key
    )


def normalize_idx_company_profile(
    row: dict[str, Any],
) -> InstrumentProfile:
    symbol_value = _pick(
        row,
        "KodeEmiten",
        "kode_emiten",
        "code",
        "symbol",
    )

    name_value = _pick(
        row,
        "NamaEmiten",
        "nama_emiten",
        "name",
        "company_name",
    )

    if symbol_value is None:
        raise ValueError(
            "IDX profile has no symbol."
        )

    if name_value is None:
        raise ValueError(
            "IDX profile has no name."
        )

    symbol = (
        str(symbol_value)
        .strip()
        .upper()
    )

    name = str(
        name_value
    ).strip()

    listed_date = _parse_date(
        _pick(
            row,
            "TanggalPencatatan",
            "listing_date",
            "listingdate",
            "listed_date",
        )
    )

    sector_name = _pick(
        row,
        "Sector",
        "Sektor",
        "NamaSektor",
    )

    subsector_name = _pick(
        row,
        "Subsector",
        "SubSektor",
        "NamaSubSektor",
    )

    industry_name = _pick(
        row,
        "Industry",
        "Industri",
        "NamaIndustri",
    )

    subindustry_name = _pick(
        row,
        "SubIndustry",
        "Sub-industry",
        "SubIndustri",
    )

    listing_board = _pick(
        row,
        "ListingBoard",
        "PapanPencatatan",
        "Board",
    )

    sector_code = _normalize_sector(
        sector_name
    )

    metadata = {
        "source_code": "IDX_OFFICIAL",
        "sector_name": sector_name,
        "subsector_name": subsector_name,
        "industry_name": industry_name,
        "subindustry_name":
            subindustry_name,
        "listing_board": listing_board,
        "raw_profile": row,
    }

    return InstrumentProfile(
        symbol=symbol,
        name=name,
        listed_date=listed_date,
        sector_code=sector_code,
        industry_code=None,
        metadata=metadata,
    )


def _extract_rows(
    payload: Any,
) -> tuple[
    list[dict[str, Any]],
    int | None,
]:
    if isinstance(payload, list):
        return payload, len(payload)

    if not isinstance(
        payload,
        dict,
    ):
        raise IDXCompanyProfilesError(
            "Unexpected IDX response type."
        )

    rows: Any = None

    for key in (
        "data",
        "Data",
        "results",
        "Results",
    ):
        candidate = payload.get(key)

        if isinstance(
            candidate,
            list,
        ):
            rows = candidate
            break

    if rows is None:
        raise IDXCompanyProfilesError(
            "IDX response does not "
            "contain company rows."
        )

    provider_total = None

    for key in (
        "recordsTotal",
        "RecordsTotal",
        "total",
        "Total",
    ):
        value = payload.get(key)

        if value is not None:
            provider_total = int(value)
            break

    return rows, provider_total


def fetch_idx_company_profiles(
    *,
    timeout: float = 30.0,
    length: int = 9999,
) -> IDXCompanyProfilesResult:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "Indonesia-Market-Intelligence"
        ),
        "Accept": (
            "application/json, "
            "text/plain, */*"
        ),
        "Referer": (
            IDX_COMPANY_PROFILES_PAGE
        ),
    }

    params = {
        "emitenType": "s",
        "start": 0,
        "length": length,
    }

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(
            IDX_COMPANY_PROFILES_ENDPOINT,
            params=params,
        )

    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise IDXCompanyProfilesError(
            "IDX company profile endpoint "
            "did not return JSON."
        ) from exc

    raw_rows, provider_total = (
        _extract_rows(payload)
    )

    profiles = []

    for row in raw_rows:
        if not isinstance(row, dict):
            continue

        profiles.append(
            normalize_idx_company_profile(
                row
            )
        )

    return IDXCompanyProfilesResult(
        profiles=profiles,
        raw_count=len(raw_rows),
        provider_total=provider_total,
    )