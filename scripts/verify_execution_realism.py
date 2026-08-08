import argparse
import time
from typing import Any

from imi.db import engine
from imi.features.execution_realism import (
    build_execution_realism_model_version,
    prepare_execution_realism_rows,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.execution_realism import (
    get_latest_calibration_model_state,
    load_execution_inputs,
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


def number_equal(
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
        calibration_state = (
            get_latest_calibration_model_state(
                connection
            )
        )

        dataset_version = str(
            calibration_state[
                "dataset_version"
            ]
        )

        universe_date = (
            extract_current_universe_date(
                dataset_version
            )
        )

        model_version = (
            build_execution_realism_model_version(
                universe_date
            )
        )

        yahoo_source_id = (
            get_source_id(
                connection,
                code="YAHOO_FINANCE",
            )
        )

        inputs = (
            load_execution_inputs(
                connection,
                dataset_version=(
                    dataset_version
                ),
                price_source_id=(
                    yahoo_source_id
                ),
            )
        )

        stored = (
            load_stored_rows(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    generated_all = (
        prepare_execution_realism_rows(
            inputs=inputs,
            model_version=(
                model_version
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

    expected_map = {
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
        "raw_entry_price",
        "raw_exit_price",
        "raw_stop_price",
        "entry_reference_price",
        "exit_reference_price",
        "entry_tick_size",
        "exit_tick_size",
        "modeled_entry_price",
        "modeled_exit_price",
        "modeled_stop_price",
        "buy_fee_rate",
        "sell_fee_rate",
        "raw_realized_return",
        "raw_realized_r",
        "gross_modeled_return",
        "gross_modeled_r",
        "net_modeled_return",
        "net_realized_r",
        "slippage_drag_r",
        "fee_drag_r",
        "total_cost_drag_r",
    )

    exact_fields = (
        "model_version",
        "calibration_dataset_version",
        "instrument_id",
        "signal_date",
        "sector_code",
        "sample_status",
        "split_label",
        "outcome_label",
        "entry_slippage_ticks",
        "exit_slippage_ticks",
        "execution_metrics_available",
        "tick_size_modeled",
        "exchange_costs_modeled",
        "slippage_modeled",
        "broker_commission_modeled",
        "auto_rejection_modeled",
        "point_in_time_safe",
        "survivorship_safe",
        "corporate_action_overlap_detected",
        "corporate_action_history_complete",
        "strict_calibration_eligible",
        "blocking_reasons",
        "input_updated_at",
        "evidence",
    )

    mismatches = 0

    for signal_id in selected_ids:
        expected = (
            expected_map.get(
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
            if not number_equal(
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
        "Execution Realism Verification"
    )

    print(
        "-----------------------------"
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
            "Execution realism "
            "verification failed."
        )


if __name__ == "__main__":
    main()