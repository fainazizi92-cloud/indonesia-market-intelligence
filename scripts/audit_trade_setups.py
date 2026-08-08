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
    get_build_state,
    get_duplicate_groups,
    get_expected_coverage,
    get_input_state_for_date,
    get_latest_screener_model_state,
    get_output_count_for_date,
    get_quality_counts,
    get_stored_coverage,
    load_all_stored,
    load_latest_output,
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
    *,
    generated: list[
        dict[str, Any]
    ],
    stored: list[
        dict[str, Any]
    ],
) -> tuple[
    int,
    list[str],
]:
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

    mismatches = 0
    details: list[
        str
    ] = []

    all_keys = sorted(
        set(
            generated_map
        )
        | set(
            stored_map
        ),
        key=lambda item: (
            item[1],
            str(
                item[0]
            ),
        ),
    )

    for key in all_keys:
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

        if expected is None:
            mismatches += 1

            details.append(

                    f"{key}: stored row "
                    "has no generated row"

            )

            continue

        if actual is None:
            mismatches += 1

            details.append(

                    f"{key}: generated row "
                    "is missing from storage"

            )

            continue

        row_mismatch = False

        for field in NUMERIC_FIELDS:
            if not numeric_equal(
                expected[field],
                actual[field],
            ):
                row_mismatch = True

                details.append(

                        f"{key} field="
                        f"{field} "
                        f"generated="
                        f"{expected[field]} "
                        f"stored="
                        f"{actual[field]}"

                )

                break

        if row_mismatch:
            mismatches += 1
            continue

        for field in EXACT_FIELDS:
            expected_value = (
                expected[field]
            )

            actual_value = (
                actual[field]
            )

            if (
                isinstance(
                    actual_value,
                    Decimal,
                )
            ):
                actual_value = float(
                    actual_value
                )

            if (
                expected_value
                != actual_value
            ):
                row_mismatch = True

                details.append(

                        f"{key} field="
                        f"{field} "
                        f"generated="
                        f"{expected_value} "
                        f"stored="
                        f"{actual_value}"

                )

                break

        if row_mismatch:
            mismatches += 1

    return (
        mismatches,
        details,
    )


