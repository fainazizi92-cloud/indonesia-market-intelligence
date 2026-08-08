import math

from imi.db import engine
from imi.features.integrated_sector import (
    extract_current_universe_date,
)
from imi.features.ownership_trend import (
    OWNERSHIP_TREND_MODEL_VERSION,
)
from imi.features.stock_screener import (
    build_stock_screener_model_version,
    prepare_stock_screener_rows,
    rank_stock_rows,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.regimes.ihsg import (
    MODEL_VERSION as IHSG_REGIME_MODEL_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.stock_screener import (
    get_current_universe_count,
    get_duplicate_groups,
    get_expected_coverage,
    get_latest_input_state,
    get_latest_integrated_model_state,
    get_status_distribution,
    get_stored_coverage,
    load_all_stored,
    load_latest_ranking,
    load_stock_inputs,
)

FLOAT_FIELDS = (
    "overall_score",
    "market_score",
    "sector_score",
    "technical_score",
    "liquidity_score",
    "risk_score",
    "ownership_score",
    "data_completeness",
)

INTEGER_FIELDS = (
    "universe_rank",
    "sector_rank",
)

EXACT_FIELDS = (
    "status",
    "input_updated_at",
    "model_version",
)


def float_matches(
    left,
    right,
) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-9,
        abs_tol=1e-4,
    )


def main() -> None:
    with engine.connect() as connection:
        yahoo_source_id = (
            get_source_id(
                connection,
                code="YAHOO_FINANCE",
            )
        )

        ksei_source_id = (
            get_source_id(
                connection,
                code="KSEI_OFFICIAL",
            )
        )

        integrated_state = (
            get_latest_integrated_model_state(
                connection
            )
        )

        universe_count = (
            get_current_universe_count(
                connection
            )
        )

    sector_model_version = str(
        integrated_state[
            "model_version"
        ]
    )

    universe_date = (
        extract_current_universe_date(
            sector_model_version
        )
    )

    model_version = (
        build_stock_screener_model_version(
            universe_date
        )
    )

    input_kwargs = {
        "price_source_id":
            yahoo_source_id,

        "ownership_source_id":
            ksei_source_id,

        "feature_version":
            FEATURE_VERSION,

        "sector_model_version":
            sector_model_version,

        "market_model_version":
            IHSG_REGIME_MODEL_VERSION,

        "ownership_model_version":
            OWNERSHIP_TREND_MODEL_VERSION,
    }

    with engine.connect() as connection:
        expected = (
            get_expected_coverage(
                connection,
                **input_kwargs,
            )
        )

        latest_input = (
            get_latest_input_state(
                connection,
                **input_kwargs,
            )
        )

        inputs = (
            load_stock_inputs(
                connection,
                **input_kwargs,
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

        actual = (
            get_stored_coverage(
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

        ranking = (
            load_latest_ranking(
                connection,
                model_version=(
                    model_version
                ),
                trading_date=(
                    latest_input[
                        "latest_input_date"
                    ]
                ),
            )
        )

        distribution = (
            get_status_distribution(
                connection,
                model_version=(
                    model_version
                ),
                trading_date=(
                    latest_input[
                        "latest_input_date"
                    ]
                ),
            )
        )

    generated = (
        prepare_stock_screener_rows(
            inputs=inputs,
            model_version=(
                model_version
            ),
        )
    )

    generated = rank_stock_rows(
        generated
    )

    generated_by_key = {
        (
            row["instrument_id"],
            row["trading_date"],
        ): row
        for row in generated
    }

    stored_by_key = {
        (
            row["instrument_id"],
            row["trading_date"],
        ): row
        for row in stored
    }

    generated_keys = set(
        generated_by_key
    )

    stored_keys = set(
        stored_by_key
    )

    mismatches: list[str] = []

    if generated_keys != stored_keys:
        missing = (
            generated_keys
            - stored_keys
        )

        unexpected = (
            stored_keys
            - generated_keys
        )

        if missing:
            mismatches.append(
                "Missing stored keys: "
                f"{list(missing)[:20]}"
            )

        if unexpected:
            mismatches.append(
                "Unexpected stored keys: "
                f"{list(unexpected)[:20]}"
            )

    forbidden_component_rows = 0
    invalid_score_rows = 0
    invalid_rank_rows = 0

    valid_statuses = {
        "BUY_SETUP",
        "WATCH",
        "WAIT",
        "AVOID",
    }

    invalid_status_rows = 0

    for key in (
        generated_keys
        & stored_keys
    ):
        generated_row = (
            generated_by_key[key]
        )

        stored_row = (
            stored_by_key[key]
        )

        for field in FLOAT_FIELDS:
            if not float_matches(
                generated_row[field],
                stored_row[field],
            ):
                mismatches.append(
                    f"{key} {field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

        for field in INTEGER_FIELDS:
            if int(
                generated_row[field]
            ) != int(
                stored_row[field]
            ):
                mismatches.append(
                    f"{key} {field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

        for field in EXACT_FIELDS:
            if (
                generated_row[field]
                != stored_row[field]
            ):
                mismatches.append(
                    f"{key} {field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

    for row in stored:
        if any(
            row[field] is not None
            for field in (
                "fundamental_score",
                "valuation_score",
                "flow_score",
                "catalyst_score",
            )
        ):
            forbidden_component_rows += 1

        for field in FLOAT_FIELDS:
            value = row[field]

            if (
                value is None
                or not (
                    0.0
                    <= float(value)
                    <= 100.0
                )
            ):
                invalid_score_rows += 1
                break

        if (
            row["universe_rank"] is None
            or int(
                row["universe_rank"]
            ) <= 0
            or row["sector_rank"]
            is None
            or int(
                row["sector_rank"]
            ) <= 0
        ):
            invalid_rank_rows += 1

        if (
            str(
                row["status"]
            )
            not in valid_statuses
        ):
            invalid_status_rows += 1

    coverage_pass = (
        int(
            actual["rows"]
        )
        == int(
            expected["expected_rows"]
        )
        and int(
            actual["instruments"]
        )
        == int(
            expected[
                "expected_instruments"
            ]
        )
        and int(
            actual["dates"]
        )
        == int(
            expected["expected_dates"]
        )
        and actual["first_date"]
        == expected["expected_first"]
        and actual["last_date"]
        == expected["expected_last"]
    )

    quality_pass = (
        not mismatches
        and duplicates == 0
        and forbidden_component_rows == 0
        and invalid_score_rows == 0
        and invalid_rank_rows == 0
        and invalid_status_rows == 0
    )

    latest_pass = (
        bool(ranking)
        and ranking[0][
            "trading_date"
        ]
        == latest_input[
            "latest_input_date"
        ]
        and len(
            ranking
        )
        == int(
            latest_input[
                "latest_candidate_count"
            ]
        )
    )

    print(
        "IDX Stock Screener Audit"
    )
    print(
        "------------------------"
    )
    print(
        f"Model version   : "
        f"{model_version}"
    )
    print(
        f"Universe size   : "
        f"{universe_count}"
    )

    print()
    print(
        "Coverage:"
    )
    print(
        f"Rows            : "
        f"{actual['rows']}"
    )
    print(
        f"Expected rows   : "
        f"{expected['expected_rows']}"
    )
    print(
        f"Instruments     : "
        f"{actual['instruments']}"
    )
    print(
        f"Expected inst.  : "
        f"{expected['expected_instruments']}"
    )
    print(
        f"Dates           : "
        f"{actual['dates']}"
    )
    print(
        f"Expected dates  : "
        f"{expected['expected_dates']}"
    )
    print(
        f"First date      : "
        f"{actual['first_date']}"
    )
    print(
        f"Expected first  : "
        f"{expected['expected_first']}"
    )
    print(
        f"Last date       : "
        f"{actual['last_date']}"
    )
    print(
        f"Expected last   : "
        f"{expected['expected_last']}"
    )

    print()
    print(
        "Quality:"
    )
    print(
        f"Mismatches                 : "
        f"{len(mismatches)}"
    )
    print(
        f"Duplicate groups           : "
        f"{duplicates}"
    )
    print(
        f"Forbidden components nonnull: "
        f"{forbidden_component_rows}"
    )
    print(
        f"Invalid score rows         : "
        f"{invalid_score_rows}"
    )
    print(
        f"Invalid rank rows          : "
        f"{invalid_rank_rows}"
    )
    print(
        f"Invalid status rows        : "
        f"{invalid_status_rows}"
    )

    if mismatches:
        print()
        print(
            "Mismatch sample:"
        )

        for item in (
            mismatches[:30]
        ):
            print(
                item
            )

    print()
    print(
        "Latest status distribution:"
    )

    for row in distribution:
        print(
            f"{row['status']!s:<12} "
            f"{row['rows']}"
        )

    print()
    print(
        "Top 30 latest candidates:"
    )

    for row in ranking[:30]:
        print(
            f"{int(row['universe_rank']):>3}. "
            f"{row['symbol']:<6} "
            f"{row['sector_code']:<12} "
            f"score="
            f"{float(row['overall_score']):>6.2f} "
            f"T="
            f"{float(row['technical_score']):>5.1f} "
            f"S="
            f"{float(row['sector_score']):>5.1f} "
            f"O="
            f"{float(row['ownership_score']):>5.1f} "
            f"L="
            f"{float(row['liquidity_score']):>5.1f} "
            f"R="
            f"{float(row['risk_score']):>5.1f} "
            f"{row['status']}"
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
        raise SystemExit(1)

    print()
    print(
        "WARNING:"
    )
    print(
        "BUY_SETUP is a screener "
        "classification, not an "
        "executable trade signal."
    )
    print(
        "No calibrated probability "
        "or expected value exists yet."
    )
    print(
        "Historical KSEI joins are "
        "research-only until source "
        "availability timestamps are "
        "modeled."
    )


if __name__ == "__main__":
    main()