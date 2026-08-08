import argparse
import time
from typing import Any

from imi.db import engine
from imi.features.backtest_calibration import (
    build_backtest_calibration_version,
    compute_backtest_summary,
    prepare_backtest_calibration_rows,
    resolve_backtest_build_mode,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.backtest_calibration import (
    delete_dataset_rows,
    get_build_state,
    get_latest_outcome_model_state,
    get_outcome_distribution,
    get_sector_summary,
    get_stored_coverage,
    load_backtest_inputs,
    upsert_backtest_rows,
    upsert_build_state,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
    )

    return parser.parse_args()


def max_input_timestamp(
    rows: list[dict[str, Any]],
) -> Any:
    values = [
        row[
            "input_updated_at"
        ]
        for row in rows
        if row[
            "input_updated_at"
        ]
        is not None
    ]

    if not values:
        return None

    return max(
        values
    )


def pct(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return (
        f"{value * 100:.2f}%"
    )


def number(
    value: float | None,
    suffix: str = "",
) -> str:
    if value is None:
        return "-"

    return (
        f"{value:.4f}{suffix}"
    )


def load_backtest_inputs_for_summary(
    connection,
    *,
    dataset_version: str,
):
    from imi.repositories.backtest_calibration import (
        load_stored_rows,
    )

    return load_stored_rows(
        connection,
        dataset_version=(
            dataset_version
        ),
    )


def print_summary_from_rows(
    *,
    rows: list[dict[str, Any]],
    dataset_version: str,
) -> None:
    summary = compute_backtest_summary(
        rows
    )

    with engine.connect() as connection:
        distribution = (
            get_outcome_distribution(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

        sectors = (
            get_sector_summary(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

    print()
    print(
        "Sample classification:"
    )

    print(
        f"Mature trades      : "
        f"{summary.mature_trades}"
    )

    print(
        f"Unfilled complete  : "
        f"{summary.unfilled_complete}"
    )

    print(
        f"Unresolved         : "
        f"{summary.unresolved}"
    )

    print()
    print(
        "Chronological split:"
    )

    print(
        f"TRAIN              : "
        f"{summary.train_trades}"
    )

    print(
        f"VALIDATION         : "
        f"{summary.validation_trades}"
    )

    print(
        f"TEST               : "
        f"{summary.test_trades}"
    )

    print()
    print(
        "Backtest analytics:"
    )

    print(
        f"Entry decided      : "
        f"{summary.entry_decided}"
    )

    print(
        f"Filled signals     : "
        f"{summary.filled_signals}"
    )

    print(
        f"Fill rate          : "
        f"{pct(summary.fill_rate)}"
    )

    print(
        f"Target trades      : "
        f"{summary.target_trades}"
    )

    print(
        f"Stop trades        : "
        f"{summary.stop_trades}"
    )

    print(
        f"Expired trades     : "
        f"{summary.expired_trades}"
    )

    print(
        f"Target rate        : "
        f"{pct(summary.target_rate)}"
    )

    print(
        f"Win rate           : "
        f"{pct(summary.win_rate)}"
    )

    print(
        f"Average R          : "
        f"{number(summary.average_r, 'R')}"
    )

    print(
        f"Median R           : "
        f"{number(summary.median_r, 'R')}"
    )

    print(
        f"Average MFE        : "
        f"{number(summary.average_mfe_r, 'R')}"
    )

    print(
        f"Average MAE        : "
        f"{number(summary.average_mae_r, 'R')}"
    )

    print(
        f"Profit factor      : "
        f"{number(summary.profit_factor)}"
    )

    print()
    print(
        "Outcome distribution:"
    )

    for row in distribution:
        print(
            f"{row['outcome_label']!s:<10} "
            f"{int(row['rows'])}"
        )

    print()
    print(
        "Sector mature-trade summary:"
    )

    for row in sectors:
        avg_r = (
            "-"
            if row["avg_r"] is None
            else (
                f"{float(row['avg_r']):.4f}R"
            )
        )

        target_rate = (
            "-"
            if row["target_rate"] is None
            else (
                f"{float(row['target_rate']) * 100:.2f}%"
            )
        )

        print(
            f"{row['sector_code']!s:<12} "
            f"n="
            f"{int(row['mature_trades']):>3} "
            f"avgR={avg_r:>9} "
            f"target={target_rate}"
        )

    print()
    print(
        "Calibration readiness:"
    )

    print(
        "READY : "
        + (
            "YES"
            if summary.calibration_ready
            else "NO"
        )
    )

    if summary.readiness_reasons:
        for reason in (
            summary.readiness_reasons
        ):
            print(
                f"- {reason}"
            )


def main() -> None:
    args = parse_args()

    started = time.perf_counter()

    with engine.connect() as connection:
        outcome_state = (
            get_latest_outcome_model_state(
                connection
            )
        )

        outcome_model = str(
            outcome_state[
                "model_version"
            ]
        )

        universe_date = (
            extract_current_universe_date(
                outcome_model
            )
        )

        dataset_version = (
            build_backtest_calibration_version(
                universe_date
            )
        )

        inputs = load_backtest_inputs(
            connection,
            outcome_model_version=(
                outcome_model
            ),
        )

        stored = (
            get_stored_coverage(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

        build_state = (
            get_build_state(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

    expected_rows = len(
        inputs
    )

    stored_rows = int(
        stored["rows"]
        or 0
    )

    latest_input_date = (
        outcome_state[
            "latest_input_date"
        ]
    )

    if latest_input_date is None:
        raise RuntimeError(
            "Outcome model has no "
            "evaluated input date."
        )

    current_timestamp = (
        max_input_timestamp(
            inputs
        )
    )

    if build_state is None:
        state_exists = False
        input_model_matches = False
        processed_through = None
        stored_timestamp = None

    else:
        state_exists = True

        input_model_matches = (
            build_state[
                "input_model_version"
            ]
            == outcome_model
        )

        processed_through = (
            build_state[
                "processed_through"
            ]
        )

        stored_timestamp = (
            build_state[
                "processed_input_updated_at"
            ]
        )

    build_mode = (
        resolve_backtest_build_mode(
            force=args.force,
            state_exists=(
                state_exists
            ),
            input_model_matches=(
                input_model_matches
            ),
            stored_rows=(
                stored_rows
            ),
            expected_rows=(
                expected_rows
            ),
            processed_through=(
                processed_through
            ),
            latest_input_date=(
                latest_input_date
            ),
            stored_input_updated_at=(
                stored_timestamp
            ),
            current_input_updated_at=(
                current_timestamp
            ),
        )
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Backtest Analytics & "
        "Calibration Dataset V1"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Dataset version   : "
        f"{dataset_version}"
    )

    print(
        f"Outcome model     : "
        f"{outcome_model}"
    )

    print(
        f"Universe          : "
        f"{universe_date}"
    )

    print(
        f"Latest input      : "
        f"{latest_input_date}"
    )

    print(
        f"Expected rows     : "
        f"{expected_rows}"
    )

    print(
        f"Stored rows       : "
        f"{stored_rows}"
    )

    print(
        f"Build mode        : "
        f"{build_mode}"
    )

    if (
        build_mode
        == "UP_TO_DATE"
    ):
        with engine.connect() as connection:
            from imi.repositories.backtest_calibration import (
                load_stored_rows,
            )

            stored_dataset = (
                load_stored_rows(
                    connection,
                    dataset_version=(
                        dataset_version
                    ),
                )
            )

        elapsed = (
            time.perf_counter()
            - started
        )

        print()
        print(
            "Calibration dataset is "
            "already up-to-date."
        )

        print(
            "Rows written      : 0"
        )

        print(
            f"Elapsed seconds   : "
            f"{elapsed:.3f}"
        )

        print_summary_from_rows(
            rows=stored_dataset,
            dataset_version=(
                dataset_version
            ),
        )

        return

    generated = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version=(
                dataset_version
            ),
        )
    )

    if (
        len(generated)
        != expected_rows
    ):
        raise RuntimeError(
            "Generated calibration rows "
            "do not match input count."
        )

    with engine.begin() as connection:
        rows_deleted = (
            delete_dataset_rows(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

        rows_written = (
            upsert_backtest_rows(
                connection,
                rows=generated,
                batch_size=(
                    args.batch_size
                ),
            )
        )

        final_coverage = (
            get_stored_coverage(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

        final_rows = int(
            final_coverage[
                "rows"
            ]
            or 0
        )

        if final_rows != expected_rows:
            raise RuntimeError(
                "Stored calibration rows "
                "do not match expected "
                "coverage."
            )

        upsert_build_state(
            connection,
            dataset_version=(
                dataset_version
            ),
            input_model_version=(
                outcome_model
            ),
            processed_through=(
                latest_input_date
            ),
            processed_input_updated_at=(
                current_timestamp
            ),
            output_rows=(
                final_rows
            ),
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print(
        f"Generated rows    : "
        f"{len(generated)}"
    )

    print(
        f"Rows deleted      : "
        f"{rows_deleted}"
    )

    print(
        f"Rows written      : "
        f"{rows_written}"
    )

    print(
        f"Stored total      : "
        f"{expected_rows}"
    )

    print(
        f"Elapsed seconds   : "
        f"{elapsed:.3f}"
    )

    print_summary_from_rows(
        rows=generated,
        dataset_version=(
            dataset_version
        ),
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "tp_before_sl_label is an "
        "observed historical label, "
        "not a predicted probability."
    )

    print(
        "Calibration remains disabled "
        "until sample-size and data-"
        "quality readiness gates pass."
    )

    print(
        "No probability_tp_before_sl "
        "or expected_value_r is written "
        "back to signals in Phase 3K."
    )


if __name__ == "__main__":
    main()