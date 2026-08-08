import argparse
from time import perf_counter

from imi.db import engine
from imi.features.sector_rotation import (
    ROTATION_LOOKBACK,
    build_sector_model_version,
    prepare_sector_score_rows,
    resolve_sector_build_mode,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.sector_rotation import (
    get_existing_latest_state,
    get_expected_sector_coverage,
    get_latest_sector_input_state,
    get_latest_snapshot_date,
    load_incremental_sector_inputs,
    load_prior_score_history,
    load_sector_daily_inputs,
    upsert_sector_scores,
)

DEFAULT_BATCH_SIZE = 2000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force a full historical "
            "sector-rotation rebuild."
        ),
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
        latest_input = (
            get_latest_sector_input_state(
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
            get_existing_latest_state(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    latest_input_date = (
        latest_input[
            "latest_input_date"
        ]
    )

    latest_input_sector_count = int(
        latest_input[
            "latest_sector_count"
        ]
    )

    existing_last_date = (
        existing["latest_date"]
    )

    existing_latest_sector_count = int(
        existing[
            "latest_sector_count"
        ]
    )

    mode = resolve_sector_build_mode(
        existing_last_date=(
            existing_last_date
        ),
        existing_latest_sector_count=(
            existing_latest_sector_count
        ),
        latest_input_date=(
            latest_input_date
        ),
        latest_input_sector_count=(
            latest_input_sector_count
        ),
        force=args.force,
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
        f"Latest input    : "
        f"{latest_input_date}"
    )
    print(
        f"Input sectors   : "
        f"{latest_input_sector_count}"
    )
    print(
        f"Existing last   : "
        f"{existing_last_date}"
    )
    print(
        f"Stored sectors  : "
        f"{existing_latest_sector_count}"
    )
    print(
        f"Build mode      : "
        f"{mode}"
    )
    print()

    if mode == "UP_TO_DATE":
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

    if mode == "FULL":
        print(
            "Loading full historical "
            "sector inputs..."
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

        rows = prepare_sector_score_rows(
            inputs=inputs,
            model_version=model_version,
        )

        expected_rows = int(
            expected["expected_rows"]
        )

        if len(rows) != expected_rows:
            raise RuntimeError(
                "Generated sector rows do "
                "not match expected "
                "coverage: "
                f"generated={len(rows)}, "
                f"expected={expected_rows}"
            )

        print(
            f"Expected rows   : "
            f"{expected_rows}"
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

    else:
        if existing_last_date is None:
            raise RuntimeError(
                "Incremental mode requires "
                "an existing sector date."
            )

        print(
            "Loading incremental sector "
            f"inputs after "
            f"{existing_last_date}..."
        )

        with engine.connect() as connection:
            prior_history = (
                load_prior_score_history(
                    connection,
                    model_version=(
                        model_version
                    ),
                    through_date=(
                        existing_last_date
                    ),
                    history_size=(
                        ROTATION_LOOKBACK
                    ),
                )
            )

            inputs = (
                load_incremental_sector_inputs(
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
                    after_date=(
                        existing_last_date
                    ),
                )
            )

        if not inputs:
            raise RuntimeError(
                "Incremental mode found no "
                "new sector inputs."
            )

        rows = prepare_sector_score_rows(
            inputs=inputs,
            model_version=model_version,
            prior_score_history=(
                prior_history
            ),
        )

        generated_last_date = max(
            row["trading_date"]
            for row in rows
        )

        if (
            generated_last_date
            != latest_input_date
        ):
            raise RuntimeError(
                "Incremental sector build "
                "did not reach latest "
                "input date: "
                f"generated="
                f"{generated_last_date}, "
                f"expected="
                f"{latest_input_date}"
            )

        latest_generated_rows = [
            row
            for row in rows
            if row["trading_date"]
            == generated_last_date
        ]

        latest_generated_sectors = {
            row["sector_code"]
            for row in latest_generated_rows
        }

        if (
            len(latest_generated_sectors)
            != latest_input_sector_count
        ):
            raise RuntimeError(
                "Latest incremental sector "
                "population mismatch: "
                f"generated="
                f"{len(latest_generated_sectors)}, "
                f"expected="
                f"{latest_input_sector_count}"
            )

    if not rows:
        raise RuntimeError(
            "No sector rotation rows "
            "were generated."
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
            f"score="
            f"{row['score']:>7.4f} "
            f"RS="
            f"{row['relative_strength_score']:>7.4f} "
            f"breadth="
            f"{row['breadth_score']:>7.4f} "
            f"volume="
            f"{row['volume_score']:>7.4f} "
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