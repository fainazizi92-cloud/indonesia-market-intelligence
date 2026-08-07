from sqlalchemy import text

from imi.db import engine

SUMMARY = text(
    """
    SELECT
        s.status,
        COUNT(*) AS instruments
    FROM eod_ingestion_state s
    JOIN data_sources d
      ON d.id = s.source_id
    WHERE d.code = 'YAHOO_FINANCE'
    GROUP BY s.status
    ORDER BY s.status
    """
)


STATE_TOTAL = text(
    """
    SELECT COUNT(*)
    FROM eod_ingestion_state s
    JOIN data_sources d
      ON d.id = s.source_id
    WHERE d.code = 'YAHOO_FINANCE'
    """
)


PRICE_SUMMARY = text(
    """
    SELECT
        COUNT(*) AS total_rows,
        COUNT(
            DISTINCT p.instrument_id
        ) AS instruments,
        MIN(p.trading_date)
            AS first_date,
        MAX(p.trading_date)
            AS last_date
    FROM market_prices_eod p
    JOIN instruments i
      ON i.id = p.instrument_id
    JOIN data_sources d
      ON d.id = p.source_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND d.code = 'YAHOO_FINANCE'
    """
)


INVALID_OHLC = text(
    """
    SELECT COUNT(*)
    FROM market_prices_eod p
    JOIN instruments i
      ON i.id = p.instrument_id
    JOIN data_sources d
      ON d.id = p.source_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND d.code = 'YAHOO_FINANCE'
      AND (
          p.open <= 0
          OR p.high <= 0
          OR p.low <= 0
          OR p.close <= 0
          OR p.high < p.low
          OR p.high < p.open
          OR p.high < p.close
          OR p.low > p.open
          OR p.low > p.close
      )
    """
)


WEEKEND_ROWS = text(
    """
    SELECT COUNT(*)
    FROM market_prices_eod p
    JOIN instruments i
      ON i.id = p.instrument_id
    JOIN data_sources d
      ON d.id = p.source_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND d.code = 'YAHOO_FINANCE'
      AND EXTRACT(
          ISODOW
          FROM p.trading_date
      ) IN (6, 7)
    """
)


BEFORE_LISTING = text(
    """
    SELECT COUNT(*)
    FROM market_prices_eod p
    JOIN instruments i
      ON i.id = p.instrument_id
    JOIN data_sources d
      ON d.id = p.source_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND d.code = 'YAHOO_FINANCE'
      AND i.listed_date IS NOT NULL
      AND p.trading_date < i.listed_date
    """
)


MISSING_PREVIOUS = text(
    """
    WITH ranked AS (
        SELECT
            p.instrument_id,
            p.source_id,
            p.trading_date,
            p.previous_close,
            ROW_NUMBER() OVER (
                PARTITION BY
                    p.instrument_id,
                    p.source_id
                ORDER BY
                    p.trading_date
            ) AS rn
        FROM market_prices_eod p
        JOIN instruments i
          ON i.id = p.instrument_id
        JOIN data_sources d
          ON d.id = p.source_id
        WHERE i.exchange = 'IDX'
          AND i.asset_type = 'EQUITY'
          AND d.code = 'YAHOO_FINANCE'
    )
    SELECT COUNT(*)
    FROM ranked
    WHERE rn > 1
      AND previous_close IS NULL
    """
)


COMPLETE_NOT_AT_TARGET = text(
    """
    WITH coverage AS (
        SELECT
            s.instrument_id,
            i.symbol,
            s.target_end_date,
            MAX(p.trading_date)
                AS last_price_date
        FROM eod_ingestion_state s
        JOIN instruments i
          ON i.id = s.instrument_id
        JOIN data_sources d
          ON d.id = s.source_id
        LEFT JOIN market_prices_eod p
          ON p.instrument_id =
             s.instrument_id
         AND p.source_id =
             s.source_id
        WHERE d.code = 'YAHOO_FINANCE'
          AND s.status = 'COMPLETE'
        GROUP BY
            s.instrument_id,
            i.symbol,
            s.target_end_date
    )
    SELECT COUNT(*)
    FROM coverage
    WHERE last_price_date IS NULL
       OR last_price_date < target_end_date
    """
)


STALE_COMPLETE_SAMPLE = text(
    """
    WITH coverage AS (
        SELECT
            s.instrument_id,
            i.symbol,
            s.target_end_date,
            MAX(p.trading_date)
                AS last_price_date
        FROM eod_ingestion_state s
        JOIN instruments i
          ON i.id = s.instrument_id
        JOIN data_sources d
          ON d.id = s.source_id
        LEFT JOIN market_prices_eod p
          ON p.instrument_id =
             s.instrument_id
         AND p.source_id =
             s.source_id
        WHERE d.code = 'YAHOO_FINANCE'
          AND s.status = 'COMPLETE'
        GROUP BY
            s.instrument_id,
            i.symbol,
            s.target_end_date
    )
    SELECT
        symbol,
        last_price_date,
        target_end_date,
        (
            target_end_date
            - last_price_date
        ) AS gap_days
    FROM coverage
    WHERE last_price_date IS NOT NULL
      AND last_price_date < target_end_date
    ORDER BY
        gap_days DESC,
        symbol
    LIMIT 20
    """
)


