import argparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
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

PERFORMANCE_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "newly-listed-stock-performance/"
)

REFERER_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "canonical-ipo-evidence-builder"
    ),
    "Accept": "*/*",
    "Referer": REFERER_URL,
}


SOURCE_LISTING_ACTIVITY = (
    "LISTING_ACTIVITY"
)

SOURCE_DIGITAL_STATISTIC = (
    "DIGITAL_STATISTIC"
)

SOURCE_PERFORMANCE = (
    "NEWLY_LISTED_PERFORMANCE"
)


STATUS_CONFIRMED = (
    "CONFIRMED_MULTI_SOURCE"
)

STATUS_RESOLVED = (
    "CONFLICT_RESOLVED_BY_CONSENSUS"
)

STATUS_SINGLE = (
    "SINGLE_SOURCE"
)

STATUS_UNRESOLVED = (
    "UNRESOLVED_CONFLICT"
)


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
    error: str | None


@dataclass(
    frozen=True,
    slots=True,
)
class CanonicalRecord:
    symbol: str
    listing_date: str | None
    status: str
    supporting_sources: tuple[
        str,
        ...
    ]
    observed_dates: tuple[
        tuple[
            str,
            tuple[
                str,
                ...
            ],
        ],
        ...
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class YearResult:
    year: int
    listing_activity_count: int
    digital_statistic_count: int
    performance_count: int
    symbol_union_count: int
    canonical_count: int
    confirmed_count: int
    resolved_conflict_count: int
    single_source_count: int
    unresolved_count: int
    incomplete_source_count: int
    performance_anchor_complete: bool
    strict_ready: bool
    canonical_records: tuple[
        CanonicalRecord,
        ...
    ]


class PerformanceTableParser(
    HTMLParser
):
    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.rows: list[
            list[str]
        ] = []

        self._in_row = False
        self._cell_depth = 0

        self._current_row: list[
            str
        ] = []

        self._cell_parts: list[
            str
        ] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[
            tuple[
                str,
                str | None,
            ]
        ],
    ) -> None:
        del attrs

        normalized = (
            tag.casefold()
        )

        if normalized == "tr":
            self._in_row = True
            self._current_row = []

        elif (
            normalized
            in {
                "td",
                "th",
            }
            and self._in_row
        ):
            self._cell_depth += 1

            if self._cell_depth == 1:
                self._cell_parts = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        if (
            self._in_row
            and self._cell_depth > 0
        ):
            self._cell_parts.append(
                data
            )

    def handle_endtag(
        self,
        tag: str,
    ) -> None:
        normalized = (
            tag.casefold()
        )

        if (
            normalized
            in {
                "td",
                "th",
            }
            and self._in_row
            and self._cell_depth > 0
        ):
            self._cell_depth -= 1

            if self._cell_depth == 0:
                value = " ".join(
                    " ".join(
                        self._cell_parts
                    ).split()
                )

                self._current_row.append(
                    value
                )

                self._cell_parts = []

        elif (
            normalized == "tr"
            and self._in_row
        ):
            if self._current_row:
                self.rows.append(
                    self._current_row
                )

            self._current_row = []
            self._cell_parts = []
            self._cell_depth = 0
            self._in_row = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build canonical IDX IPO "
            "evidence for years with "
            "three validated official "
            "IDX sources."
        )
    )

    parser.add_argument(
        "--start-year",
        type=int,
        default=2025,
    )

    parser.add_argument(
        "--end-year",
        type=int,
        default=2023,
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

    parser.add_argument(
        "--show-all",
        action="store_true",
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if not (
        2023
        <= args.end_year
        <= args.start_year
        <= 2025
    ):
        raise ValueError(
            "This strict three-source "
            "builder currently supports "
            "only 2023 through 2025."
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
        try:
            parsed = date.fromisoformat(
                text[:10]
            )

        except ValueError:
            pass

        else:
            if parsed.year != 1:
                return parsed.isoformat()

    for date_format in (
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
    ):
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


def fetch_listing_activity_year(
    *,
    client: httpx.Client,
    year: int,
    pause: float,
) -> SourceResult:
    records = []

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
                    records
                ),
                error=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        if response.status_code != 200:
            return SourceResult(
                records=tuple(
                    records
                ),
                error=(
                    "ListingActivity HTTP "
                    f"{response.status_code}."
                ),
            )

        try:
            payload = response.json()

        except ValueError:
            return SourceResult(
                records=tuple(
                    records
                ),
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
                    records
                ),
                error=(
                    "ListingActivity root "
                    "is not an object."
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
                    records
                ),
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
                    records
                ),
                error=(
                    "ListingActivity Result "
                    "is not an array."
                ),
            )

        if str(
            criteria.get(
                "Year"
            )
        ) != str(
            year
        ):
            return SourceResult(
                records=tuple(
                    records
                ),
                error=(
                    "ListingActivity Year "
                    "echo mismatch."
                ),
            )

        if (
            criteria.get(
                "Status"
            )
            != "ipo"
        ):
            return SourceResult(
                records=tuple(
                    records
                ),
                error=(
                    "ListingActivity Status "
                    "echo mismatch."
                ),
            )

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                continue

            record = make_record(
                symbol=row.get(
                    "KodeEmiten"
                ),
                listing_date=row.get(
                    "TanggalPencatatan"
                ),
            )

            if record is None:
                continue

            if not (
                record.listing_date
                .startswith(
                    f"{year}-"
                )
            ):
                return SourceResult(
                    records=tuple(
                        records
                    ),
                    error=(
                        "ListingActivity "
                        "event year mismatch."
                    ),
                )

            records.append(
                record
            )

        if len(
            rows
        ) < LISTING_PAGE_SIZE:
            break

        if pause > 0:
            sleep(
                pause
            )

    return SourceResult(
        records=tuple(
            records
        ),
        error=None,
    )


