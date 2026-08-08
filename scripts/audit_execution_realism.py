from decimal import Decimal
from typing import Any

from imi.db import engine
from imi.features.execution_realism import (
    build_execution_realism_model_version,
    compute_execution_summary,
    prepare_execution_realism_rows,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.execution_realism import (
    get_build_state,
    get_duplicate_groups,
    get_latest_calibration_model_state,
    get_quality_counts,
    get_stored_coverage,
    load_execution_inputs,
    load_stored_rows,
)

NUMERIC_FIELDS = (
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


EXACT_FIELDS = (
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

        duplicates = (
            get_duplicate_groups(
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
        prepare_execution_realism_rows(
            inputs=inputs,
            model_version=(
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

    generated_summary = (
        compute_execution_summary(
            generated
        )
    )

    stored_summary = (
        compute_execution_summary(
            stored
        )
    )

    expected_rows = len(
        inputs
    )

    stored_rows = int(
        coverage["rows"]
        or 0
    )

    coverage_pass = (
        expected_rows
        == len(generated)
        == stored_rows
        and duplicates == 0
    )

    quality_pass = (
        mismatches == 0
        and int(
            quality[
                "invalid_available_execution"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "execution_on_non_mature"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "strict_with_blockers"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "strict_without_execution"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_entry_tick"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_exit_tick"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_buy_fee"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_sell_fee"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_blocking_json"
            ]
            or 0
        )
        == 0
        and generated_summary
        == stored_summary
    )

    latest_input_date = (
        calibration_state[
            "latest_input_date"
        ]
    )

    latest_pass = (
        build_state is not None
        and build_state[
            "input_model_version"
        ]
        == dataset_version
        and build_state[
            "processed_through"
        ]
        == latest_input_date
        and int(
            build_state[
                "output_rows"
            ]
            or 0
        )
        == stored_rows
    )

    print(
        "Execution Realism Audit"
    )

    print(
        "-----------------------"
    )

    print(
        f"Calibration input : "
        f"{dataset_version}"
    )

    print(
        f"Model version     : "
        f"{model_version}"
    )

    print()
    print(
        "Coverage:"
    )

    print(
        f"Input rows        : "
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
        f"Duplicate groups  : "
        f"{duplicates}"
    )

    print()
    print(
        "Execution metrics:"
    )

    print(
        f"Mature trades     : "
        f"{stored_summary.mature_trades}"
    )

    print(
        f"Metrics available : "
        f"{stored_summary.execution_metrics_available}"
    )

    print(
        f"Strict eligible   : "
        f"{stored_summary.strict_eligible}"
    )

    print(
        f"Raw avg R         : "
        f"{stored_summary.raw_average_r}"
    )

    print(
        f"Net avg R         : "
        f"{stored_summary.net_average_r}"
    )

    print(
        f"Raw PF            : "
        f"{stored_summary.raw_profit_factor}"
    )

    print(
        f"Net PF            : "
        f"{stored_summary.net_profit_factor}"
    )

    print()
    print(
        "Quality:"
    )

    print(
        f"Mismatches                  : "
        f"{mismatches}"
    )

    for key, value in quality.items():
        print(
            f"{key:<28}: {value}"
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
        "Strict calibration ready:"
    )

    print(
        "YES"
        if stored_summary.strict_eligible > 0
        else "NO"
    )

    if not (
        coverage_pass
        and quality_pass
        and latest_pass
    ):
        raise RuntimeError(
            "Execution realism audit failed."
        )


if __name__ == "__main__":
    main()