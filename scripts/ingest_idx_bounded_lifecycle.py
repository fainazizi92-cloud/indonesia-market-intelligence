import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from imi.db import engine
from imi.repositories.point_in_time import (
    UPSERT_AUDIT_STATE,
    UPSERT_AVAILABILITY,
    UPSERT_LIFECYCLE,
    UPSERT_UNIVERSE_MEMBERSHIP,
)

DEFAULT_BOUNDED_SNAPSHOT = "data/derived/idx_bounded_lifecycle_2023_2025.json"
DEFAULT_MEMBERSHIP_SNAPSHOT = "data/derived/idx_monthly_membership_delta.json"

WINDOW_START = date(2023, 1, 1)
WINDOW_END = date(2025, 12, 31)

DB_SOURCE_CODE = "IDX_BOUNDED_LIFECYCLE_2023_2025_V1"
UNIVERSE_CODE = "IDX_ALL_HISTORICAL"
AVAILABILITY_DATASET_CODE = "IDX_BOUNDED_LIFECYCLE_2023_2025"

IDX_ORIGIN = "https://www.idx.id"
API_PATH = "/primary/DigitalStatistic/GetApiDataPaginated"
PAGE_SIZE = 1000

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "bounded-lifecycle-db-ingestion"
    ),
    "Accept": "application/json,text/plain,*/*",
}


ACTIVE_SPECIAL_SECURITY_REGISTRY = {
    "CNTB": {
        "name": "Century Textile Industry Tbk Seri B",
        "listed_date": date(2000, 12, 22),
        "security_type": "COMMON_SHARE_SERIES_B_COMPANY_LISTING",
        "status": "ACTIVE",
        "source": "KSEI_REGISTERED_SECURITIES",
        "source_reference": (
            "https://web.ksei.co.id/services/registered-securities/"
            "shares/lc/CNTB"
        ),
        "research_eligible_default": False,
    },
    "CNTX": {
        "name": "Century Textile Industry Tbk Seri A",
        "listed_date": date(1989, 6, 16),
        "security_type": "PREFERRED_SHARE_SERIES_A",
        "status": "ACTIVE",
        "source": "KSEI_REGISTERED_SECURITIES",
        "source_reference": (
            "https://web.ksei.co.id/services/registered-securities/"
            "shares/lc/CNTX"
        ),
        "research_eligible_default": False,
    },
}


REQUIRED_TABLES = (
    "instruments",
    "instrument_lifecycle_history",
    "historical_universe_membership",
    "data_publication_availability",
    "point_in_time_audit_state",
)


@dataclass(frozen=True, slots=True)
class InstrumentRow:
    instrument_id: str
    symbol: str
    name: str
    listed_date: date | None
    delisted_date: date | None
    is_active: bool


@dataclass(frozen=True, slots=True)
class MissingInstrumentResolution:
    symbol: str
    name: str
    evidence_year: int
    evidence_month: int
    listing_date: date | None
    delisting_date: date


@dataclass(frozen=True, slots=True)
class ActiveSpecialResolution:
    symbol: str
    name: str
    listing_date: date
    security_type: str
    source: str
    source_reference: str
    research_eligible_default: bool


@dataclass(frozen=True, slots=True)
class PreparedRows:
    lifecycle: tuple[dict[str, Any], ...]
    universe: tuple[dict[str, Any], ...]
    availability: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class PreflightResult:
    snapshot_version: str
    interval_count: int
    event_count: int
    unique_symbols: int
    matched_existing: int
    missing_symbols: tuple[str, ...]
    eligible_missing_delisted: tuple[str, ...]
    eligible_missing_active_special: tuple[str, ...]
    unsupported_missing: tuple[str, ...]
    resolved_missing: tuple[MissingInstrumentResolution, ...]
    resolved_active_special: tuple[ActiveSpecialResolution, ...]
    unresolved_missing: tuple[str, ...]
    gate_passed: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and optionally ingest the bounded 2023-2025 IDX "
            "lifecycle reconstruction into point-in-time infrastructure."
        )
    )
    parser.add_argument(
        "--snapshot",
        default=DEFAULT_BOUNDED_SNAPSHOT,
    )
    parser.add_argument(
        "--membership-snapshot",
        default=DEFAULT_MEMBERSHIP_SNAPSHOT,
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=25.0,
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Commit validated rows to PostgreSQL. Default is dry-run.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} root must be a JSON object.")
    return payload


def require_bounded_snapshot(payload: dict[str, Any]) -> None:
    if payload.get("bounded_universe_ready") is not True:
        raise ValueError("Bounded lifecycle snapshot gate is not PASS.")

    if payload.get("monthly_presence_replay_ready") is not True:
        raise ValueError("Monthly presence replay is not ready.")

    if payload.get("event_date_ready") is not True:
        raise ValueError("Lifecycle event-date gate is not ready.")

    if payload.get("window_start") != WINDOW_START.isoformat():
        raise ValueError("Unexpected bounded snapshot window_start.")

    if payload.get("window_end") != WINDOW_END.isoformat():
        raise ValueError("Unexpected bounded snapshot window_end.")