def fetch_digital_month(
    *,
    client: httpx.Client,
    year: int,
    month: int,
    pause: float,
) -> SourceResult:
    records = []

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
                    records
                ),
                error=(
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        if response.status_code != 200:
            return SourceResult(
                records=tuple(
                    records
                ),
                error=(
                    "Digital Statistic "
                    f"{year}-{month:02d} "
                    f"HTTP {response.status_code}."
                ),
            )

        try:
            payload = response.json()

        except ValueError:
            return SourceResult(
                records=tuple(
                    records
                ),
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
                    records
                ),
                error=(
                    "Digital Statistic root "
                    "is not an object."
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
                    records
                ),
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
                continue

            record = make_record(
                symbol=row.get(
                    "code"
                ),
                listing_date=row.get(
                    "ListingDate"
                ),
            )

            if record is None:
                continue

            if not (
                record.listing_date
                .startswith(
                    f"{year}-"
                )
            ):
                return SourceResult(
                    records=tuple(
                        records
                    ),
                    error=(
                        "Digital Statistic "
                        "event year mismatch."
                    ),
                )

            records.append(
                record
            )

        if len(
            rows
        ) < DIGITAL_PAGE_SIZE:
            break

        if pause > 0:
            sleep(
                pause
            )

    return SourceResult(
        records=tuple(
            records
        ),
        error=None,
    )


def fetch_digital_year(
    *,
    client: httpx.Client,
    year: int,
    pause: float,
) -> SourceResult:
    records = []

    for month in range(
        1,
        13,
    ):
        monthly = fetch_digital_month(
            client=client,
            year=year,
            month=month,
            pause=pause,
        )

        if monthly.error is not None:
            return SourceResult(
                records=tuple(
                    records
                ),
                error=(
                    f"{year}-{month:02d}: "
                    f"{monthly.error}"
                ),
            )

        records.extend(
            monthly.records
        )

        if pause > 0:
            sleep(
                pause
            )

    unique_records = tuple(
        sorted(
            set(
                records
            ),
            key=lambda record: (
                record.listing_date,
                record.symbol,
            ),
        )
    )

    return SourceResult(
        records=unique_records,
        error=None,
    )


def fetch_performance(
    *,
    client: httpx.Client,
) -> SourceResult:
    try:
        response = client.get(
            PERFORMANCE_URL
        )

    except httpx.HTTPError as exc:
        return SourceResult(
            records=(),
            error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    if response.status_code != 200:
        return SourceResult(
            records=(),
            error=(
                "Performance page HTTP "
                f"{response.status_code}."
            ),
        )

    parser = PerformanceTableParser()

    parser.feed(
        response.text
    )

    parser.close()

    records = []

    for row in parser.rows:
        if len(row) < 4:
            continue

        if not (
            row[0]
            .strip()
            .isdigit()
        ):
            continue

        record = make_record(
            symbol=row[1],
            listing_date=row[3],
        )

        if record is not None:
            records.append(
                record
            )

    if not records:
        return SourceResult(
            records=(),
            error=(
                "No performance records "
                "were parsed."
            ),
        )

    return SourceResult(
        records=tuple(
            records
        ),
        error=None,
    )


def records_for_year(
    *,
    records: tuple[
        ListingRecord,
        ...
    ],
    year: int,
) -> set[
    ListingRecord
]:
    return {
        record
        for record in records
        if (
            record.listing_date
            .startswith(
                f"{year}-"
            )
        )
    }


def source_symbol_dates(
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
    ] = defaultdict(
        set
    )

    for record in records:
        result[
            record.symbol
        ].add(
            record.listing_date
        )

    return dict(
        result
    )


def add_source_votes(
    *,
    votes: dict[
        str,
        dict[
            str,
            set[str],
        ],
    ],
    source: str,
    records: set[
        ListingRecord
    ],
) -> None:
    for record in records:
        votes.setdefault(
            record.symbol,
            {},
        ).setdefault(
            record.listing_date,
            set(),
        ).add(
            source
        )


def canonicalize_symbol(
    *,
    symbol: str,
    date_votes: dict[
        str,
        set[str],
    ],
) -> CanonicalRecord:
    ranked = sorted(
        date_votes.items(),
        key=lambda item: (
            -len(
                item[1]
            ),
            item[0],
        ),
    )

    observed_dates = tuple(
        (
            observed_date,
            tuple(
                sorted(
                    sources
                )
            ),
        )
        for observed_date, sources
        in sorted(
            date_votes.items()
        )
    )

    if not ranked:
        return CanonicalRecord(
            symbol=symbol,
            listing_date=None,
            status=STATUS_UNRESOLVED,
            supporting_sources=(),
            observed_dates=(
                observed_dates
            ),
        )

    best_date = ranked[
        0
    ][0]

    best_sources = ranked[
        0
    ][1]

    best_vote_count = len(
        best_sources
    )

    tied_dates = [
        observed_date
        for observed_date, sources
        in ranked
        if len(
            sources
        )
        == best_vote_count
    ]

    if (
        best_vote_count >= 2
        and len(
            tied_dates
        )
        == 1
    ):
        if len(
            date_votes
        ) > 1:
            status = (
                STATUS_RESOLVED
            )

        else:
            status = (
                STATUS_CONFIRMED
            )

        return CanonicalRecord(
            symbol=symbol,
            listing_date=best_date,
            status=status,
            supporting_sources=tuple(
                sorted(
                    best_sources
                )
            ),
            observed_dates=(
                observed_dates
            ),
        )

    if (
        best_vote_count == 1
        and len(
            date_votes
        )
        == 1
    ):
        return CanonicalRecord(
            symbol=symbol,
            listing_date=best_date,
            status=STATUS_SINGLE,
            supporting_sources=tuple(
                sorted(
                    best_sources
                )
            ),
            observed_dates=(
                observed_dates
            ),
        )

    return CanonicalRecord(
        symbol=symbol,
        listing_date=None,
        status=STATUS_UNRESOLVED,
        supporting_sources=(),
        observed_dates=(
            observed_dates
        ),
    )


def build_year_result(
    *,
    year: int,
    listing_records: set[
        ListingRecord
    ],
    digital_records: set[
        ListingRecord
    ],
    performance_records: set[
        ListingRecord
    ],
) -> YearResult:
    votes: dict[
        str,
        dict[
            str,
            set[str],
        ],
    ] = {}

    add_source_votes(
        votes=votes,
        source=(
            SOURCE_LISTING_ACTIVITY
        ),
        records=listing_records,
    )

    add_source_votes(
        votes=votes,
        source=(
            SOURCE_DIGITAL_STATISTIC
        ),
        records=digital_records,
    )

    add_source_votes(
        votes=votes,
        source=SOURCE_PERFORMANCE,
        records=performance_records,
    )

    canonical_records = tuple(
        canonicalize_symbol(
            symbol=symbol,
            date_votes=votes[
                symbol
            ],
        )
        for symbol in sorted(
            votes
        )
    )

    confirmed_count = sum(
        record.status
        == STATUS_CONFIRMED
        for record in canonical_records
    )

    resolved_count = sum(
        record.status
        == STATUS_RESOLVED
        for record in canonical_records
    )

    single_count = sum(
        record.status
        == STATUS_SINGLE
        for record in canonical_records
    )

    unresolved_count = sum(
        record.status
        == STATUS_UNRESOLVED
        for record in canonical_records
    )

    canonical_count = sum(
        record.listing_date
        is not None
        for record in canonical_records
    )

    listing_symbols = set(
        source_symbol_dates(
            listing_records
        )
    )

    digital_symbols = set(
        source_symbol_dates(
            digital_records
        )
    )

    performance_symbols = set(
        source_symbol_dates(
            performance_records
        )
    )

    symbol_union = (
        listing_symbols
        | digital_symbols
        | performance_symbols
    )

    incomplete_source_count = 0

    for symbol in symbol_union:
        presence = sum(
            (
                symbol
                in listing_symbols,
                symbol
                in digital_symbols,
                symbol
                in performance_symbols,
            )
        )

        if presence < 3:
            incomplete_source_count += 1

    performance_anchor_complete = (
        performance_symbols
        == symbol_union
    )

    strict_ready = (
        performance_anchor_complete
        and canonical_count
        == len(
            symbol_union
        )
        and single_count == 0
        and unresolved_count == 0
    )

    return YearResult(
        year=year,
        listing_activity_count=len(
            listing_symbols
        ),
        digital_statistic_count=len(
            digital_symbols
        ),
        performance_count=len(
            performance_symbols
        ),
        symbol_union_count=len(
            symbol_union
        ),
        canonical_count=canonical_count,
        confirmed_count=(
            confirmed_count
        ),
        resolved_conflict_count=(
            resolved_count
        ),
        single_source_count=(
            single_count
        ),
        unresolved_count=(
            unresolved_count
        ),
        incomplete_source_count=(
            incomplete_source_count
        ),
        performance_anchor_complete=(
            performance_anchor_complete
        ),
        strict_ready=strict_ready,
        canonical_records=(
            canonical_records
        ),
    )


def print_observed_dates(
    record: CanonicalRecord,
) -> None:
    for (
        observed_date,
        sources,
    ) in record.observed_dates:
        print(
            f"      {observed_date} "
            f"<- "
            f"{', '.join(sources)}"
        )


def print_year_result(
    *,
    result: YearResult,
    show_all: bool,
) -> None:
    print(
        f"{result.year}"
    )

    print(
        f"  ListingActivity   : "
        f"{result.listing_activity_count}"
    )

    print(
        f"  DigitalStatistic  : "
        f"{result.digital_statistic_count}"
    )

    print(
        f"  Performance       : "
        f"{result.performance_count}"
    )

    print(
        f"  Symbol union      : "
        f"{result.symbol_union_count}"
    )

    print(
        f"  Canonical rows    : "
        f"{result.canonical_count}"
    )

    print(
        f"  Confirmed         : "
        f"{result.confirmed_count}"
    )

    print(
        f"  Conflict resolved : "
        f"{result.resolved_conflict_count}"
    )

    print(
        f"  Single source     : "
        f"{result.single_source_count}"
    )

    print(
        f"  Unresolved        : "
        f"{result.unresolved_count}"
    )

    print(
        f"  Source gaps       : "
        f"{result.incomplete_source_count}"
    )

    print(
        "  Performance anchor: "
        + (
            "COMPLETE"
            if (
                result
                .performance_anchor_complete
            )
            else "INCOMPLETE"
        )
    )

    print(
        "  Strict ready      : "
        + (
            "YES"
            if result.strict_ready
            else "NO"
        )
    )

    exceptions = [
        record
        for record
        in result.canonical_records
        if (
            show_all
            or record.status
            != STATUS_CONFIRMED
            or len(
                record
                .supporting_sources
            )
            < 3
        )
    ]

    if exceptions:
        print(
            "  Evidence details:"
        )

        for record in exceptions:
            print(
                f"    {record.symbol:<8} "
                f"canonical="
                f"{record.listing_date} "
                f"status="
                f"{record.status}"
            )

            print(
                "      supporting="
                + (
                    ", ".join(
                        record
                        .supporting_sources
                    )
                    if (
                        record
                        .supporting_sources
                    )
                    else "-"
                )
            )

            print_observed_dates(
                record
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
        "IDX Canonical IPO Evidence "
        "Builder V1"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Years      : "
        f"{args.start_year} "
        f"→ {args.end_year}"
    )

    print(
        "Mode       : DRY RUN"
    )

    print(
        "DB writes  : DISABLED"
    )

    print()

    results = []

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        performance = fetch_performance(
            client=client
        )

        if performance.error is not None:
            print(
                "Performance source ERROR:"
            )

            print(
                f"  {performance.error}"
            )

            return

        print(
            "Performance source:"
        )

        print(
            f"  Parsed records : "
            f"{len(performance.records)}"
        )

        print()

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

            if listing.error is not None:
                print(
                    f"{year} "
                    f"ListingActivity ERROR:"
                )

                print(
                    f"  {listing.error}"
                )

                return

            digital = (
                fetch_digital_year(
                    client=client,
                    year=year,
                    pause=args.pause,
                )
            )

            if digital.error is not None:
                print(
                    f"{year} "
                    f"DigitalStatistic ERROR:"
                )

                print(
                    f"  {digital.error}"
                )

                return

            listing_records = set(
                listing.records
            )

            digital_records = set(
                digital.records
            )

            performance_records = (
                records_for_year(
                    records=(
                        performance.records
                    ),
                    year=year,
                )
            )

            result = build_year_result(
                year=year,
                listing_records=(
                    listing_records
                ),
                digital_records=(
                    digital_records
                ),
                performance_records=(
                    performance_records
                ),
            )

            results.append(
                result
            )

            print_year_result(
                result=result,
                show_all=args.show_all,
            )

            if args.pause > 0:
                sleep(
                    args.pause
                )

    total_canonical = sum(
        result.canonical_count
        for result in results
    )

    total_confirmed = sum(
        result.confirmed_count
        for result in results
    )

    total_resolved = sum(
        result.resolved_conflict_count
        for result in results
    )

    total_single = sum(
        result.single_source_count
        for result in results
    )

    total_unresolved = sum(
        result.unresolved_count
        for result in results
    )

    all_ready = all(
        result.strict_ready
        for result in results
    )

    print(
        "SUMMARY"
    )

    print(
        f"Years evaluated   : "
        f"{len(results)}"
    )

    print(
        f"Canonical rows    : "
        f"{total_canonical}"
    )

    print(
        f"Confirmed         : "
        f"{total_confirmed}"
    )

    print(
        f"Conflicts resolved: "
        f"{total_resolved}"
    )

    print(
        f"Single source     : "
        f"{total_single}"
    )

    print(
        f"Unresolved        : "
        f"{total_unresolved}"
    )

    print(
        "Strict canonical gate: "
        + (
            "PASS"
            if all_ready
            else "FAIL"
        )
    )

    print()

    print(
        "EXPECTED INTERPRETATION:"
    )

    print(
        "2023-2025 may be promoted "
        "to canonical IPO event dates "
        "only when the strict gate PASSes."
    )

    print(
        "This does not make historical "
        "available_at point-in-time safe."
    )

    print(
        "2020-2022 and 2026 are excluded "
        "from this strict builder."
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