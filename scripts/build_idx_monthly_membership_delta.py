import argparse
import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from itertools import pairwise
from pathlib import Path
from time import sleep
from typing import Any
from urllib.parse import urljoin

import httpx

IDX_ORIGIN = "https://www.idx.id"
PAGE_PATH = (
    "/en/market-data/statistical-reports/digital-statistic/monthly/"
    "trading-summary/table-of-stock-price"
)
API_PATH = "/primary/DigitalStatistic/GetApiDataPaginated"
DEFAULT_IPO_SNAPSHOT = "data/derived/idx_ipo_history_snapshot.json"
DEFAULT_LIFECYCLE_SNAPSHOT = "data/derived/idx_lifecycle_evidence_batch.json"
DEFAULT_OUTPUT = "data/derived/idx_monthly_membership_delta.json"
PAGE_SIZE = 1000
MAX_PAGES = 5
MIN_VALID_SYMBOLS = 100
SYMBOL_RE = re.compile(r"^[A-Z]{4}$")
LINK_RE = re.compile(r"\bLINK_[A-Z0-9_]+\b")
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 Indonesia-Market-Intelligence/"
        "idx-stock-price-contract-builder"
    ),
    "Accept": "*/*",
}


@dataclass(frozen=True, slots=True)
class ContractProbe:
    candidate: str
    score: int
    http_status: int | None
    data_rows: int
    unique_symbols: int
    symbol_field: str | None
    valid: bool
    error: str | None


@dataclass(frozen=True, slots=True)
class ContractResult:
    page_http_status: int | None
    asset_count: int
    observed_candidates: tuple[str, ...]
    probes: tuple[ContractProbe, ...]
    selected_url_name: str | None
    selected_symbol_field: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class MonthSnapshot:
    year: int
    month: int
    status: str
    http_status: int | None
    row_count: int
    unique_symbols: int
    duplicate_count: int
    pages: int
    symbol_field: str | None
    symbols: tuple[str, ...]
    fingerprint: str | None
    error: str | None


@dataclass(frozen=True, slots=True)
class MembershipDelta:
    year: int
    month: int
    previous_year: int
    previous_month: int
    removed: tuple[str, ...]
    added: tuple[str, ...]
    ipo_explained: tuple[str, ...]
    relisting_explained: tuple[str, ...]
    unexplained_additions: tuple[str, ...]
    highlight_previous_count: int | None
    highlight_current_count: int | None
    highlight_alignment: str


@dataclass(frozen=True, slots=True)
class RemovalCandidate:
    symbol: str
    last_present_year: int
    last_present_month: int
    first_absent_year: int
    first_absent_month: int
    later_reappearance: bool
    classification: str
    highlight_alignment: str


@dataclass(frozen=True, slots=True)
class BatchSnapshot:
    generated_at: str
    snapshot_version: str
    contract: ContractResult
    months: tuple[MonthSnapshot, ...]
    deltas: tuple[MembershipDelta, ...]
    removal_candidates: tuple[RemovalCandidate, ...]
    months_requested: int
    months_valid: int
    months_invalid: int
    distinct_monthly_fingerprints: int
    persistent_removal_candidates: int
    temporary_absences: int
    unexplained_additions: int
    monthly_membership_ready: bool
    exact_delisting_ready: bool
    strict_pit_ready: bool


class ScriptSourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "script":
            return
        source = dict(attrs).get("src")
        if source:
            self.sources.append(source)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover the official IDX Table of Stock Price client API and "
            "build month-to-month stock membership deltas."
        )
    )
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--start-month", type=int, default=1)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--end-month", type=int, default=12)
    parser.add_argument("--ipo-snapshot", default=DEFAULT_IPO_SNAPSHOT)
    parser.add_argument("--lifecycle-snapshot", default=DEFAULT_LIFECYCLE_SNAPSHOT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument("--pause", type=float, default=0.08)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not 1900 <= args.start_year <= args.end_year <= 2100:
        raise ValueError("Invalid year range.")
    if not 1 <= args.start_month <= 12:
        raise ValueError("start-month must be 1-12.")
    if not 1 <= args.end_month <= 12:
        raise ValueError("end-month must be 1-12.")
    if (args.start_year, args.start_month) > (args.end_year, args.end_month):
        raise ValueError("Start period must not be after end period.")
    if args.timeout <= 0:
        raise ValueError("timeout must be positive.")
    if args.pause < 0:
        raise ValueError("pause cannot be negative.")


def make_filter(year: int, month: int) -> str:
    payload = {
        "year": str(year),
        "month": str(month),
        "quarter": 0,
        "type": "monthly",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.b64encode(raw).decode("ascii")


def page_url(year: int, month: int) -> str:
    return f"{IDX_ORIGIN}{PAGE_PATH}?filter={make_filter(year, month)}"


def previous_period(year: int, month: int) -> tuple[int, int]:
    if month > 1:
        return year, month - 1
    return year - 1, 12


def next_period(year: int, month: int) -> tuple[int, int]:
    if month < 12:
        return year, month + 1
    return year + 1, 1


def periods(
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
) -> tuple[tuple[int, int], ...]:
    values: list[tuple[int, int]] = []
    year = start_year
    month = start_month
    while True:
        values.append((year, month))
        if (year, month) == (end_year, end_month):
            break
        year, month = next_period(year, month)
    return tuple(values)


def candidate_score(name: str, contexts: list[str]) -> int:
    score = 0
    upper = name.upper()
    if "STOCK" in upper:
        score += 2
    if "PRICE" in upper:
        score += 3
    if "TABLE" in upper:
        score += 1
    for context in contexts:
        lowered = context.casefold()
        if "table-of-stock-price" in lowered or "table of stock price" in lowered:
            score += 10
        if "getapidatapaginated" in lowered:
            score += 2
    return score


def extract_candidate_contexts(text: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for match in LINK_RE.finditer(text):
        start = max(0, match.start() - 2500)
        end = min(len(text), match.end() + 2500)
        name = match.group(0)
        result.setdefault(name, []).append(text[start:end])
    return result


def merge_contexts(
    target: dict[str, list[str]],
    source: dict[str, list[str]],
) -> None:
    for key, values in source.items():
        target.setdefault(key, []).extend(values)


def api_params(
    *,
    url_name: str,
    year: int,
    month: int,
    page_number: int,
) -> dict[str, str | int]:
    return {
        "urlName": url_name,
        "periodYear": year,
        "periodMonth": month,
        "periodType": "monthly",
        "isPrint": "False",
        "cumulative": "false",
        "pageSize": PAGE_SIZE,
        "pageNumber": page_number,
        "orderBy": "",
        "search": "",
    }


def response_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise TypeError("API JSON root is not an object.")
    data = payload.get("data")
    if not isinstance(data, list):
        raise TypeError("API JSON data is not an array.")
    return [row for row in data if isinstance(row, dict)]


def detect_symbol_field(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    keys = set().union(*(row.keys() for row in rows))
    best_key = None
    best_score: tuple[float, int] = (0.0, 0)
    for key in keys:
        values = [row.get(key) for row in rows]
        string_values = [value.strip().upper() for value in values if isinstance(value, str)]
        if not string_values:
            continue
        matches = [value for value in string_values if SYMBOL_RE.fullmatch(value)]
        ratio = len(matches) / len(string_values)
        unique = len(set(matches))
        score = (ratio, unique)
        if ratio >= 0.70 and unique >= 20 and score > best_score:
            best_key = key
            best_score = score
    return best_key


def symbols_from_rows(rows: list[dict[str, Any]], field: str) -> list[str]:
    values = []
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str):
            continue
        symbol = value.strip().upper()
        if SYMBOL_RE.fullmatch(symbol):
            values.append(symbol)
    return values


def probe_candidate(
    *,
    client: httpx.Client,
    candidate: str,
    score: int,
) -> ContractProbe:
    try:
        response = client.get(
            IDX_ORIGIN + API_PATH,
            params=api_params(
                url_name=candidate,
                year=2025,
                month=9,
                page_number=1,
            ),
        )
    except httpx.HTTPError as exc:
        return ContractProbe(
            candidate=candidate,
            score=score,
            http_status=None,
            data_rows=0,
            unique_symbols=0,
            symbol_field=None,
            valid=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    if response.status_code != 200:
        return ContractProbe(
            candidate=candidate,
            score=score,
            http_status=response.status_code,
            data_rows=0,
            unique_symbols=0,
            symbol_field=None,
            valid=False,
            error=f"HTTP {response.status_code}",
        )
    try:
        payload = response.json()
        rows = response_rows(payload)
    except (TypeError, ValueError) as exc:
        return ContractProbe(
            candidate=candidate,
            score=score,
            http_status=response.status_code,
            data_rows=0,
            unique_symbols=0,
            symbol_field=None,
            valid=False,
            error=f"{type(exc).__name__}: {exc}",
        )
    field = detect_symbol_field(rows)
    if field is None:
        return ContractProbe(
            candidate=candidate,
            score=score,
            http_status=response.status_code,
            data_rows=len(rows),
            unique_symbols=0,
            symbol_field=None,
            valid=False,
            error="No stock-code-like field detected.",
        )
    symbols = symbols_from_rows(rows, field)
    unique = len(set(symbols))
    valid = unique >= MIN_VALID_SYMBOLS
    return ContractProbe(
        candidate=candidate,
        score=score,
        http_status=response.status_code,
        data_rows=len(rows),
        unique_symbols=unique,
        symbol_field=field,
        valid=valid,
        error=None if valid else "Too few unique stock symbols.",
    )


def discover_contract(
    *,
    client: httpx.Client,
    pause: float,
) -> ContractResult:
    try:
        page_response = client.get(page_url(2025, 9))
    except httpx.HTTPError as exc:
        return ContractResult(
            page_http_status=None,
            asset_count=0,
            observed_candidates=(),
            probes=(),
            selected_url_name=None,
            selected_symbol_field=None,
            error=f"{type(exc).__name__}: {exc}",
        )
    if page_response.status_code != 200:
        return ContractResult(
            page_http_status=page_response.status_code,
            asset_count=0,
            observed_candidates=(),
            probes=(),
            selected_url_name=None,
            selected_symbol_field=None,
            error=f"Page HTTP {page_response.status_code}",
        )
    parser = ScriptSourceParser()
    parser.feed(page_response.text)
    parser.close()
    asset_urls = tuple(dict.fromkeys(urljoin(str(page_response.url), src) for src in parser.sources))
    contexts: dict[str, list[str]] = {}
    merge_contexts(contexts, extract_candidate_contexts(page_response.text))
    for asset_url in asset_urls:
        try:
            response = client.get(asset_url)
        except httpx.HTTPError:
            continue
        if response.status_code != 200:
            continue
        merge_contexts(contexts, extract_candidate_contexts(response.text))
        if pause > 0:
            sleep(pause)
    ranked = sorted(
        ((candidate_score(name, values), name) for name, values in contexts.items()),
        key=lambda item: (-item[0], item[1]),
    )
    prioritized = [item for item in ranked if item[0] > 0]
    if not prioritized:
        prioritized = ranked
    probes: list[ContractProbe] = []
    for score, candidate in prioritized[:80]:
        probe = probe_candidate(client=client, candidate=candidate, score=score)
        probes.append(probe)
        if probe.valid:
            return ContractResult(
                page_http_status=page_response.status_code,
                asset_count=len(asset_urls),
                observed_candidates=tuple(name for _, name in ranked),
                probes=tuple(probes),
                selected_url_name=probe.candidate,
                selected_symbol_field=probe.symbol_field,
                error=None,
            )
        if pause > 0:
            sleep(pause)
    return ContractResult(
        page_http_status=page_response.status_code,
        asset_count=len(asset_urls),
        observed_candidates=tuple(name for _, name in ranked),
        probes=tuple(probes),
        selected_url_name=None,
        selected_symbol_field=None,
        error="No observed urlName candidate returned a valid stock universe.",
    )


def fetch_month(
    *,
    client: httpx.Client,
    url_name: str,
    expected_field: str,
    year: int,
    month: int,
    pause: float,
) -> MonthSnapshot:
    raw_symbols: list[str] = []
    field = expected_field
    last_status = None
    for page_number in range(1, MAX_PAGES + 1):
        try:
            response = client.get(
                IDX_ORIGIN + API_PATH,
                params=api_params(
                    url_name=url_name,
                    year=year,
                    month=month,
                    page_number=page_number,
                ),
            )
        except httpx.HTTPError as exc:
            return MonthSnapshot(
                year=year,
                month=month,
                status="INVALID",
                http_status=last_status,
                row_count=len(raw_symbols),
                unique_symbols=len(set(raw_symbols)),
                duplicate_count=len(raw_symbols) - len(set(raw_symbols)),
                pages=page_number - 1,
                symbol_field=field,
                symbols=tuple(sorted(set(raw_symbols))),
                fingerprint=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        last_status = response.status_code
        if response.status_code != 200:
            return MonthSnapshot(
                year=year,
                month=month,
                status="INVALID",
                http_status=response.status_code,
                row_count=len(raw_symbols),
                unique_symbols=len(set(raw_symbols)),
                duplicate_count=len(raw_symbols) - len(set(raw_symbols)),
                pages=page_number,
                symbol_field=field,
                symbols=tuple(sorted(set(raw_symbols))),
                fingerprint=None,
                error=f"HTTP {response.status_code}",
            )
        try:
            rows = response_rows(response.json())
        except (TypeError, ValueError) as exc:
            return MonthSnapshot(
                year=year,
                month=month,
                status="INVALID",
                http_status=response.status_code,
                row_count=len(raw_symbols),
                unique_symbols=len(set(raw_symbols)),
                duplicate_count=len(raw_symbols) - len(set(raw_symbols)),
                pages=page_number,
                symbol_field=field,
                symbols=tuple(sorted(set(raw_symbols))),
                fingerprint=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        if page_number == 1:
            detected = detect_symbol_field(rows)
            if detected is not None:
                field = detected
        page_symbols = symbols_from_rows(rows, field)
        raw_symbols.extend(page_symbols)
        if len(rows) < PAGE_SIZE:
            break
        if pause > 0:
            sleep(pause)
    unique_symbols = tuple(sorted(set(raw_symbols)))
    if len(unique_symbols) < MIN_VALID_SYMBOLS:
        return MonthSnapshot(
            year=year,
            month=month,
            status="INVALID",
            http_status=last_status,
            row_count=len(raw_symbols),
            unique_symbols=len(unique_symbols),
            duplicate_count=len(raw_symbols) - len(unique_symbols),
            pages=page_number,
            symbol_field=field,
            symbols=unique_symbols,
            fingerprint=None,
            error="Too few unique stock symbols.",
        )
    fingerprint = hashlib.sha256("\n".join(unique_symbols).encode()).hexdigest()
    return MonthSnapshot(
        year=year,
        month=month,
        status="VALID",
        http_status=last_status,
        row_count=len(raw_symbols),
        unique_symbols=len(unique_symbols),
        duplicate_count=len(raw_symbols) - len(unique_symbols),
        pages=page_number,
        symbol_field=field,
        symbols=unique_symbols,
        fingerprint=fingerprint,
        error=None,
    )


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} root must be a JSON object.")
    return payload


def parse_event_month(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str) or len(value) < 7:
        return None
    try:
        return int(value[:4]), int(value[5:7])
    except ValueError:
        return None


def normalize_symbol(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    symbol = value.strip().upper()
    return symbol if SYMBOL_RE.fullmatch(symbol) else None


def load_event_maps(
    *,
    ipo_path: Path,
    lifecycle_path: Path,
) -> tuple[
    dict[tuple[int, int], set[str]],
    dict[tuple[int, int], set[str]],
    dict[tuple[int, int], int | None],
]:
    ipo_payload = load_json(ipo_path)
    lifecycle_payload = load_json(lifecycle_path)
    ipo: dict[tuple[int, int], set[str]] = {}
    for year_data in ipo_payload.get("years", []):
        if not isinstance(year_data, dict):
            continue
        for record in year_data.get("records", []):
            if not isinstance(record, dict):
                continue
            symbol = normalize_symbol(record.get("symbol"))
            event_month = parse_event_month(record.get("listing_date"))
            if symbol is not None and event_month is not None:
                ipo.setdefault(event_month, set()).add(symbol)
    relisting: dict[tuple[int, int], set[str]] = {}
    for record in lifecycle_payload.get("relisting_records", []):
        if not isinstance(record, dict):
            continue
        symbol = normalize_symbol(record.get("symbol"))
        event_month = parse_event_month(record.get("event_date"))
        if symbol is not None and event_month is not None:
            relisting.setdefault(event_month, set()).add(symbol)
    highlights: dict[tuple[int, int], int | None] = {}
    for record in lifecycle_payload.get("delisting_months", []):
        if not isinstance(record, dict):
            continue
        year = record.get("year")
        month = record.get("month")
        highlight = record.get("highlight")
        if not isinstance(year, int) or not isinstance(month, int) or not isinstance(highlight, dict):
            continue
        count = highlight.get("issuer_count")
        highlights[(year, month)] = count if isinstance(count, int) else None
    return ipo, relisting, highlights


def alignment(
    *,
    removed_count: int,
    previous_count: int | None,
    current_count: int | None,
) -> str:
    if removed_count == 0:
        return "NOT_APPLICABLE"
    previous_match = previous_count == removed_count if previous_count is not None else False
    current_match = current_count == removed_count if current_count is not None else False
    if previous_match and current_match:
        return "BOTH"
    if previous_match:
        return "PREVIOUS_MONTH"
    if current_match:
        return "CURRENT_MONTH"
    if previous_count is None and current_count is None:
        return "UNKNOWN"
    return "NO_MATCH"


def build_deltas(
    *,
    months: tuple[MonthSnapshot, ...],
    ipo: dict[tuple[int, int], set[str]],
    relisting: dict[tuple[int, int], set[str]],
    highlights: dict[tuple[int, int], int | None],
) -> tuple[MembershipDelta, ...]:
    results: list[MembershipDelta] = []
    valid_months = [month for month in months if month.status == "VALID"]
    for previous, current in pairwise(valid_months):
        if next_period(previous.year, previous.month) != (current.year, current.month):
            continue
        previous_symbols = set(previous.symbols)
        current_symbols = set(current.symbols)
        removed = previous_symbols - current_symbols
        added = current_symbols - previous_symbols
        current_period = (current.year, current.month)
        ipo_explained = added & ipo.get(current_period, set())
        relisting_explained = added & relisting.get(current_period, set())
        unexplained = added - ipo_explained - relisting_explained
        previous_count = highlights.get((previous.year, previous.month))
        current_count = highlights.get(current_period)
        results.append(
            MembershipDelta(
                year=current.year,
                month=current.month,
                previous_year=previous.year,
                previous_month=previous.month,
                removed=tuple(sorted(removed)),
                added=tuple(sorted(added)),
                ipo_explained=tuple(sorted(ipo_explained)),
                relisting_explained=tuple(sorted(relisting_explained)),
                unexplained_additions=tuple(sorted(unexplained)),
                highlight_previous_count=previous_count,
                highlight_current_count=current_count,
                highlight_alignment=alignment(
                    removed_count=len(removed),
                    previous_count=previous_count,
                    current_count=current_count,
                ),
            )
        )
    return tuple(results)


def build_candidates(
    *,
    months: tuple[MonthSnapshot, ...],
    deltas: tuple[MembershipDelta, ...],
) -> tuple[RemovalCandidate, ...]:
    valid_months = [month for month in months if month.status == "VALID"]
    positions = {(month.year, month.month): index for index, month in enumerate(valid_months)}
    symbols_by_period = {(month.year, month.month): set(month.symbols) for month in valid_months}
    candidates: list[RemovalCandidate] = []
    for delta in deltas:
        position = positions.get((delta.year, delta.month))
        if position is None:
            continue
        later_periods = valid_months[position + 1 :]
        for symbol in delta.removed:
            reappears = any(
                symbol in symbols_by_period[(month.year, month.month)] for month in later_periods
            )
            classification = (
                "TEMPORARY_ABSENCE_OR_DATA_GAP"
                if reappears
                else "PERSISTENT_REMOVAL_CANDIDATE"
            )
            candidates.append(
                RemovalCandidate(
                    symbol=symbol,
                    last_present_year=delta.previous_year,
                    last_present_month=delta.previous_month,
                    first_absent_year=delta.year,
                    first_absent_month=delta.month,
                    later_reappearance=reappears,
                    classification=classification,
                    highlight_alignment=delta.highlight_alignment,
                )
            )
    return tuple(candidates)


def write_snapshot(snapshot: BatchSnapshot, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(snapshot), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def print_contract(contract: ContractResult) -> None:
    print("1. CLIENT API CONTRACT DISCOVERY")
    print(f"  Page HTTP       : {contract.page_http_status}")
    print(f"  JS assets       : {contract.asset_count}")
    print(f"  Candidates      : {len(contract.observed_candidates)}")
    for probe in contract.probes:
        print(
            f"  {probe.candidate:<36} score={probe.score:<3} "
            f"HTTP={probe.http_status} rows={probe.data_rows:<4} "
            f"symbols={probe.unique_symbols:<4} field={probe.symbol_field} "
            f"valid={probe.valid}"
        )
    print(f"  Selected urlName: {contract.selected_url_name}")
    print(f"  Symbol field    : {contract.selected_symbol_field}")
    if contract.error:
        print(f"  ERROR           : {contract.error}")
    print()


def print_coverage(months: tuple[MonthSnapshot, ...]) -> None:
    print("3. YEAR COVERAGE")
    for year in sorted({month.year for month in months}):
        selected = [month for month in months if month.year == year]
        valid = [month for month in selected if month.status == "VALID"]
        counts = [month.unique_symbols for month in valid]
        count_range = f"{min(counts)}→{max(counts)}" if counts else "-"
        print(
            f"  {year} valid={len(valid)}/{len(selected)} "
            f"symbols={count_range} invalid={len(selected) - len(valid)}"
        )
        for month in selected:
            if month.status != "VALID":
                print(f"    {month.year}-{month.month:02d} {month.error}")
    print()


def print_material_deltas(deltas: tuple[MembershipDelta, ...]) -> None:
    print("4. MATERIAL MEMBERSHIP DELTAS")
    material = 0
    for delta in deltas:
        if not delta.removed and not delta.unexplained_additions:
            continue
        material += 1
        print(
            f"  {delta.previous_year}-{delta.previous_month:02d} -> "
            f"{delta.year}-{delta.month:02d}"
        )
        print(f"    Removed       : {', '.join(delta.removed) or '-'}")
        print(f"    Added         : {', '.join(delta.added) or '-'}")
        print(f"    IPO explained : {', '.join(delta.ipo_explained) or '-'}")
        print(f"    Relist explain: {', '.join(delta.relisting_explained) or '-'}")
        print(f"    Unexplained + : {', '.join(delta.unexplained_additions) or '-'}")
        print(f"    Highlight prev: {delta.highlight_previous_count}")
        print(f"    Highlight curr: {delta.highlight_current_count}")
        print(f"    Alignment     : {delta.highlight_alignment}")
    if material == 0:
        print("  No material deltas.")
    print()


def main() -> None:
    args = parse_args()
    validate_args(args)
    ipo_path = Path(args.ipo_snapshot)
    lifecycle_path = Path(args.lifecycle_snapshot)
    if not ipo_path.exists():
        raise FileNotFoundError(ipo_path)
    if not lifecycle_path.exists():
        raise FileNotFoundError(lifecycle_path)
    baseline_year, baseline_month = previous_period(args.start_year, args.start_month)
    scan_periods = periods(
        baseline_year,
        baseline_month,
        args.end_year,
        args.end_month,
    )
    ipo, relisting, highlights = load_event_maps(
        ipo_path=ipo_path,
        lifecycle_path=lifecycle_path,
    )
    print("Indonesia Market Intelligence")
    print("IDX Monthly Membership Delta Builder V3")
    print("--------------------------------")
    print("Source method : official IDX client API discovered from page assets")
    print(
        f"Target period : {args.start_year}-{args.start_month:02d} → "
        f"{args.end_year}-{args.end_month:02d}"
    )
    print("Database write: DISABLED")
    print()
    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        contract = discover_contract(client=client, pause=args.pause)
        print_contract(contract)
        if contract.selected_url_name is None or contract.selected_symbol_field is None:
            print("STOP: no validated stock-price client API contract was discovered.")
            print("The previous V2 rows=1 output is INVALID and must not be used.")
            return
        print("2. MONTHLY CLIENT API SCAN")
        month_results: list[MonthSnapshot] = []
        for index, (year, month) in enumerate(scan_periods, start=1):
            result = fetch_month(
                client=client,
                url_name=contract.selected_url_name,
                expected_field=contract.selected_symbol_field,
                year=year,
                month=month,
                pause=args.pause,
            )
            month_results.append(result)
            print(
                f"  {year}-{month:02d} {result.status:<7} "
                f"symbols={result.unique_symbols:<4} pages={result.pages}"
            )
            if args.pause > 0 and index < len(scan_periods):
                sleep(args.pause)
    months = tuple(month_results)
    print()
    print_coverage(months)
    deltas = build_deltas(
        months=months,
        ipo=ipo,
        relisting=relisting,
        highlights=highlights,
    )
    candidates = build_candidates(months=months, deltas=deltas)
    print_material_deltas(deltas)
    print("5. REMOVAL CANDIDATES")
    if not candidates:
        print("  No removal candidates.")
    for candidate in candidates:
        print(
            f"  {candidate.symbol:<8} "
            f"last={candidate.last_present_year}-{candidate.last_present_month:02d} "
            f"first_absent={candidate.first_absent_year}-{candidate.first_absent_month:02d} "
            f"{candidate.classification} highlight={candidate.highlight_alignment}"
        )
    print()
    valid_count = sum(month.status == "VALID" for month in months)
    invalid_count = len(months) - valid_count
    fingerprints = {month.fingerprint for month in months if month.fingerprint is not None}
    persistent = sum(
        candidate.classification == "PERSISTENT_REMOVAL_CANDIDATE" for candidate in candidates
    )
    temporary = sum(
        candidate.classification == "TEMPORARY_ABSENCE_OR_DATA_GAP" for candidate in candidates
    )
    unexplained = sum(len(delta.unexplained_additions) for delta in deltas)
    ready = invalid_count == 0 and len(fingerprints) >= 6
    snapshot = BatchSnapshot(
        generated_at=datetime.now(UTC).isoformat(),
        snapshot_version="idx_monthly_membership_delta_v3",
        contract=contract,
        months=months,
        deltas=deltas,
        removal_candidates=candidates,
        months_requested=len(months),
        months_valid=valid_count,
        months_invalid=invalid_count,
        distinct_monthly_fingerprints=len(fingerprints),
        persistent_removal_candidates=persistent,
        temporary_absences=temporary,
        unexplained_additions=unexplained,
        monthly_membership_ready=ready,
        exact_delisting_ready=False,
        strict_pit_ready=False,
    )
    output_path = Path(args.output)
    write_snapshot(snapshot, output_path)
    print("SUMMARY")
    print(f"Months requested              : {len(months)}")
    print(f"Months valid                  : {valid_count}")
    print(f"Months invalid                : {invalid_count}")
    print(f"Distinct monthly fingerprints : {len(fingerprints)}")
    print(f"Removal observations          : {len(candidates)}")
    print(f"Persistent removal candidates : {persistent}")
    print(f"Temporary/data-gap candidates : {temporary}")
    print(f"Unexplained additions         : {unexplained}")
    print(f"Output                         : {output_path}")
    print()
    print("READINESS")
    print(f"Monthly membership evidence : {'READY' if ready else 'NOT READY'}")
    print("Exact delisting dates       : NOT READY")
    print("Strict PIT lifecycle        : NOT READY")
    print()
    print("DATABASE WRITE:")
    print("ENABLED : NO")


if __name__ == "__main__":
    main()
