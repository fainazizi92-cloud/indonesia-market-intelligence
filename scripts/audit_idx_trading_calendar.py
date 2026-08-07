from sqlalchemy import text

from imi.db import engine

SUMMARY = text(
    """
    SELECT
        day_type,
        COUNT(*)
    FROM trading_calendar
    WHERE market = 'IDX'
    GROUP BY day_type
    ORDER BY day_type
    """
)


MISSING_OBSERVED = text(
    """
    SELECT COUNT(*)
    FROM market_prices_eod mp
    JOIN instruments i
        ON i.id = mp.instrument_id
    JOIN data_sources ds
        ON ds.id = mp.source_id
    LEFT JOIN trading_calendar tc
        ON tc.trading_date =
            mp.trading_date
       AND tc.market = 'IDX'
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND ds.code = 'YAHOO_FINANCE'
      AND mp.quality = 'VALID'
      AND (
          tc.trading_date IS NULL
          OR tc.is_trading_day = FALSE
      )
    """
)


TRADING_WITHOUT_PRICE = text(
    """
    SELECT COUNT(*)
    FROM trading_calendar tc
    LEFT JOIN market_prices_eod mp
        ON mp.trading_date =
            tc.trading_date
    LEFT JOIN instruments i
        ON i.id = mp.instrument_id
       AND i.symbol = 'IHSG'
       AND i.exchange = 'IDX'
    LEFT JOIN data_sources ds
        ON ds.id = mp.source_id
       AND ds.code = 'YAHOO_FINANCE'
    WHERE tc.market = 'IDX'
      AND tc.is_trading_day = TRUE
      AND i.id IS NULL
    """
)


WEEKEND_TRADING = text(
    """
    SELECT COUNT(*)
    FROM trading_calendar
    WHERE market = 'IDX'
      AND is_trading_day = TRUE
      AND EXTRACT(
          ISODOW FROM trading_date
      ) IN (6, 7)
    """
)


def main() -> None:
    with engine.connect() as connection:
        summary = list(
            connection.execute(
                SUMMARY
            )
        )

        missing_observed = (
            connection.execute(
                MISSING_OBSERVED
            ).scalar_one()
        )

        trading_without_price = (
            connection.execute(
                TRADING_WITHOUT_PRICE
            ).scalar_one()
        )

        weekend_trading = (
            connection.execute(
                WEEKEND_TRADING
            ).scalar_one()
        )

    print(
        "IDX Trading Calendar Audit"
    )
    print(
        "--------------------------"
    )

    for row in summary:
        print(
            f"{row[0]:24}: {row[1]}"
        )

    print()
    print(
        "Observed price dates "
        "missing calendar : "
        f"{missing_observed}"
    )
    print(
        "Trading calendar "
        "without IHSG bar : "
        f"{trading_without_price}"
    )
    print(
        "Weekend trading rows     : "
        f"{weekend_trading}"
    )


if __name__ == "__main__":
    main()