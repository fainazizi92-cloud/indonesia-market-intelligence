from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

LATEST_SNAPSHOT_DATE = text(
    """
    SELECT MAX(snapshot_date)
    FROM instrument_universe_snapshots
    WHERE universe_code =
          'IDX_ALL_CURRENT'
    """
)


EXPECTED_SECTOR_COVERAGE = text(
    """
    WITH current_universe AS (
        SELECT
            u.instrument_id,
            i.sector_code
        FROM instrument_universe_snapshots u
        JOIN instruments i
          ON i.id =
             u.instrument_id
        WHERE u.universe_code =
              'IDX_ALL_CURRENT'
          AND u.snapshot_date =
              :snapshot_date
          AND u.is_member = TRUE
          AND i.exchange =
              'IDX'
          AND i.asset_type =
              'EQUITY'
          AND i.sector_code
              IS NOT NULL
    ),
    benchmark AS (
        SELECT
            tf.trading_date
        FROM technical_features_daily tf
        JOIN instruments i
          ON i.id =
             tf.instrument_id
        WHERE i.symbol =
              'IHSG'
          AND i.exchange =
              'IDX'
          AND i.asset_type =
              'INDEX'
          AND tf.feature_version =
              :feature_version
          AND tf.return_20d
              IS NOT NULL
          AND tf.return_60d
              IS NOT NULL
    ),
    sector_dates AS (
        SELECT DISTINCT
            tf.trading_date,
            u.sector_code
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

        JOIN benchmark b
          ON b.trading_date =
             tf.trading_date

        WHERE tf.feature_version =
              :feature_version
          AND tf.ema200
              IS NOT NULL
          AND p.quality =
              'VALID'
    )
    SELECT
        COUNT(*) AS expected_rows,

        COUNT(
            DISTINCT sector_code
        ) AS expected_sectors,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM sector_dates
    """
)


LOAD_SECTOR_DAILY_INPUTS = text(
    """
    WITH current_universe AS (
        SELECT
            u.instrument_id,
            i.sector_code
        FROM instrument_universe_snapshots u
        JOIN instruments i
          ON i.id =
             u.instrument_id
        WHERE u.universe_code =
              'IDX_ALL_CURRENT'
          AND u.snapshot_date =
              :snapshot_date
          AND u.is_member = TRUE
          AND i.exchange = 'IDX'
          AND i.asset_type = 'EQUITY'
          AND i.sector_code IS NOT NULL
    ),
    benchmark AS (
        SELECT
            tf.trading_date,

            CAST(
                tf.return_20d
                AS DOUBLE PRECISION
            ) AS ihsg_return_20d,

            CAST(
                tf.return_60d
                AS DOUBLE PRECISION
            ) AS ihsg_return_60d

        FROM technical_features_daily tf

        JOIN instruments i
          ON i.id =
             tf.instrument_id

        WHERE i.symbol = 'IHSG'
          AND i.exchange = 'IDX'
          AND i.asset_type = 'INDEX'
          AND tf.feature_version =
              :feature_version
    ),
    base AS (
        SELECT
            tf.trading_date,
            u.sector_code,

            CAST(
                tf.return_20d
                AS DOUBLE PRECISION
            ) AS return_20d,

            CAST(
                tf.return_60d
                AS DOUBLE PRECISION
            ) AS return_60d,

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
          AND tf.ema200 IS NOT NULL
          AND p.quality = 'VALID'
    )
    SELECT
        b.trading_date,
        b.sector_code,

        COUNT(*) AS eligible_count,

        AVG(
            b.return_20d
        ) AS sector_return_20d,

        AVG(
            b.return_60d
        ) AS sector_return_60d,

        MAX(
            benchmark.ihsg_return_20d
        ) AS ihsg_return_20d,

        MAX(
            benchmark.ihsg_return_60d
        ) AS ihsg_return_60d,

        COUNT(*) FILTER (
            WHERE b.previous_close
                  IS NOT NULL
              AND b.close
                  > b.previous_close
        ) AS advances,

        COUNT(*) FILTER (
            WHERE b.previous_close
                  IS NOT NULL
              AND b.close
                  < b.previous_close
        ) AS declines,

        COUNT(*) FILTER (
            WHERE b.previous_close
                  IS NOT NULL
              AND b.close
                  = b.previous_close
        ) AS unchanged,

        100.0 * AVG(
            CASE
                WHEN b.close > b.ema20
                    THEN 1.0
                ELSE 0.0
            END
        ) AS pct_above_ema20,

        100.0 * AVG(
            CASE
                WHEN b.close > b.ema50
                    THEN 1.0
                ELSE 0.0
            END
        ) AS pct_above_ema50,

        100.0 * AVG(
            CASE
                WHEN b.close > b.ema200
                    THEN 1.0
                ELSE 0.0
            END
        ) AS pct_above_ema200,

        COALESCE(
            SUM(b.volume) FILTER (
                WHERE b.previous_close
                      IS NOT NULL
                  AND b.close
                      > b.previous_close
            ),
            0.0
        ) AS up_volume,

        COALESCE(
            SUM(b.volume) FILTER (
                WHERE b.previous_close
                      IS NOT NULL
                  AND b.close
                      < b.previous_close
            ),
            0.0
        ) AS down_volume

    FROM base b

    JOIN benchmark
      ON benchmark.trading_date =
         b.trading_date

    WHERE benchmark.ihsg_return_20d
          IS NOT NULL
      AND benchmark.ihsg_return_60d
          IS NOT NULL

    GROUP BY
        b.trading_date,
        b.sector_code

    ORDER BY
        b.sector_code,
        b.trading_date
    """
)


