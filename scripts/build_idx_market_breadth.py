import argparse
from time import perf_counter

from imi.db import engine
from imi.features.market_breadth import (
    build_universe_code,
    prepare_breadth_rows,
    resolve_build_mode,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.market_breadth import (
    get_existing_coverage,
    get_latest_eligible_feature_date,
    get_latest_snapshot_date,
    load_daily_breadth_inputs,
    load_incremental_breadth_inputs,
    upsert_breadth_rows,
)

DEFAULT_BATCH_SIZE = 2000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force a full historical "
            "breadth recalculation."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Market Breadth"
    )
    print(
        "-----------------------------"
    )

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        snapshot_date = (
            get_latest_snapshot_date(
                connection
            )
        )

    universe_code = (
        build_universe_code(
            snapshot_date
        )
    )

    with engine.connect() as connection:
        latest_input_date = (
            get_latest_eligible_feature_date(
                connection,
                snapshot_date=(
                    snapshot_date
                ),
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

        existing = (
            get_existing_coverage(
                connection,
                universe_code=(
                    universe_code
                ),
            )
        )

    existing_rows = int(
        existing["rows"]
    )

    existing_last_date = (
        existing["last_date"]
    )

    mode = resolve_build_mode(
        existing_rows=(
            existing_rows
        ),
        existing_last_date=(
            existing_last_date
        ),
        latest_input_date=(
            latest_input_date
        ),
        force=args.force,
    )

    print(
        f"Feature version : "
        f"{FEATURE_VERSION}"
    )
    print(
        f"Snapshot date   : "
        f"{snapshot_date}"
    )
    print(
        f"Universe code   : "
        f"{universe_code}"
    )
    print(
        f"Latest input    : "
        f"{latest_input_date}"
    )
    print(
        f"Existing rows   : "
        f"{existing_rows}"
    )
    print(
        f"Existing last   : "
        f"{existing_last_date}"
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
            "Breadth dataset is already "
            "up-to-date."
        )
        print(
            "Rows written    : 0"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )
        return

    if mode == "FULL":
        print(
            "Loading full historical "
            "breadth inputs..."
        )

        with engine.connect() as connection:
            inputs = (
                load_daily_breadth_inputs(
                    connection,
                    snapshot_date=(
                        snapshot_date
                    ),
                    source_id=(
                        source_id
                    ),
                    feature_version=(
                        FEATURE_VERSION
                    ),
                )
            )

    else:
        if existing_last_date is None:
            raise RuntimeError(
                "Incremental mode requires "
                "an existing last date."
            )

        print(
            "Loading incremental breadth "
            f"after {existing_last_date}..."
        )

        with engine.connect() as connection:
            inputs = (
                load_incremental_breadth_inputs(
                    connection,
                    snapshot_date=(
                        snapshot_date
                    ),
                    source_id=(
                        source_id
                    ),
                    feature_version=(
                        FEATURE_VERSION
                    ),
                    after_date=(
                        existing_last_date
                    ),
                )
            )

    if not inputs:
        raise RuntimeError(
            "No breadth inputs were "
            "generated for build mode "
            f"{mode}."
        )

    rows = prepare_breadth_rows(
        inputs=inputs,
        universe_code=universe_code,
        source_id=source_id,
    )

    generated_first = (
        rows[0]["trading_date"]
    )

    generated_last = (
        rows[-1]["trading_date"]
    )

    if (
        mode == "INCREMENTAL"
        and generated_last
        != latest_input_date
    ):
        raise RuntimeError(
            "Incremental breadth did not "
            "reach latest input date: "
            f"generated={generated_last}, "
            f"expected={latest_input_date}."
        )

    print(
        f"Generated dates : "
        f"{len(rows)}"
    )
    print(
        f"First generated : "
        f"{generated_first}"
    )
    print(
        f"Last generated  : "
        f"{generated_last}"
    )
    print()

    with engine.begin() as connection:
        written = upsert_breadth_rows(
            connection,
            rows=rows,
            batch_size=(
                args.batch_size
            ),
        )

    latest = rows[-1]

    latest_total = (
        latest["advances"]
        + latest["declines"]
        + latest["unchanged"]
    )

    elapsed = (
        perf_counter()
        - started
    )

    print(
        f"Rows written    : "
        f"{written}"
    )
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    print()
    print(
        "Latest breadth:"
    )
    print(
        f"Eligible        : "
        f"{latest_total}"
    )
    print(
        f"Advances        : "
        f"{latest['advances']}"
    )
    print(
        f"Declines        : "
        f"{latest['declines']}"
    )
    print(
        f"Unchanged       : "
        f"{latest['unchanged']}"
    )
    print(
        f"% > EMA20       : "
        f"{latest['pct_above_ema20']}"
    )
    print(
        f"% > EMA50       : "
        f"{latest['pct_above_ema50']}"
    )
    print(
        f"% > EMA200      : "
        f"{latest['pct_above_ema200']}"
    )
    print(
        f"New High 20D    : "
        f"{latest['new_high_20d']}"
    )
    print(
        f"New Low 20D     : "
        f"{latest['new_low_20d']}"
    )
    print(
        f"New High 52W    : "
        f"{latest['new_high_52w']}"
    )
    print(
        f"New Low 52W     : "
        f"{latest['new_low_52w']}"
    )
    print(
        f"Breadth score   : "
        f"{latest['breadth_score']}"
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Historical breadth uses the "
        "current IDX universe snapshot."
    )
    print(
        "It is survivorship-biased and "
        "is not yet safe for historical "
        "production backtests."
    )


if __name__ == "__main__":
    main()