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
        "listing-evidence-inspector"
    ),
    "Accept": "*/*",
    "Referer": REFERER_URL,
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
class DigitalObservation:
    record: ListingRecord
    query_year: int
    query_month: int


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
            "Inspect cross-source IDX "
            "IPO evidence and monthly "
            "Digital Statistic duplicate "
            "provenance."
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
        "--latest-month",
        type=int,
        default=8,
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

    if not (
        1
        <= args.latest_month
        <= 12
    ):
        raise ValueError(
            "latest-month must be "
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


def fetch_listing_activity(
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

        rows = payload.get(
            "Result"
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

            if record is not None:
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
) -> tuple[
    DigitalObservation,
    ...
]:
    observations = []

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

        response = client.get(
            (
                IDX_ORIGIN
                + DIGITAL_STATISTIC_ENDPOINT
            ),
            params=params,
        )

        if response.status_code != 200:
            raise RuntimeError(
                "Digital Statistic "
                f"{year}-{month:02d} "
                f"HTTP {response.status_code}."
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise ValueError(
                "Digital Statistic "
                f"{year}-{month:02d} "
                "response is not JSON."
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "Digital Statistic root "
                "is not an object."
            )

        rows = payload.get(
            "data"
        )

        if not isinstance(
            rows,
            list,
        ):
            raise TypeError(
                "Digital Statistic data "
                "is not an array."
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

            observations.append(
                DigitalObservation(
                    record=record,
                    query_year=year,
                    query_month=month,
                )
            )

        if len(
            rows
        ) < DIGITAL_PAGE_SIZE:
            break

        if pause > 0:
            sleep(
                pause
            )

    return tuple(
        observations
    )


def fetch_digital_year(
    *,
    client: httpx.Client,
    year: int,
    max_month: int,
    pause: float,
) -> tuple[
    DigitalObservation,
    ...
]:
    observations = []

    for month in range(
        1,
        max_month + 1,
    ):
        monthly = fetch_digital_month(
            client=client,
            year=year,
            month=month,
            pause=pause,
        )

        observations.extend(
            monthly
        )

        if pause > 0:
            sleep(
                pause
            )

    return tuple(
        observations
    )


def fetch_performance_records(
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

        number = (
            row[0]
            .strip()
        )

        if not number.isdigit():
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
                "No performance table "
                "records parsed."
            ),
        )

    return SourceResult(
        records=tuple(
            records
        ),
        error=None,
    )


def group_by_year(
    records: tuple[
        ListingRecord,
        ...
    ],
) -> dict[
    int,
    set[
        ListingRecord
    ],
]:
    result: dict[
        int,
        set[
            ListingRecord
        ],
    ] = defaultdict(
        set
    )

    for record in records:
        year = int(
            record.listing_date[
                :4
            ]
        )

        result[
            year
        ].add(
            record
        )

    return dict(
        result
    )


def print_digital_duplicates(
    observations: tuple[
        DigitalObservation,
        ...
    ],
) -> None:
    provenance: dict[
        ListingRecord,
        list[int],
    ] = defaultdict(
        list
    )

    for observation in observations:
        provenance[
            observation.record
        ].append(
            observation.query_month
        )

    duplicates = {
        record: months
        for record, months
        in provenance.items()
        if len(
            months
        ) > 1
    }

    duplicate_count = sum(
        len(
            months
        )
        - 1
        for months
        in duplicates.values()
    )

    print(
        f"  Digital raw rows   : "
        f"{len(observations)}"
    )

    print(
        f"  Digital unique     : "
        f"{len(provenance)}"
    )

    print(
        f"  Duplicate records  : "
        f"{duplicate_count}"
    )

    if duplicates:
        print(
            "  Duplicate provenance:"
        )

        for record, months in sorted(
            duplicates.items(),
            key=lambda item: (
                item[0].listing_date,
                item[0].symbol,
            ),
        ):
            month_text = ", ".join(
                f"{month:02d}"
                for month in months
            )

            print(
                f"    "
                f"{record.symbol:<8} "
                f"{record.listing_date} "
                f"months=[{month_text}]"
            )


def symbol_map(
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


def print_three_source_year(
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
) -> None:
    listing_map = symbol_map(
        listing_records
    )

    digital_map = symbol_map(
        digital_records
    )

    performance_map = symbol_map(
        performance_records
    )

    symbols = sorted(
        set(
            listing_map
        )
        | set(
            digital_map
        )
        | set(
            performance_map
        )
    )

    print()

    print(
        f"{year} THREE-SOURCE EVIDENCE"
    )

    print(
        f"  ListingActivity : "
        f"{len(listing_map)}"
    )

    print(
        f"  DigitalStatistic: "
        f"{len(digital_map)}"
    )

    print(
        f"  Performance     : "
        f"{len(performance_map)}"
    )

    print(
        f"  Symbol union    : "
        f"{len(symbols)}"
    )

    print(
        "  Disputed / incomplete symbols:"
    )

    disputed = 0

    for symbol in symbols:
        listing_dates = (
            listing_map.get(
                symbol,
                set(),
            )
        )

        digital_dates = (
            digital_map.get(
                symbol,
                set(),
            )
        )

        performance_dates = (
            performance_map.get(
                symbol,
                set(),
            )
        )

        present_count = sum(
            (
                bool(
                    listing_dates
                ),
                bool(
                    digital_dates
                ),
                bool(
                    performance_dates
                ),
            )
        )

        all_dates = (
            listing_dates
            | digital_dates
            | performance_dates
        )

        if (
            present_count == 3
            and len(
                all_dates
            ) == 1
        ):
            continue

        disputed += 1

        print(
            f"    {symbol}"
        )

        print(
            "      ListingActivity : "
            + (
                ", ".join(
                    sorted(
                        listing_dates
                    )
                )
                if listing_dates
                else "-"
            )
        )

        print(
            "      DigitalStatistic: "
            + (
                ", ".join(
                    sorted(
                        digital_dates
                    )
                )
                if digital_dates
                else "-"
            )
        )

        print(
            "      Performance     : "
            + (
                ", ".join(
                    sorted(
                        performance_dates
                    )
                )
                if performance_dates
                else "-"
            )
        )

    if disputed == 0:
        print(
            "    -"
        )

    print(
        f"  Disputed count  : "
        f"{disputed}"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX IPO Evidence Inspector V1"
    )

    print(
        "-----------------------------"
    )

    print(
        f"Years : "
        f"{args.start_year} "
        f"→ {args.end_year}"
    )

    print()

    listing_by_year: dict[
        int,
        set[
            ListingRecord
        ],
    ] = {}

    digital_by_year: dict[
        int,
        set[
            ListingRecord
        ],
    ] = {}

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        performance = (
            fetch_performance_records(
                client=client
            )
        )

        if performance.error is not None:
            print(
                "Performance source ERROR:"
            )

            print(
                f"  {performance.error}"
            )

            performance_by_year: dict[
                int,
                set[
                    ListingRecord
                ],
            ] = {}

        else:
            performance_by_year = (
                group_by_year(
                    performance.records
                )
            )

            print(
                "Performance source:"
            )

            print(
                f"  Parsed records : "
                f"{len(performance.records)}"
            )

            print(
                "  Years          : "
                + ", ".join(
                    str(
                        year
                    )
                    for year in sorted(
                        performance_by_year
                    )
                )
            )

        print()

        for year in range(
            args.start_year,
            args.end_year - 1,
            -1,
        ):
            max_month = (
                args.latest_month
                if year
                == args.start_year
                else 12
            )

            listing = (
                fetch_listing_activity(
                    client=client,
                    year=year,
                    pause=args.pause,
                )
            )

            if listing.error is not None:
                print(
                    f"{year} "
                    f"ListingActivity ERROR: "
                    f"{listing.error}"
                )

                listing_records: set[
                    ListingRecord
                ] = set()

            else:
                listing_records = set(
                    listing.records
                )

            try:
                observations = (
                    fetch_digital_year(
                        client=client,
                        year=year,
                        max_month=max_month,
                        pause=args.pause,
                    )
                )

            except (
                httpx.HTTPError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                print(
                    f"{year} "
                    f"DigitalStatistic ERROR: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                observations = ()

            digital_records = {
                observation.record
                for observation
                in observations
            }

            listing_by_year[
                year
            ] = listing_records

            digital_by_year[
                year
            ] = digital_records

            print(
                f"{year}"
            )

            print(
                f"  ListingActivity   : "
                f"{len(listing_records)}"
            )

            print_digital_duplicates(
                observations
            )

            print()

        print(
            "THREE-SOURCE COMPARISON"
        )

        for year in (
            2025,
            2024,
            2023,
        ):
            if not (
                args.end_year
                <= year
                <= args.start_year
            ):
                continue

            print_three_source_year(
                year=year,
                listing_records=(
                    listing_by_year.get(
                        year,
                        set(),
                    )
                ),
                digital_records=(
                    digital_by_year.get(
                        year,
                        set(),
                    )
                ),
                performance_records=(
                    performance_by_year.get(
                        year,
                        set(),
                    )
                ),
            )

    print()

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "No source is promoted to "
        "canonical solely because it "
        "contains more rows."
    )

    print(
        "Third-source agreement may "
        "adjudicate specific symbol/date "
        "disagreements."
    )

    print(
        "Digital monthly duplicates are "
        "retained as provenance evidence "
        "and not counted twice."
    )

    print(
        "Historical available_at remains "
        "UNKNOWN unless publication-time "
        "evidence exists."
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