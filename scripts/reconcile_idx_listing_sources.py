import argparse
from dataclasses import dataclass
from datetime import date
from time import sleep, strptime
from typing import Any

import httpx

IDX_ORIGIN = "https://www.idx.id"

LISTING_ACTIVITY_ENDPOINT = (
    "/primary/ListingActivity/"
    "GetIpoRelisting"
)

DIGITAL_STATISTIC_ENDPOINT = (
    "/primary/DigitalStatistic/"
    "GetApiDataPaginated"
)

LISTING_PAGE_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "listing-source-reconciliation"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),
    "Referer": LISTING_PAGE_URL,
}


LISTING_PAGE_SIZE = 200

DIGITAL_PAGE_SIZE = 100

MAX_PAGES = 20


@dataclass(
    frozen=True,
    slots=True,
)
class ListingRecord:
    symbol: str
    listing_date: str


@dataclass(
    frozen=True,
    slots=True,
)
class SourceResult:
    records: tuple[
        ListingRecord,
        ...
    ]
    requests: int
    error: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class ReconciliationResult:
    year: int
    listing_count: int
    digital_count: int
    exact_matches: int
    listing_only: tuple[
        ListingRecord,
        ...
    ]
    digital_only: tuple[
        ListingRecord,
        ...
    ]
    date_disagreements: tuple[
        tuple[
            str,
            tuple[str, ...],
            tuple[str, ...],
        ],
        ...
    ]
    listing_duplicates: int
    digital_duplicates: int
    listing_error: str | None
    digital_error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile IDX ListingActivity "
            "IPO records against Digital "
            "Statistic Stock New Listing."
        )
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2026,
    )

    parser.add_argument(
        "--start-month",
        type=int,
        default=8,
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=2020,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.12,
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

    if not 1 <= args.start_month <= 12:
        raise ValueError(
            "start-month must be "
            "between 1 and 12."
        )

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )


def normalize_symbol(
    value: Any,
) -> str | None:
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


def normalize_date(
    value: Any,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    text = value.strip()

    if not text:
        return None

    if (
        len(text) >= 10
        and text[4] == "-"
        and text[7] == "-"
    ):
        candidate = text[
            :10
        ]

        try:
            parsed = date.fromisoformat(
                candidate
            )

        except ValueError:
            pass

        else:
            if parsed.year == 1:
                return None

            return parsed.isoformat()

    formats = (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
    )

    for date_format in formats:
        try:
            parsed_time = strptime(
                text,
                date_format,
            )

        except ValueError:
            continue

        parsed = date(
            parsed_time.tm_year,
            parsed_time.tm_mon,
            parsed_time.tm_mday,
        )

        if parsed.year == 1:
            return None

        return parsed.isoformat()

    return None


def make_record(
    *,
    symbol: Any,
    listing_date: Any,
) -> ListingRecord | None:
    normalized_symbol = (
        normalize_symbol(
            symbol
        )
    )

    normalized_date = (
        normalize_date(
            listing_date
        )
    )

    if (
        normalized_symbol is None
        or normalized_date is None
    ):
        return None

    return ListingRecord(
        symbol=normalized_symbol,
        listing_date=normalized_date,
    )


def duplicate_count(
    records: tuple[
        ListingRecord,
        ...
    ],
) -> int:
    return (
        len(records)
        - len(
            set(
                records
            )
        )
    )


def fetch_listing_activity_year(
    *,
    client: httpx.Client,
    year: int,
    pause: float,
) -> SourceResult:
    collected = []

    requests = 0

    for page in range(
        1,
        MAX_PAGES + 1,
    ):
        params = {
            "Status": "ipo",
            "Year": year,
            "indexfrom": page,
            "pagesize": (
                LISTING_PAGE_SIZE
            ),
        }

        try:
            response = client.get(
                (
                    IDX_ORIGIN
                    + LISTING_ACTIVITY_ENDPOINT
                ),
                params=params,
            )

        except httpx.HTTPError as exc:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        requests += 1

        if response.status_code != 200:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "Unexpected HTTP "
                    f"{response.status_code}."
                ),
            )

        try:
            payload = response.json()

        except ValueError:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity "
                    "response is not JSON."
                ),
            )

        if not isinstance(
            payload,
            dict,
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity JSON "
                    "root is not an object."
                ),
            )

        criteria = payload.get(
            "SearchCriteria"
        )

        rows = payload.get(
            "Result"
        )

        if not isinstance(
            criteria,
            dict,
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity "
                    "SearchCriteria missing."
                ),
            )

        if not isinstance(
            rows,
            list,
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity Result "
                    "is not an array."
                ),
            )

        echoed_year = str(
            criteria.get(
                "Year"
            )
        )

        echoed_status = (
            criteria.get(
                "Status"
            )
        )

        try:
            echoed_page = int(
                criteria.get(
                    "indexfrom"
                )
            )

            echoed_pagesize = int(
                criteria.get(
                    "pagesize"
                )
            )

        except (
            TypeError,
            ValueError,
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity "
                    "pagination echo invalid."
                ),
            )

        if echoed_year != str(
            year
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity Year "
                    "echo mismatch."
                ),
            )

        if echoed_status != "ipo":
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity Status "
                    "echo mismatch."
                ),
            )

        if echoed_page != page:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity page "
                    "echo mismatch."
                ),
            )

        if (
            echoed_pagesize
            != LISTING_PAGE_SIZE
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "ListingActivity pagesize "
                    "echo mismatch."
                ),
            )

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                return SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        "ListingActivity "
                        "contains non-object "
                        "row."
                    ),
                )

            record = make_record(
                symbol=row.get(
                    "KodeEmiten"
                ),
                listing_date=row.get(
                    "TanggalPencatatan"
                ),
            )

            if record is None:
                return SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        "ListingActivity row "
                        "has invalid symbol "
                        "or listing date."
                    ),
                )

            if not record.listing_date.startswith(
                f"{year}-"
            ):
                return SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        "ListingActivity row "
                        "year mismatch."
                    ),
                )

            collected.append(
                record
            )

        if not rows:
            break

        if len(
            rows
        ) < LISTING_PAGE_SIZE:
            break

        if pause > 0:
            sleep(
                pause
            )

    else:
        return SourceResult(
            records=tuple(
                collected
            ),
            requests=requests,
            error=(
                "ListingActivity maximum "
                "page limit reached."
            ),
        )

    return SourceResult(
        records=tuple(
            collected
        ),
        requests=requests,
        error=None,
    )


