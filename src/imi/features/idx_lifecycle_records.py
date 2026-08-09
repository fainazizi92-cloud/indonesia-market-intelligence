import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

SYMBOL_PATTERN = re.compile(
    r"^[A-Z0-9]{1,12}$"
)


@dataclass(
    frozen=True,
    slots=True,
)
class NewListingRecord:
    code: str
    issuer_name: str
    listing_date: date
    listed_shares: int
    shares_offered: int
    par_value: Decimal
    offering_price: Decimal
    fund_raised: Decimal
    listing_type: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class NewListingPage:
    records: tuple[
        NewListingRecord,
        ...
    ]
    total_items: int
    page_size: int
    page_number: int
    order_by: str
    search: str


def _required_text(
    row: dict[str, Any],
    *,
    key: str,
) -> str:
    value = row.get(
        key
    )

    if value is None:
        raise ValueError(
            f"Missing required field: {key}"
        )

    normalized = str(
        value
    ).strip()

    if not normalized:
        raise ValueError(
            f"Empty required field: {key}"
        )

    return normalized


def _required_int(
    row: dict[str, Any],
    *,
    key: str,
) -> int:
    value = row.get(
        key
    )

    if value is None:
        raise ValueError(
            f"Missing numeric field: {key}"
        )

    try:
        decimal_value = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        ValueError,
    ) as exc:
        raise ValueError(
            f"Invalid numeric field: {key}"
        ) from exc

    if not decimal_value.is_finite():
        raise ValueError(
            f"Non-finite numeric field: {key}"
        )

    integral = (
        decimal_value
        .to_integral_value()
    )

    if decimal_value != integral:
        raise ValueError(
            f"Expected integer field: {key}"
        )

    result = int(
        integral
    )

    if result < 0:
        raise ValueError(
            f"Negative numeric field: {key}"
        )

    return result


def _required_decimal(
    row: dict[str, Any],
    *,
    key: str,
) -> Decimal:
    value = row.get(
        key
    )

    if value is None:
        raise ValueError(
            f"Missing decimal field: {key}"
        )

    try:
        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        ValueError,
    ) as exc:
        raise ValueError(
            f"Invalid decimal field: {key}"
        ) from exc

    if not result.is_finite():
        raise ValueError(
            f"Non-finite decimal field: {key}"
        )

    if result < 0:
        raise ValueError(
            f"Negative decimal field: {key}"
        )

    return result


def _parse_iso_date(
    value: str,
) -> date:
    try:
        return date.fromisoformat(
            value
        )

    except ValueError as exc:
        raise ValueError(
            "Invalid ListingDate: "
            f"{value}"
        ) from exc


def parse_new_listing_record(
    row: dict[str, Any],
    *,
    expected_year: int,
    expected_month: int,
) -> NewListingRecord:
    code = (
        _required_text(
            row,
            key="code",
        )
        .upper()
    )

    if not SYMBOL_PATTERN.fullmatch(
        code
    ):
        raise ValueError(
            f"Invalid IDX symbol: {code}"
        )

    issuer_name = (
        _required_text(
            row,
            key="issuerName",
        )
    )

    listing_date = (
        _parse_iso_date(
            _required_text(
                row,
                key="ListingDate",
            )
        )
    )

    if (
        listing_date.year
        != expected_year
        or listing_date.month
        != expected_month
    ):
        raise ValueError(
            "ListingDate outside requested "
            f"month: {code} "
            f"{listing_date.isoformat()}"
        )

    listing_type_value = (
        row.get(
            "Type"
        )
    )

    listing_type = (
        None
        if listing_type_value is None
        else str(
            listing_type_value
        ).strip()
        or None
    )

    return NewListingRecord(
        code=code,
        issuer_name=issuer_name,
        listing_date=listing_date,
        listed_shares=(
            _required_int(
                row,
                key="ListedShares",
            )
        ),
        shares_offered=(
            _required_int(
                row,
                key="NumOfShares",
            )
        ),
        par_value=(
            _required_decimal(
                row,
                key="Nominal",
            )
        ),
        offering_price=(
            _required_decimal(
                row,
                key="Offering",
            )
        ),
        fund_raised=(
            _required_decimal(
                row,
                key="FundRaised",
            )
        ),
        listing_type=(
            listing_type
        ),
    )


def parse_new_listing_payload(
    payload: Any,
    *,
    expected_year: int,
    expected_month: int,
) -> NewListingPage:
    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(
            "New-listing payload "
            "must be an object."
        )

    raw_data = payload.get(
        "data"
    )

    if not isinstance(
        raw_data,
        list,
    ):
        raise TypeError(
            "Payload data must be a list."
        )

    raw_meta = payload.get(
        "meta"
    )

    if not isinstance(
        raw_meta,
        dict,
    ):
        raise TypeError(
            "Payload meta must be an object."
        )

    records = []
    seen_codes = set()

    for raw_row in raw_data:
        if not isinstance(
            raw_row,
            dict,
        ):
            raise TypeError(
                "Payload data row "
                "must be an object."
            )

        record = (
            parse_new_listing_record(
                raw_row,
                expected_year=(
                    expected_year
                ),
                expected_month=(
                    expected_month
                ),
            )
        )

        if record.code in seen_codes:
            raise ValueError(
                "Duplicate new-listing "
                f"symbol: {record.code}"
            )

        seen_codes.add(
            record.code
        )

        records.append(
            record
        )

    try:
        total_items = int(
            raw_meta[
                "totalItems"
            ]
        )

        page_size = int(
            raw_meta[
                "pageSize"
            ]
        )

        page_number = int(
            raw_meta[
                "pageNumber"
            ]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Invalid pagination metadata."
        ) from exc

    if total_items < 0:
        raise ValueError(
            "totalItems cannot be negative."
        )

    if page_size <= 0:
        raise ValueError(
            "pageSize must be positive."
        )

    if page_number <= 0:
        raise ValueError(
            "pageNumber must be positive."
        )

    return NewListingPage(
        records=tuple(
            records
        ),
        total_items=(
            total_items
        ),
        page_size=(
            page_size
        ),
        page_number=(
            page_number
        ),
        order_by=str(
            raw_meta.get(
                "orderBy",
                "",
            )
            or ""
        ),
        search=str(
            raw_meta.get(
                "search",
                "",
            )
            or ""
        ),
    )