def check_required_tables(connection: Connection) -> None:
    missing = []
    for table_name in REQUIRED_TABLES:
        exists = connection.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": f"public.{table_name}"},
        ).scalar_one_or_none()
        if exists is None:
            missing.append(table_name)

    if missing:
        raise RuntimeError(
            "Required database tables are missing: " + ", ".join(missing)
        )


def load_instruments(connection: Connection) -> dict[str, InstrumentRow]:
    rows = connection.execute(
        text(
            """
            SELECT
                id::text AS instrument_id,
                UPPER(symbol) AS symbol,
                name,
                listed_date,
                delisted_date,
                is_active
            FROM instruments
            WHERE exchange = 'IDX'
              AND asset_type = 'EQUITY'
            """
        )
    ).mappings()

    result = {}
    for row in rows:
        symbol = str(row["symbol"]).strip().upper()
        if symbol in result:
            raise RuntimeError(f"Duplicate IDX equity symbol in instruments: {symbol}")
        result[symbol] = InstrumentRow(
            instrument_id=str(row["instrument_id"]),
            symbol=symbol,
            name=str(row["name"]),
            listed_date=row["listed_date"],
            delisted_date=row["delisted_date"],
            is_active=bool(row["is_active"]),
        )
    return result


def snapshot_symbols(payload: dict[str, Any]) -> set[str]:
    result = set()
    intervals = payload.get("intervals", [])
    if not isinstance(intervals, list):
        raise TypeError("Snapshot intervals must be a list.")

    for interval in intervals:
        if not isinstance(interval, dict):
            raise TypeError("Snapshot interval row must be an object.")
        symbol = interval.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("Snapshot interval has invalid symbol.")
        result.add(symbol.strip().upper())
    return result


def event_index(
    payload: dict[str, Any],
) -> tuple[
    dict[str, date],
    dict[str, date],
    dict[tuple[str, str], dict[str, Any]],
]:
    listing_dates: dict[str, date] = {}
    delisting_dates: dict[str, date] = {}
    events_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    events = payload.get("events", [])
    if not isinstance(events, list):
        raise TypeError("Snapshot events must be a list.")

    for event in events:
        if not isinstance(event, dict):
            raise TypeError("Snapshot event row must be an object.")

        symbol_value = event.get("symbol")
        date_value = event.get("effective_date")
        event_type = event.get("event_type")

        if not isinstance(symbol_value, str):
            raise TypeError("Lifecycle event symbol must be a string.")
        if not symbol_value.strip():
            raise ValueError("Lifecycle event has an empty symbol.")
        if not isinstance(date_value, str):
            raise TypeError("Lifecycle event effective_date must be a string.")
        if not isinstance(event_type, str):
            raise TypeError("Lifecycle event event_type must be a string.")

        symbol = symbol_value.strip().upper()
        effective_date = date.fromisoformat(date_value)
        events_by_key[(symbol, event_type)] = event

        if event_type in {"LISTED", "RELISTED"}:
            current = listing_dates.get(symbol)
            if current is None or effective_date < current:
                listing_dates[symbol] = effective_date
        elif event_type == "DELISTED":
            if symbol in delisting_dates:
                raise ValueError(f"Multiple bounded delisting events for {symbol}.")
            delisting_dates[symbol] = effective_date

    return listing_dates, delisting_dates, events_by_key


def membership_contract(payload: dict[str, Any]) -> tuple[str, str]:
    contract = payload.get("contract")
    if not isinstance(contract, dict):
        raise TypeError("Membership snapshot contract is missing.")

    url_name = contract.get("selected_url_name")
    symbol_field = contract.get("selected_symbol_field")

    if not isinstance(url_name, str) or not url_name.strip():
        raise ValueError("Membership snapshot has no selected urlName.")
    if not isinstance(symbol_field, str) or not symbol_field.strip():
        raise ValueError("Membership snapshot has no selected symbol field.")

    return url_name, symbol_field


def symbol_latest_periods(
    payload: dict[str, Any],
    symbols: set[str],
) -> dict[str, tuple[int, int]]:
    periods: dict[str, tuple[int, int]] = {}
    months = payload.get("months", [])
    if not isinstance(months, list):
        raise TypeError("Membership snapshot months must be a list.")

    for month_row in months:
        if not isinstance(month_row, dict):
            continue
        if month_row.get("status") != "VALID":
            continue

        year = month_row.get("year")
        month = month_row.get("month")
        month_symbols = month_row.get("symbols")

        if not isinstance(year, int) or not isinstance(month, int):
            continue
        if not (2023 <= year <= 2025):
            continue
        if not isinstance(month_symbols, list):
            continue

        normalized = {
            value.strip().upper()
            for value in month_symbols
            if isinstance(value, str) and value.strip()
        }
        for symbol in symbols & normalized:
            periods[symbol] = (year, month)

    return periods


