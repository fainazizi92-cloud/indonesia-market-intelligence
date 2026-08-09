import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

import httpx
from build_idx_canonical_ipo_evidence import (
    DEFAULT_HEADERS,
    ListingRecord,
    build_year_result,
    fetch_digital_year,
    fetch_listing_activity_year,
    fetch_performance,
    records_for_year,
)

CURRENT_YEAR = 2026

STRICT_START_YEAR = 2023
STRICT_END_YEAR = 2025

OLDER_START_YEAR = 2020
OLDER_END_YEAR = 2022


ANNUAL_COUNT_ANCHORS = {
    2020: 51,
    2021: 54,
    2022: 59,
}


STATUS_CONFIRMED = (
    "CONFIRMED_MULTI_SOURCE"
)

STATUS_CONSENSUS = (
    "CONFLICT_RESOLVED_BY_CONSENSUS"
)

STATUS_COUNT_ANCHORED = (
    "COUNT_ANCHORED_SINGLE_SOURCE"
)

STATUS_PROVISIONAL = (
    "CURRENT_YEAR_PROVISIONAL"
)

STATUS_UNRESOLVED = (
    "UNRESOLVED"
)


QUALITY_VALID = "VALID"
QUALITY_WARNING = "WARNING"
QUALITY_REJECTED = "REJECTED"


@dataclass(
    frozen=True,
    slots=True,
)
class SnapshotRecord:
    symbol: str
    listing_date: str | None
    evidence_status: str
    supporting_sources: tuple[
        str,
        ...
    ]
    quality: str
    availability_status: str


@dataclass(
    frozen=True,
    slots=True,
)
class SnapshotYear:
    year: int
    mode: str
    expected_count: int | None
    listing_activity_count: int
    digital_statistic_count: int
    performance_count: int
    union_count: int
    canonical_count: int
    unresolved_count: int
    single_source_count: int
    coverage_anchor_match: bool | None
    event_date_ready: bool
    strict_pit_ready: bool
    records: tuple[
        SnapshotRecord,
        ...
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class IpoSnapshot:
    generated_at: str
    snapshot_version: str
    years: tuple[
        SnapshotYear,
        ...
    ]
    total_canonical_rows: int
    total_unresolved: int
    strict_pit_ready: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a consolidated IDX IPO "
            "history evidence snapshot for "
            "2020 through the current year."
        )
    )

    parser.add_argument(
        "--output",
        default=(
            "data/derived/"
            "idx_ipo_history_snapshot.json"
        ),
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
    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )

    if not args.output.strip():
        raise ValueError(
            "output path cannot be empty."
        )


