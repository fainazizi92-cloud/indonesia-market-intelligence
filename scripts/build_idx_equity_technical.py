import argparse

from imi.db import engine
from imi.features.equity_technical import (
    calculate_equity_technical_features,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_analytics import (
    load_current_equity_candidates,
    load_equity_prices,
    load_ihsg_return20,
    upsert_technical_features,
)
from imi.repositories.equity_eod import (
    get_source_id,
)

DEFAULT_MIN_BARS = 15
DEFAULT_BATCH_SIZE = 2000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help=(
            "Comma-separated IDX symbols. "
            "Example: BBCA,BBRI,TLKM"
        ),
    )

    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--min-bars",
        type=int,
        default=DEFAULT_MIN_BARS,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.min_bars <= 0:
        raise ValueError(
            "min-bars must be "
            "greater than zero."
        )

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

    requested_symbols = None

    if args.symbols:
        requested_symbols = {
            symbol.strip().upper()
            for symbol
            in args.symbols.split(",")
            if symbol.strip()
        }

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        candidates = (
            load_current_equity_candidates(
                connection,
                source_id=source_id,
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

        ihsg_return20 = (
            load_ihsg_return20(
                connection,
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

    if not ihsg_return20:
        raise RuntimeError(
            "IHSG return_20d benchmark "
            "is unavailable. Build IHSG "
            "analytics first."
        )

    if requested_symbols is not None:
        candidates = [
            candidate
            for candidate
            in candidates
            if candidate.symbol
            in requested_symbols
        ]

    selected = []

    skipped_up_to_date = 0
    skipped_insufficient = 0

    for candidate in candidates:
        if (
            candidate.price_rows
            < args.min_bars
        ):
            skipped_insufficient += 1

            if requested_symbols:
                print(
                    f"SKIP {candidate.symbol}: "
                    f"{candidate.price_rows} "
                    "price bars "
                    f"(< {args.min_bars})"
                )

            continue

        is_up_to_date = (
            candidate.feature_rows
            == candidate.price_rows
            and
            candidate.last_feature_date
            == candidate.last_price_date
        )

        if (
            is_up_to_date
            and not args.force
        ):
            skipped_up_to_date += 1
            continue

        selected.append(
            candidate
        )

    if args.max_symbols is not None:
        selected = selected[
            : args.max_symbols
        ]

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Equity Technical Features"
    )
    print(
        "-----------------------------"
    )
    print(
        f"Feature version      : "
        f"{FEATURE_VERSION}"
    )
    print(
        f"Candidates           : "
        f"{len(candidates)}"
    )
    print(
        f"Build queue          : "
        f"{len(selected)}"
    )
    print(
        f"Already up-to-date   : "
        f"{skipped_up_to_date}"
    )
    print(
        f"Insufficient history : "
        f"{skipped_insufficient}"
    )
    print()

    total_written = 0

    for position, candidate in enumerate(
        selected,
        start=1,
    ):
        print(
            f"[{position}/{len(selected)}] "
            f"{candidate.symbol}"
        )

        with engine.connect() as connection:
            prices = load_equity_prices(
                connection,
                instrument_id=(
                    candidate.instrument_id
                ),
                source_id=source_id,
            )

        if len(prices) < args.min_bars:
            print(
                "  SKIP: insufficient "
                f"history ({len(prices)})"
            )
            continue

        features = (
            calculate_equity_technical_features(
                prices,
                ihsg_return20_by_date=(
                    ihsg_return20
                ),
            )
        )

        with engine.begin() as connection:
            written = (
                upsert_technical_features(
                    connection,
                    instrument_id=(
                        candidate.instrument_id
                    ),
                    features=features,
                    batch_size=(
                        args.batch_size
                    ),
                )
            )

        total_written += written

        latest = (
            features[-1]
            if features
            else None
        )

        print(
            f"  price rows   : "
            f"{len(prices)}"
        )
        print(
            f"  feature rows : "
            f"{written}"
        )

        if latest is not None:
            print(
                "  latest       : "
                f"{latest['trading_date']}"
            )
            print(
                "  RSI14        : "
                f"{latest['rsi14']}"
            )
            print(
                "  EMA200       : "
                f"{latest['ema200']}"
            )
            print(
                "  RS IHSG 20D  : "
                f"{latest['rs_ihsg_20d']}"
            )

        print(
            "  COMPLETE"
        )
        print()

    print(
        "Technical feature build "
        "finished."
    )
    print(
        f"Total rows written: "
        f"{total_written}"
    )


if __name__ == "__main__":
    main()