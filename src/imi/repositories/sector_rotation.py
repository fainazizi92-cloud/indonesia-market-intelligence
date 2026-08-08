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


LATEST_SECTOR_INPUT_STATE = text(
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
    latest_equity AS (
        SELECT
            MAX(
                tf.trading_date
            ) AS trading_date
        FROM technical_features_daily tf
        JOIN current_universe u
          ON u.instrument_id =
             tf.instrument_id
        WHERE tf.feature_version =
              :feature_version
          AND tf.ema200 IS NOT NULL
    ),
    latest_benchmark AS (
        SELECT
            MAX(
                tf.trading_date
            ) AS trading_date
        FROM technical_features_daily tf
        JOIN instruments i
          ON i.id =
             tf.instrument_id
        WHERE i.symbol = 'IHSG'
          AND i.exchange = 'IDX'
          AND i.asset_type = 'INDEX'
          AND tf.feature_version =
              :feature_version
          AND tf.return_20d
              IS NOT NULL
          AND tf.return_60d
              IS NOT NULL
    ),
    candidate AS (
        SELECT LEAST(
            latest_equity.trading_date,
            latest_benchmark.trading_date
        ) AS trading_date
        FROM latest_equity
        CROSS JOIN latest_benchmark
    )
    SELECT
        candidate.trading_date
            AS latest_input_date,

        COUNT(
            DISTINCT u.sector_code
        ) AS latest_sector_count

    FROM candidate

    JOIN technical_features_daily tf
      ON tf.trading_date =
         candidate.trading_date

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

    GROUP BY candidate.trading_date
    """
)


EXISTING_LATEST_STATE = text(
    """
    WITH latest AS (
        SELECT MAX(
            trading_date
        ) AS trading_date
        FROM sector_scores_daily
        WHERE model_version =
              :model_version
    )
    SELECT
        latest.trading_date
            AS latest_date,

        COALESCE(
            (
                SELECT COUNT(
                    DISTINCT sector_code
                )
                FROM sector_scores_daily
                WHERE model_version =
                      :model_version
                  AND trading_date =
                      latest.trading_date
            ),
            0
        ) AS latest_sector_count

    FROM latest
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


LOAD_INCREMENTAL_SECTOR_INPUTS = text(
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
          AND tf.trading_date >
              :after_date
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
          AND tf.trading_date >
              :after_date
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


PRIOR_SCORE_HISTORY = text(
    """
    SELECT
        sector_code,
        trading_date,
        score
    FROM (
        SELECT
            sector_code,
            trading_date,
            score,

            ROW_NUMBER() OVER (
                PARTITION BY sector_code
                ORDER BY trading_date DESC
            ) AS row_number

        FROM sector_scores_daily

        WHERE model_version =
              :model_version
          AND trading_date <=
              :through_date
    ) ranked

    WHERE row_number <=
          :history_size

    ORDER BY
        sector_code,
        trading_date
    """
)


RECENT_SECTOR_DATES = text(
    """
    SELECT DISTINCT
        trading_date
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
    ORDER BY trading_date DESC
    LIMIT :limit
    """
)


LOAD_STORED_SECTOR_ROWS_AFTER = text(
    """
    SELECT
        trading_date,
        sector_code,
        rotation_label,
        score,
        relative_strength_score,
        breadth_score,
        flow_score,
        volume_score,
        catalyst_score,
        model_version
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND trading_date >
          :after_date
    ORDER BY
        sector_code,
        trading_date
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


def get_latest_sector_input_state(
    connection: Connection,
    *,
    snapshot_date: date,
    source_id: UUID,
    feature_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_SECTOR_INPUT_STATE,
        {
            "snapshot_date":
                snapshot_date,
            "source_id":
                source_id,
            "feature_version":
                feature_version,
        },
    ).mappings().one_or_none()

    if row is None:
        raise RuntimeError(
            "Latest sector input state "
            "is unavailable."
        )

    result = dict(row)

    if result["latest_input_date"] is None:
        raise RuntimeError(
            "Latest sector input date "
            "is unavailable."
        )

    if int(
        result["latest_sector_count"]
    ) <= 0:
        raise RuntimeError(
            "Latest sector input contains "
            "no eligible sectors."
        )

    return result


def get_existing_latest_state(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        EXISTING_LATEST_STATE,
        {
            "model_version":
                model_version
        },
    ).mappings().one()

    return dict(row)


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


def load_incremental_sector_inputs(
    connection: Connection,
    *,
    snapshot_date: date,
    source_id: UUID,
    feature_version: str,
    after_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_INCREMENTAL_SECTOR_INPUTS,
        {
            "snapshot_date":
                snapshot_date,
            "source_id":
                source_id,
            "feature_version":
                feature_version,
            "after_date":
                after_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_prior_score_history(
    connection: Connection,
    *,
    model_version: str,
    through_date: date,
    history_size: int,
) -> dict[str, list[float]]:
    rows = connection.execute(
        PRIOR_SCORE_HISTORY,
        {
            "model_version":
                model_version,
            "through_date":
                through_date,
            "history_size":
                history_size,
        },
    ).mappings().all()

    histories: dict[
        str,
        list[float],
    ] = {}

    for row in rows:
        sector_code = str(
            row["sector_code"]
        )

        histories.setdefault(
            sector_code,
            [],
        ).append(
            float(
                row["score"]
            )
        )

    return histories


def get_recent_sector_dates(
    connection: Connection,
    *,
    model_version: str,
    limit: int,
) -> list[date]:
    rows = connection.execute(
        RECENT_SECTOR_DATES,
        {
            "model_version":
                model_version,
            "limit":
                limit,
        },
    )

    return [
        row.trading_date
        for row in rows
    ]


def load_stored_sector_rows_after(
    connection: Connection,
    *,
    model_version: str,
    after_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED_SECTOR_ROWS_AFTER,
        {
            "model_version":
                model_version,
            "after_date":
                after_date,
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