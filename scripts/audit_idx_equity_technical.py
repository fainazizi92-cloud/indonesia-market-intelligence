from sqlalchemy import text

from imi.db import engine
from imi.features.technical import (
    FEATURE_VERSION,
)

SUMMARY = text(
    """
    SELECT
        COUNT(*) AS feature_rows,
        COUNT(
            DISTINCT tf.instrument_id
        ) AS instruments,
        MIN(tf.trading_date)
            AS first_date,
        MAX(tf.trading_date)
            AS last_date
    FROM technical_features_daily tf
    JOIN instruments i
      ON i.id =
         tf.instrument_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND tf.feature_version =
          :feature_version
    """
)


COVERAGE = text(
    """
    WITH latest_snapshot AS (
        SELECT
            MAX(snapshot_date)
                AS snapshot_date
        FROM instrument_universe_snapshots
        WHERE universe_code =
              'IDX_ALL_CURRENT'
    ),
    yahoo_source AS (
        SELECT id
        FROM data_sources
        WHERE code =
              'YAHOO_FINANCE'
    ),
    price_coverage AS (
        SELECT
            p.instrument_id,
            COUNT(*) AS price_rows,
            MAX(p.trading_date)
                AS last_price_date
        FROM market_prices_eod p
        JOIN yahoo_source y
          ON y.id = p.source_id
        WHERE p.quality = 'VALID'
        GROUP BY
            p.instrument_id
    ),
    feature_coverage AS (
        SELECT
            instrument_id,
            COUNT(*) AS feature_rows,
            MAX(trading_date)
                AS last_feature_date
        FROM technical_features_daily
        WHERE feature_version =
              :feature_version
        GROUP BY
            instrument_id
    )
    SELECT
        COUNT(*) FILTER (
            WHERE pc.price_rows >= 15
        ) AS eligible_instruments,

        COUNT(*) FILTER (
            WHERE pc.price_rows >= 200
        ) AS screen_eligible,

        COUNT(*) FILTER (
            WHERE pc.price_rows < 15
        ) AS insufficient_history,

        COUNT(*) FILTER (
            WHERE fc.instrument_id
                  IS NOT NULL
        ) AS feature_instruments,

        COUNT(*) FILTER (
            WHERE pc.price_rows >= 15
              AND fc.feature_rows =
                  pc.price_rows
              AND fc.last_feature_date =
                  pc.last_price_date
        ) AS up_to_date,

        COUNT(*) FILTER (
            WHERE pc.price_rows >= 15
              AND (
                  fc.instrument_id
                      IS NULL
                  OR fc.feature_rows
                     <> pc.price_rows
                  OR fc.last_feature_date
                     IS DISTINCT FROM
                     pc.last_price_date
              )
        ) AS stale_or_missing
    FROM instrument_universe_snapshots u
    JOIN latest_snapshot ls
      ON ls.snapshot_date =
         u.snapshot_date
    JOIN instruments i
      ON i.id =
         u.instrument_id
    JOIN yahoo_source y
      ON TRUE
    JOIN eod_ingestion_state s
      ON s.instrument_id =
         i.id
     AND s.source_id =
         y.id
    LEFT JOIN price_coverage pc
      ON pc.instrument_id =
         i.id
    LEFT JOIN feature_coverage fc
      ON fc.instrument_id =
         i.id
    WHERE u.universe_code =
          'IDX_ALL_CURRENT'
      AND u.is_member = TRUE
      AND i.exchange = 'IDX'
      AND i.asset_type =
          'EQUITY'
      AND s.status =
          'COMPLETE'
      AND pc.instrument_id
          IS NOT NULL
    """
)


ORPHAN_FEATURES = text(
    """
    SELECT COUNT(*)
    FROM technical_features_daily tf
    JOIN instruments i
      ON i.id =
         tf.instrument_id
    LEFT JOIN data_sources d
      ON d.code =
         'YAHOO_FINANCE'
    LEFT JOIN market_prices_eod p
      ON p.instrument_id =
         tf.instrument_id
     AND p.trading_date =
         tf.trading_date
     AND p.source_id =
         d.id
    WHERE i.exchange = 'IDX'
      AND i.asset_type =
          'EQUITY'
      AND tf.feature_version =
          :feature_version
      AND p.instrument_id IS NULL
    """
)


