import argparse
import math
from datetime import timedelta
from time import perf_counter
from typing import Any

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
    get_latest_integrated_model_state,
    get_recent_dates,
    load_stock_inputs,
    load_stored_after,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify incremental stock "
            "screener parity."
        )
    )

    parser.add_argument(
        "--dates",
        type=int,
        default=10,
    )

    return parser.parse_args()


def float_matches(
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

    if args.dates <= 0:
        raise ValueError(
            "dates must be greater "
            "than zero."
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
        recent_dates = (
            get_recent_dates(
                connection,
                model_version=(
                    model_version
                ),
                limit=args.dates,
            )
        )

    if len(recent_dates) < args.dates:
        raise RuntimeError(
            "Not enough stored stock "
            "screener dates."
        )

    expected_dates = set(
        recent_dates
    )

    earliest = min(
        expected_dates
    )

    after_date = (
        earliest
        - timedelta(
            days=1
        )
    )

    with engine.connect() as connection:
        inputs = (
            load_stock_inputs(
                connection,
                **input_kwargs,
                after_date=(
                    after_date
                ),
            )
        )

        stored = (
            load_stored_after(
                connection,
                model_version=(
                    model_version
                ),
                after_date=(
                    after_date
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
            stored_keys
            - generated_keys
        )

        unexpected = (
            generated_keys
            - stored_keys
        )

        if missing:
            mismatches.append(
                "Missing generated keys: "
                f"{list(missing)[:20]}"
            )

        if unexpected:
            mismatches.append(
                "Unexpected generated keys: "
                f"{list(unexpected)[:20]}"
            )

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

    elapsed = (
        perf_counter()
        - started
    )

    print(
        "IDX Stock Screener "
        "Incremental Verification"
    )
    print(
        "-----------------------------"
    )
    print(
        f"Dates           : "
        f"{args.dates}"
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
            mismatches[:30]
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