def api_params(
    *,
    url_name: str,
    year: int,
    month: int,
) -> dict[str, str | int]:
    return {
        "urlName": url_name,
        "periodYear": year,
        "periodMonth": month,
        "periodType": "monthly",
        "isPrint": "False",
        "cumulative": "false",
        "pageSize": PAGE_SIZE,
        "pageNumber": 1,
        "orderBy": "",
        "search": "",
    }


def response_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TypeError("IDX API JSON root is not an object.")
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise TypeError("IDX API data is not an array.")
    return [row for row in rows if isinstance(row, dict)]


def detect_name_field(
    rows: list[dict[str, Any]],
    symbol_field: str,
) -> str | None:
    if not rows:
        return None

    keys = set().union(*(row.keys() for row in rows))
    preferred = (
        "StockName",
        "Stock Name",
        "stockName",
        "CompanyName",
        "Company Name",
        "IssuerName",
        "Name",
        "NamaSaham",
        "NamaEmiten",
    )

    for key in preferred:
        if key in keys and key != symbol_field:
            return key

    candidates = [
        key
        for key in keys
        if key != symbol_field
        and isinstance(key, str)
        and "name" in key.casefold()
    ]

    best_key = None
    best_count = -1
    for key in candidates:
        count = sum(
            isinstance(row.get(key), str) and bool(row.get(key).strip())
            for row in rows
        )
        if count > best_count:
            best_key = key
            best_count = count

    return best_key


def fetch_period_rows(
    *,
    client: httpx.Client,
    url_name: str,
    year: int,
    month: int,
) -> list[dict[str, Any]]:
    response = client.get(
        IDX_ORIGIN + API_PATH,
        params=api_params(
            url_name=url_name,
            year=year,
            month=month,
        ),
    )
    response.raise_for_status()
    return response_rows(response.json())


def resolve_missing_instruments(
    *,
    missing_symbols: set[str],
    eligible_delisted: set[str],
    listing_dates: dict[str, date],
    delisting_dates: dict[str, date],
    membership_payload: dict[str, Any],
    timeout: float,
) -> tuple[
    tuple[MissingInstrumentResolution, ...],
    tuple[str, ...],
]:
    if not eligible_delisted:
        return (), ()

    url_name, symbol_field = membership_contract(membership_payload)
    latest_period = symbol_latest_periods(
        membership_payload,
        eligible_delisted,
    )

    missing_periods = eligible_delisted - set(latest_period)
    if missing_periods:
        return (), tuple(sorted(missing_periods))

    grouped: dict[tuple[int, int], set[str]] = defaultdict(set)
    for symbol, period in latest_period.items():
        grouped[period].add(symbol)

    resolved: dict[str, MissingInstrumentResolution] = {}
    unresolved = set(eligible_delisted)

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for (year, month), symbols in sorted(grouped.items()):
            rows = fetch_period_rows(
                client=client,
                url_name=url_name,
                year=year,
                month=month,
            )
            name_field = detect_name_field(rows, symbol_field)
            if name_field is None:
                continue

            by_symbol = {}
            for row in rows:
                symbol_value = row.get(symbol_field)
                if not isinstance(symbol_value, str):
                    continue
                symbol = symbol_value.strip().upper()
                if symbol not in symbols:
                    continue
                name_value = row.get(name_field)
                if not isinstance(name_value, str) or not name_value.strip():
                    continue
                by_symbol[symbol] = name_value.strip()

            for symbol in symbols:
                name = by_symbol.get(symbol)
                if name is None:
                    continue
                resolved[symbol] = MissingInstrumentResolution(
                    symbol=symbol,
                    name=name,
                    evidence_year=year,
                    evidence_month=month,
                    listing_date=listing_dates.get(symbol),
                    delisting_date=delisting_dates[symbol],
                )
                unresolved.discard(symbol)

    unexpected = missing_symbols - eligible_delisted
    unresolved.update(unexpected)

    return (
        tuple(sorted(resolved.values(), key=lambda item: item.symbol)),
        tuple(sorted(unresolved)),
    )


