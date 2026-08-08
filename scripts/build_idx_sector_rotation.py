import argparse
from time import perf_counter

from imi.db import engine
from imi.features.sector_rotation import (
    build_sector_model_version,
    prepare_sector_score_rows,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.sector_rotation import (
    get_existing_sector_coverage,
    get_expected_sector_coverage,
    get_latest_snapshot_date,
    load_sector_daily_inputs,
    upsert_sector_scores,
)

DEFAULT_BATCH_SIZE = 2000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Sector Rotation"
    )
    print(
        "-----------------------------"
    )

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        snapshot_date = (
            get_latest_snapshot_date(
                connection
            )
        )

    model_version = (
        build_sector_model_version(
            snapshot_date
        )
    )

    with engine.connect() as connection:
        expected = (
            get_expected_sector_coverage(
                connection,
                snapshot_date=(
                    snapshot_date
                ),
                source_id=(
                    source_id
                ),
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

        existing = (
            get_existing_sector_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    print(
        f"Feature version : "
        f"{FEATURE_VERSION}"
    )
    print(
        f"Snapshot date   : "
        f"{snapshot_date}"
    )
    print(
        f"Model version   : "
        f"{model_version}"
    )
    print(
        f"Expected rows   : "
        f"{expected['expected_rows']}"
    )
    print(
        f"Expected sectors: "
        f"{expected['expected_sectors']}"
    )
    print(
        f"Expected first  : "
        f"{expected['expected_first']}"
    )
    print(
        f"Expected last   : "
        f"{expected['expected_last']}"
    )
    print(
        f"Existing rows   : "
        f"{existing['rows']}"
    )
    print()

    is_up_to_date = (
        int(existing["rows"])
        == int(
            expected["expected_rows"]
        )
        and int(existing["sectors"])
        == int(
            expected[
                "expected_sectors"
            ]
        )
        and existing["first_date"]
        == expected[
            "expected_first"
        ]
        and existing["last_date"]
        == expected[
            "expected_last"
        ]
    )

    if (
        is_up_to_date
        and not args.force
    ):
        elapsed = (
            perf_counter()
            - started
        )

        print(
            "Sector rotation dataset "
            "is already up-to-date."
        )
        print(
            "Rows written    : 0"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )
        return

    print(
        "Loading historical "
        "sector inputs..."
    )

    with engine.connect() as connection:
        inputs = (
            load_sector_daily_inputs(
                connection,
                snapshot_date=(
                    snapshot_date
                ),
                source_id=(
                    source_id
                ),
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

    if not inputs:
        raise RuntimeError(
            "No sector rotation inputs "
            "were generated."
        )

    rows = prepare_sector_score_rows(
        inputs=inputs,
        model_version=model_version,
    )

    if len(rows) != int(
        expected["expected_rows"]
    ):
        raise RuntimeError(
            "Generated sector rows do not "
            "match expected coverage: "
            f"generated={len(rows)}, "
            f"expected="
            f"{expected['expected_rows']}"
        )

    with engine.begin() as connection:
        written = upsert_sector_scores(
            connection,
            rows=rows,
            batch_size=(
                args.batch_size
            ),
        )

    latest_date = max(
        row["trading_date"]
        for row in rows
    )

    latest_rows = [
        row
        for row in rows
        if row["trading_date"]
        == latest_date
    ]

    latest_rows.sort(
        key=lambda row: row["score"],
        reverse=True,
    )

    elapsed = (
        perf_counter()
        - started
    )

    print()
    print(
        f"Generated rows  : "
        f"{len(rows)}"
    )
    print(
        f"Rows written    : "
        f"{written}"
    )
    print(
        f"Latest date     : "
        f"{latest_date}"
    )
    print(
        f"Latest sectors  : "
        f"{len(latest_rows)}"
    )
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    print()
    print(
        "Latest sector ranking:"
    )

    for position, row in enumerate(
        latest_rows,
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['sector_code']:<12} "
            f"score={row['score']:>7.4f} "
            f"RS={row['relative_strength_score']:>7.4f} "
            f"breadth={row['breadth_score']:>7.4f} "
            f"volume={row['volume_score']:>7.4f} "
            f"{row['rotation_label']}"
        )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "flow_score and catalyst_score "
        "remain NULL in Sector Rotation V1."
    )
    print(
        "Historical sector scores use "
        "the current IDX universe snapshot."
    )
    print(
        "Historical results therefore "
        "remain survivorship-biased."
    )


if __name__ == "__main__":
    main()