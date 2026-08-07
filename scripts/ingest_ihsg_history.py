import argparse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from imi.collectors.yahoo_chart import (
    fetch_yahoo_daily_period,
)
from imi.db import engine
from imi.repositories.market_prices import (
    get_instrument_id,
    get_source_id,
    rebuild_previous_close,
    upsert_market_prices,
)
from imi.validators.market_prices import (
    validate_market_price,
)

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

DEFAULT_START = date(
    1990,
    5,
    1,
)


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill IHSG daily history "
            "using explicit Yahoo periods."
        )
    )

    parser.add_argument(
        "--start",
        type=parse_date,
        default=DEFAULT_START,
    )

    parser.add_argument(
        "--end",
        type=parse_date,
        default=datetime.now(
            JAKARTA_TZ
        ).date(),
    )

    parser.add_argument(
        "--chunk-days",
        type=int,
        default=3000,
    )

    return parser.parse_args()


def iter_chunks(
    *,
    start: date,
    end: date,
    chunk_days: int,
):
    current = start

    while current <= end:
        chunk_end = min(
            current
            + timedelta(
                days=chunk_days - 1
            ),
            end,
        )

        yield current, chunk_end

        current = (
            chunk_end
            + timedelta(days=1)
        )


def main() -> None:
    args = parse_args()

    if args.chunk_days <= 0:
        raise ValueError(
            "chunk-days must be > 0"
        )

    if args.end < args.start:
        raise ValueError(
            "End date must not be "
            "earlier than start date."
        )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IHSG Clean Daily Backfill"
    )
    print(
        "--------------------------"
    )
    print(
        f"Start       : {args.start}"
    )
    print(
        f"End         : {args.end}"
    )
    print(
        f"Chunk days  : {args.chunk_days}"
    )
    print()

    total_complete = 0
    total_incomplete = 0
    total_accepted = 0
    total_rejected = 0
    total_upserted = 0

    with engine.begin() as connection:
        instrument_id = get_instrument_id(
            connection,
            symbol="IHSG",
            exchange="IDX",
            asset_type="INDEX",
        )

        source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        for (
            chunk_start,
            chunk_end,
        ) in iter_chunks(
            start=args.start,
            end=args.end,
            chunk_days=args.chunk_days,
        ):
            print(
                "Fetching "
                f"{chunk_start} "
                "through "
                f"{chunk_end}"
            )

            result = (
                fetch_yahoo_daily_period(
                    symbol="^JKSE",
                    start=chunk_start,
                    end=chunk_end,
                )
            )

            print(
                "  granularity : "
                f"{result.data_granularity}"
            )
            print(
                "  median gap  : "
                f"{result.median_gap_days}"
            )
            print(
                "  bars        : "
                f"{len(result.bars)}"
            )
            print(
                "  incomplete  : "
                f"{result.skipped_incomplete}"
            )

            accepted = []

            rejected_count = 0

            for bar in result.bars:
                if not (
                    chunk_start
                    <= bar.trading_date
                    <= chunk_end
                ):
                    continue

                validation = (
                    validate_market_price(
                        bar
                    )
                )

                if (
                    validation.record.quality
                    == "REJECTED"
                ):
                    rejected_count += 1
                    continue

                accepted.append(
                    validation.record
                )

            upserted = (
                upsert_market_prices(
                    connection,
                    instrument_id=(
                        instrument_id
                    ),
                    source_id=source_id,
                    records=accepted,
                )
            )

            total_complete += len(
                result.bars
            )

            total_incomplete += (
                result.skipped_incomplete
            )

            total_accepted += len(
                accepted
            )

            total_rejected += (
                rejected_count
            )

            total_upserted += upserted

            print(
                "  accepted    : "
                f"{len(accepted)}"
            )
            print(
                "  rejected    : "
                f"{rejected_count}"
            )
            print(
                "  upserted    : "
                f"{upserted}"
            )
            print()

        rebuild_previous_close(
            connection,
            instrument_id=instrument_id,
            source_id=source_id,
        )

    print(
        "Backfill complete."
    )
    print(
        f"Complete bars   : "
        f"{total_complete}"
    )
    print(
        f"Incomplete skip : "
        f"{total_incomplete}"
    )
    print(
        f"Accepted bars   : "
        f"{total_accepted}"
    )
    print(
        f"Rejected bars   : "
        f"{total_rejected}"
    )
    print(
        f"Upserted bars   : "
        f"{total_upserted}"
    )


if __name__ == "__main__":
    main()