def resolve_active_special_instruments(
    symbols: set[str],
) -> tuple[ActiveSpecialResolution, ...]:
    resolutions = []

    for symbol in sorted(symbols):
        record = ACTIVE_SPECIAL_SECURITY_REGISTRY.get(symbol)
        if record is None:
            continue

        name = record.get("name")
        listed_date = record.get("listed_date")
        security_type = record.get("security_type")
        source = record.get("source")
        source_reference = record.get("source_reference")
        research_eligible_default = record.get("research_eligible_default")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Active special security has invalid name: {symbol}")
        if not isinstance(listed_date, date):
            raise TypeError(
                f"Active special security listed_date must be date: {symbol}"
            )
        if not isinstance(security_type, str) or not security_type.strip():
            raise ValueError(
                f"Active special security has invalid security_type: {symbol}"
            )
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"Active special security has invalid source: {symbol}")
        if not isinstance(source_reference, str) or not source_reference.strip():
            raise ValueError(
                f"Active special security has invalid source_reference: {symbol}"
            )
        if not isinstance(research_eligible_default, bool):
            raise TypeError(
                "Active special security research_eligible_default "
                f"must be bool: {symbol}"
            )

        resolutions.append(
            ActiveSpecialResolution(
                symbol=symbol,
                name=name.strip(),
                listing_date=listed_date,
                security_type=security_type.strip(),
                source=source.strip(),
                source_reference=source_reference.strip(),
                research_eligible_default=research_eligible_default,
            )
        )

    return tuple(resolutions)


def run_preflight(
    *,
    connection: Connection,
    bounded_payload: dict[str, Any],
    membership_payload: dict[str, Any],
    timeout: float,
) -> PreflightResult:
    require_bounded_snapshot(bounded_payload)
    check_required_tables(connection)

    instruments = load_instruments(connection)
    symbols = snapshot_symbols(bounded_payload)
    listing_dates, delisting_dates, _ = event_index(bounded_payload)

    missing = symbols - set(instruments)
    active_special = missing & set(ACTIVE_SPECIAL_SECURITY_REGISTRY)
    eligible_delisted = (missing - active_special) & set(delisting_dates)
    unsupported_missing = missing - eligible_delisted - active_special

    resolved, unresolved = resolve_missing_instruments(
        missing_symbols=eligible_delisted,
        eligible_delisted=eligible_delisted,
        listing_dates=listing_dates,
        delisting_dates=delisting_dates,
        membership_payload=membership_payload,
        timeout=timeout,
    )

    resolved_active_special = resolve_active_special_instruments(active_special)

    intervals = bounded_payload.get("intervals", [])
    events = bounded_payload.get("events", [])
    if not isinstance(intervals, list) or not isinstance(events, list):
        raise TypeError("Bounded snapshot intervals/events must be lists.")

    snapshot_version = bounded_payload.get("snapshot_version")
    if not isinstance(snapshot_version, str):
        snapshot_version = "UNKNOWN"

    gate_passed = (
        not unsupported_missing
        and not unresolved
        and len(resolved) == len(eligible_delisted)
        and len(resolved_active_special) == len(active_special)
    )

    return PreflightResult(
        snapshot_version=snapshot_version,
        interval_count=len(intervals),
        event_count=len(events),
        unique_symbols=len(symbols),
        matched_existing=len(symbols & set(instruments)),
        missing_symbols=tuple(sorted(missing)),
        eligible_missing_delisted=tuple(sorted(eligible_delisted)),
        eligible_missing_active_special=tuple(sorted(active_special)),
        unsupported_missing=tuple(sorted(unsupported_missing)),
        resolved_missing=resolved,
        resolved_active_special=resolved_active_special,
        unresolved_missing=unresolved,
        gate_passed=gate_passed,
    )


def insert_historical_stubs(
    connection: Connection,
    resolutions: tuple[MissingInstrumentResolution, ...],
) -> int:
    statement = text(
        """
        INSERT INTO instruments (
            symbol,
            name,
            asset_type,
            exchange,
            currency,
            listed_date,
            delisted_date,
            is_active,
            metadata
        )
        VALUES (
            :symbol,
            :name,
            'EQUITY'::asset_type,
            'IDX',
            'IDR',
            :listed_date,
            :delisted_date,
            FALSE,
            CAST(:metadata AS jsonb)
        )
        ON CONFLICT (
            symbol,
            exchange,
            asset_type
        )
        DO NOTHING
        """
    )

    parameters = []
    for item in resolutions:
        parameters.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "listed_date": item.listing_date,
                "delisted_date": item.delisting_date,
                "metadata": json.dumps(
                    {
                        "historical_stub": True,
                        "source": "IDX Table of Stock Price",
                        "evidence_year": item.evidence_year,
                        "evidence_month": item.evidence_month,
                        "created_for": DB_SOURCE_CODE,
                        "current_status_basis": "ADJUDICATED_DELISTING",
                    }
                ),
            }
        )

    if parameters:
        connection.execute(statement, parameters)
    return len(parameters)


