import argparse
from time import perf_counter

from imi.db import engine
from imi.features.ownership_trend import (
    OWNERSHIP_TREND_MODEL_VERSION,
)
from imi.features.sector_ownership import (
    build_sector_ownership_model_version,
    prepare_sector_ownership_rows,
    resolve_sector_ownership_build_mode,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.sector_ownership import (
    get_expected_coverage,
    get_expected_sector_count_for_date,
    get_latest_input_state,
    get_latest_universe_snapshot_date,
    get_stored_latest_state,
    load_latest_ranking,
    load_sector_inputs,
    upsert_sector_ownership_rows,
)

DEFAULT_BATCH_SIZE = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build historical or "
            "incremental KSEI sector "
            "ownership signals."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force a full historical "
            "rebuild."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def print_ranking(
    *,
    source_id,
    model_version: str,
    as_of_date,
) -> None:
    with engine.connect() as connection:
        rows = load_latest_ranking(
            connection,
            source_id=source_id,
            model_version=model_version,
            as_of_date=as_of_date,
        )

    if not rows:
        return

    print()
    print(
        "Latest sector ownership ranking:"
    )

    for position, row in enumerate(
        rows,
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['sector_code']:<12} "
            f"score="
            f"{float(row['score']):>7.2f} "
            f"breadth="
            f"{float(row['breadth_score']):>7.2f} "
            f"intensity="
            f"{float(row['intensity_score']):>7.2f} "
            f"coverage="
            f"{float(row['coverage_pct']):>6.2f}% "
            f"A/S/D="
            f"{row['accumulating_count']}/"
            f"{row['stable_count']}/"
            f"{row['distributing_count']} "
            f"{row['signal_label']}"
        )


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        snapshot_date = (
            get_latest_universe_snapshot_date(
                connection
            )
        )

    model_version = (
        build_sector_ownership_model_version(
            snapshot_date
        )
    )

    with engine.connect() as connection:
        latest_input = (
            get_latest_input_state(
                connection,
                source_id=source_id,
                input_model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
            )
        )

        stored = (
            get_stored_latest_state(
                connection,
                source_id=source_id,
                model_version=model_version,
            )
        )

    latest_input_date = (
        latest_input[
            "latest_input_date"
        ]
    )

    existing_last_date = (
        stored["latest_date"]
    )

    existing_latest_sector_count = int(
        stored[
            "latest_sector_count"
        ]
    )

    if existing_last_date is None:
        existing_expected_sector_count = 0

    else:
        with engine.connect() as connection:
            existing_expected_sector_count = (
                get_expected_sector_count_for_date(
                    connection,
                    source_id=source_id,
                    input_model_version=(
                        OWNERSHIP_TREND_MODEL_VERSION
                    ),
                    as_of_date=(
                        existing_last_date
                    ),
                )
            )

    mode = (
        resolve_sector_ownership_build_mode(
            existing_last_date=(
                existing_last_date
            ),
            existing_latest_sector_count=(
                existing_latest_sector_count
            ),
            existing_expected_sector_count=(
                existing_expected_sector_count
            ),
            latest_input_date=(
                latest_input_date
            ),
            force=args.force,
        )
    )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "KSEI Sector Ownership Engine"
    )
    print(
        "----------------------------"
    )
    print(
        "Source          : "
        "KSEI_OFFICIAL"
    )
    print(
        f"Input model     : "
        f"{OWNERSHIP_TREND_MODEL_VERSION}"
    )
    print(
        f"Universe        : "
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
        f"Input rows      : "
        f"{latest_input['latest_input_rows']}"
    )
    print(
        f"Input sectors   : "
        f"{latest_input['latest_sector_count']}"
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
        f"Expected stored : "
        f"{existing_expected_sector_count}"
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
            "Sector ownership dataset "
            "is already up-to-date."
        )
        print(
            "Rows written    : 0"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )

        print_ranking(
            source_id=source_id,
            model_version=model_version,
            as_of_date=latest_input_date,
        )

        return

    after_date = None

    if mode == "INCREMENTAL":
        if existing_last_date is None:
            raise RuntimeError(
                "Incremental mode requires "
                "existing sector ownership "
                "data."
            )

        after_date = (
            existing_last_date
        )

    with engine.connect() as connection:
        expected = (
            get_expected_coverage(
                connection,
                source_id=source_id,
                input_model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
                after_date=after_date,
            )
        )

        inputs = (
            load_sector_inputs(
                connection,
                source_id=source_id,
                input_model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
                after_date=after_date,
            )
        )

    rows = (
        prepare_sector_ownership_rows(
            inputs=inputs,
            source_id=source_id,
            input_model_version=(
                OWNERSHIP_TREND_MODEL_VERSION
            ),
            model_version=model_version,
        )
    )

    expected_rows = int(
        expected["expected_rows"]
    )

    if len(rows) != expected_rows:
        raise RuntimeError(
            "Generated sector ownership "
            "rows do not match expected "
            "coverage: "
            f"generated={len(rows)}, "
            f"expected={expected_rows}."
        )

    if not rows:
        raise RuntimeError(
            "No sector ownership rows "
            "were generated."
        )

    generated_last_date = max(
        row["as_of_date"]
        for row in rows
    )

    if (
        generated_last_date
        != latest_input_date
    ):
        raise RuntimeError(
            "Sector ownership build did "
            "not reach latest input date: "
            f"generated="
            f"{generated_last_date}, "
            f"expected="
            f"{latest_input_date}."
        )

    with engine.begin() as connection:
        written = (
            upsert_sector_ownership_rows(
                connection,
                rows=rows,
                batch_size=args.batch_size,
            )
        )

    elapsed = (
        perf_counter()
        - started
    )

    print(
        f"Expected rows   : "
        f"{expected_rows}"
    )
    print(
        f"Generated rows  : "
        f"{len(rows)}"
    )
    print(
        f"Rows written    : "
        f"{written}"
    )
    print(
        f"Expected sectors: "
        f"{expected['expected_sectors']}"
    )
    print(
        f"Expected dates  : "
        f"{expected['expected_dates']}"
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
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    print_ranking(
        source_id=source_id,
        model_version=model_version,
        as_of_date=latest_input_date,
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Sector ownership measures "
        "KSEI ownership changes, "
        "not daily foreign trading flow."
    )
    print(
        "Corporate-action and snapshot-"
        "gap rows are excluded from "
        "clean breadth/intensity."
    )
    print(
        "Per-stock intensity contribution "
        "is clipped at +/-0.50 pp to "
        "reduce extreme-stock distortion."
    )
    print(
        "Historical results remain "
        "current-universe biased."
    )


if __name__ == "__main__":
    main()