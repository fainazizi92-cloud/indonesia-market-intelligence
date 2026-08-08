from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

LATEST_SNAPSHOT_DATE = text(
    """
    SELECT MAX(snapshot_date)
    FROM instrument_universe_snapshots
    WHERE universe_code = 'IDX_ALL_CURRENT'
    """
)


LOAD_DAILY_BREADTH_INPUTS = text(
    """
    WITH current_universe AS (
        SELECT instrument_id
        FROM instrument_universe_snapshots
        WHERE universe_code = 'IDX_ALL_CURRENT'
          AND snapshot_date = :snapshot_date
          AND is_member = TRUE
    ),
    base AS (
        SELECT
            tf.instrument_id,
            tf.trading_date,

            CAST(
                p.close
                AS DOUBLE PRECISION
            ) AS close,

            CAST(
                p.previous_close
                AS DOUBLE PRECISION
            ) AS previous_close,

            CAST(
                p.volume
                AS DOUBLE PRECISION
            ) AS volume,

            CAST(
                tf.ema20
                AS DOUBLE PRECISION
            ) AS ema20,

            CAST(
                tf.ema50
                AS DOUBLE PRECISION
            ) AS ema50,

            CAST(
                tf.ema200
                AS DOUBLE PRECISION
            ) AS ema200

        FROM technical_features_daily tf

        JOIN current_universe u
          ON u.instrument_id =
             tf.instrument_id

        JOIN market_prices_eod p
          ON p.instrument_id =
             tf.instrument_id
         AND p.trading_date =
             tf.trading_date
         AND p.source_id =
             :source_id

        WHERE tf.feature_version =
              :feature_version
          AND p.quality = 'VALID'
    ),
    rolling AS (
        SELECT
            base.*,

            COUNT(close) OVER (
                PARTITION BY instrument_id
                ORDER BY trading_date
                ROWS BETWEEN
                    20 PRECEDING
                    AND 1 PRECEDING
            ) AS prior_20_count,

            MAX(close) OVER (
                PARTITION BY instrument_id
                ORDER BY trading_date
                ROWS BETWEEN
                    20 PRECEDING
                    AND 1 PRECEDING
            ) AS prior_20_high,

            MIN(close) OVER (
                PARTITION BY instrument_id
                ORDER BY trading_date
                ROWS BETWEEN
                    20 PRECEDING
                    AND 1 PRECEDING
            ) AS prior_20_low,

            COUNT(close) OVER (
                PARTITION BY instrument_id
                ORDER BY trading_date
                ROWS BETWEEN
                    252 PRECEDING
                    AND 1 PRECEDING
            ) AS prior_252_count,

            MAX(close) OVER (
                PARTITION BY instrument_id
                ORDER BY trading_date
                ROWS BETWEEN
                    252 PRECEDING
                    AND 1 PRECEDING
            ) AS prior_252_high,

            MIN(close) OVER (
                PARTITION BY instrument_id
                ORDER BY trading_date
                ROWS BETWEEN
                    252 PRECEDING
                    AND 1 PRECEDING
            ) AS prior_252_low

        FROM base
    ),
    eligible AS (
        SELECT *
        FROM rolling
        WHERE ema200 IS NOT NULL
    )
    SELECT
        trading_date,

        COUNT(*) AS eligible_count,

        COUNT(*) FILTER (
            WHERE previous_close
                  IS NOT NULL
              AND close
                  > previous_close
        ) AS advances,

        COUNT(*) FILTER (
            WHERE previous_close
                  IS NOT NULL
              AND close
                  < previous_close
        ) AS declines,

        COUNT(*) FILTER (
            WHERE previous_close
                  IS NOT NULL
              AND close
                  = previous_close
        ) AS unchanged,

        COUNT(*) FILTER (
            WHERE prior_20_count = 20
              AND close > prior_20_high
        ) AS new_high_20d,

        COUNT(*) FILTER (
            WHERE prior_20_count = 20
              AND close < prior_20_low
        ) AS new_low_20d,

        COUNT(*) FILTER (
            WHERE prior_252_count = 252
              AND close > prior_252_high
        ) AS new_high_52w,

        COUNT(*) FILTER (
            WHERE prior_252_count = 252
              AND close < prior_252_low
        ) AS new_low_52w,

        100.0 * AVG(
            CASE
                WHEN close > ema20
                    THEN 1.0
                ELSE 0.0
            END
        ) AS pct_above_ema20,

        100.0 * AVG(
            CASE
                WHEN close > ema50
                    THEN 1.0
                ELSE 0.0
            END
        ) AS pct_above_ema50,

        100.0 * AVG(
            CASE
                WHEN close > ema200
                    THEN 1.0
                ELSE 0.0
            END
        ) AS pct_above_ema200,

        COALESCE(
            SUM(volume) FILTER (
                WHERE previous_close
                      IS NOT NULL
                  AND close
                      > previous_close
            ),
            0.0
        ) AS up_volume,

        COALESCE(
            SUM(volume) FILTER (
                WHERE previous_close
                      IS NOT NULL
                  AND close
                      < previous_close
            ),
            0.0
        ) AS down_volume

    FROM eligible

    GROUP BY trading_date

    ORDER BY trading_date
    """
)