def insert_active_special_stubs(
    connection: Connection,
    resolutions: tuple[ActiveSpecialResolution, ...],
) -> int:
    statement = text(
        """
        INSERT INTO instruments (
            symbol,
            name,
            asset_type,
            exchange,
            currency,
            listed_date,
            delisted_date,
            is_active,
            metadata
        )
        VALUES (
            :symbol,
            :name,
            'EQUITY'::asset_type,
            'IDX',
            'IDR',
            :listed_date,
            NULL,
            TRUE,
            CAST(:metadata AS jsonb)
        )
        ON CONFLICT (
            symbol,
            exchange,
            asset_type
        )
        DO NOTHING
        """
    )

    parameters = []
    for item in resolutions:
        parameters.append(
            {
                "symbol": item.symbol,
                "name": item.name,
                "listed_date": item.listing_date,
                "metadata": json.dumps(
                    {
                        "historical_stub": False,
                        "special_security_stub": True,
                        "security_type": item.security_type,
                        "source": item.source,
                        "source_reference": item.source_reference,
                        "created_for": DB_SOURCE_CODE,
                        "current_status_basis": "KSEI_ACTIVE_SECURITY",
                        "research_eligible_default": item.research_eligible_default,
                        "current_universe_snapshot_member": False,
                    }
                ),
            }
        )

    if parameters:
        connection.execute(statement, parameters)
    return len(parameters)


def interval_quality(
    interval: dict[str, Any],
    events_by_key: dict[tuple[str, str], dict[str, Any]],
) -> str:
    symbol = str(interval["symbol"]).strip().upper()
    start_reason = interval.get("start_reason")
    end_reason = interval.get("end_reason")

    if end_reason == "DELISTED":
        return "WARNING"
    if start_reason == "WINDOW_BASELINE":
        return "WARNING"

    event = events_by_key.get((symbol, str(start_reason)))
    if event is None:
        return "WARNING"

    quality = event.get("quality")
    return quality if quality in {"VALID", "WARNING"} else "WARNING"


