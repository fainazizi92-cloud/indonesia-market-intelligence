import argparse
from typing import Any

from imi.db import engine
from imi.features.market_breadth import (
    build_universe_code,
    calculate_breadth_score,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.market_breadth import (
    get_existing_coverage,
    get_latest_snapshot_date,
    load_daily_breadth_inputs,
    upsert_breadth_rows,
)

DEFAULT_BATCH_SIZE = 2000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Recalculate and upsert all "
            "breadth rows."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def prepare_breadth_rows(
    *,
    inputs: list[dict[str, Any]],
    universe_code: str,
    source_id: object,
) -> list[dict[str, Any]]:
    output: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        advances = int(
            item["advances"]
        )

        declines = int(
            item["declines"]
        )

        unchanged = int(
            item["unchanged"]
        )

        eligible_count = int(
            item["eligible_count"]
        )

        directional_total = (
            advances
            + declines
            + unchanged
        )

        if (
            directional_total
            != eligible_count
        ):
            raise RuntimeError(
                "Breadth population mismatch "
                f"on {item['trading_date']}: "
                f"eligible={eligible_count}, "
                f"A+D+U={directional_total}"
            )

        new_high_20d = int(
            item["new_high_20d"]
        )

        new_low_20d = int(
            item["new_low_20d"]
        )

        new_high_52w = int(
            item["new_high_52w"]
        )

        new_low_52w = int(
            item["new_low_52w"]
        )

        pct_above_ema20 = float(
            item["pct_above_ema20"]
        )

        pct_above_ema50 = float(
            item["pct_above_ema50"]
        )

        pct_above_ema200 = float(
            item["pct_above_ema200"]
        )

        up_volume = float(
            item["up_volume"]
        )

        down_volume = float(
            item["down_volume"]
        )

        breadth_score = (
            calculate_breadth_score(
                advances=advances,
                declines=declines,
                unchanged=unchanged,
                new_high_20d=(
                    new_high_20d
                ),
                new_low_20d=(
                    new_low_20d
                ),
                new_high_52w=(
                    new_high_52w
                ),
                new_low_52w=(
                    new_low_52w
                ),
                pct_above_ema20=(
                    pct_above_ema20
                ),
                pct_above_ema50=(
                    pct_above_ema50
                ),
                pct_above_ema200=(
                    pct_above_ema200
                ),
                up_volume=up_volume,
                down_volume=(
                    down_volume
                ),
            )
        )

        output.append(
            {
                "trading_date":
                    item["trading_date"],
                "universe_code":
                    universe_code,
                "advances":
                    advances,
                "declines":
                    declines,
                "unchanged":
                    unchanged,
                "new_high_20d":
                    new_high_20d,
                "new_low_20d":
                    new_low_20d,
                "new_high_52w":
                    new_high_52w,
                "new_low_52w":
                    new_low_52w,
                "pct_above_ema20":
                    round(
                        pct_above_ema20,
                        4,
                    ),
                "pct_above_ema50":
                    round(
                        pct_above_ema50,
                        4,
                    ),
                "pct_above_ema200":
                    round(
                        pct_above_ema200,
                        4,
                    ),
                "up_volume":
                    up_volume,
                "down_volume":
                    down_volume,
                "breadth_score":
                    breadth_score,
                "source_id":
                    source_id,
            }
        )

    return output


def main() -> None:
    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
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

        inputs = (
            load_daily_breadth_inputs(
                connection,
                snapshot_date=(
                    snapshot_date
                ),
                source_id=source_id,
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

    if not inputs:
        raise RuntimeError(
            "No eligible breadth inputs "
            "were generated."
        )

    universe_code = (
        build_universe_code(
            snapshot_date
        )
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

    with engine.connect() as connection:
        existing = (
            get_existing_coverage(
                connection,
                universe_code=(
                    universe_code
                ),
            )
        )

    is_up_to_date = (
        int(existing["rows"])
        == len(rows)
        and existing["first_date"]
        == generated_first
        and existing["last_date"]
        == generated_last
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
        f"Generated dates : "
        f"{len(rows)}"
    )
    print(
        f"First date      : "
        f"{generated_first}"
    )
    print(
        f"Last date       : "
        f"{generated_last}"
    )
    print()

    if (
        is_up_to_date
        and not args.force
    ):
        print(
            "Breadth dataset is already "
            "up-to-date."
        )
        print(
            "Rows written: 0"
        )
        return

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

    print(
        f"Rows written    : {written}"
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