def fetch_digital_statistic_month(
    *,
    client: httpx.Client,
    year: int,
    month: int,
    pause: float,
) -> SourceResult:
    collected = []

    requests = 0

    for page in range(
        1,
        MAX_PAGES + 1,
    ):
        params = {
            "urlName": (
                "LINK_STOCK_NEW_LISTING"
            ),
            "periodYear": year,
            "periodMonth": month,
            "periodType": "monthly",
            "isPrint": "False",
            "cumulative": "false",
            "pageSize": (
                DIGITAL_PAGE_SIZE
            ),
            "pageNumber": page,
            "orderBy": "",
            "search": "",
        }

        try:
            response = client.get(
                (
                    IDX_ORIGIN
                    + DIGITAL_STATISTIC_ENDPOINT
                ),
                params=params,
            )

        except httpx.HTTPError as exc:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        requests += 1

        if response.status_code != 200:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "Digital Statistic "
                    f"HTTP {response.status_code}."
                ),
            )

        try:
            payload = response.json()

        except ValueError:
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "Digital Statistic "
                    "response is not JSON."
                ),
            )

        if not isinstance(
            payload,
            dict,
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "Digital Statistic JSON "
                    "root is not an object."
                ),
            )

        rows = payload.get(
            "data"
        )

        if not isinstance(
            rows,
            list,
        ):
            return SourceResult(
                records=tuple(
                    collected
                ),
                requests=requests,
                error=(
                    "Digital Statistic data "
                    "is not an array."
                ),
            )

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                return SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        "Digital Statistic "
                        "contains non-object "
                        "row."
                    ),
                )

            record = make_record(
                symbol=row.get(
                    "code"
                ),
                listing_date=row.get(
                    "ListingDate"
                ),
            )

            if record is None:
                return SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        "Digital Statistic "
                        "row has invalid symbol "
                        "or ListingDate."
                    ),
                )

            if not record.listing_date.startswith(
                f"{year}-"
            ):
                return SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        "Digital Statistic "
                        "row year mismatch."
                    ),
                )

            collected.append(
                record
            )

        if not rows:
            break

        if len(
            rows
        ) < DIGITAL_PAGE_SIZE:
            break

        if pause > 0:
            sleep(
                pause
            )

    else:
        return SourceResult(
            records=tuple(
                collected
            ),
            requests=requests,
            error=(
                "Digital Statistic maximum "
                "page limit reached."
            ),
        )

    return SourceResult(
        records=tuple(
            collected
        ),
        requests=requests,
        error=None,
    )