def prepare_rows(
    *,
    payload: dict[str, Any],
    instrument_ids: dict[str, InstrumentRow],
    snapshot_path: Path,
) -> PreparedRows:
    listing_dates, _delisting_dates, events_by_key = event_index(payload)

    lifecycle_rows = []
    universe_rows = []
    availability_rows = []

    intervals = payload.get("intervals", [])
    if not isinstance(intervals, list):
        raise TypeError("Snapshot intervals must be a list.")

    for interval in intervals:
        if not isinstance(interval, dict):
            raise TypeError("Snapshot interval must be an object.")

        symbol = str(interval["symbol"]).strip().upper()
        instrument = instrument_ids.get(symbol)
        if instrument is None:
            raise LookupError(f"Instrument not matched after stub creation: {symbol}")

        valid_from = date.fromisoformat(str(interval["valid_from"]))
        valid_to_value = interval.get("valid_to")
        end_reason = interval.get("end_reason")
        start_reason = str(interval.get("start_reason") or "UNKNOWN")

        delisting_date = None
        if end_reason == "DELISTED":
            if not isinstance(valid_to_value, str):
                raise ValueError(f"Delisted interval without valid_to: {symbol}")
            delisting_date = date.fromisoformat(valid_to_value)
            active_to = delisting_date - timedelta(days=1)
        else:
            active_to = WINDOW_END

        if active_to < valid_from:
            raise ValueError(f"Invalid bounded active interval for {symbol}.")

        listing_date = listing_dates.get(symbol)
        if start_reason == "WINDOW_BASELINE":
            listing_date = None

        quality = interval_quality(interval, events_by_key)
        base_evidence = {
            "symbol": symbol,
            "snapshot_version": payload.get("snapshot_version"),
            "snapshot_path": str(snapshot_path),
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
            "window_bounded": True,
            "start_reason": start_reason,
            "end_reason": end_reason,
            "strict_pit_ready": False,
        }

        lifecycle_rows.append(
            {
                "instrument_id": instrument.instrument_id,
                "effective_from": valid_from,
                "effective_to": active_to,
                "lifecycle_status": "LISTED",
                "listing_date": listing_date,
                "delisting_date": delisting_date,
                "source_code": DB_SOURCE_CODE,
                "source_reference": str(snapshot_path),
                "available_at": None,
                "availability_status": "UNKNOWN",
                "quality": quality,
                "evidence": json.dumps(base_evidence),
            }
        )

        universe_rows.append(
            {
                "instrument_id": instrument.instrument_id,
                "universe_code": UNIVERSE_CODE,
                "valid_from": valid_from,
                "valid_to": active_to,
                "membership_status": "ACTIVE",
                "source_code": DB_SOURCE_CODE,
                "available_at": None,
                "availability_status": "UNKNOWN",
                "point_in_time_safe": False,
                "evidence": json.dumps(base_evidence),
            }
        )

        if delisting_date is not None:
            inactive_evidence = {
                **base_evidence,
                "state_transition": "DELISTED",
                "delisting_effective_date": delisting_date.isoformat(),
            }

            lifecycle_rows.append(
                {
                    "instrument_id": instrument.instrument_id,
                    "effective_from": delisting_date,
                    "effective_to": WINDOW_END,
                    "lifecycle_status": "DELISTED",
                    "listing_date": None,
                    "delisting_date": delisting_date,
                    "source_code": DB_SOURCE_CODE,
                    "source_reference": str(snapshot_path),
                    "available_at": None,
                    "availability_status": "UNKNOWN",
                    "quality": "WARNING",
                    "evidence": json.dumps(inactive_evidence),
                }
            )

            universe_rows.append(
                {
                    "instrument_id": instrument.instrument_id,
                    "universe_code": UNIVERSE_CODE,
                    "valid_from": delisting_date,
                    "valid_to": WINDOW_END,
                    "membership_status": "INACTIVE",
                    "source_code": DB_SOURCE_CODE,
                    "available_at": None,
                    "availability_status": "UNKNOWN",
                    "point_in_time_safe": False,
                    "evidence": json.dumps(inactive_evidence),
                }
            )

    events = payload.get("events", [])
    if not isinstance(events, list):
        raise TypeError("Snapshot events must be a list.")

    for event in events:
        if not isinstance(event, dict):
            continue

        symbol_value = event.get("symbol")
        event_type = event.get("event_type")
        effective_value = event.get("effective_date")
        if not isinstance(symbol_value, str):
            continue
        if not isinstance(event_type, str) or not isinstance(effective_value, str):
            continue

        symbol = symbol_value.strip().upper()
        if symbol not in instrument_ids:
            raise LookupError(f"Availability event instrument not matched: {symbol}")

        observation_date = date.fromisoformat(effective_value)
        availability_rows.append(
            {
                "dataset_code": AVAILABILITY_DATASET_CODE,
                "observation_key": f"{symbol}:{event_type}",
                "observation_date": observation_date,
                "published_at": None,
                "available_at": None,
                "availability_status": "UNKNOWN",
                "source_code": str(event.get("source_code") or DB_SOURCE_CODE),
                "source_reference": str(snapshot_path),
                "point_in_time_safe": False,
                "evidence": json.dumps(
                    {
                        "symbol": symbol,
                        "event_type": event_type,
                        "event_quality": event.get("quality"),
                        "evidence_status": event.get("evidence_status"),
                        "snapshot_version": payload.get("snapshot_version"),
                        "historical_available_at": "UNKNOWN",
                    }
                ),
            }
        )

    return PreparedRows(
        lifecycle=tuple(lifecycle_rows),
        universe=tuple(universe_rows),
        availability=tuple(availability_rows),
    )


def upsert_prepared_rows(
    *,
    connection: Connection,
    rows: PreparedRows,
) -> None:
    if rows.lifecycle:
        connection.execute(UPSERT_LIFECYCLE, list(rows.lifecycle))
    if rows.universe:
        connection.execute(UPSERT_UNIVERSE_MEMBERSHIP, list(rows.universe))
    if rows.availability:
        connection.execute(UPSERT_AVAILABILITY, list(rows.availability))

    observation_dates = [row["observation_date"] for row in rows.availability]
    connection.execute(
        UPSERT_AUDIT_STATE,
        {
            "dataset_code": AVAILABILITY_DATASET_CODE,
            "total_observations": len(rows.availability),
            "known_availability": 0,
            "unknown_availability": len(rows.availability),
            "estimated_availability": 0,
            "pit_safe_observations": 0,
            "first_observation_date": min(observation_dates) if observation_dates else None,
            "last_observation_date": max(observation_dates) if observation_dates else None,
            "evidence": json.dumps(
                {
                    "source_code": DB_SOURCE_CODE,
                    "window_start": WINDOW_START.isoformat(),
                    "window_end": WINDOW_END.isoformat(),
                    "strict_pit_ready": False,
                }
            ),
        },
    )