RS_SECTOR_NON_NULL = text(
    """
    SELECT COUNT(*)
    FROM technical_features_daily tf
    JOIN instruments i
      ON i.id =
         tf.instrument_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type =
          'EQUITY'
      AND tf.feature_version =
          :feature_version
      AND tf.rs_sector_20d
          IS NOT NULL
    """
)


INVALID_RSI = text(
    """
    SELECT COUNT(*)
    FROM technical_features_daily tf
    JOIN instruments i
      ON i.id =
         tf.instrument_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type =
          'EQUITY'
      AND tf.feature_version =
          :feature_version
      AND tf.rsi14 IS NOT NULL
      AND (
          tf.rsi14 < 0
          OR tf.rsi14 > 100
      )
    """
)


INVALID_ATR = text(
    """
    SELECT COUNT(*)
    FROM technical_features_daily tf
    JOIN instruments i
      ON i.id =
         tf.instrument_id
    WHERE i.exchange = 'IDX'
      AND i.asset_type =
          'EQUITY'
      AND tf.feature_version =
          :feature_version
      AND tf.atr14 IS NOT NULL
      AND tf.atr14 < 0
    """
)


LATEST_SAMPLE = text(
    """
    WITH latest AS (
        SELECT
            tf.*,
            ROW_NUMBER() OVER (
                PARTITION BY
                    tf.instrument_id
                ORDER BY
                    tf.trading_date DESC
            ) AS rn
        FROM technical_features_daily tf
        JOIN instruments i
          ON i.id =
             tf.instrument_id
        WHERE i.exchange = 'IDX'
          AND i.asset_type =
              'EQUITY'
          AND tf.feature_version =
              :feature_version
    )
    SELECT
        i.symbol,
        l.trading_date,
        l.return_20d,
        l.ema20,
        l.ema50,
        l.ema200,
        l.rsi14,
        l.atr14,
        l.volume_z20,
        l.rs_ihsg_20d,
        l.breakout_flag,
        l.failed_breakout_flag
    FROM latest l
    JOIN instruments i
      ON i.id =
         l.instrument_id
    WHERE l.rn = 1
    ORDER BY
        i.symbol
    LIMIT 20
    """
)


def main() -> None:
    parameters = {
        "feature_version":
            FEATURE_VERSION
    }

    with engine.connect() as connection:
        summary = (
            connection.execute(
                SUMMARY,
                parameters,
            ).mappings().one()
        )

        coverage = (
            connection.execute(
                COVERAGE,
                parameters,
            ).mappings().one()
        )

        orphan_features = (
            connection.execute(
                ORPHAN_FEATURES,
                parameters,
            ).scalar_one()
        )

        rs_sector_non_null = (
            connection.execute(
                RS_SECTOR_NON_NULL,
                parameters,
            ).scalar_one()
        )

        invalid_rsi = (
            connection.execute(
                INVALID_RSI,
                parameters,
            ).scalar_one()
        )

        invalid_atr = (
            connection.execute(
                INVALID_ATR,
                parameters,
            ).scalar_one()
        )

        latest_sample = list(
            connection.execute(
                LATEST_SAMPLE,
                parameters,
            )
        )

    print(
        "IDX Equity Technical Feature Audit"
    )
    print(
        "----------------------------------"
    )

    print()
    print(
        f"Feature version : "
        f"{FEATURE_VERSION}"
    )

    print()
    print(
        "Feature data:"
    )

    for key, value in (
        summary.items()
    ):
        print(
            f"{key:<18} : {value}"
        )

    print()
    print(
        "Coverage:"
    )

    for key, value in (
        coverage.items()
    ):
        print(
            f"{key:<20} : {value}"
        )

    print()
    print(
        "Quality:"
    )
    print(
        f"Orphan features      : "
        f"{orphan_features}"
    )
    print(
        f"Invalid RSI          : "
        f"{invalid_rsi}"
    )
    print(
        f"Invalid ATR          : "
        f"{invalid_atr}"
    )
    print(
        f"RS sector non-null   : "
        f"{rs_sector_non_null}"
    )

    print()
    print(
        "Latest feature sample:"
    )

    for row in latest_sample:
        print(row)


if __name__ == "__main__":
    main()