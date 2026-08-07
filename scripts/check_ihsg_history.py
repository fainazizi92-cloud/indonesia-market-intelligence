from sqlalchemy import text

from imi.db import engine

SUMMARY_QUERY = text(
    """
    SELECT
        COUNT(*) AS total_rows,
        MIN(mp.trading_date) AS first_date,
        MAX(mp.trading_date) AS last_date,
        COUNT(*) FILTER (
            WHERE mp.quality = 'VALID'
        ) AS valid_rows,
        COUNT(*) FILTER (
            WHERE mp.quality = 'WARNING'
        ) AS warning_rows,
        COUNT(*) FILTER (
            WHERE mp.quality = 'REJECTED'
        ) AS rejected_rows
    FROM market_prices_eod mp
    JOIN instruments i
        ON i.id = mp.instrument_id
    JOIN data_sources ds
        ON ds.id = mp.source_id
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND ds.code = 'YAHOO_FINANCE'
    """
)


LATEST_QUERY = text(
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
    ORDER BY mp.trading_date DESC
    LIMIT 10
    """
)


def main() -> None:
    with engine.connect() as connection:
        summary = connection.execute(
            SUMMARY_QUERY
        ).mappings().one()

        latest_rows = connection.execute(
            LATEST_QUERY
        ).all()

    print(
        "IHSG Historical Data Check"
    )
    print(
        "--------------------------"
    )
    print(
        f"Total rows    : "
        f"{summary['total_rows']}"
    )
    print(
        f"First date    : "
        f"{summary['first_date']}"
    )
    print(
        f"Last date     : "
        f"{summary['last_date']}"
    )
    print(
        f"VALID         : "
        f"{summary['valid_rows']}"
    )
    print(
        f"WARNING       : "
        f"{summary['warning_rows']}"
    )
    print(
        f"REJECTED      : "
        f"{summary['rejected_rows']}"
    )

    print()
    print(
        "Latest 10 observations:"
    )

    for row in latest_rows:
        print(row)


if __name__ == "__main__":
    main()