SPARSE_COMPLETE = text(
    """
    SELECT
        i.symbol,
        i.listed_date,
        COUNT(p.trading_date)
            AS rows,
        MIN(p.trading_date)
            AS first_date,
        MAX(p.trading_date)
            AS last_date
    FROM eod_ingestion_state s
    JOIN instruments i
      ON i.id = s.instrument_id
    JOIN data_sources d
      ON d.id = s.source_id
    LEFT JOIN market_prices_eod p
      ON p.instrument_id =
         s.instrument_id
     AND p.source_id =
         s.source_id
    WHERE d.code = 'YAHOO_FINANCE'
      AND s.status = 'COMPLETE'
    GROUP BY
        i.symbol,
        i.listed_date
    HAVING COUNT(p.trading_date) < 30
    ORDER BY
        COUNT(p.trading_date),
        i.symbol
    """
)


TOP_COVERAGE = text(
    """
    SELECT
        i.symbol,
        COUNT(*) AS rows,
        MIN(p.trading_date)
            AS first_date,
        MAX(p.trading_date)
            AS last_date
    FROM market_prices_eod p
    JOIN instruments i
      ON i.id = p.instrument_id
    JOIN data_sources d
      ON d.id = p.source_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND d.code = 'YAHOO_FINANCE'
    GROUP BY
        i.symbol
    ORDER BY
        COUNT(*) DESC
    LIMIT 20
    """
)


NON_TERMINAL_STATES = text(
    """
    SELECT
        i.symbol,
        s.status,
        s.next_start_date,
        s.last_success_date,
        s.attempts,
        s.last_error
    FROM eod_ingestion_state s
    JOIN instruments i
      ON i.id = s.instrument_id
    JOIN data_sources d
      ON d.id = s.source_id
    WHERE d.code = 'YAHOO_FINANCE'
      AND s.status IN (
          'FAILED',
          'PARTIAL',
          'RUNNING'
      )
    ORDER BY
        s.status,
        i.symbol
    LIMIT 50
    """
)


def main() -> None:
    with engine.connect() as connection:
        states = list(
            connection.execute(
                SUMMARY
            )
        )

        state_total = (
            connection.execute(
                STATE_TOTAL
            ).scalar_one()
        )

        price_summary = (
            connection.execute(
                PRICE_SUMMARY
            ).mappings().one()
        )

        invalid_ohlc = (
            connection.execute(
                INVALID_OHLC
            ).scalar_one()
        )

        weekend_rows = (
            connection.execute(
                WEEKEND_ROWS
            ).scalar_one()
        )

        before_listing = (
            connection.execute(
                BEFORE_LISTING
            ).scalar_one()
        )

        missing_previous = (
            connection.execute(
                MISSING_PREVIOUS
            ).scalar_one()
        )

        complete_not_at_target = (
            connection.execute(
                COMPLETE_NOT_AT_TARGET
            ).scalar_one()
        )

        stale_complete_sample = list(
            connection.execute(
                STALE_COMPLETE_SAMPLE
            )
        )

        sparse_complete = list(
            connection.execute(
                SPARSE_COMPLETE
            )
        )

        coverage = list(
            connection.execute(
                TOP_COVERAGE
            )
        )

        non_terminal_states = list(
            connection.execute(
                NON_TERMINAL_STATES
            )
        )

    print(
        "IDX Equity Historical EOD Audit"
    )
    print(
        "-------------------------------"
    )

    print()
    print(
        "Ingestion states:"
    )

    for row in states:
        print(
            f"{row.status:<10} : "
            f"{row.instruments}"
        )

    print(
        f"TOTAL      : {state_total}"
    )

    if state_total != 962:
        print(
            "WARNING    : expected "
            "962 ingestion states"
        )

    print()
    print(
        "Price data:"
    )

    for key, value in (
        price_summary.items()
    ):
        print(
            f"{key:<12} : {value}"
        )

    print()
    print(
        "Data quality:"
    )

    print(
        f"Invalid OHLC           : "
        f"{invalid_ohlc}"
    )
    print(
        f"Weekend rows           : "
        f"{weekend_rows}"
    )
    print(
        f"Before listing         : "
        f"{before_listing}"
    )
    print(
        f"Missing prev close     : "
        f"{missing_previous}"
    )
    print(
        f"Complete not at target : "
        f"{complete_not_at_target}"
    )

    if stale_complete_sample:
        print()
        print(
            "COMPLETE histories ending "
            "before target:"
        )

        for row in stale_complete_sample:
            print(
                (
                    row.symbol,
                    row.last_price_date,
                    row.target_end_date,
                    row.gap_days,
                )
            )

    if sparse_complete:
        print()
        print(
            "Sparse COMPLETE histories "
            "(<30 valid bars):"
        )

        for row in sparse_complete:
            print(
                (
                    row.symbol,
                    row.listed_date,
                    row.rows,
                    row.first_date,
                    row.last_date,
                )
            )

    if non_terminal_states:
        print()
        print(
            "FAILED / PARTIAL / RUNNING "
            "states:"
        )

        for row in non_terminal_states:
            print(
                (
                    row.symbol,
                    row.status,
                    row.next_start_date,
                    row.last_success_date,
                    row.attempts,
                    row.last_error,
                )
            )

    print()
    print(
        "Largest histories:"
    )

    for row in coverage:
        print(row)


if __name__ == "__main__":
    main()
