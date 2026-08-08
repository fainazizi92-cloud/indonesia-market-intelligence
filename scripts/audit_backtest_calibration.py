from decimal import Decimal
from typing import Any

from imi.db import engine
from imi.features.backtest_calibration import (
    build_backtest_calibration_version,
    compute_backtest_summary,
    prepare_backtest_calibration_rows,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.backtest_calibration import (
    get_build_state,
    get_duplicate_groups,
    get_latest_outcome_model_state,
    get_quality_counts,
    get_stored_coverage,
    load_backtest_inputs,
    load_stored_rows,
)

NUMERIC_FIELDS = (
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


EXACT_FIELDS = (
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

        coverage = (
            get_stored_coverage(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

        quality = (
            get_quality_counts(
                connection,
                dataset_version=(
                    dataset_version
                ),
            )
        )

        duplicates = (
            get_duplicate_groups(
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

    generated = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version=(
                dataset_version
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

    generated_summary = (
        compute_backtest_summary(
            generated
        )
    )

    stored_summary = (
        compute_backtest_summary(
            stored
        )
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
                "invalid_eligible_sample"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "eligible_excluded"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "excluded_with_split"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_mature"
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
                "invalid_entry_date"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_exit_date"
            ]
            or 0
        )
        == 0
        and generated_summary
        == stored_summary
    )

    latest_input_date = (
        outcome_state[
            "latest_input_date"
        ]
    )

    latest_pass = (
        build_state is not None
        and build_state[
            "input_model_version"
        ]
        == outcome_model
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
        "Backtest Calibration Dataset Audit"
    )

    print(
        "----------------------------------"
    )

    print(
        f"Outcome model    : "
        f"{outcome_model}"
    )

    print(
        f"Dataset version  : "
        f"{dataset_version}"
    )

    print()
    print(
        "Coverage:"
    )

    print(
        f"Input rows       : "
        f"{expected_rows}"
    )

    print(
        f"Generated rows   : "
        f"{len(generated)}"
    )

    print(
        f"Stored rows      : "
        f"{stored_rows}"
    )

    print(
        f"Duplicate groups : "
        f"{duplicates}"
    )

    print()
    print(
        "Sample classes:"
    )

    print(
        f"Mature trades     : "
        f"{stored_summary.mature_trades}"
    )

    print(
        f"Unfilled complete : "
        f"{stored_summary.unfilled_complete}"
    )

    print(
        f"Unresolved        : "
        f"{stored_summary.unresolved}"
    )

    print()
    print(
        "Splits:"
    )

    print(
        f"TRAIN      : "
        f"{stored_summary.train_trades}"
    )

    print(
        f"VALIDATION : "
        f"{stored_summary.validation_trades}"
    )

    print(
        f"TEST       : "
        f"{stored_summary.test_trades}"
    )

    print()
    print(
        "Quality:"
    )

    print(
        f"Mismatches             : "
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
        "Readiness:"
    )

    print(
        "Calibration ready : "
        + (
            "YES"
            if stored_summary
            .calibration_ready
            else "NO"
        )
    )

    for reason in (
        stored_summary
        .readiness_reasons
    ):
        print(
            f"- {reason}"
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

    if not (
        coverage_pass
        and quality_pass
        and latest_pass
    ):
        raise RuntimeError(
            "Backtest calibration "
            "dataset audit failed."
        )


if __name__ == "__main__":
    main()