def symbol_date_map(
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


def build_votes(
    *,
    listing_records: set[
        ListingRecord
    ],
    digital_records: set[
        ListingRecord
    ],
) -> dict[
    str,
    dict[
        str,
        set[str],
    ],
]:
    votes: dict[
        str,
        dict[
            str,
            set[str],
        ],
    ] = {}

    for source_name, records in (
        (
            "LISTING_ACTIVITY",
            listing_records,
        ),
        (
            "DIGITAL_STATISTIC",
            digital_records,
        ),
    ):
        for record in records:
            votes.setdefault(
                record.symbol,
                {},
            ).setdefault(
                record.listing_date,
                set(),
            ).add(
                source_name
            )

    return votes


def canonicalize_older_symbol(
    *,
    symbol: str,
    date_votes: dict[
        str,
        set[str],
    ],
    coverage_anchor_match: bool,
) -> SnapshotRecord:
    if not date_votes:
        return SnapshotRecord(
            symbol=symbol,
            listing_date=None,
            evidence_status=(
                STATUS_UNRESOLVED
            ),
            supporting_sources=(),
            quality=QUALITY_REJECTED,
            availability_status="UNKNOWN",
        )

    ranked = sorted(
        date_votes.items(),
        key=lambda item: (
            -len(
                item[1]
            ),
            item[0],
        ),
    )

    highest_vote_count = len(
        ranked[
            0
        ][1]
    )

    tied = [
        item
        for item in ranked
        if len(
            item[1]
        )
        == highest_vote_count
    ]

    if (
        len(
            date_votes
        )
        > 1
        and len(
            tied
        )
        != 1
    ):
        return SnapshotRecord(
            symbol=symbol,
            listing_date=None,
            evidence_status=(
                STATUS_UNRESOLVED
            ),
            supporting_sources=(),
            quality=QUALITY_REJECTED,
            availability_status="UNKNOWN",
        )

    selected_date = ranked[
        0
    ][0]

    sources = tuple(
        sorted(
            ranked[
                0
            ][1]
        )
    )

    if len(
        sources
    ) >= 2:
        return SnapshotRecord(
            symbol=symbol,
            listing_date=selected_date,
            evidence_status=(
                STATUS_CONFIRMED
            ),
            supporting_sources=sources,
            quality=QUALITY_VALID,
            availability_status="UNKNOWN",
        )

    if (
        len(
            date_votes
        )
        == 1
        and coverage_anchor_match
    ):
        return SnapshotRecord(
            symbol=symbol,
            listing_date=selected_date,
            evidence_status=(
                STATUS_COUNT_ANCHORED
            ),
            supporting_sources=sources,
            quality=QUALITY_WARNING,
            availability_status="UNKNOWN",
        )

    return SnapshotRecord(
        symbol=symbol,
        listing_date=None,
        evidence_status=(
            STATUS_UNRESOLVED
        ),
        supporting_sources=sources,
        quality=QUALITY_REJECTED,
        availability_status="UNKNOWN",
    )


def build_older_year(
    *,
    year: int,
    listing_records: set[
        ListingRecord
    ],
    digital_records: set[
        ListingRecord
    ],
) -> SnapshotYear:
    expected_count = (
        ANNUAL_COUNT_ANCHORS[
            year
        ]
    )

    listing_symbols = set(
        symbol_date_map(
            listing_records
        )
    )

    digital_symbols = set(
        symbol_date_map(
            digital_records
        )
    )

    symbol_union = (
        listing_symbols
        | digital_symbols
    )

    coverage_anchor_match = (
        len(
            symbol_union
        )
        == expected_count
    )

    votes = build_votes(
        listing_records=(
            listing_records
        ),
        digital_records=(
            digital_records
        ),
    )

    records = tuple(
        canonicalize_older_symbol(
            symbol=symbol,
            date_votes=votes[
                symbol
            ],
            coverage_anchor_match=(
                coverage_anchor_match
            ),
        )
        for symbol in sorted(
            votes
        )
    )

    canonical_count = sum(
        record.listing_date
        is not None
        for record in records
    )

    unresolved_count = sum(
        record.evidence_status
        == STATUS_UNRESOLVED
        for record in records
    )

    single_source_count = sum(
        record.evidence_status
        == STATUS_COUNT_ANCHORED
        for record in records
    )

    event_date_ready = (
        coverage_anchor_match
        and canonical_count
        == expected_count
        and unresolved_count == 0
    )

    return SnapshotYear(
        year=year,
        mode=(
            "BOUNDED_COUNT_ANCHORED"
        ),
        expected_count=expected_count,
        listing_activity_count=len(
            listing_symbols
        ),
        digital_statistic_count=len(
            digital_symbols
        ),
        performance_count=0,
        union_count=len(
            symbol_union
        ),
        canonical_count=(
            canonical_count
        ),
        unresolved_count=(
            unresolved_count
        ),
        single_source_count=(
            single_source_count
        ),
        coverage_anchor_match=(
            coverage_anchor_match
        ),
        event_date_ready=(
            event_date_ready
        ),
        strict_pit_ready=False,
        records=records,
    )


def convert_strict_year(
    *,
    year_result,
) -> SnapshotYear:
    records = []

    for record in (
        year_result
        .canonical_records
    ):
        if record.listing_date is None:
            quality = (
                QUALITY_REJECTED
            )

        else:
            quality = (
                QUALITY_VALID
            )

        records.append(
            SnapshotRecord(
                symbol=record.symbol,
                listing_date=(
                    record.listing_date
                ),
                evidence_status=(
                    record.status
                ),
                supporting_sources=(
                    record
                    .supporting_sources
                ),
                quality=quality,
                availability_status=(
                    "UNKNOWN"
                ),
            )
        )

    return SnapshotYear(
        year=year_result.year,
        mode=(
            "STRICT_THREE_SOURCE"
        ),
        expected_count=(
            year_result
            .symbol_union_count
        ),
        listing_activity_count=(
            year_result
            .listing_activity_count
        ),
        digital_statistic_count=(
            year_result
            .digital_statistic_count
        ),
        performance_count=(
            year_result
            .performance_count
        ),
        union_count=(
            year_result
            .symbol_union_count
        ),
        canonical_count=(
            year_result
            .canonical_count
        ),
        unresolved_count=(
            year_result
            .unresolved_count
        ),
        single_source_count=(
            year_result
            .single_source_count
        ),
        coverage_anchor_match=(
            year_result
            .performance_anchor_complete
        ),
        event_date_ready=(
            year_result
            .strict_ready
        ),
        strict_pit_ready=False,
        records=tuple(
            records
        ),
    )


def build_current_year(
    *,
    listing_records: set[
        ListingRecord
    ],
) -> SnapshotYear:
    records = tuple(
        SnapshotRecord(
            symbol=record.symbol,
            listing_date=(
                record.listing_date
            ),
            evidence_status=(
                STATUS_PROVISIONAL
            ),
            supporting_sources=(
                "LISTING_ACTIVITY",
            ),
            quality=QUALITY_WARNING,
            availability_status="UNKNOWN",
        )
        for record in sorted(
            listing_records,
            key=lambda value: (
                value.listing_date,
                value.symbol,
            ),
        )
    )

    return SnapshotYear(
        year=CURRENT_YEAR,
        mode="CURRENT_YEAR_PROVISIONAL",
        expected_count=None,
        listing_activity_count=len(
            listing_records
        ),
        digital_statistic_count=0,
        performance_count=0,
        union_count=len(
            listing_records
        ),
        canonical_count=len(
            records
        ),
        unresolved_count=0,
        single_source_count=len(
            records
        ),
        coverage_anchor_match=None,
        event_date_ready=False,
        strict_pit_ready=False,
        records=records,
    )


def print_year(
    result: SnapshotYear,
) -> None:
    print(
        f"{result.year}"
    )

    print(
        f"  Mode               : "
        f"{result.mode}"
    )

    print(
        f"  Expected count     : "
        f"{result.expected_count}"
    )

    print(
        f"  ListingActivity    : "
        f"{result.listing_activity_count}"
    )

    print(
        f"  DigitalStatistic   : "
        f"{result.digital_statistic_count}"
    )

    print(
        f"  Performance        : "
        f"{result.performance_count}"
    )

    print(
        f"  Symbol union       : "
        f"{result.union_count}"
    )

    print(
        f"  Canonical rows     : "
        f"{result.canonical_count}"
    )

    print(
        f"  Single-source rows : "
        f"{result.single_source_count}"
    )

    print(
        f"  Unresolved         : "
        f"{result.unresolved_count}"
    )

    print(
        f"  Count anchor match : "
        f"{result.coverage_anchor_match}"
    )

    print(
        "  Event-date ready   : "
        + (
            "YES"
            if result.event_date_ready
            else "NO"
        )
    )

    print(
        "  Strict PIT ready   : NO"
    )

    print()


def write_snapshot(
    *,
    snapshot: IpoSnapshot,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = asdict(
        snapshot
    )

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
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
        "IDX Consolidated IPO History "
        "Snapshot V1"
    )

    print(
        "--------------------------------"
    )

    print(
        "Database writes : DISABLED"
    )

    print(
        "Local snapshot  : ENABLED"
    )

    print()

    year_results = []

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        performance = (
            fetch_performance(
                client=client
            )
        )

        if performance.error is not None:
            raise RuntimeError(
                "Performance source failed: "
                + performance.error
            )

        for year in range(
            STRICT_END_YEAR,
            STRICT_START_YEAR - 1,
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
                raise RuntimeError(
                    f"{year} ListingActivity: "
                    f"{listing.error}"
                )

            digital = (
                fetch_digital_year(
                    client=client,
                    year=year,
                    pause=args.pause,
                )
            )

            if digital.error is not None:
                raise RuntimeError(
                    f"{year} DigitalStatistic: "
                    f"{digital.error}"
                )

            strict_result = (
                build_year_result(
                    year=year,
                    listing_records=set(
                        listing.records
                    ),
                    digital_records=set(
                        digital.records
                    ),
                    performance_records=(
                        records_for_year(
                            records=(
                                performance.records
                            ),
                            year=year,
                        )
                    ),
                )
            )

            result = convert_strict_year(
                year_result=(
                    strict_result
                )
            )

            year_results.append(
                result
            )

            print_year(
                result
            )

            if args.pause > 0:
                sleep(
                    args.pause
                )

        for year in range(
            OLDER_END_YEAR,
            OLDER_START_YEAR - 1,
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
                raise RuntimeError(
                    f"{year} ListingActivity: "
                    f"{listing.error}"
                )

            digital = (
                fetch_digital_year(
                    client=client,
                    year=year,
                    pause=args.pause,
                )
            )

            if digital.error is not None:
                raise RuntimeError(
                    f"{year} DigitalStatistic: "
                    f"{digital.error}"
                )

            result = build_older_year(
                year=year,
                listing_records=set(
                    listing.records
                ),
                digital_records=set(
                    digital.records
                ),
            )

            year_results.append(
                result
            )

            print_year(
                result
            )

            if args.pause > 0:
                sleep(
                    args.pause
                )

        current_listing = (
            fetch_listing_activity_year(
                client=client,
                year=CURRENT_YEAR,
                pause=args.pause,
            )
        )

        if current_listing.error is not None:
            raise RuntimeError(
                "Current-year "
                "ListingActivity: "
                + current_listing.error
            )

        current_result = (
            build_current_year(
                listing_records=set(
                    current_listing.records
                )
            )
        )

        year_results.append(
            current_result
        )

        print_year(
            current_result
        )

    ordered_results = tuple(
        sorted(
            year_results,
            key=lambda result: (
                result.year
            ),
            reverse=True,
        )
    )

    total_canonical = sum(
        result.canonical_count
        for result in ordered_results
    )

    total_unresolved = sum(
        result.unresolved_count
        for result in ordered_results
    )

    generated_at = (
        datetime.now(
            UTC
        )
        .isoformat()
    )

    snapshot = IpoSnapshot(
        generated_at=generated_at,
        snapshot_version=(
            "idx_ipo_history_v1"
        ),
        years=ordered_results,
        total_canonical_rows=(
            total_canonical
        ),
        total_unresolved=(
            total_unresolved
        ),
        strict_pit_ready=False,
    )

    output_path = Path(
        args.output
    )

    write_snapshot(
        snapshot=snapshot,
        output_path=output_path,
    )

    print(
        "SUMMARY"
    )

    print(
        f"Years              : "
        f"{len(ordered_results)}"
    )

    print(
        f"Canonical rows     : "
        f"{total_canonical}"
    )

    print(
        f"Unresolved rows    : "
        f"{total_unresolved}"
    )

    print(
        f"Snapshot           : "
        f"{output_path}"
    )

    print()

    print(
        "READINESS:"
    )

    print(
        "IPO event dates 2023-2025 "
        "are strict evidence-ready."
    )

    print(
        "IPO event dates 2020-2022 "
        "are bounded count-anchored."
    )

    print(
        "IPO 2026 remains provisional."
    )

    print(
        "Historical available_at "
        "remains UNKNOWN."
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