import argparse
import time
from typing import Any

from imi.db import engine
from imi.features.signal_outcome import (
    MAX_FUTURE_BARS,
    build_signal_outcome_model_version,
    prepare_signal_outcome_rows,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.signal_outcome import (
    get_latest_trade_setup_model_state,
    load_all_stored,
    load_signal_outcome_inputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--signals",
        type=int,
        default=50,
    )

    return parser.parse_args()


def same_number(
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
        trade_state = (
            get_latest_trade_setup_model_state(
                connection
            )
        )

        trade_model = str(
            trade_state[
                "model_version"
            ]
        )

        universe_date = (
            extract_current_universe_date(
                trade_model
            )
        )

        model_version = (
            build_signal_outcome_model_version(
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
            load_signal_outcome_inputs(
                connection,
                trade_setup_model_version=(
                    trade_model
                ),
                price_source_id=(
                    yahoo_source_id
                ),
                max_future_bars=(
                    MAX_FUTURE_BARS
                ),
            )
        )

        stored = (
            load_all_stored(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    inputs = sorted(
        inputs,
        key=lambda item: (
            item[
                "trading_date"
            ],
            str(
                item[
                    "signal_id"
                ]
            ),
        ),
        reverse=True,
    )[
        :args.signals
    ]

    selected_ids = {
        row["signal_id"]
        for row in inputs
    }

    stored = [
        row
        for row in stored
        if row[
            "signal_id"
        ]
        in selected_ids
    ]

    generated = (
        prepare_signal_outcome_rows(
            inputs=inputs,
            evaluation_model_version=(
                model_version
            ),
        )
    )

    generated_map = {
        row["signal_id"]:
            row
        for row in generated
    }

    stored_map = {
        row["signal_id"]:
            row
        for row in stored
    }

    mismatches = 0

    numeric_fields = (
        "return_t1",
        "return_t3",
        "return_t5",
        "return_t10",
        "return_t20",
        "mfe",
        "mae",
        "entry_price",
        "exit_price",
        "realized_return",
        "realized_r",
        "mfe_r",
        "mae_r",
    )

    exact_fields = (
        "evaluated_through",
        "target_hit",
        "stop_hit",
        "entry_filled",
        "entry_date",
        "exit_date",
        "outcome_label",
        "bars_to_entry",
        "bars_held",
        "target_hit_date",
        "stop_hit_date",
        "horizon_complete",
        "available_bars",
        "sequence_ambiguous",
        "evaluation_model_version",
        "input_updated_at",
        "evidence",
    )

    for signal_id in (
        selected_ids
    ):
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
            if not same_number(
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
        "Signal Outcome Verification"
    )
    print(
        "---------------------------"
    )

    print(
        f"Requested signals : "
        f"{args.signals}"
    )

    print(
        f"Generated rows    : "
        f"{len(generated)}"
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
        len(generated)
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
            "Signal outcome verification "
            "failed."
        )


if __name__ == "__main__":
    main()