def month_limit(
    *,
    year: int,
    start_year: int,
    start_month: int,
) -> int:
    if year == start_year:
        return start_month

    return 12


def fetch_digital_statistic_year(
    *,
    client: httpx.Client,
    year: int,
    start_year: int,
    start_month: int,
    pause: float,
) -> tuple[
    SourceResult,
    tuple[
        tuple[int, int],
        ...
    ],
]:
    collected = []

    requests = 0

    monthly_counts = []

    max_month = month_limit(
        year=year,
        start_year=start_year,
        start_month=start_month,
    )

    for month in range(
        1,
        max_month + 1,
    ):
        result = (
            fetch_digital_statistic_month(
                client=client,
                year=year,
                month=month,
                pause=pause,
            )
        )

        requests += (
            result.requests
        )

        if result.error is not None:
            return (
                SourceResult(
                    records=tuple(
                        collected
                    ),
                    requests=requests,
                    error=(
                        f"{year}-{month:02d}: "
                        f"{result.error}"
                    ),
                ),
                tuple(
                    monthly_counts
                ),
            )

        collected.extend(
            result.records
        )

        monthly_counts.append(
            (
                month,
                len(
                    result.records
                ),
            )
        )

        if pause > 0:
            sleep(
                pause
            )

    return (
        SourceResult(
            records=tuple(
                collected
            ),
            requests=requests,
            error=None,
        ),
        tuple(
            monthly_counts
        ),
    )


def symbol_dates(
    records: set[
        ListingRecord
    ],
) -> dict[
    str,
    set[str],
]:
    result: dict[
        str,
        set[str],
    ] = {}

    for record in records:
        result.setdefault(
            record.symbol,
            set(),
        ).add(
            record.listing_date
        )

    return result


def reconcile(
    *,
    year: int,
    listing: SourceResult,
    digital: SourceResult,
) -> ReconciliationResult:
    listing_set = set(
        listing.records
    )

    digital_set = set(
        digital.records
    )

    exact = (
        listing_set
        & digital_set
    )

    listing_symbols = (
        symbol_dates(
            listing_set
        )
    )

    digital_symbols = (
        symbol_dates(
            digital_set
        )
    )

    shared_symbols = (
        set(
            listing_symbols
        )
        & set(
            digital_symbols
        )
    )

    disagreements = []

    for symbol in sorted(
        shared_symbols
    ):
        left_dates = (
            listing_symbols[
                symbol
            ]
        )

        right_dates = (
            digital_symbols[
                symbol
            ]
        )

        if left_dates == right_dates:
            continue

        disagreements.append(
            (
                symbol,
                tuple(
                    sorted(
                        left_dates
                    )
                ),
                tuple(
                    sorted(
                        right_dates
                    )
                ),
            )
        )

    listing_only = tuple(
        sorted(
            listing_set
            - digital_set,
            key=lambda record: (
                record.listing_date,
                record.symbol,
            ),
        )
    )

    digital_only = tuple(
        sorted(
            digital_set
            - listing_set,
            key=lambda record: (
                record.listing_date,
                record.symbol,
            ),
        )
    )

    return ReconciliationResult(
        year=year,
        listing_count=len(
            listing_set
        ),
        digital_count=len(
            digital_set
        ),
        exact_matches=len(
            exact
        ),
        listing_only=listing_only,
        digital_only=digital_only,
        date_disagreements=tuple(
            disagreements
        ),
        listing_duplicates=(
            duplicate_count(
                listing.records
            )
        ),
        digital_duplicates=(
            duplicate_count(
                digital.records
            )
        ),
        listing_error=listing.error,
        digital_error=digital.error,
    )


def print_records(
    *,
    title: str,
    records: tuple[
        ListingRecord,
        ...
    ],
) -> None:
    if not records:
        return

    print(
        f"  {title}:"
    )

    for record in records:
        print(
            f"    {record.symbol:<8} "
            f"{record.listing_date}"
        )


def print_month_counts(
    monthly_counts: tuple[
        tuple[int, int],
        ...
    ],
) -> None:
    text = " ".join(
        (
            f"{month:02d}={count}"
        )
        for month, count
        in monthly_counts
    )

    print(
        f"  Digital monthly : "
        f"{text}"
    )