EXISTING_COVERAGE = text(
    """
    SELECT
        COUNT(*) AS rows,
        MIN(trading_date)
            AS first_date,
        MAX(trading_date)
            AS last_date
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
    """
)


UPSERT_BREADTH = text(
    """
    INSERT INTO market_breadth_daily (
        trading_date,
        universe_code,
        advances,
        declines,
        unchanged,
        new_high_20d,
        new_low_20d,
        new_high_52w,
        new_low_52w,
        pct_above_ema20,
        pct_above_ema50,
        pct_above_ema200,
        up_volume,
        down_volume,
        breadth_score,
        source_id,
        ingested_at
    )
    VALUES (
        :trading_date,
        :universe_code,
        :advances,
        :declines,
        :unchanged,
        :new_high_20d,
        :new_low_20d,
        :new_high_52w,
        :new_low_52w,
        :pct_above_ema20,
        :pct_above_ema50,
        :pct_above_ema200,
        :up_volume,
        :down_volume,
        :breadth_score,
        :source_id,
        NOW()
    )
    ON CONFLICT (
        trading_date,
        universe_code
    )
    DO UPDATE SET
        advances =
            EXCLUDED.advances,
        declines =
            EXCLUDED.declines,
        unchanged =
            EXCLUDED.unchanged,
        new_high_20d =
            EXCLUDED.new_high_20d,
        new_low_20d =
            EXCLUDED.new_low_20d,
        new_high_52w =
            EXCLUDED.new_high_52w,
        new_low_52w =
            EXCLUDED.new_low_52w,
        pct_above_ema20 =
            EXCLUDED.pct_above_ema20,
        pct_above_ema50 =
            EXCLUDED.pct_above_ema50,
        pct_above_ema200 =
            EXCLUDED.pct_above_ema200,
        up_volume =
            EXCLUDED.up_volume,
        down_volume =
            EXCLUDED.down_volume,
        breadth_score =
            EXCLUDED.breadth_score,
        source_id =
            EXCLUDED.source_id,
        ingested_at =
            NOW()
    """
)


def get_latest_snapshot_date(
    connection: Connection,
) -> date:
    value = connection.execute(
        LATEST_SNAPSHOT_DATE
    ).scalar_one()

    if value is None:
        raise RuntimeError(
            "IDX current-universe snapshot "
            "is unavailable."
        )

    return value


def load_daily_breadth_inputs(
    connection: Connection,
    *,
    snapshot_date: date,
    source_id: UUID,
    feature_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_DAILY_BREADTH_INPUTS,
        {
            "snapshot_date":
                snapshot_date,
            "source_id":
                source_id,
            "feature_version":
                feature_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_existing_coverage(
    connection: Connection,
    *,
    universe_code: str,
) -> dict[str, Any]:
    row = connection.execute(
        EXISTING_COVERAGE,
        {
            "universe_code":
                universe_code
        },
    ).mappings().one()

    return dict(row)


def upsert_breadth_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
    batch_size: int = 2000,
) -> int:
    if not rows:
        return 0

    total = 0

    for start in range(
        0,
        len(rows),
        batch_size,
    ):
        batch = rows[
            start:
            start + batch_size
        ]

        connection.execute(
            UPSERT_BREADTH,
            batch,
        )

        total += len(batch)

    return total