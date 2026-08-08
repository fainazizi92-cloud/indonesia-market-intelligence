import argparse
import time
from decimal import Decimal
from typing import Any

from imi.db import engine
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.features.trade_setup import (
    build_trade_setup_model_version,
    extract_current_universe_date,
    prepare_trade_setup_rows,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.trade_setup import (
    get_latest_screener_model_state,
    get_recent_screener_dates,
    load_stored_from,
    load_trade_setup_inputs,
)

NUMERIC_FIELDS = (
    "entry_low",
    "entry_high",
    "invalidation_price",
    "stop_price",
    "target_primary",
    "expected_rr",
    "risk_per_share",
    "risk_pct_price",
    "reference_capital",
    "risk_budget_pct",
    "capital_required",
)

EXACT_FIELDS = (
    "status",
    "horizon_days",
    "confidence",
    "thesis",
    "model_version",
    "is_frozen",
    "setup_decision",
    "position_size_shares",
    "position_size_lots",
    "probability_tp_before_sl",
    "expected_value_r",
    "input_updated_at",
    "decision_reasons",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dates",
        type=int,
        default=10,
    )

    return parser.parse_args()


def numeric_equal(
    left: Any,
    right: Any,
    tolerance: float = 0.0001,
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
        <= tolerance
    )


def compare_rows(
    generated: list[
        dict[str, Any]
    ],
    stored: list[
        dict[str, Any]
    ],
) -> int:
    generated_map = {
        (
            row["instrument_id"],
            row["trading_date"],
        ):
        row
        for row in generated
    }

    stored_map = {
        (
            row["instrument_id"],
            row["trading_date"],
        ):
        row
        for row in stored
    }

    keys = (
        set(
            generated_map
        )
        | set(
            stored_map
        )
    )

    mismatches = 0

    for key in keys:
        expected = (
            generated_map.get(
                key
            )
        )

        actual = (
            stored_map.get(
                key
            )
        )

        if (
            expected is None
            or actual is None
        ):
            mismatches += 1
            continue

        different = False

        for field in NUMERIC_FIELDS:
            if not numeric_equal(
                expected[field],
                actual[field],
            ):
                different = True
                break

        if different:
            mismatches += 1
            continue

        for field in EXACT_FIELDS:
            expected_value = (
                expected[field]
            )

            actual_value = (
                actual[field]
            )

            if isinstance(
                actual_value,
                Decimal,
            ):
                actual_value = float(
                    actual_value
                )

            if (
                expected_value
                != actual_value
            ):
                different = True
                break

        if different:
            mismatches += 1

    return mismatches


def main() -> None:
    args = parse_args()

    if args.dates <= 0:
        raise ValueError(
            "--dates must be positive."
        )

    started = time.perf_counter()

    with engine.connect() as connection:
        screener_state = (
            get_latest_screener_model_state(
                connection
            )
        )

        screener_model = str(
            screener_state[
                "model_version"
            ]
        )

        universe_date = (
            extract_current_universe_date(
                screener_model
            )
        )

        model_version = (
            build_trade_setup_model_version(
                universe_date
            )
        )

        yahoo_source_id = (
            get_source_id(
                connection,
                code="YAHOO_FINANCE",
            )
        )

        dates = (
            get_recent_screener_dates(
                connection,
                screener_model_version=(
                    screener_model
                ),
                limit=args.dates,
            )
        )

        if not dates:
            raise RuntimeError(
                "No screener dates available."
            )

        selected_dates = set(
            dates
        )

        start_date = min(
            dates
        )

        inputs = (
            load_trade_setup_inputs(
                connection,
                screener_model_version=(
                    screener_model
                ),
                feature_version=(
                    FEATURE_VERSION
                ),
                price_source_id=(
                    yahoo_source_id
                ),
                start_date=(
                    start_date
                ),
            )
        )

        inputs = [
            row
            for row in inputs
            if row[
                "trading_date"
            ]
            in selected_dates
        ]

        stored = (
            load_stored_from(
                connection,
                model_version=(
                    model_version
                ),
                start_date=(
                    start_date
                ),
            )
        )

        stored = [
            row
            for row in stored
            if row[
                "trading_date"
            ]
            in selected_dates
        ]

    generated = (
        prepare_trade_setup_rows(
            inputs=inputs,
            model_version=(
                model_version
            ),
        )
    )

    mismatches = compare_rows(
        generated,
        stored,
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    print(
        "IDX Trade Setup Incremental "
        "Verification"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Dates           : "
        f"{len(dates)}"
    )

    print(
        f"Generated rows  : "
        f"{len(generated)}"
    )

    print(
        f"Stored rows     : "
        f"{len(stored)}"
    )

    print(
        f"Mismatches      : "
        f"{mismatches}"
    )

    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    passed = (
        len(generated)
        == len(stored)
        and mismatches == 0
    )

    print(
        "Result          : "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    if not passed:
        raise RuntimeError(
            "Incremental trade setup "
            "verification failed."
        )


if __name__ == "__main__":
    main()