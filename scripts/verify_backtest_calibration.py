import argparse
import time
from typing import Any

from imi.db import engine
from imi.features.backtest_calibration import (
    build_backtest_calibration_version,
    prepare_backtest_calibration_rows,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.backtest_calibration import (
    get_latest_outcome_model_state,
    load_backtest_inputs,
    load_stored_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--signals",
        type=int,
        default=50,
    )

    return parser.parse_args()


def numeric_equal(
    left: Any,
    right: Any,
) -> bool:
    if (
        left is None
        and right is None
    ):
        return True

    if (
        left is None
        or right is None
    ):
        return False

    return (
        abs(
            float(left)
            - float(right)
        )
        <= 0.0001
    )


def main() -> None:
    args = parse_args()

    if args.signals <= 0:
        raise ValueError(
            "--signals must be positive."
        )

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
            load_stored_rows(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

    generated_all = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version=(
                dataset_version
            ),
        )
    )

    generated_all = sorted(
        generated_all,
        key=lambda row: (
            row[
                "signal_date"
            ],
            str(
                row[
                    "signal_id"
                ]
            ),
        ),
        reverse=True,
    )

    selected = generated_all[
        :args.signals
    ]

    selected_ids = {
        row["signal_id"]
        for row in selected
    }

    stored = [
        row
        for row in stored
        if row[
            "signal_id"
        ]
        in selected_ids
    ]

    generated_map = {
        row["signal_id"]:
            row
        for row in selected
    }

    stored_map = {
        row["signal_id"]:
            row
        for row in stored
    }

    numeric_fields = (
        "realized_return",
        "realized_r",
        "mfe_r",
        "mae_r",
        "setup_expected_rr",
        "setup_risk_pct",
        "overall_score",
        "market_score",
        "sector_score",
        "technical_score",
        "liquidity_score",
        "ownership_score",
        "risk_score",
        "data_completeness",
    )

    exact_fields = (
        "dataset_version",
        "outcome_model_version",
        "instrument_id",
        "signal_date",
        "sector_code",
        "sample_status",
        "split_label",
        "calibration_eligible",
        "outcome_label",
        "entry_filled",
        "horizon_complete",
        "entry_date",
        "exit_date",
        "target_hit",
        "stop_hit",
        "tp_before_sl_label",
        "positive_r_label",
        "horizon_days",
        "score_bucket",
        "input_updated_at",
        "evidence",
    )

    mismatches = 0

    for signal_id in selected_ids:
        expected = (
            generated_map.get(
                signal_id
            )
        )

        actual = (
            stored_map.get(
                signal_id
            )
        )

        if (
            expected is None
            or actual is None
        ):
            mismatches += 1
            continue

        failed = False

        for field in numeric_fields:
            if not numeric_equal(
                expected[field],
                actual[field],
            ):
                mismatches += 1
                failed = True
                break

        if failed:
            continue

        for field in exact_fields:
            if (
                expected[field]
                != actual[field]
            ):
                mismatches += 1
                break

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        "Backtest Calibration Verification"
    )

    print(
        "---------------------------------"
    )

    print(
        f"Requested signals : "
        f"{args.signals}"
    )

    print(
        f"Generated rows    : "
        f"{len(selected)}"
    )

    print(
        f"Stored rows       : "
        f"{len(stored)}"
    )

    print(
        f"Mismatches        : "
        f"{mismatches}"
    )

    print(
        f"Elapsed seconds   : "
        f"{elapsed:.3f}"
    )

    passed = (
        len(selected)
        == len(stored)
        and mismatches == 0
    )

    print(
        "Result            : "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    if not passed:
        raise RuntimeError(
            "Backtest calibration "
            "verification failed."
        )


if __name__ == "__main__":
    main()