def main() -> None:
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

        latest_date = (
            screener_state[
                "latest_date"
            ]
        )

        if latest_date is None:
            raise RuntimeError(
                "Stock screener has no "
                "latest date."
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

        input_kwargs = {
            "screener_model_version":
                screener_model,

            "feature_version":
                FEATURE_VERSION,

            "price_source_id":
                yahoo_source_id,
        }

        expected = (
            get_expected_coverage(
                connection,
                **input_kwargs,
            )
        )

        stored_coverage = (
            get_stored_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        input_rows = (
            load_trade_setup_inputs(
                connection,
                **input_kwargs,
            )
        )

        stored_rows = (
            load_all_stored(
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

        latest_input_state = (
            get_input_state_for_date(
                connection,
                **input_kwargs,
                as_of_date=(
                    latest_date
                ),
            )
        )

        latest_stored_count = (
            get_output_count_for_date(
                connection,
                model_version=(
                    model_version
                ),
                trading_date=(
                    latest_date
                ),
            )
        )

        latest_output = (
            load_latest_output(
                connection,
                model_version=(
                    model_version
                ),
                trading_date=(
                    latest_date
                ),
            )
        )

    generated = (
        prepare_trade_setup_rows(
            inputs=input_rows,
            model_version=(
                model_version
            ),
        )
    )

    (
        mismatch_count,
        mismatch_details,
    ) = compare_rows(
        generated=generated,
        stored=stored_rows,
    )

    expected_rows = int(
        expected[
            "expected_rows"
        ]
        or 0
    )

    stored_count = int(
        stored_coverage[
            "rows"
        ]
        or 0
    )

    expected_latest_count = int(
        latest_input_state[
            "candidate_count"
        ]
        or 0
    )

    coverage_pass = (
        stored_count
        == expected_rows
        and len(
            generated
        )
        == expected_rows
        and duplicates == 0
    )

    quality_pass = (
        mismatch_count == 0
        and int(
            quality[
                "forbidden_probability_ev"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "nonnull_confidence"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_decision"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_accept"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_watch"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_reject"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "frozen_rows"
            ]
            or 0
        )
        == 0
        and int(
            quality[
                "invalid_reason_json"
            ]
            or 0
        )
        == 0
    )

    latest_pass = (
        build_state is not None
        and build_state[
            "input_model_version"
        ]
        == screener_model
        and build_state[
            "processed_through"
        ]
        == latest_date
        and build_state[
            "processed_input_updated_at"
        ]
        == latest_input_state[
            "input_updated_at"
        ]
        and int(
            build_state[
                "output_rows"
            ]
            or 0
        )
        == stored_count
        and latest_stored_count
        == expected_latest_count
    )

    print(
        "IDX Trade Setup & Risk Engine Audit"
    )
    print(
        "-----------------------------------"
    )

    print(
        f"Screener model : "
        f"{screener_model}"
    )

    print(
        f"Model version  : "
        f"{model_version}"
    )

    print()
    print(
        "Coverage:"
    )

    print(
        f"Rows            : "
        f"{stored_count}"
    )

    print(
        f"Expected rows   : "
        f"{expected_rows}"
    )

    print(
        f"Generated rows  : "
        f"{len(generated)}"
    )

    print(
        f"Candidate dates : "
        f"{expected['expected_candidate_dates']}"
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
        f"Latest input    : "
        f"{latest_date}"
    )

    print(
        f"Latest expected : "
        f"{expected_latest_count}"
    )

    print(
        f"Latest stored   : "
        f"{latest_stored_count}"
    )

    print()
    print(
        "Quality:"
    )

    print(
        f"Mismatches                : "
        f"{mismatch_count}"
    )

    print(
        f"Duplicate groups          : "
        f"{duplicates}"
    )

    print(
        f"Probability/EV nonnull    : "
        f"{quality['forbidden_probability_ev']}"
    )

    print(
        f"Confidence nonnull        : "
        f"{quality['nonnull_confidence']}"
    )

    print(
        f"Invalid decisions         : "
        f"{quality['invalid_decision']}"
    )

    print(
        f"Invalid ACCEPT rows       : "
        f"{quality['invalid_accept']}"
    )

    print(
        f"Invalid WATCH rows        : "
        f"{quality['invalid_watch']}"
    )

    print(
        f"Invalid REJECT rows       : "
        f"{quality['invalid_reject']}"
    )

    print(
        f"Frozen generated rows     : "
        f"{quality['frozen_rows']}"
    )

    print(
        f"Invalid reason JSON       : "
        f"{quality['invalid_reason_json']}"
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
        "Latest decisions:"
    )

    accepted = 0
    watched = 0
    rejected = 0

    for row in latest_output:
        decision = (
            row[
                "setup_decision"
            ]
        )

        if decision == "ACCEPT":
            accepted += 1

        elif decision == "WATCH":
            watched += 1

        elif decision == "REJECT":
            rejected += 1

    print(
        f"ACCEPT : {accepted}"
    )

    print(
        f"WATCH  : {watched}"
    )

    print(
        f"REJECT : {rejected}"
    )

    print()
    print(
        "Build state:"
    )

    if build_state is None:
        print(
            "MISSING"
        )

    else:
        print(
            f"Processed through : "
            f"{build_state['processed_through']}"
        )

        print(
            f"Output rows       : "
            f"{build_state['output_rows']}"
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
        "WARNING:"
    )

    print(
        "Phase 3I does not provide "
        "calibrated win probability or EV."
    )

    print(
        "Historical KSEI as_of_date joins "
        "remain unsuitable for strict "
        "point-in-time backtests until "
        "availability timestamps exist."
    )

    print(
        "Normalized position sizing is "
        "not account-specific."
    )

    if not (
        coverage_pass
        and quality_pass
        and latest_pass
    ):
        raise RuntimeError(
            "Trade setup audit failed."
        )


if __name__ == "__main__":
    main()