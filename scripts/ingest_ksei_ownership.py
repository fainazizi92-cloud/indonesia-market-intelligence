import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

from imi.db import engine
from imi.ksei_holding import (
    build_holder_details,
    extract_archive_snapshot_date,
    parse_ksei_holding_archive,
    validate_archive_identity,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.ownership import (
    get_idx_equity_map,
    get_ownership_coverage,
    upsert_ownership_rows,
)

DEFAULT_BATCH_SIZE = 1000


@dataclass(frozen=True)
class PreparedArchive:
    path: Path
    member_name: str
    snapshot_date: date
    valid_equities: int
    rows: list[dict[str, Any]]
    unmapped_codes: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest official KSEI "
            "local-foreign holding "
            "composition archives."
        )
    )

    parser.add_argument(
        "path",
        type=Path,
        help=(
            "KSEI ZIP archive or "
            "directory containing "
            "KSEI archives."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=(
            "Database upsert batch size."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Parse and validate all "
            "archives without writing "
            "to PostgreSQL."
        ),
    )

    return parser.parse_args()


def resolve_archives(
    path: Path,
) -> list[Path]:
    path = path.resolve()

    if not path.exists():
        raise FileNotFoundError(
            path
        )

    if path.is_file():
        if (
            path.suffix.lower()
            != ".zip"
        ):
            raise ValueError(
                "Input file must be ZIP."
            )

        extract_archive_snapshot_date(
            path
        )

        return [path]

    archives = [
        item
        for item in path.glob(
            "BalanceposEfek*.zip"
        )
        if item.is_file()
    ]

    if not archives:
        raise RuntimeError(
            "No BalanceposEfek*.zip "
            "archives found."
        )

    for archive in archives:
        extract_archive_snapshot_date(
            archive
        )

    return sorted(
        archives,
        key=extract_archive_snapshot_date,
    )


def find_duplicate_codes(
    codes: list[str],
) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for code in codes:
        if code in seen:
            duplicates.add(
                code
            )
        else:
            seen.add(
                code
            )

    return sorted(
        duplicates
    )


def prepare_archive(
    *,
    archive_path: Path,
    instrument_map: dict[str, UUID],
    source_id: UUID,
) -> PreparedArchive:
    (
        records,
        rejected,
        member_name,
    ) = parse_ksei_holding_archive(
        archive_path,
        equity_only=True,
    )

    if rejected:
        raise RuntimeError(
            f"{archive_path.name}: "
            f"{len(rejected)} rejected "
            "EQUITY records. "
            f"Sample: {rejected[:5]}"
        )

    snapshot_date = (
        validate_archive_identity(
            archive_path=archive_path,
            member_name=member_name,
            records=records,
        )
    )

    codes = [
        record.code
        for record in records
    ]

    duplicate_codes = (
        find_duplicate_codes(
            codes
        )
    )

    if duplicate_codes:
        raise RuntimeError(
            f"{archive_path.name}: "
            "duplicate EQUITY codes "
            "found: "
            f"{duplicate_codes[:20]}"
        )

    rows: list[
        dict[str, Any]
    ] = []

    unmapped_codes: list[str] = []

    for record in records:
        instrument_id = (
            instrument_map.get(
                record.code
            )
        )

        if instrument_id is None:
            unmapped_codes.append(
                record.code
            )
            continue

        rows.append(
            {
                "instrument_id":
                    instrument_id,
                "as_of_date":
                    record.as_of_date,

                # These fields are NOT
                # inferred from the KSEI
                # holding-composition file.
                "free_float_pct":
                    None,
                "hsc_flag":
                    None,
                "concentration_score":
                    None,

                "foreign_ownership_pct":
                    round(
                        record
                        .foreign_ownership_pct,
                        8,
                    ),

                "holder_details":
                    build_holder_details(
                        record,
                        archive_name=(
                            archive_path.name
                        ),
                        member_name=(
                            member_name
                        ),
                    ),

                "source_id":
                    source_id,
            }
        )

    if not rows:
        raise RuntimeError(
            f"{archive_path.name}: "
            "no records mapped to "
            "the IDX instrument master."
        )

    return PreparedArchive(
        path=archive_path,
        member_name=member_name,
        snapshot_date=snapshot_date,
        valid_equities=len(
            records
        ),
        rows=rows,
        unmapped_codes=tuple(
            sorted(
                unmapped_codes
            )
        ),
    )


def validate_unique_snapshot_dates(
    prepared: list[PreparedArchive],
) -> None:
    seen: dict[
        date,
        str,
    ] = {}

    for item in prepared:
        previous = seen.get(
            item.snapshot_date
        )

        if previous is not None:
            raise RuntimeError(
                "Duplicate KSEI snapshot "
                f"date {item.snapshot_date}: "
                f"{previous} and "
                f"{item.path.name}"
            )

        seen[
            item.snapshot_date
        ] = item.path.name


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

    archives = resolve_archives(
        args.path
    )

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        instrument_map = (
            get_idx_equity_map(
                connection
            )
        )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "KSEI Ownership Ingestion"
    )
    print(
        "-------------------------"
    )
    print(
        f"Archives        : "
        f"{len(archives)}"
    )
    print(
        f"IDX instruments : "
        f"{len(instrument_map)}"
    )
    print(
        f"Dry run         : "
        f"{args.dry_run}"
    )
    print()

    print(
        "Preflight validation..."
    )

    prepared: list[
        PreparedArchive
    ] = []

    for archive_path in archives:
        item = prepare_archive(
            archive_path=archive_path,
            instrument_map=instrument_map,
            source_id=source_id,
        )

        prepared.append(
            item
        )

        print(
            f"  {item.snapshot_date} | "
            f"{item.path.name} | "
            f"valid="
            f"{item.valid_equities} | "
            f"mapped="
            f"{len(item.rows)} | "
            f"unmapped="
            f"{len(item.unmapped_codes)}"
        )

    validate_unique_snapshot_dates(
        prepared
    )

    print()
    print(
        "Preflight result : PASS"
    )

    total_rows = sum(
        len(item.rows)
        for item in prepared
    )

    all_unmapped = {
        code
        for item in prepared
        for code in item.unmapped_codes
    }

    if args.dry_run:
        elapsed = (
            perf_counter()
            - started
        )

        print()
        print(
            "DRY RUN - database was "
            "not modified."
        )
        print(
            f"Rows ready      : "
            f"{total_rows}"
        )
        print(
            f"Unique unmapped : "
            f"{len(all_unmapped)}"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )

        if all_unmapped:
            print()
            print(
                "Historical/current-universe "
                "unmapped codes:"
            )
            print(
                ", ".join(
                    sorted(
                        all_unmapped
                    )
                )
            )

        return

    rows = [
        row
        for item in prepared
        for row in item.rows
    ]

    print()
    print(
        "Writing ownership snapshots "
        "in one transaction..."
    )

    with engine.begin() as connection:
        written = (
            upsert_ownership_rows(
                connection,
                rows=rows,
                batch_size=(
                    args.batch_size
                ),
            )
        )

    with engine.connect() as connection:
        coverage = (
            get_ownership_coverage(
                connection,
                source_id=(
                    source_id
                ),
            )
        )

    elapsed = (
        perf_counter()
        - started
    )

    print()
    print(
        "Summary:"
    )
    print(
        f"Archives        : "
        f"{len(prepared)}"
    )
    print(
        f"Rows upserted   : "
        f"{written}"
    )
    print(
        f"Unique unmapped : "
        f"{len(all_unmapped)}"
    )

    print()
    print(
        "Database coverage:"
    )
    print(
        f"Rows            : "
        f"{coverage['rows']}"
    )
    print(
        f"Instruments     : "
        f"{coverage['instruments']}"
    )
    print(
        f"Snapshot dates  : "
        f"{coverage['snapshot_dates']}"
    )
    print(
        f"First date      : "
        f"{coverage['first_date']}"
    )
    print(
        f"Last date       : "
        f"{coverage['last_date']}"
    )
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    if all_unmapped:
        print()
        print(
            "Historical/current-universe "
            "unmapped codes:"
        )
        print(
            ", ".join(
                sorted(
                    all_unmapped
                )
            )
        )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Ownership snapshots are not "
        "daily foreign trading flow."
    )
    print(
        "Historical mapping currently "
        "uses the current IDX instrument "
        "master and is therefore "
        "survivorship-biased."
    )
    print(
        "free_float_pct, hsc_flag, "
        "and concentration_score "
        "remain NULL."
    )


if __name__ == "__main__":
    main()