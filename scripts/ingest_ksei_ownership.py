import argparse
from pathlib import Path
from time import perf_counter

from imi.db import engine
from imi.ksei_holding import (
    build_holder_details,
    parse_ksei_holding_archive,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.ownership import (
    get_idx_equity_map,
    get_ownership_coverage,
    upsert_ownership_rows,
)


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
            "KSEI ZIP file or directory "
            "containing KSEI ZIP files."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
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
        if path.suffix.lower() != ".zip":
            raise ValueError(
                "Input file must be ZIP."
            )

        return [path]

    archives = sorted(
        item
        for item in path.glob(
            "BalanceposEfek*.zip"
        )
        if item.is_file()
    )

    if not archives:
        raise RuntimeError(
            "No BalanceposEfek*.zip "
            "archives found."
        )

    return archives


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
    print()

    total_parsed = 0
    total_rejected = 0
    total_mapped = 0
    total_unmapped = 0
    total_written = 0

    unmapped_codes: set[str] = set()

    for archive_path in archives:
        print(
            f"Processing: "
            f"{archive_path.name}"
        )

        (
            records,
            rejected,
            member_name,
        ) = parse_ksei_holding_archive(
            archive_path,
            equity_only=True,
        )

        total_parsed += len(
            records
        )

        total_rejected += len(
            rejected
        )

        rows = []

        snapshot_dates = {
            record.as_of_date
            for record in records
        }

        if len(snapshot_dates) != 1:
            raise RuntimeError(
                f"{archive_path.name}: "
                "expected exactly one "
                "snapshot date."
            )

        snapshot_date = next(
            iter(snapshot_dates)
        )

        for record in records:
            instrument_id = (
                instrument_map.get(
                    record.code
                )
            )

            if instrument_id is None:
                total_unmapped += 1

                unmapped_codes.add(
                    record.code
                )

                continue

            total_mapped += 1

            rows.append(
                {
                    "instrument_id":
                        instrument_id,
                    "as_of_date":
                        record.as_of_date,

                    # Do not infer these
                    # from KSEI holdings.
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

        total_written += written

        print(
            f"  Snapshot      : "
            f"{snapshot_date}"
        )
        print(
            f"  Valid EQUITY  : "
            f"{len(records)}"
        )
        print(
            f"  Rejected      : "
            f"{len(rejected)}"
        )
        print(
            f"  Mapped        : "
            f"{len(rows)}"
        )
        print(
            f"  Written       : "
            f"{written}"
        )

        if rejected:
            print(
                "  Rejected sample:"
            )

            for item in rejected[:5]:
                print(
                    f"    {item}"
                )

        print()

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

    print(
        "Summary:"
    )
    print(
        f"Parsed valid    : "
        f"{total_parsed}"
    )
    print(
        f"Rejected        : "
        f"{total_rejected}"
    )
    print(
        f"Mapped          : "
        f"{total_mapped}"
    )
    print(
        f"Unmapped        : "
        f"{total_unmapped}"
    )
    print(
        f"Rows written    : "
        f"{total_written}"
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

    print()
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    if unmapped_codes:
        print()
        print(
            "Unmapped KSEI codes "
            f"({len(unmapped_codes)}):"
        )

        sample = sorted(
            unmapped_codes
        )[:50]

        print(
            ", ".join(sample)
        )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "KSEI ownership snapshots "
        "are not daily foreign "
        "buy/sell flow."
    )
    print(
        "free_float_pct, hsc_flag, "
        "and concentration_score "
        "remain NULL."
    )


if __name__ == "__main__":
    main()