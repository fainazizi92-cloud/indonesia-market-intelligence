from datetime import date
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

LOAD_CURRENT_EQUITY_CANDIDATES = text(
    """
    WITH latest_snapshot AS (
        SELECT
            MAX(snapshot_date)
                AS snapshot_date
        FROM instrument_universe_snapshots
        WHERE universe_code =
              'IDX_ALL_CURRENT'
    ),
    price_coverage AS (
        SELECT
            instrument_id,
            COUNT(*) AS price_rows,
            MIN(trading_date)
                AS first_price_date,
            MAX(trading_date)
                AS last_price_date
        FROM market_prices_eod
        WHERE source_id =
              :source_id
          AND quality = 'VALID'
        GROUP BY
            instrument_id
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
        i.id AS instrument_id,
        i.symbol,
        i.listed_date,
        s.status,
        s.target_end_date,
        pc.price_rows,
        pc.first_price_date,
        pc.last_price_date,
        COALESCE(
            fc.feature_rows,
            0
        ) AS feature_rows,
        fc.last_feature_date
    FROM instrument_universe_snapshots u
    JOIN latest_snapshot ls
      ON ls.snapshot_date =
         u.snapshot_date
    JOIN instruments i
      ON i.id =
         u.instrument_id
    JOIN eod_ingestion_state s
      ON s.instrument_id =
         i.id
     AND s.source_id =
         :source_id
    JOIN price_coverage pc
      ON pc.instrument_id =
         i.id
    LEFT JOIN feature_coverage fc
      ON fc.instrument_id =
         i.id
    WHERE u.universe_code =
          'IDX_ALL_CURRENT'
      AND u.is_member = TRUE
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND s.status = 'COMPLETE'
    ORDER BY
        i.symbol
    """
)


LOAD_EQUITY_PRICES = text(
    """
    SELECT
        trading_date,
        open,
        high,
        low,
        close,
        volume
    FROM market_prices_eod
    WHERE instrument_id =
          :instrument_id
      AND source_id =
          :source_id
      AND quality =
          'VALID'
    ORDER BY
        trading_date
    """
)


LOAD_IHSG_RETURN20 = text(
    """
    SELECT
        tf.trading_date,
        tf.return_20d
    FROM technical_features_daily tf
    JOIN instruments i
      ON i.id =
         tf.instrument_id
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND tf.feature_version =
          :feature_version
    ORDER BY
        tf.trading_date
    """
)


UPSERT_TECHNICAL_FEATURE = text(
    """
    INSERT INTO technical_features_daily (
        instrument_id,
        trading_date,
        return_1d,
        return_5d,
        return_20d,
        return_60d,
        ema20,
        ema50,
        ema100,
        ema200,
        rsi14,
        atr14,
        volume_z20,
        rs_ihsg_20d,
        rs_sector_20d,
        breakout_flag,
        failed_breakout_flag,
        feature_version,
        calculated_at
    )
    VALUES (
        :instrument_id,
        :trading_date,
        :return_1d,
        :return_5d,
        :return_20d,
        :return_60d,
        :ema20,
        :ema50,
        :ema100,
        :ema200,
        :rsi14,
        :atr14,
        :volume_z20,
        :rs_ihsg_20d,
        :rs_sector_20d,
        :breakout_flag,
        :failed_breakout_flag,
        :feature_version,
        NOW()
    )
    ON CONFLICT (
        instrument_id,
        trading_date,
        feature_version
    )
    DO UPDATE SET
        return_1d =
            EXCLUDED.return_1d,
        return_5d =
            EXCLUDED.return_5d,
        return_20d =
            EXCLUDED.return_20d,
        return_60d =
            EXCLUDED.return_60d,
        ema20 =
            EXCLUDED.ema20,
        ema50 =
            EXCLUDED.ema50,
        ema100 =
            EXCLUDED.ema100,
        ema200 =
            EXCLUDED.ema200,
        rsi14 =
            EXCLUDED.rsi14,
        atr14 =
            EXCLUDED.atr14,
        volume_z20 =
            EXCLUDED.volume_z20,
        rs_ihsg_20d =
            EXCLUDED.rs_ihsg_20d,
        rs_sector_20d =
            EXCLUDED.rs_sector_20d,
        breakout_flag =
            EXCLUDED.breakout_flag,
        failed_breakout_flag =
            EXCLUDED.failed_breakout_flag,
        calculated_at =
            NOW()
    """
)


def load_current_equity_candidates(
    connection: Connection,
    *,
    source_id: UUID,
    feature_version: str,
) -> list:
    return list(
        connection.execute(
            LOAD_CURRENT_EQUITY_CANDIDATES,
            {
                "source_id":
                    source_id,
                "feature_version":
                    feature_version,
            },
        )
    )


def load_equity_prices(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
) -> pd.DataFrame:
    rows = connection.execute(
        LOAD_EQUITY_PRICES,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
        },
    ).mappings().all()

    return pd.DataFrame(
        rows
    )


def load_ihsg_return20(
    connection: Connection,
    *,
    feature_version: str,
) -> dict[
    date,
    float | None,
]:
    rows = connection.execute(
        LOAD_IHSG_RETURN20,
        {
            "feature_version":
                feature_version
        },
    )

    result: dict[
        date,
        float | None,
    ] = {}

    for row in rows:
        value = row.return_20d

        result[
            row.trading_date
        ] = (
            None
            if value is None
            else float(value)
        )

    return result


def upsert_technical_features(
    connection: Connection,
    *,
    instrument_id: UUID,
    features: list[
        dict[str, Any]
    ],
    batch_size: int = 2000,
) -> int:
    if not features:
        return 0

    total = 0

    for start in range(
        0,
        len(features),
        batch_size,
    ):
        batch = features[
            start:
            start + batch_size
        ]

        parameters = []

        for feature in batch:
            parameters.append(
                {
                    "instrument_id":
                        instrument_id,
                    **feature,
                }
            )

        connection.execute(
            UPSERT_TECHNICAL_FEATURE,
            parameters,
        )

        total += len(
            parameters
        )

    return total