def print_reconciliation(
    *,
    result: ReconciliationResult,
    monthly_counts: tuple[
        tuple[int, int],
        ...
    ],
    listing_requests: int,
    digital_requests: int,
) -> None:
    print(
        f"{result.year}"
    )

    print(
        f"  ListingActivity : "
        f"{result.listing_count}"
    )

    print(
        f"  DigitalStatistic: "
        f"{result.digital_count}"
    )

    print(
        f"  Exact matches   : "
        f"{result.exact_matches}"
    )

    print(
        f"  Listing dupes   : "
        f"{result.listing_duplicates}"
    )

    print(
        f"  Digital dupes   : "
        f"{result.digital_duplicates}"
    )

    print(
        f"  Listing requests: "
        f"{listing_requests}"
    )

    print(
        f"  Digital requests: "
        f"{digital_requests}"
    )

    print_month_counts(
        monthly_counts
    )

    print(
        f"  Listing only    : "
        f"{len(result.listing_only)}"
    )

    print(
        f"  Digital only    : "
        f"{len(result.digital_only)}"
    )

    print(
        f"  Date disagreements: "
        f"{len(result.date_disagreements)}"
    )

    if result.listing_error is not None:
        print(
            f"  Listing error   : "
            f"{result.listing_error}"
        )

    if result.digital_error is not None:
        print(
            f"  Digital error   : "
            f"{result.digital_error}"
        )

    print_records(
        title="ListingActivity only",
        records=result.listing_only,
    )

    print_records(
        title="DigitalStatistic only",
        records=result.digital_only,
    )

    if result.date_disagreements:
        print(
            "  Date disagreements:"
        )

        for (
            symbol,
            listing_dates,
            digital_dates,
        ) in result.date_disagreements:
            print(
                f"    {symbol}"
            )

            print(
                "      ListingActivity : "
                + ", ".join(
                    listing_dates
                )
            )

            print(
                "      DigitalStatistic: "
                + ", ".join(
                    digital_dates
                )
            )

    passed = (
        result.listing_error is None
        and result.digital_error is None
        and result.listing_duplicates == 0
        and result.digital_duplicates == 0
        and not result.listing_only
        and not result.digital_only
        and not result.date_disagreements
    )

    print(
        "  Reconciliation   : "
        + (
            "PASS"
            if passed
            else "MISMATCH"
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
        "IDX IPO Cross-Source "
        "Reconciliation V1"
    )

    print(
        "--------------------------------"
    )

    print(
        "Source A : ListingActivity"
    )

    print(
        "Source B : Digital Statistic "
        "Stock New Listing"
    )

    print(
        f"Years    : "
        f"{args.start_year} "
        f"→ {args.end_year}"
    )

    print(
        f"Latest month scanned : "
        f"{args.start_month}"
    )

    print()

    results = []

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
            listing = (
                fetch_listing_activity_year(
                    client=client,
                    year=year,
                    pause=args.pause,
                )
            )

            (
                digital,
                monthly_counts,
            ) = fetch_digital_statistic_year(
                client=client,
                year=year,
                start_year=(
                    args.start_year
                ),
                start_month=(
                    args.start_month
                ),
                pause=args.pause,
            )

            result = reconcile(
                year=year,
                listing=listing,
                digital=digital,
            )

            results.append(
                result
            )

            print_reconciliation(
                result=result,
                monthly_counts=(
                    monthly_counts
                ),
                listing_requests=(
                    listing.requests
                ),
                digital_requests=(
                    digital.requests
                ),
            )

            if args.pause > 0:
                sleep(
                    args.pause
                )

    print(
        "SUMMARY"
    )

    print(
        f"Years compared : "
        f"{len(results)}"
    )

    pass_count = sum(
        (
            result.listing_error is None
            and result.digital_error is None
            and result.listing_duplicates == 0
            and result.digital_duplicates == 0
            and not result.listing_only
            and not result.digital_only
            and not result.date_disagreements
        )
        for result in results
    )

    print(
        f"Exact PASS     : "
        f"{pass_count}/"
        f"{len(results)}"
    )

    total_listing = sum(
        result.listing_count
        for result in results
    )

    total_digital = sum(
        result.digital_count
        for result in results
    )

    total_exact = sum(
        result.exact_matches
        for result in results
    )

    print(
        f"Listing rows   : "
        f"{total_listing}"
    )

    print(
        f"Digital rows   : "
        f"{total_digital}"
    )

    print(
        f"Exact matches  : "
        f"{total_exact}"
    )

    print()

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "Exact agreement supports "
        "cross-source consistency."
    )

    print(
        "It does not prove either source "
        "is historically complete."
    )

    print(
        "Historical retrieval today also "
        "does not establish historical "
        "publication availability."
    )

    print(
        "No lifecycle rows are written "
        "to the database by this script."
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