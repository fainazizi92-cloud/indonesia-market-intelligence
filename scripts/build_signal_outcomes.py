import argparse
import time
from typing import Any

from imi.db import engine
from imi.features.signal_outcome import (
    MAX_FUTURE_BARS,
    build_signal_outcome_model_version,
    prepare_signal_outcome_rows,
    resolve_signal_outcome_build_mode,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.signal_outcome import (
    delete_model_rows,
    get_build_state,
    get_latest_price_state,
    get_latest_trade_setup_model_state,
    get_outcome_distribution,
    get_stored_coverage,
    load_recent_outcomes,
    load_signal_outcome_inputs,
    upsert_build_state,
    upsert_outcomes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
    )

    return parser.parse_args()


def max_input_timestamp(
    inputs: list[dict[str, Any]],
) -> Any:
    timestamps = []

    for item in inputs:
        for value in (
            item[
                "signal_input_updated_at"
            ],
            item["issued_at"],
        ):
            if value is not None:
                timestamps.append(
                    value
                )

        for bar in item["bars"]:
            value = bar.get(
                "ingested_at"
            )

            if value is not None:
                timestamps.append(
                    value
                )

    if not timestamps:
        return None

    return max(
        timestamps
    )


def print_summary(
    *,
    model_version: str,
) -> None:
    with engine.connect() as connection:
        distribution = (
            get_outcome_distribution(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        recent = (
            load_recent_outcomes(
                connection,
                model_version=(
                    model_version
                ),
                limit=20,
            )
        )

    print()
    print(
        "Outcome distribution:"
    )

    for row in distribution:
        print(
            f"{row['outcome_label']!s:<10} "
            f"{int(row['rows'])}"
        )

    print()
    print(
        "Recent accepted-signal outcomes:"
    )

    for row in recent:
        realized_r = (
            "-"
            if row[
                "realized_r"
            ]
            is None
            else (
                f"{float(row['realized_r']):.2f}R"
            )
        )

        print(
            f"{row['signal_date']} "
            f"{row['symbol']:<6} "
            f"{row['outcome_label']:<10} "
            f"entry="
            f"{row['entry_date']} "
            f"exit="
            f"{row['exit_date']} "
            f"R={realized_r}"
        )


def main() -> None:
    args = parse_args()

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

    expected_rows = len(
        inputs
    )

    stored_rows = int(
        stored["rows"]
        or 0
    )

    current_timestamp = (
        max_input_timestamp(
            inputs
        )
    )

    latest_price_date = (
        price_state[
            "latest_price_date"
        ]
    )

    if build_state is None:
        state_exists = False
        input_model_matches = False
        processed_through = None
        stored_timestamp = None

    else:
        state_exists = True

        input_model_matches = (
            build_state[
                "input_model_version"
            ]
            == trade_model
        )

        processed_through = (
            build_state[
                "processed_through"
            ]
        )

        stored_timestamp = (
            build_state[
                "processed_input_updated_at"
            ]
        )

    build_mode = (
        resolve_signal_outcome_build_mode(
            force=args.force,
            state_exists=(
                state_exists
            ),
            input_model_matches=(
                input_model_matches
            ),
            stored_rows=(
                stored_rows
            ),
            expected_rows=(
                expected_rows
            ),
            processed_through=(
                processed_through
            ),
            latest_price_date=(
                latest_price_date
            ),
            stored_input_updated_at=(
                stored_timestamp
            ),
            current_input_updated_at=(
                current_timestamp
            ),
        )
    )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "Historical Signal Outcome V1"
    )
    print(
        "----------------------------"
    )

    print(
        f"Model version     : "
        f"{model_version}"
    )

    print(
        f"Trade setup model : "
        f"{trade_model}"
    )

    print(
        f"Universe          : "
        f"{universe_date}"
    )

    print(
        f"Latest price      : "
        f"{latest_price_date}"
    )

    print(
        f"Accepted signals  : "
        f"{expected_rows}"
    )

    print(
        f"Stored outcomes   : "
        f"{stored_rows}"
    )

    print(
        f"Build mode        : "
        f"{build_mode}"
    )

    if build_mode == "UP_TO_DATE":
        elapsed = (
            time.perf_counter()
            - started
        )

        print()
        print(
            "Signal outcome dataset is "
            "already up-to-date."
        )

        print(
            "Rows written      : 0"
        )

        print(
            f"Elapsed seconds   : "
            f"{elapsed:.3f}"
        )

        print_summary(
            model_version=(
                model_version
            )
        )

        return

    generated = (
        prepare_signal_outcome_rows(
            inputs=inputs,
            evaluation_model_version=(
                model_version
            ),
        )
    )

    if (
        len(generated)
        != expected_rows
    ):
        raise RuntimeError(
            "Generated outcome count "
            "does not match accepted "
            "signal count."
        )

    with engine.begin() as connection:
        rows_deleted = (
            delete_model_rows(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        rows_written = (
            upsert_outcomes(
                connection,
                rows=generated,
                batch_size=(
                    args.batch_size
                ),
            )
        )

        final = (
            get_stored_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        final_rows = int(
            final["rows"]
            or 0
        )

        if final_rows != expected_rows:
            raise RuntimeError(
                "Stored outcome count "
                "does not match expected "
                "accepted signal count."
            )

        upsert_build_state(
            connection,
            model_version=(
                model_version
            ),
            input_model_version=(
                trade_model
            ),
            processed_through=(
                latest_price_date
            ),
            processed_input_updated_at=(
                current_timestamp
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
        f"Elapsed seconds   : "
        f"{elapsed:.3f}"
    )

    print_summary(
        model_version=(
            model_version
        )
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "Returns are research outcomes "
        "from daily OHLC data."
    )

    print(
        "No transaction fee, slippage, "
        "or intraday execution sequence "
        "is modeled."
    )

    print(
        "Same-bar target and stop uses "
        "a conservative STOP-FIRST rule."
    )

    print(
        "These outcomes are not yet "
        "sufficient to publish calibrated "
        "trade probabilities."
    )


if __name__ == "__main__":
    main()