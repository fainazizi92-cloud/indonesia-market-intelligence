import argparse
import time
from datetime import date

from imi.db import engine
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.features.trade_setup import (
    REFERENCE_CAPITAL_IDR,
    RISK_BUDGET_PCT,
    build_trade_setup_model_version,
    extract_current_universe_date,
    prepare_trade_setup_rows,
    resolve_trade_setup_build_mode,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.trade_setup import (
    delete_model_rows,
    get_build_state,
    get_decision_distribution,
    get_expected_coverage,
    get_input_state_for_date,
    get_latest_screener_model_state,
    get_stored_coverage,
    load_latest_output,
    load_trade_setup_inputs,
    upsert_build_state,
    upsert_trade_setup_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force a full rebuild of the "
            "current Phase 3I model."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
    )

    return parser.parse_args()


def print_latest_output(
    *,
    model_version: str,
    trading_date: date,
) -> None:
    with engine.connect() as connection:
        distribution = (
            get_decision_distribution(
                connection,
                model_version=(
                    model_version
                ),
                trading_date=(
                    trading_date
                ),
            )
        )

        rows = load_latest_output(
            connection,
            model_version=(
                model_version
            ),
            trading_date=(
                trading_date
            ),
        )

    print()
    print(
        "Latest Phase 3I distribution:"
    )

    if not distribution:
        print(
            "No Phase 3I candidates."
        )

    for row in distribution:
        print(
            f"{row['setup_decision']!s:<8} "
            f"{row['status']!s:<10} "
            f"{int(row['rows'])}"
        )

    accepted = [
        row
        for row in rows
        if row[
            "setup_decision"
        ]
        == "ACCEPT"
    ]

    print()
    print(
        "Latest accepted trade setups:"
    )

    if not accepted:
        print(
            "No ACCEPT setups."
        )

    for index, row in enumerate(
        accepted[:30],
        start=1,
    ):
        risk_pct = (
            None
            if row[
                "risk_pct_price"
            ]
            is None
            else float(
                row[
                    "risk_pct_price"
                ]
            )
            * 100.0
        )

        print(
            f"{index:>2}. "
            f"{row['symbol']:<6} "
            f"{row['sector_code']:<12} "
            f"entry="
            f"{float(row['entry_low']):.2f}"
            f"-"
            f"{float(row['entry_high']):.2f} "
            f"stop="
            f"{float(row['stop_price']):.2f} "
            f"target="
            f"{float(row['target_primary']):.2f} "
            f"RR="
            f"{float(row['expected_rr']):.2f} "
            f"risk="
            f"{risk_pct:.2f}% "
            f"lots="
            f"{int(row['position_size_lots'])}"
        )


def main() -> None:
    args = parse_args()

    started = time.perf_counter()

    with engine.connect() as connection:
        screener_state = (
            get_latest_screener_model_state(
                connection
            )
        )

        screener_model_version = str(
            screener_state[
                "model_version"
            ]
        )

        latest_input_date = (
            screener_state[
                "latest_date"
            ]
        )

        if latest_input_date is None:
            raise RuntimeError(
                "Stock screener has no "
                "trading dates."
            )

        universe_date = (
            extract_current_universe_date(
                screener_model_version
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
                screener_model_version,

            "feature_version":
                FEATURE_VERSION,

            "price_source_id":
                yahoo_source_id,
        }

        latest_input_state = (
            get_input_state_for_date(
                connection,
                **input_kwargs,
                as_of_date=(
                    latest_input_date
                ),
            )
        )

        expected = (
            get_expected_coverage(
                connection,
                **input_kwargs,
            )
        )

        stored = (
            get_stored_coverage(
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

        stored_rows = int(
            stored["rows"]
            or 0
        )

        expected_rows = int(
            expected[
                "expected_rows"
            ]
            or 0
        )

        if build_state is None:
            state_exists = False
            processed_through = None
            state_output_rows = 0

            stored_processed_timestamp = (
                None
            )

            current_processed_timestamp = (
                None
            )

            input_model_matches = False

        else:
            state_exists = True

            processed_through = (
                build_state[
                    "processed_through"
                ]
            )

            state_output_rows = int(
                build_state[
                    "output_rows"
                ]
                or 0
            )

            stored_processed_timestamp = (
                build_state[
                    "processed_input_updated_at"
                ]
            )

            input_model_matches = (
                build_state[
                    "input_model_version"
                ]
                == screener_model_version
            )

            if processed_through is None:
                current_processed_timestamp = (
                    None
                )

            else:
                processed_state = (
                    get_input_state_for_date(
                        connection,
                        **input_kwargs,
                        as_of_date=(
                            processed_through
                        ),
                    )
                )

                current_processed_timestamp = (
                    processed_state[
                        "input_updated_at"
                    ]
                )

        build_mode = (
            resolve_trade_setup_build_mode(
                force=args.force,
                state_exists=(
                    state_exists
                ),
                input_model_matches=(
                    input_model_matches
                ),
                processed_through=(
                    processed_through
                ),
                latest_input_date=(
                    latest_input_date
                ),
                stored_rows=(
                    stored_rows
                ),
                state_output_rows=(
                    state_output_rows
                ),
                expected_rows=(
                    expected_rows
                ),
                stored_processed_input_updated_at=(
                    stored_processed_timestamp
                ),
                current_processed_input_updated_at=(
                    current_processed_timestamp
                ),
            )
        )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Trade Setup & Risk Engine V1"
    )
    print(
        "--------------------------------"
    )

    print(
        f"Model version     : "
        f"{model_version}"
    )

    print(
        f"Screener model    : "
        f"{screener_model_version}"
    )

    print(
        f"Feature version   : "
        f"{FEATURE_VERSION}"
    )

    print(
        f"Universe          : "
        f"{universe_date}"
    )

    print(
        f"Latest input      : "
        f"{latest_input_date}"
    )

    print(
        f"Latest candidates : "
        f"{latest_input_state['candidate_count']}"
    )

    print(
        f"Expected rows     : "
        f"{expected_rows}"
    )

    print(
        f"Stored rows       : "
        f"{stored_rows}"
    )

    print(
        f"Processed through : "
        f"{processed_through}"
    )

    print(
        f"Build mode        : "
        f"{build_mode}"
    )

    print(
        f"Reference capital : "
        f"Rp{REFERENCE_CAPITAL_IDR:,.0f}"
    )

    print(
        f"Risk budget       : "
        f"{RISK_BUDGET_PCT * 100:.2f}%"
    )

    if build_mode == "UP_TO_DATE":
        elapsed = (
            time.perf_counter()
            - started
        )

        print()
        print(
            "Trade setup dataset is "
            "already up-to-date."
        )

        print(
            "Rows written      : 0"
        )

        print(
            f"Elapsed seconds   : "
            f"{elapsed:.3f}"
        )

        print_latest_output(
            model_version=(
                model_version
            ),
            trading_date=(
                latest_input_date
            ),
        )

        return

    if build_mode == "FULL":
        after_date = None

    else:
        after_date = (
            processed_through
        )

        if after_date is None:
            raise RuntimeError(
                "Incremental build requires "
                "processed_through."
            )

    with engine.connect() as connection:
        rows_input = (
            load_trade_setup_inputs(
                connection,
                **input_kwargs,
                after_date=(
                    after_date
                ),
            )
        )

        if after_date is None:
            expected_build = expected

        else:
            expected_build = (
                get_expected_coverage(
                    connection,
                    **input_kwargs,
                    after_date=(
                        after_date
                    ),
                )
            )

    generated = (
        prepare_trade_setup_rows(
            inputs=rows_input,
            model_version=(
                model_version
            ),
        )
    )

    expected_build_rows = int(
        expected_build[
            "expected_rows"
        ]
        or 0
    )

    if (
        len(generated)
        != expected_build_rows
    ):
        raise RuntimeError(
            "Generated trade setup rows "
            "do not match expected rows: "
            f"generated={len(generated)}, "
            f"expected={expected_build_rows}."
        )

    with engine.begin() as connection:
        if build_mode == "FULL":
            rows_deleted = (
                delete_model_rows(
                    connection,
                    model_version=(
                        model_version
                    ),
                )
            )

        else:
            rows_deleted = 0

        rows_written = (
            upsert_trade_setup_rows(
                connection,
                rows=generated,
                batch_size=(
                    args.batch_size
                ),
            )
        )

        final_coverage = (
            get_stored_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        final_rows = int(
            final_coverage[
                "rows"
            ]
            or 0
        )

        if final_rows != expected_rows:
            raise RuntimeError(
                "Stored trade setup coverage "
                "does not match expected "
                "coverage: "
                f"stored={final_rows}, "
                f"expected={expected_rows}."
            )

        upsert_build_state(
            connection,
            model_version=(
                model_version
            ),
            input_model_version=(
                screener_model_version
            ),
            processed_through=(
                latest_input_date
            ),
            processed_input_updated_at=(
                latest_input_state[
                    "input_updated_at"
                ]
            ),
            output_rows=(
                final_rows
            ),
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print(
        f"Generated rows    : "
        f"{len(generated)}"
    )

    print(
        f"Rows deleted      : "
        f"{rows_deleted}"
    )

    print(
        f"Rows written      : "
        f"{rows_written}"
    )

    print(
        f"Stored total      : "
        f"{expected_rows}"
    )

    print(
        f"Candidate dates   : "
        f"{expected['expected_candidate_dates']}"
    )

    print(
        f"Expected first    : "
        f"{expected['expected_first']}"
    )

    print(
        f"Expected last     : "
        f"{expected['expected_last']}"
    )

    print(
        f"Processed through : "
        f"{latest_input_date}"
    )

    print(
        f"Elapsed seconds   : "
        f"{elapsed:.3f}"
    )

    print_latest_output(
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
        "ACCEPT is a deterministic "
        "Phase 3I research setup, not "
        "a calibrated probability."
    )

    print(
        "probability_tp_before_sl and "
        "expected_value_r remain NULL."
    )

    print(
        "Position sizing uses a normalized "
        "Rp100,000,000 reference capital, "
        "not the user's actual account."
    )

    print(
        "IDX tick-price rules and daily "
        "price limits are not yet modeled."
    )


if __name__ == "__main__":
    main()