def validation_counts(
    connection: Connection,
) -> dict[str, int]:
    lifecycle_count = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM instrument_lifecycle_history
            WHERE source_code = :source_code
            """
        ),
        {"source_code": DB_SOURCE_CODE},
    ).scalar_one()

    universe_count = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM historical_universe_membership
            WHERE source_code = :source_code
              AND universe_code = :universe_code
            """
        ),
        {
            "source_code": DB_SOURCE_CODE,
            "universe_code": UNIVERSE_CODE,
        },
    ).scalar_one()

    universe_pit_true = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM historical_universe_membership
            WHERE source_code = :source_code
              AND universe_code = :universe_code
              AND point_in_time_safe = TRUE
            """
        ),
        {
            "source_code": DB_SOURCE_CODE,
            "universe_code": UNIVERSE_CODE,
        },
    ).scalar_one()

    universe_not_unknown = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM historical_universe_membership
            WHERE source_code = :source_code
              AND universe_code = :universe_code
              AND availability_status <> 'UNKNOWN'
            """
        ),
        {
            "source_code": DB_SOURCE_CODE,
            "universe_code": UNIVERSE_CODE,
        },
    ).scalar_one()

    lifecycle_overlap = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM instrument_lifecycle_history a
            JOIN instrument_lifecycle_history b
              ON a.instrument_id = b.instrument_id
             AND a.source_code = b.source_code
             AND a.id < b.id
             AND a.effective_from <= COALESCE(b.effective_to, DATE '9999-12-31')
             AND b.effective_from <= COALESCE(a.effective_to, DATE '9999-12-31')
            WHERE a.source_code = :source_code
            """
        ),
        {"source_code": DB_SOURCE_CODE},
    ).scalar_one()

    universe_overlap = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM historical_universe_membership a
            JOIN historical_universe_membership b
              ON a.instrument_id = b.instrument_id
             AND a.universe_code = b.universe_code
             AND a.source_code = b.source_code
             AND a.valid_from < b.valid_from
             AND a.valid_from <= COALESCE(b.valid_to, DATE '9999-12-31')
             AND b.valid_from <= COALESCE(a.valid_to, DATE '9999-12-31')
            WHERE a.source_code = :source_code
              AND a.universe_code = :universe_code
            """
        ),
        {
            "source_code": DB_SOURCE_CODE,
            "universe_code": UNIVERSE_CODE,
        },
    ).scalar_one()

    availability_count = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM data_publication_availability
            WHERE dataset_code = :dataset_code
            """
        ),
        {"dataset_code": AVAILABILITY_DATASET_CODE},
    ).scalar_one()

    return {
        "lifecycle_count": int(lifecycle_count),
        "universe_count": int(universe_count),
        "universe_pit_true": int(universe_pit_true),
        "universe_not_unknown": int(universe_not_unknown),
        "lifecycle_overlap": int(lifecycle_overlap),
        "universe_overlap": int(universe_overlap),
        "availability_count": int(availability_count),
    }


def print_preflight(result: PreflightResult) -> None:
    print("1. INSTRUMENT MATCHING")
    print(f"  Snapshot version          : {result.snapshot_version}")
    print(f"  Universe intervals        : {result.interval_count}")
    print(f"  Lifecycle events          : {result.event_count}")
    print(f"  Unique bounded symbols    : {result.unique_symbols}")
    print(f"  Existing DB matches       : {result.matched_existing}")
    print(f"  Missing instruments       : {len(result.missing_symbols)}")
    print(
        "  Missing symbols           : "
        + (", ".join(result.missing_symbols) or "-")
    )
    print(
        "  Eligible historical stubs : "
        + (", ".join(result.eligible_missing_delisted) or "-")
    )
    print(
        "  Active special securities : "
        + (", ".join(result.eligible_missing_active_special) or "-")
    )
    print(
        "  Unsupported missing       : "
        + (", ".join(result.unsupported_missing) or "-")
    )
    print(f"  Official delisted resolved: {len(result.resolved_missing)}")
    print(f"  Active special resolved   : {len(result.resolved_active_special)}")
    print(
        "  Unresolved missing        : "
        + (", ".join(result.unresolved_missing) or "-")
    )
    print(f"  Instrument gate           : {'PASS' if result.gate_passed else 'FAIL'}")
    print()

    if result.resolved_missing:
        print("2. HISTORICAL STUB PLAN")
        for item in result.resolved_missing:
            print(
                f"  {item.symbol:<8} {item.name} "
                f"source_month={item.evidence_year}-{item.evidence_month:02d} "
                f"delisted={item.delisting_date}"
            )
        print()

    if result.resolved_active_special:
        print("2B. ACTIVE SPECIAL SECURITY PLAN")
        for item in result.resolved_active_special:
            print(
                f"  {item.symbol:<8} {item.name} "
                f"listed={item.listing_date} "
                f"type={item.security_type} "
                f"research_default={item.research_eligible_default}"
            )
        print()


def main() -> None:
    args = parse_args()

    snapshot_path = Path(args.snapshot)
    membership_path = Path(args.membership_snapshot)

    if not snapshot_path.exists():
        raise FileNotFoundError(snapshot_path)
    if not membership_path.exists():
        raise FileNotFoundError(membership_path)
    if args.timeout <= 0:
        raise ValueError("timeout must be positive.")

    bounded_payload = load_json(snapshot_path)
    membership_payload = load_json(membership_path)

    print("Indonesia Market Intelligence")
    print("IDX Bounded Lifecycle DB Ingestion V1")
    print("--------------------------------")
    print(f"Window         : {WINDOW_START} -> {WINDOW_END}")
    print(f"Write mode     : {'ENABLED' if args.write else 'DRY RUN'}")
    print(f"Universe code  : {UNIVERSE_CODE}")
    print(f"Source code    : {DB_SOURCE_CODE}")
    print()

    with engine.connect() as connection:
        preflight = run_preflight(
            connection=connection,
            bounded_payload=bounded_payload,
            membership_payload=membership_payload,
            timeout=args.timeout,
        )

    print_preflight(preflight)

    if not preflight.gate_passed:
        print("STOP")
        print("Instrument preflight failed. No database write was attempted.")
        return

    if not args.write:
        print("3. WRITE PLAN")
        print(f"  Historical delisted stubs    : {len(preflight.resolved_missing)}")
        print(
            "  Active special stubs        : "
            f"{len(preflight.resolved_active_special)}"
        )
        print(f"  Active universe intervals    : {preflight.interval_count}")
        print("  Delisted-state rows          : 15 expected from bounded snapshot")
        print(f"  Publication observations     : {preflight.event_count}")
        print()
        print("DATABASE WRITE:")
        print("ENABLED : NO")
        print()
        print("NEXT COMMAND:")
        print("python scripts\\ingest_idx_bounded_lifecycle.py --write")
        return

    with engine.begin() as connection:
        check_required_tables(connection)

        inserted_historical_stub_attempts = insert_historical_stubs(
            connection,
            preflight.resolved_missing,
        )

        inserted_active_special_attempts = insert_active_special_stubs(
            connection,
            preflight.resolved_active_special,
        )

        instruments = load_instruments(connection)
        required_symbols = snapshot_symbols(bounded_payload)
        still_missing = required_symbols - set(instruments)
        if still_missing:
            raise RuntimeError(
                "Instrument matching failed inside transaction: "
                + ", ".join(sorted(still_missing))
            )

        rows = prepare_rows(
            payload=bounded_payload,
            instrument_ids=instruments,
            snapshot_path=snapshot_path,
        )

        upsert_prepared_rows(
            connection=connection,
            rows=rows,
        )

        counts = validation_counts(connection)

        expected_lifecycle = len(rows.lifecycle)
        expected_universe = len(rows.universe)
        expected_availability = len(rows.availability)

        validation_pass = (
            counts["lifecycle_count"] == expected_lifecycle
            and counts["universe_count"] == expected_universe
            and counts["availability_count"] == expected_availability
            and counts["universe_pit_true"] == 0
            and counts["universe_not_unknown"] == 0
            and counts["lifecycle_overlap"] == 0
            and counts["universe_overlap"] == 0
        )

        if not validation_pass:
            raise RuntimeError(
                "Post-write validation failed; transaction will be rolled back. "
                + json.dumps(counts, sort_keys=True)
            )

    print("3. DATABASE INGESTION")
    print(
        "  Historical stub attempts : "
        f"{inserted_historical_stub_attempts}"
    )
    print(
        "  Active special attempts  : "
        f"{inserted_active_special_attempts}"
    )
    print(f"  Lifecycle rows           : {counts['lifecycle_count']}")
    print(f"  Universe rows            : {counts['universe_count']}")
    print(f"  Availability rows        : {counts['availability_count']}")
    print()

    print("4. POST-WRITE VALIDATION")
    print(f"  Lifecycle overlaps       : {counts['lifecycle_overlap']}")
    print(f"  Universe overlaps        : {counts['universe_overlap']}")
    print(f"  Universe PIT=true        : {counts['universe_pit_true']}")
    print(f"  Availability != UNKNOWN : {counts['universe_not_unknown']}")
    print("  Database gate            : PASS")
    print()

    print("SUMMARY")
    print("Bounded lifecycle DB gate : PASS")
    print("Historical universe DB    : READY for bounded 2023-2025 research")
    print("Strict PIT gate           : FAIL")
    print()

    print("IMPORTANT")
    print(
        "This ingestion does not backdate publication availability. "
        "All bounded historical membership rows remain point_in_time_safe=False."
    )
    print(
        "Historical delisted stubs are created only for missing symbols with an "
        "adjudicated delisting event and an official IDX Table of Stock Price name."
    )
    print(
        "CNTB and CNTX are inserted only as separately evidenced active special "
        "security lines; they are not added to the current IDX profile snapshot."
    )
    print(
        "Existing instrument current-status fields are not auto-inactivated or overwritten."
    )
    print()
    print("DATABASE WRITE:")
    print("ENABLED : YES")


if __name__ == "__main__":
    main()
