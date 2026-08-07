from statistics import median

from sqlalchemy import text

from imi.db import engine

QUERY = text(
    """
    SELECT
        mp.trading_date,
        mp.open,
        mp.high,
        mp.low,
        mp.close,
        mp.previous_close,
        mp.volume,
        mp.quality
    FROM market_prices_eod mp
    JOIN instruments i
        ON i.id = mp.instrument_id
    JOIN data_sources ds
        ON ds.id = mp.source_id
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND ds.code = 'YAHOO_FINANCE'
    ORDER BY mp.trading_date
    """
)


def main() -> None:
    with engine.connect() as connection:
        rows = (
            connection.execute(QUERY)
            .mappings()
            .all()
        )

    if not rows:
        print("No IHSG Yahoo rows found.")
        return

    weekend_rows = []
    null_ohlc = []
    invalid_ohlc = []
    zero_volume = []
    previous_mismatch = []

    dates = []

    previous_row = None

    for row in rows:
        trading_date = row["trading_date"]

        dates.append(trading_date)

        if trading_date.weekday() >= 5:
            weekend_rows.append(row)

        ohlc = (
            row["open"],
            row["high"],
            row["low"],
            row["close"],
        )

        if any(
            value is None
            for value in ohlc
        ):
            null_ohlc.append(row)

        elif (
            row["high"] < max(ohlc)
            or row["low"] > min(ohlc)
        ):
            invalid_ohlc.append(row)

        if row["volume"] == 0:
            zero_volume.append(row)

        if (
            previous_row is not None
            and row["previous_close"]
            != previous_row["close"]
        ):
            previous_mismatch.append(row)

        previous_row = row

    duplicate_dates = (
        len(dates)
        - len(set(dates))
    )

    gaps = []
    large_gaps = []

    for index in range(
        1,
        len(dates),
    ):
        previous_date = dates[index - 1]
        current_date = dates[index]

        gap_days = (
            current_date
            - previous_date
        ).days

        gaps.append(gap_days)

        if gap_days > 10:
            large_gaps.append(
                (
                    previous_date,
                    current_date,
                    gap_days,
                )
            )

    median_gap = (
        median(gaps)
        if gaps
        else None
    )

    print("IHSG Daily History Audit")
    print("------------------------")

    print(
        f"Total rows            : "
        f"{len(rows)}"
    )
    print(
        f"First date            : "
        f"{dates[0]}"
    )
    print(
        f"Last date             : "
        f"{dates[-1]}"
    )
    print(
        f"Median calendar gap   : "
        f"{median_gap}"
    )
    print(
        f"Weekend rows          : "
        f"{len(weekend_rows)}"
    )
    print(
        f"NULL OHLC             : "
        f"{len(null_ohlc)}"
    )
    print(
        f"Invalid OHLC          : "
        f"{len(invalid_ohlc)}"
    )
    print(
        f"Duplicate dates       : "
        f"{duplicate_dates}"
    )
    print(
        f"Previous-close errors : "
        f"{len(previous_mismatch)}"
    )
    print(
        f"Zero-volume rows      : "
        f"{len(zero_volume)}"
    )
    print(
        f"Gaps > 10 days        : "
        f"{len(large_gaps)}"
    )

    if large_gaps:
        print()
        print("Large calendar gaps:")

        for (
            previous_date,
            current_date,
            gap_days,
        ) in large_gaps:
            print(
                f"{previous_date}"
                f" -> {current_date}"
                f" ({gap_days} days)"
            )

    if weekend_rows:
        print()
        print("Weekend samples:")

        for row in weekend_rows[:5]:
            print(
                row["trading_date"],
                row["close"],
            )


if __name__ == "__main__":
    main()