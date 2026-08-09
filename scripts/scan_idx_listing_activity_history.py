import argparse
from dataclasses import dataclass
from time import sleep
from typing import Any

import httpx

IDX_ORIGIN = "https://www.idx.id"

ENDPOINT = (
    "/primary/ListingActivity/"
    "GetIpoRelisting"
)

PAGE_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "listing-activity-history-scanner"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),
    "Referer": PAGE_URL,
}


DEFAULT_PAGE_SIZE = 200

DEFAULT_MAX_PAGES = 20


@dataclass(
    frozen=True,
    slots=True,
)
class ScanTarget:
    status: str


TARGETS = (
    ScanTarget(
        status="ipo",
    ),
    ScanTarget(
        status="relisting",
    ),
)


@dataclass(
    frozen=True,
    slots=True,
)
class PageResult:
    year: int
    status: str
    page: int
    pagesize: int
    http_status: int | None
    echoed_year: str | None
    echoed_status: str | None
    echoed_page: int | None
    echoed_pagesize: int | None
    rows: tuple[
        dict[str, Any],
        ...
    ]
    error: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class AnnualResult:
    year: int
    status: str
    pages_requested: int
    total_rows: int
    unique_rows: int
    duplicate_rows: int
    symbols: tuple[str, ...]
    min_event_date: str | None
    max_event_date: str | None
    response_coverage: bool
    error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan bounded historical "
            "coverage of the observed IDX "
            "GetIpoRelisting endpoint using "
            "confirmed one-based pagination."
        )
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2026,
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=2020,
    )

    parser.add_argument(
        "--pagesize",
        type=int,
        default=DEFAULT_PAGE_SIZE,
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.25,
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if not (
        1900
        <= args.end_year
        <= args.start_year
        <= 2100
    ):
        raise ValueError(
            "Require 1900 <= end-year "
            "<= start-year <= 2100."
        )

    if args.pagesize <= 0:
        raise ValueError(
            "pagesize must be positive."
        )

    if args.max_pages <= 0:
        raise ValueError(
            "max-pages must be positive."
        )

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )


def normalize_string(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    return (
        normalized
        if normalized
        else None
    )


def normalize_integer(
    value: Any,
) -> int | None:
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def extract_year(
    value: Any,
) -> int | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    if len(value) < 4:
        return None

    prefix = value[
        :4
    ]

    if not prefix.isdigit():
        return None

    year = int(
        prefix
    )

    if year == 1:
        return None

    return year


def extract_event_date(
    row: dict[str, Any],
) -> str | None:
    value = row.get(
        "TanggalPencatatan"
    )

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = (
        value.strip()
    )

    if extract_year(
        normalized
    ) is None:
        return None

    return normalized


def extract_symbol(
    row: dict[str, Any],
) -> str | None:
    value = row.get(
        "KodeEmiten"
    )

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = (
        value.strip()
        .upper()
    )

    return (
        normalized
        if normalized
        else None
    )


def row_fingerprint(
    row: dict[str, Any],
) -> tuple[
    str | None,
    ...
]:
    fields = (
        "KodeEmiten",
        "TanggalPencatatan",
        "RencanaStatus",
        "Delisting",
        "EfekType",
        "PapanPencatatan",
    )

    return tuple(
        normalize_string(
            row.get(
                field
            )
        )
        for field in fields
    )


def failure_page(
    *,
    year: int,
    status: str,
    page: int,
    pagesize: int,
    http_status: int | None,
    error: str,
) -> PageResult:
    return PageResult(
        year=year,
        status=status,
        page=page,
        pagesize=pagesize,
        http_status=http_status,
        echoed_year=None,
        echoed_status=None,
        echoed_page=None,
        echoed_pagesize=None,
        rows=(),
        error=error,
    )


def parse_page(
    *,
    year: int,
    status: str,
    page: int,
    pagesize: int,
    response: httpx.Response,
) -> PageResult:
    try:
        payload = (
            response.json()
        )

    except ValueError:
        return failure_page(
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
            http_status=(
                response.status_code
            ),
            error=(
                "Response is not JSON."
            ),
        )

    if not isinstance(
        payload,
        dict,
    ):
        return failure_page(
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
            http_status=(
                response.status_code
            ),
            error=(
                "JSON root is not "
                "an object."
            ),
        )

    criteria = payload.get(
        "SearchCriteria"
    )

    result = payload.get(
        "Result"
    )

    if not isinstance(
        criteria,
        dict,
    ):
        return failure_page(
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
            http_status=(
                response.status_code
            ),
            error=(
                "SearchCriteria is not "
                "an object."
            ),
        )

    if not isinstance(
        result,
        list,
    ):
        return failure_page(
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
            http_status=(
                response.status_code
            ),
            error=(
                "Result is not "
                "an array."
            ),
        )

    if not all(
        isinstance(
            row,
            dict,
        )
        for row in result
    ):
        return failure_page(
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
            http_status=(
                response.status_code
            ),
            error=(
                "Result contains "
                "non-object rows."
            ),
        )

    echoed_year = (
        normalize_string(
            criteria.get(
                "Year"
            )
        )
    )

    echoed_status = (
        normalize_string(
            criteria.get(
                "Status"
            )
        )
    )

    echoed_page = (
        normalize_integer(
            criteria.get(
                "indexfrom"
            )
        )
    )

    echoed_pagesize = (
        normalize_integer(
            criteria.get(
                "pagesize"
            )
        )
    )

    error = None

    if response.status_code != 200:
        error = (
            f"Unexpected HTTP "
            f"{response.status_code}."
        )

    elif echoed_year != str(
        year
    ):
        error = (
            "Year echo mismatch."
        )

    elif echoed_status != status:
        error = (
            "Status echo mismatch."
        )

    elif echoed_page != page:
        error = (
            "indexfrom echo mismatch."
        )

    elif echoed_pagesize != pagesize:
        error = (
            "pagesize echo mismatch."
        )

    elif status == "ipo":
        invalid_years = [
            extract_event_date(
                row
            )
            for row in result
            if (
                extract_event_date(
                    row
                )
                is not None
                and extract_year(
                    extract_event_date(
                        row
                    )
                )
                != year
            )
        ]

        if invalid_years:
            error = (
                f"{len(invalid_years)} "
                "IPO rows do not match "
                "the requested year."
            )

    return PageResult(
        year=year,
        status=status,
        page=page,
        pagesize=pagesize,
        http_status=(
            response.status_code
        ),
        echoed_year=echoed_year,
        echoed_status=echoed_status,
        echoed_page=echoed_page,
        echoed_pagesize=(
            echoed_pagesize
        ),
        rows=tuple(
            result
        ),
        error=error,
    )


def fetch_page(
    *,
    client: httpx.Client,
    year: int,
    status: str,
    page: int,
    pagesize: int,
) -> PageResult:
    params = {
        "Status": status,
        "Year": year,
        "indexfrom": page,
        "pagesize": pagesize,
    }

    try:
        response = client.get(
            IDX_ORIGIN + ENDPOINT,
            params=params,
        )

    except httpx.HTTPError as exc:
        return failure_page(
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
            http_status=None,
            error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    return parse_page(
        year=year,
        status=status,
        page=page,
        pagesize=pagesize,
        response=response,
    )


def scan_annual(
    *,
    client: httpx.Client,
    year: int,
    status: str,
    pagesize: int,
    max_pages: int,
    pause: float,
) -> AnnualResult:
    rows = []

    page_results = []

    response_coverage = False

    terminal_error = None

    for page in range(
        1,
        max_pages + 1,
    ):
        result = fetch_page(
            client=client,
            year=year,
            status=status,
            page=page,
            pagesize=pagesize,
        )

        page_results.append(
            result
        )

        print(
            f"    PAGE {page:<2} "
            f"HTTP="
            f"{result.http_status!s:<4} "
            f"ROWS="
            f"{len(result.rows):<4} "
            f"VALID="
            f"{result.error is None}"
        )

        if result.error is not None:
            terminal_error = (
                result.error
            )
            break

        rows.extend(
            result.rows
        )

        if len(
            result.rows
        ) < pagesize:
            response_coverage = True
            break

        if (
            page < max_pages
            and pause > 0
        ):
            sleep(
                pause
            )

    else:
        terminal_error = (
            "Maximum page limit reached "
            "without a terminal short page."
        )

    fingerprints = [
        row_fingerprint(
            row
        )
        for row in rows
    ]

    unique_fingerprints = set(
        fingerprints
    )

    duplicate_rows = (
        len(
            fingerprints
        )
        - len(
            unique_fingerprints
        )
    )

    symbols = tuple(
        sorted(
            {
                symbol
                for row in rows
                if (
                    symbol := extract_symbol(
                        row
                    )
                )
                is not None
            }
        )
    )

    dates = [
        event_date
        for row in rows
        if (
            event_date := extract_event_date(
                row
            )
        )
        is not None
    ]

    if (
        duplicate_rows > 0
        and terminal_error is None
    ):
        terminal_error = (
            f"{duplicate_rows} duplicate "
            "row fingerprints detected "
            "across collected pages."
        )

        response_coverage = False

    return AnnualResult(
        year=year,
        status=status,
        pages_requested=len(
            page_results
        ),
        total_rows=len(
            rows
        ),
        unique_rows=len(
            unique_fingerprints
        ),
        duplicate_rows=duplicate_rows,
        symbols=symbols,
        min_event_date=(
            min(
                dates
            )
            if dates
            else None
        ),
        max_event_date=(
            max(
                dates
            )
            if dates
            else None
        ),
        response_coverage=(
            response_coverage
            and terminal_error is None
        ),
        error=terminal_error,
    )


def print_annual_result(
    result: AnnualResult,
) -> None:
    print(
        f"  Total rows        : "
        f"{result.total_rows}"
    )

    print(
        f"  Unique rows       : "
        f"{result.unique_rows}"
    )

    print(
        f"  Duplicate rows    : "
        f"{result.duplicate_rows}"
    )

    print(
        f"  Pages requested   : "
        f"{result.pages_requested}"
    )

    print(
        f"  Date range        : "
        f"{result.min_event_date} "
        f"→ "
        f"{result.max_event_date}"
    )

    print(
        f"  Unique symbols    : "
        f"{len(result.symbols)}"
    )

    print(
        "  Symbols           : "
        + (
            ", ".join(
                result.symbols
            )
            if result.symbols
            else "-"
        )
    )

    print(
        "  Response coverage : "
        + (
            "CONFIRMED"
            if result.response_coverage
            else "NOT CONFIRMED"
        )
    )

    print(
        "  Validation        : "
        + (
            "PASS"
            if result.error is None
            else (
                "FAIL — "
                + result.error
            )
        )
    )

    print()


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX ListingActivity "
        "Historical Coverage Scanner V2"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Start year : "
        f"{args.start_year}"
    )

    print(
        f"End year   : "
        f"{args.end_year}"
    )

    print(
        f"Statuses   : "
        f"{', '.join(
            target.status
            for target in TARGETS
        )}"
    )

    print(
        f"Page size  : "
        f"{args.pagesize}"
    )

    print(
        f"Max pages  : "
        f"{args.max_pages}"
    )

    print()

    annual_results = []

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for year in range(
            args.start_year,
            args.end_year - 1,
            -1,
        ):
            for target in TARGETS:
                print(
                    f"{year} "
                    f"{target.status.upper()}"
                )

                result = scan_annual(
                    client=client,
                    year=year,
                    status=(
                        target.status
                    ),
                    pagesize=(
                        args.pagesize
                    ),
                    max_pages=(
                        args.max_pages
                    ),
                    pause=args.pause,
                )

                annual_results.append(
                    result
                )

                print_annual_result(
                    result
                )

                if args.pause > 0:
                    sleep(
                        args.pause
                    )

    print(
        "SUMMARY"
    )

    print(
        f"Annual queries    : "
        f"{len(annual_results)}"
    )

    coverage_pass = sum(
        result.response_coverage
        for result in annual_results
    )

    validation_pass = sum(
        result.error is None
        for result in annual_results
    )

    print(
        f"Coverage confirmed: "
        f"{coverage_pass}/"
        f"{len(annual_results)}"
    )

    print(
        f"Validation PASS   : "
        f"{validation_pass}/"
        f"{len(annual_results)}"
    )

    for status in (
        "ipo",
        "relisting",
    ):
        matching = [
            result
            for result in annual_results
            if result.status == status
        ]

        total_rows = sum(
            result.total_rows
            for result in matching
        )

        non_empty_years = [
            result.year
            for result in matching
            if result.total_rows > 0
        ]

        print()

        print(
            status.upper()
        )

        print(
            f"  Total rows      : "
            f"{total_rows}"
        )

        print(
            "  Non-empty years : "
            + (
                ", ".join(
                    str(
                        year
                    )
                    for year
                    in non_empty_years
                )
                if non_empty_years
                else "-"
            )
        )

    print()

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "Response coverage means all "
        "pages exposed by the observed "
        "query contract were collected."
    )

    print(
        "It does not by itself establish "
        "historical source completeness."
    )

    print(
        "Relisting zero-row years remain "
        "query results, not proof that no "
        "historical relisting event existed."
    )

    print(
        "Delisting remains excluded because "
        "its advertised backend route "
        "currently returns HTTP 404."
    )

    print()

    print(
        "DATABASE WRITE:"
    )

    print(
        "ENABLED : NO"
    )


if __name__ == "__main__":
    main()