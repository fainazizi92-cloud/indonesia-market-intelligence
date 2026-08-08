import argparse
from time import perf_counter

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
    resolve_stock_screener_build_mode,
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
from imi.repositories.sector_ownership import (
    get_latest_universe_snapshot_date,
)
from imi.repositories.stock_screener import (
    delete_model_rows,
    get_current_universe_count,
    get_expected_coverage,
    get_input_state_for_date,
    get_latest_input_state,
    get_latest_integrated_model_state,
    get_status_distribution,
    get_stored_latest_state,
    load_latest_ranking,
    load_stock_inputs,
    upsert_stock_scores,
)

DEFAULT_BATCH_SIZE = 1000
TOP_ROWS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build historical or "
            "incremental IDX stock "
            "screener scores."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force a full rebuild."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def print_latest(
    *,
    model_version: str,
    trading_date,
) -> None:
    with engine.connect() as connection:
        ranking = (
            load_latest_ranking(
                connection,
                model_version=(
                    model_version
                ),
                trading_date=(
                    trading_date
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
                    trading_date
                ),
            )
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
        "Top stock candidates:"
    )

    for row in ranking[:TOP_ROWS]:
        print(
            f"{int(row['universe_rank']):>3}. "
            f"{row['symbol']:<6} "
            f"{row['sector_code']:<12} "
            f"score="
            f"{float(row['overall_score']):>6.2f} "
            f"M="
            f"{float(row['market_score']):>5.1f} "
            f"S="
            f"{float(row['sector_score']):>5.1f} "
            f"T="
            f"{float(row['technical_score']):>5.1f} "
            f"L="
            f"{float(row['liquidity_score']):>5.1f} "
            f"O="
            f"{float(row['ownership_score']):>5.1f} "
            f"R="
            f"{float(row['risk_score']):>5.1f} "
            f"{row['status']}"
        )


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

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

        latest_universe_date = (
            get_latest_universe_snapshot_date(
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

    integrated_universe_date = (
        extract_current_universe_date(
            sector_model_version
        )
    )

    if (
        integrated_universe_date
        != latest_universe_date
    ):
        raise RuntimeError(
            "Integrated sector model "
            "does not use the latest "
            "current universe: "
            f"sector="
            f"{integrated_universe_date}, "
            f"universe="
            f"{latest_universe_date}."
        )

    model_version = (
        build_stock_screener_model_version(
            latest_universe_date
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
        latest_input = (
            get_latest_input_state(
                connection,
                **input_kwargs,
            )
        )

        stored = (
            get_stored_latest_state(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    latest_input_date = (
        latest_input[
            "latest_input_date"
        ]
    )

    existing_last_date = (
        stored[
            "latest_date"
        ]
    )

    existing_latest_count = int(
        stored[
            "latest_count"
        ]
        or 0
    )

    existing_input_updated_at = (
        stored[
            "input_updated_at"
        ]
    )

    if existing_last_date is None:
        expected_existing_count = 0
        expected_input_updated_at = None

    else:
        with engine.connect() as connection:
            expected_existing = (
                get_input_state_for_date(
                    connection,
                    **input_kwargs,
                    as_of_date=(
                        existing_last_date
                    ),
                )
            )

        expected_existing_count = int(
            expected_existing[
                "candidate_count"
            ]
            or 0
        )

        expected_input_updated_at = (
            expected_existing[
                "input_updated_at"
            ]
        )

    mode = (
        resolve_stock_screener_build_mode(
            existing_last_date=(
                existing_last_date
            ),
            existing_latest_count=(
                existing_latest_count
            ),
            existing_expected_count=(
                expected_existing_count
            ),
            existing_input_updated_at=(
                existing_input_updated_at
            ),
            expected_input_updated_at=(
                expected_input_updated_at
            ),
            latest_input_date=(
                latest_input_date
            ),
            force=args.force,
        )
    )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Stock Swing Screener V1"
    )
    print(
        "---------------------------"
    )
    print(
        f"Model version   : "
        f"{model_version}"
    )
    print(
        f"Feature version : "
        f"{FEATURE_VERSION}"
    )
    print(
        f"Market model    : "
        f"{IHSG_REGIME_MODEL_VERSION}"
    )
    print(
        f"Sector model    : "
        f"{sector_model_version}"
    )
    print(
        f"Ownership model : "
        f"{OWNERSHIP_TREND_MODEL_VERSION}"
    )
    print(
        f"Universe        : "
        f"{latest_universe_date}"
    )
    print(
        f"Universe size   : "
        f"{universe_count}"
    )
    print(
        f"Latest input    : "
        f"{latest_input_date}"
    )
    print(
        f"Eligible latest : "
        f"{latest_input['latest_candidate_count']}"
    )
    print(
        f"Latest sectors  : "
        f"{latest_input['latest_sector_count']}"
    )
    print(
        f"Existing last   : "
        f"{existing_last_date}"
    )
    print(
        f"Stored latest   : "
        f"{existing_latest_count}"
    )
    print(
        f"Expected stored : "
        f"{expected_existing_count}"
    )
    print(
        f"Build mode      : "
        f"{mode}"
    )
    print()

    if mode == "UP_TO_DATE":
        elapsed = (
            perf_counter()
            - started
        )

        print(
            "Stock screener dataset "
            "is already up-to-date."
        )
        print(
            "Rows written    : 0"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )

        print_latest(
            model_version=(
                model_version
            ),
            trading_date=(
                latest_input_date
            ),
        )

        return

    after_date = None

    if mode == "INCREMENTAL":
        if existing_last_date is None:
            raise RuntimeError(
                "Incremental mode requires "
                "existing screener rows."
            )

        after_date = (
            existing_last_date
        )

    with engine.connect() as connection:
        expected = (
            get_expected_coverage(
                connection,
                **input_kwargs,
                after_date=(
                    after_date
                ),
            )
        )

        inputs = (
            load_stock_inputs(
                connection,
                **input_kwargs,
                after_date=(
                    after_date
                ),
            )
        )

    rows = (
        prepare_stock_screener_rows(
            inputs=inputs,
            model_version=(
                model_version
            ),
        )
    )

    rows = rank_stock_rows(
        rows
    )

    expected_rows = int(
        expected[
            "expected_rows"
        ]
    )

    if len(rows) != expected_rows:
        raise RuntimeError(
            "Generated stock score row "
            "count does not match "
            "expected coverage: "
            f"generated={len(rows)}, "
            f"expected={expected_rows}."
        )

    if not rows:
        raise RuntimeError(
            "No stock screener rows "
            "were generated."
        )

    generated_last_date = max(
        row["trading_date"]
        for row in rows
    )

    if (
        generated_last_date
        != latest_input_date
    ):
        raise RuntimeError(
            "Stock screener build did "
            "not reach latest input: "
            f"generated="
            f"{generated_last_date}, "
            f"expected="
            f"{latest_input_date}."
        )

    with engine.begin() as connection:
        deleted = 0

        if mode == "FULL":
            deleted = (
                delete_model_rows(
                    connection,
                    model_version=(
                        model_version
                    ),
                )
            )

        written = (
            upsert_stock_scores(
                connection,
                rows=rows,
                batch_size=(
                    args.batch_size
                ),
            )
        )

    elapsed = (
        perf_counter()
        - started
    )

    print(
        f"Expected rows   : "
        f"{expected_rows}"
    )
    print(
        f"Generated rows  : "
        f"{len(rows)}"
    )
    print(
        f"Rows deleted    : "
        f"{deleted}"
    )
    print(
        f"Rows written    : "
        f"{written}"
    )
    print(
        f"Expected inst.  : "
        f"{expected['expected_instruments']}"
    )
    print(
        f"Expected dates  : "
        f"{expected['expected_dates']}"
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
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    print_latest(
        model_version=(
            model_version
        ),
        trading_date=(
            latest_input_date
        ),
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "BUY_SETUP is a screening "
        "classification only."
    )
    print(
        "No entry, stop, target, "
        "probability, or expected "
        "value is generated here."
    )
    print(
        "fundamental_score, "
        "valuation_score, flow_score, "
        "and catalyst_score remain NULL."
    )
    print(
        "Historical KSEI joins use "
        "as_of_date and are not yet "
        "publication-time-safe for "
        "strict backtesting."
    )


if __name__ == "__main__":
    main()