EXISTING_COVERAGE = text(
    """
    SELECT
        COUNT(*) AS rows,
        COUNT(
            DISTINCT sector_code
        ) AS sectors,
        MIN(trading_date)
            AS first_date,
        MAX(trading_date)
            AS last_date
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
    """
)


UPSERT_SECTOR_SCORE = text(
    """
    INSERT INTO sector_scores_daily (
        trading_date,
        sector_code,
        rotation_label,
        score,
        relative_strength_score,
        breadth_score,
        flow_score,
        volume_score,
        catalyst_score,
        model_version,
        calculated_at
    )
    VALUES (
        :trading_date,
        :sector_code,
        :rotation_label,
        :score,
        :relative_strength_score,
        :breadth_score,
        :flow_score,
        :volume_score,
        :catalyst_score,
        :model_version,
        NOW()
    )
    ON CONFLICT (
        trading_date,
        sector_code,
        model_version
    )
    DO UPDATE SET
        rotation_label =
            EXCLUDED.rotation_label,
        score =
            EXCLUDED.score,
        relative_strength_score =
            EXCLUDED.relative_strength_score,
        breadth_score =
            EXCLUDED.breadth_score,
        flow_score =
            EXCLUDED.flow_score,
        volume_score =
            EXCLUDED.volume_score,
        catalyst_score =
            EXCLUDED.catalyst_score,
        calculated_at =
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


def get_expected_sector_coverage(
    connection: Connection,
    *,
    snapshot_date: date,
    source_id: UUID,
    feature_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        EXPECTED_SECTOR_COVERAGE,
        {
            "snapshot_date":
                snapshot_date,
            "source_id":
                source_id,
            "feature_version":
                feature_version,
        },
    ).mappings().one()

    return dict(row)


def load_sector_daily_inputs(
    connection: Connection,
    *,
    snapshot_date: date,
    source_id: UUID,
    feature_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_SECTOR_DAILY_INPUTS,
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


def get_existing_sector_coverage(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        EXISTING_COVERAGE,
        {
            "model_version":
                model_version
        },
    ).mappings().one()

    return dict(row)


def upsert_sector_scores(
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
            UPSERT_SECTOR_SCORE,
            batch,
        )

        total += len(batch)

    return total