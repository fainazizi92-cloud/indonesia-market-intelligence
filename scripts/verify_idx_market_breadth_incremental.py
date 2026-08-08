import argparse
import math
from time import perf_counter
from typing import Any

from imi.db import engine
from imi.features.market_breadth import (
    build_universe_code,
    prepare_breadth_rows,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.market_breadth import (
    get_latest_snapshot_date,
    get_recent_breadth_dates,
    load_incremental_breadth_inputs,
    load_stored_breadth_after,
)

INTEGER_FIELDS = (
    "advances",
    "declines",
    "unchanged",
    "new_high_20d",
    "new_low_20d",
    "new_high_52w",
    "new_low_52w",
)

FLOAT_FIELDS = (
    "pct_above_ema20",
    "pct_above_ema50",
    "pct_above_ema200",
    "up_volume",
    "down_volume",
    "breadth_score",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--days",
        type=int,
        default=10,
        help=(
            "Number of recent breadth "
            "dates to verify."
        ),
    )

    return parser.parse_args()


def _float_matches(
    left: Any,
    right: Any,
) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-9,
        abs_tol=1e-4,
    )


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.days <= 0:
        raise ValueError(
            "days must be greater "
            "than zero."
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
        recent_dates = (
            get_recent_breadth_dates(
                connection,
                universe_code=(
                    universe_code
                ),
                limit=(
                    args.days + 1
                ),
            )
        )

    if len(recent_dates) < (
        args.days + 1
    ):
        raise RuntimeError(
            "Not enough stored breadth "
            "dates for verification."
        )

    ordered_dates = sorted(
        recent_dates
    )

    after_date = (
        ordered_dates[0]
    )

    expected_dates = set(
        ordered_dates[1:]
    )

    print(
        "IDX Market Breadth "
        "Incremental Verification"
    )
    print(
        "-----------------------------------"
    )
    print(
        f"Universe code   : "
        f"{universe_code}"
    )
    print(
        f"Verify days     : "
        f"{args.days}"
    )
    print(
        f"After date      : "
        f"{after_date}"
    )
    print()

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
                    after_date
                ),
            )
        )

        stored = (
            load_stored_breadth_after(
                connection,
                universe_code=(
                    universe_code
                ),
                after_date=(
                    after_date
                ),
            )
        )

    generated = prepare_breadth_rows(
        inputs=inputs,
        universe_code=universe_code,
        source_id=source_id,
    )

    generated = [
        row
        for row in generated
        if row["trading_date"]
        in expected_dates
    ]

    stored = [
        row
        for row in stored
        if row["trading_date"]
        in expected_dates
    ]

    generated_by_date = {
        row["trading_date"]: row
        for row in generated
    }

    stored_by_date = {
        row["trading_date"]: row
        for row in stored
    }

    mismatches: list[str] = []

    if (
        set(generated_by_date)
        != expected_dates
    ):
        mismatches.append(
            "Generated dates do not match "
            "expected verification dates."
        )

    if (
        set(stored_by_date)
        != expected_dates
    ):
        mismatches.append(
            "Stored dates do not match "
            "expected verification dates."
        )

    for trading_date in sorted(
        expected_dates
    ):
        generated_row = (
            generated_by_date.get(
                trading_date
            )
        )

        stored_row = (
            stored_by_date.get(
                trading_date
            )
        )

        if (
            generated_row is None
            or stored_row is None
        ):
            continue

        for field in INTEGER_FIELDS:
            if int(
                generated_row[field]
            ) != int(
                stored_row[field]
            ):
                mismatches.append(
                    f"{trading_date} "
                    f"{field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

        for field in FLOAT_FIELDS:
            if not _float_matches(
                generated_row[field],
                stored_row[field],
            ):
                mismatches.append(
                    f"{trading_date} "
                    f"{field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

    elapsed = (
        perf_counter()
        - started
    )

    print(
        f"Generated rows  : "
        f"{len(generated)}"
    )
    print(
        f"Stored rows     : "
        f"{len(stored)}"
    )
    print(
        f"Mismatches      : "
        f"{len(mismatches)}"
    )
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    if mismatches:
        print()
        print(
            "Mismatch sample:"
        )

        for mismatch in (
            mismatches[:20]
        ):
            print(
                mismatch
            )

    print()
    print(
        "Result          : "
        + (
            "PASS"
            if not mismatches
            else "FAIL"
        )
    )

    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()