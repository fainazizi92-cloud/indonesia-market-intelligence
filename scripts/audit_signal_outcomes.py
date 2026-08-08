from decimal import Decimal
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
    get_build_state,
    get_latest_price_state,
    get_latest_trade_setup_model_state,
    get_quality_counts,
    get_stored_coverage,
    load_all_stored,
    load_signal_outcome_inputs,
)

NUMERIC_FIELDS = (
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

EXACT_FIELDS = (
    "evaluated_through",
    "target_hit",
    "stop_hit",
    "target_hit_at",
    "stop_hit_at",
    "time_to_target_hours",
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
    generated: list[dict[str, Any]],
    stored: list[dict[str, Any]],
) -> tuple[int, list[str]]:
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
    details = []

    for signal_id in (
        set(generated_map)
        | set(stored_map)
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
            details.append(
                f"{signal_id}: missing row"
            )
            continue

        failed = False

        for field in NUMERIC_FIELDS:
            if not numeric_equal(
                expected[field],
                actual[field],
            ):
                mismatches += 1
                details.append(
                    
                        f"{signal_id} "
                        f"{field}: "
                        f"{expected[field]} != "
                        f"{actual[field]}"
                    
                )
                failed = True
                break

        if failed:
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
                mismatches += 1
                details.append(
                    
                        f"{signal_id} "
                        f"{field}: mismatch"
                    
                )
                break

    return (
        mismatches,
        details,
    )


def main() -> None:
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

        price_state = (
            get_latest_price_state(
                connection,
                price_source_id=(
                    yahoo_source_id
                ),
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

        coverage = (
            get_stored_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        quality = (
            get_quality_counts(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        build_state = (
            get_build_state(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    generated = (
        prepare_signal_outcome_rows(
            inputs=inputs,
            evaluation_model_version=(
                model_version
            ),
        )
    )

    (
        mismatches,
        mismatch_details,
    ) = compare_rows(
        generated,
        stored,
    )

    expected_rows = len(
        inputs
    )

    stored_rows = int(
        coverage["rows"]
        or 0
    )

    coverage_pass = (
        stored_rows
        == expected_rows
        == len(generated)
    )

    quality_pass = (
        mismatches == 0
        and int(
            quality[
                "invalid_label"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_filled"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_unfilled"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_target"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_stop"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_incomplete"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "fabricated_intraday_time"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_available_bars"
            ]
            or 0
        )
        == 0
    )

    latest_price_date = (
        price_state[
            "latest_price_date"
        ]
    )

    latest_pass = (
        build_state is not None
        and build_state[
            "input_model_version"
        ]
        == trade_model
        and build_state[
            "processed_through"
        ]
        == latest_price_date
        and int(
            build_state[
                "output_rows"
            ]
            or 0
        )
        == expected_rows
    )

    print(
        "Historical Signal Outcome Audit"
    )
    print(
        "-------------------------------"
    )

    print(
        f"Trade setup model : "
        f"{trade_model}"
    )

    print(
        f"Outcome model     : "
        f"{model_version}"
    )

    print(
        f"Latest price      : "
        f"{latest_price_date}"
    )

    print()
    print(
        "Coverage:"
    )

    print(
        f"Accepted signals  : "
        f"{expected_rows}"
    )

    print(
        f"Generated rows    : "
        f"{len(generated)}"
    )

    print(
        f"Stored rows       : "
        f"{stored_rows}"
    )

    print(
        f"Complete rows     : "
        f"{coverage['complete_rows']}"
    )

    print(
        f"Incomplete rows   : "
        f"{coverage['incomplete_rows']}"
    )

    print()
    print(
        "Quality:"
    )

    print(
        f"Mismatches              : "
        f"{mismatches}"
    )

    for key, value in quality.items():
        print(
            f"{key:<24}: {value}"
        )

    if mismatch_details:
        print()
        print(
            "First mismatches:"
        )

        for detail in (
            mismatch_details[:20]
        ):
            print(
                detail
            )

    print()
    print(
        "Result:"
    )

    print(
        "Coverage : "
        + (
            "PASS"
            if coverage_pass
            else "FAIL"
        )
    )

    print(
        "Quality  : "
        + (
            "PASS"
            if quality_pass
            else "FAIL"
        )
    )

    print(
        "Latest   : "
        + (
            "PASS"
            if latest_pass
            else "FAIL"
        )
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This is a research outcome "
        "dataset, not yet a strict "
        "point-in-time backtest."
    )

    print(
        "Intraday target/stop timestamps "
        "remain NULL because daily OHLC "
        "cannot provide exact event time."
    )

    if not (
        coverage_pass
        and quality_pass
        and latest_pass
    ):
        raise RuntimeError(
            "Signal outcome audit failed."
        )


if __name__ == "__main__":
    main()