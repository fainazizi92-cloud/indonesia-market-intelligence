import json
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

LATEST_INTEGRATED_MODEL = text(
    """
    SELECT
        model_version,
        MAX(trading_date)
            AS latest_date,
        MAX(calculated_at)
            AS latest_calculated_at

    FROM integrated_sector_intelligence

    GROUP BY model_version

    ORDER BY
        latest_date DESC,
        latest_calculated_at DESC

    LIMIT 1
    """
)


CURRENT_UNIVERSE_COUNT = text(
    """
    WITH latest AS (
        SELECT MAX(snapshot_date)
            AS snapshot_date

        FROM instrument_universe_snapshots

        WHERE universe_code =
              'IDX_ALL_CURRENT'
    )

    SELECT COUNT(*)

    FROM instrument_universe_snapshots u

    CROSS JOIN latest

    JOIN instruments i
      ON i.id =
         u.instrument_id

    WHERE u.universe_code =
          'IDX_ALL_CURRENT'
      AND u.snapshot_date =
          latest.snapshot_date
      AND u.is_member = TRUE
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND i.sector_code IS NOT NULL
    """
)


SCREENER_INPUT_CTE = """
WITH latest_universe AS (
    SELECT MAX(snapshot_date)
        AS snapshot_date

    FROM instrument_universe_snapshots

    WHERE universe_code =
          'IDX_ALL_CURRENT'
),

current_universe AS (
    SELECT
        u.instrument_id,
        i.symbol,
        i.sector_code

    FROM instrument_universe_snapshots u

    CROSS JOIN latest_universe lu

    JOIN instruments i
      ON i.id =
         u.instrument_id

    WHERE u.universe_code =
          'IDX_ALL_CURRENT'
      AND u.snapshot_date =
          lu.snapshot_date
      AND u.is_member = TRUE
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND i.sector_code IS NOT NULL
),

integrated_range AS (
    SELECT
        MIN(trading_date)
            AS first_date,

        MAX(trading_date)
            AS last_date

    FROM integrated_sector_intelligence

    WHERE model_version =
          :sector_model_version
),

price_window AS (
    SELECT
        mp.instrument_id,
        mp.trading_date,
        mp.close,
        mp.volume,

        AVG(
            mp.close
            * mp.volume
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                19 PRECEDING
                AND CURRENT ROW
        ) AS avg_turnover_20d,

        MAX(
            mp.ingested_at
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                19 PRECEDING
                AND CURRENT ROW
        ) AS turnover_input_updated_at

    FROM market_prices_eod mp

    CROSS JOIN integrated_range r

    WHERE mp.source_id =
          :price_source_id
      AND mp.quality = 'VALID'
      AND mp.close IS NOT NULL
      AND mp.close > 0
      AND mp.volume IS NOT NULL
      AND mp.trading_date
          BETWEEN
              r.first_date - 45
              AND r.last_date
),

base_input AS (
    SELECT
        tf.instrument_id,
        cu.symbol,
        cu.sector_code,
        tf.trading_date,

        p.close,
        p.avg_turnover_20d,

        tf.return_1d,
        tf.return_5d,
        tf.return_20d,
        tf.return_60d,

        tf.ema20,
        tf.ema50,
        tf.ema100,
        tf.ema200,

        tf.rsi14,
        tf.atr14,
        tf.volume_z20,

        tf.rs_ihsg_20d,
        tf.rs_sector_20d,

        tf.breakout_flag,
        tf.failed_breakout_flag,

        tf.feature_version,

        s.integrated_score
            AS sector_score,

        s.integrated_label
            AS sector_integrated_label,

        s.alignment_label
            AS sector_alignment_label,

        s.ownership_stale_flag
            AS sector_ownership_stale_flag,

        s.model_version
            AS sector_model_version,

        m.regime
            AS market_regime,

        m.confidence
            AS market_confidence,

        m.model_version
            AS market_model_version,

        o.as_of_date
            AS ownership_as_of_date,

        o.trend_label
            AS ownership_trend_label,

        o.signal_strength
            AS ownership_signal_strength,

        o.corporate_action_risk
            AS ownership_corporate_action_risk,

        o.snapshot_gap_flag
            AS ownership_snapshot_gap_flag,

        GREATEST(
            tf.calculated_at,
            p.turnover_input_updated_at,
            s.calculated_at,
            m.calculated_at,
            COALESCE(
                o.calculated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            )
        ) AS input_updated_at

    FROM technical_features_daily tf

    JOIN current_universe cu
      ON cu.instrument_id =
         tf.instrument_id

    JOIN price_window p
      ON p.instrument_id =
         tf.instrument_id
     AND p.trading_date =
         tf.trading_date

    JOIN integrated_sector_intelligence s
      ON s.trading_date =
         tf.trading_date
     AND s.sector_code =
         cu.sector_code
     AND s.model_version =
         :sector_model_version

    JOIN market_regimes_daily m
      ON m.trading_date =
         tf.trading_date
     AND m.model_version =
         :market_model_version

    LEFT JOIN LATERAL (
        SELECT
            t.as_of_date,
            t.trend_label,
            t.signal_strength,
            t.corporate_action_risk,
            t.snapshot_gap_flag,
            t.calculated_at

        FROM ownership_trends t

        WHERE t.instrument_id =
              tf.instrument_id
          AND t.source_id =
              :ownership_source_id
          AND t.model_version =
              :ownership_model_version
          AND t.as_of_date
              <= tf.trading_date

        ORDER BY
            t.as_of_date DESC

        LIMIT 1
    ) o
      ON TRUE

    WHERE tf.feature_version =
          :feature_version

      AND tf.return_20d
          IS NOT NULL

      AND tf.ema20
          IS NOT NULL

      AND tf.ema50
          IS NOT NULL

      AND tf.ema200
          IS NOT NULL

      AND tf.rsi14
          IS NOT NULL

      AND tf.atr14
          IS NOT NULL

      AND tf.rs_ihsg_20d
          IS NOT NULL

      AND tf.breakout_flag
          IS NOT NULL

      AND tf.failed_breakout_flag
          IS NOT NULL

      AND p.avg_turnover_20d
          IS NOT NULL
),

ranked_input AS (
    SELECT
        base_input.*,

        PERCENT_RANK() OVER (
            PARTITION BY
                trading_date

            ORDER BY
                avg_turnover_20d
        ) AS liquidity_percentile

    FROM base_input
)
"""


LOAD_ALL_INPUTS = text(
    SCREENER_INPUT_CTE
    + """
    SELECT *

    FROM ranked_input

    ORDER BY
        trading_date,
        instrument_id
    """
)


LOAD_INCREMENTAL_INPUTS = text(
    SCREENER_INPUT_CTE
    + """
    SELECT *

    FROM ranked_input

    WHERE trading_date >
          :after_date

    ORDER BY
        trading_date,
        instrument_id
    """
)


EXPECTED_COVERAGE = text(
    SCREENER_INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS expected_instruments,

        COUNT(
            DISTINCT trading_date
        ) AS expected_dates,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM ranked_input
    """
)


EXPECTED_COVERAGE_AFTER = text(
    SCREENER_INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS expected_instruments,

        COUNT(
            DISTINCT trading_date
        ) AS expected_dates,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM ranked_input

    WHERE trading_date >
          :after_date
    """
)


LATEST_INPUT_STATE = text(
    SCREENER_INPUT_CTE
    + """
    ,
    latest AS (
        SELECT MAX(trading_date)
            AS trading_date

        FROM ranked_input
    )

    SELECT
        latest.trading_date
            AS latest_input_date,

        COUNT(
            r.instrument_id
        ) AS latest_candidate_count,

        COUNT(
            DISTINCT r.sector_code
        ) AS latest_sector_count,

        MAX(
            r.input_updated_at
        ) AS latest_input_updated_at

    FROM latest

    LEFT JOIN ranked_input r
      ON r.trading_date =
         latest.trading_date

    GROUP BY
        latest.trading_date
    """
)


INPUT_STATE_FOR_DATE = text(
    SCREENER_INPUT_CTE
    + """
    SELECT
        CAST(
            :as_of_date
            AS DATE
        ) AS trading_date,

        COUNT(
            instrument_id
        ) AS candidate_count,

        MAX(
            input_updated_at
        ) AS input_updated_at

    FROM ranked_input

    WHERE trading_date =
          :as_of_date
    """
)


STORED_LATEST_STATE = text(
    """
    WITH latest AS (
        SELECT MAX(trading_date)
            AS trading_date

        FROM stock_scores_daily

        WHERE model_version =
              :model_version
    )

    SELECT
        latest.trading_date
            AS latest_date,

        COUNT(
            s.instrument_id
        ) AS latest_count,

        MAX(
            s.input_updated_at
        ) AS input_updated_at

    FROM latest

    LEFT JOIN stock_scores_daily s
      ON s.trading_date =
         latest.trading_date
     AND s.model_version =
         :model_version

    GROUP BY
        latest.trading_date
    """
)


UPSERT_SCORE = text(
    """
    INSERT INTO stock_scores_daily (
        instrument_id,
        trading_date,

        overall_score,
        market_score,
        sector_score,

        fundamental_score,
        valuation_score,

        technical_score,
        liquidity_score,

        flow_score,
        catalyst_score,

        risk_score,
        ownership_score,

        data_completeness,

        status,
        universe_rank,
        sector_rank,

        input_updated_at,
        evidence,

        model_version,
        calculated_at
    )
    VALUES (
        :instrument_id,
        :trading_date,

        :overall_score,
        :market_score,
        :sector_score,

        :fundamental_score,
        :valuation_score,

        :technical_score,
        :liquidity_score,

        :flow_score,
        :catalyst_score,

        :risk_score,
        :ownership_score,

        :data_completeness,

        CAST(
            :status
            AS signal_status
        ),

        :universe_rank,
        :sector_rank,

        :input_updated_at,

        CAST(
            :evidence
            AS JSONB
        ),

        :model_version,
        NOW()
    )

    ON CONFLICT (
        instrument_id,
        trading_date,
        model_version
    )
    DO UPDATE SET
        overall_score =
            EXCLUDED.overall_score,

        market_score =
            EXCLUDED.market_score,

        sector_score =
            EXCLUDED.sector_score,

        fundamental_score =
            EXCLUDED.fundamental_score,

        valuation_score =
            EXCLUDED.valuation_score,

        technical_score =
            EXCLUDED.technical_score,

        liquidity_score =
            EXCLUDED.liquidity_score,

        flow_score =
            EXCLUDED.flow_score,

        catalyst_score =
            EXCLUDED.catalyst_score,

        risk_score =
            EXCLUDED.risk_score,

        ownership_score =
            EXCLUDED.ownership_score,

        data_completeness =
            EXCLUDED.data_completeness,

        status =
            EXCLUDED.status,

        universe_rank =
            EXCLUDED.universe_rank,

        sector_rank =
            EXCLUDED.sector_rank,

        input_updated_at =
            EXCLUDED.input_updated_at,

        evidence =
            EXCLUDED.evidence,

        calculated_at =
            NOW()
    """
)


DELETE_MODEL = text(
    """
    DELETE FROM stock_scores_daily

    WHERE model_version =
          :model_version
    """
)


STORED_COVERAGE = text(
    """
    SELECT
        COUNT(*)
            AS rows,

        COUNT(
            DISTINCT instrument_id
        ) AS instruments,

        COUNT(
            DISTINCT trading_date
        ) AS dates,

        MIN(trading_date)
            AS first_date,

        MAX(trading_date)
            AS last_date

    FROM stock_scores_daily

    WHERE model_version =
          :model_version
    """
)


LATEST_RANKING = text(
    """
    SELECT
        s.instrument_id,
        i.symbol,
        i.sector_code,

        s.trading_date,

        s.overall_score,
        s.market_score,
        s.sector_score,
        s.technical_score,
        s.liquidity_score,
        s.ownership_score,
        s.risk_score,

        s.data_completeness,

        s.status,
        s.universe_rank,
        s.sector_rank,

        s.input_updated_at,
        s.model_version

    FROM stock_scores_daily s

    JOIN instruments i
      ON i.id =
         s.instrument_id

    WHERE s.model_version =
          :model_version
      AND s.trading_date =
          :trading_date

    ORDER BY
        s.universe_rank
    """
)


LOAD_ALL_STORED = text(
    """
    SELECT
        instrument_id,
        trading_date,

        overall_score,
        market_score,
        sector_score,

        fundamental_score,
        valuation_score,

        technical_score,
        liquidity_score,

        flow_score,
        catalyst_score,

        risk_score,
        ownership_score,

        data_completeness,

        status,
        universe_rank,
        sector_rank,

        input_updated_at,
        model_version

    FROM stock_scores_daily

    WHERE model_version =
          :model_version

    ORDER BY
        trading_date,
        instrument_id
    """
)


LOAD_STORED_AFTER = text(
    """
    SELECT
        instrument_id,
        trading_date,

        overall_score,
        market_score,
        sector_score,

        fundamental_score,
        valuation_score,

        technical_score,
        liquidity_score,

        flow_score,
        catalyst_score,

        risk_score,
        ownership_score,

        data_completeness,

        status,
        universe_rank,
        sector_rank,

        input_updated_at,
        model_version

    FROM stock_scores_daily

    WHERE model_version =
          :model_version
      AND trading_date >
          :after_date

    ORDER BY
        trading_date,
        instrument_id
    """
)


RECENT_DATES = text(
    """
    SELECT DISTINCT
        trading_date

    FROM stock_scores_daily

    WHERE model_version =
          :model_version

    ORDER BY trading_date DESC

    LIMIT :limit
    """
)


DUPLICATE_GROUPS = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            instrument_id,
            trading_date,
            model_version

        FROM stock_scores_daily

        WHERE model_version =
              :model_version

        GROUP BY
            instrument_id,
            trading_date,
            model_version

        HAVING COUNT(*) != 1
    ) duplicates
    """
)


STATUS_DISTRIBUTION = text(
    """
    SELECT
        status,
        COUNT(*)
            AS rows

    FROM stock_scores_daily

    WHERE model_version =
          :model_version
      AND trading_date =
          :trading_date

    GROUP BY status

    ORDER BY status
    """
)


def get_latest_integrated_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_INTEGRATED_MODEL
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "Integrated sector "
            "intelligence is unavailable."
        )

    return dict(
        row
    )


def get_current_universe_count(
    connection: Connection,
) -> int:
    return int(
        connection.execute(
            CURRENT_UNIVERSE_COUNT
        ).scalar_one()
    )


def _input_params(
    *,
    price_source_id,
    ownership_source_id,
    feature_version: str,
    sector_model_version: str,
    market_model_version: str,
    ownership_model_version: str,
) -> dict[str, Any]:
    return {
        "price_source_id":
            price_source_id,

        "ownership_source_id":
            ownership_source_id,

        "feature_version":
            feature_version,

        "sector_model_version":
            sector_model_version,

        "market_model_version":
            market_model_version,

        "ownership_model_version":
            ownership_model_version,
    }


def get_latest_input_state(
    connection: Connection,
    *,
    price_source_id,
    ownership_source_id,
    feature_version: str,
    sector_model_version: str,
    market_model_version: str,
    ownership_model_version: str,
) -> dict[str, Any]:
    params = _input_params(
        price_source_id=(
            price_source_id
        ),
        ownership_source_id=(
            ownership_source_id
        ),
        feature_version=(
            feature_version
        ),
        sector_model_version=(
            sector_model_version
        ),
        market_model_version=(
            market_model_version
        ),
        ownership_model_version=(
            ownership_model_version
        ),
    )

    row = connection.execute(
        LATEST_INPUT_STATE,
        params,
    ).mappings().one()

    result = dict(
        row
    )

    if (
        result["latest_input_date"]
        is None
    ):
        raise RuntimeError(
            "No stock screener input "
            "rows are available."
        )

    return result


def get_input_state_for_date(
    connection: Connection,
    *,
    price_source_id,
    ownership_source_id,
    feature_version: str,
    sector_model_version: str,
    market_model_version: str,
    ownership_model_version: str,
    as_of_date: date,
) -> dict[str, Any]:
    params = _input_params(
        price_source_id=(
            price_source_id
        ),
        ownership_source_id=(
            ownership_source_id
        ),
        feature_version=(
            feature_version
        ),
        sector_model_version=(
            sector_model_version
        ),
        market_model_version=(
            market_model_version
        ),
        ownership_model_version=(
            ownership_model_version
        ),
    )

    params[
        "as_of_date"
    ] = as_of_date

    row = connection.execute(
        INPUT_STATE_FOR_DATE,
        params,
    ).mappings().one()

    return dict(
        row
    )


def get_stored_latest_state(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_LATEST_STATE,
        {
            "model_version":
                model_version,
        },
    ).mappings().one()

    return dict(
        row
    )


def get_expected_coverage(
    connection: Connection,
    *,
    price_source_id,
    ownership_source_id,
    feature_version: str,
    sector_model_version: str,
    market_model_version: str,
    ownership_model_version: str,
    after_date: date | None = None,
) -> dict[str, Any]:
    params = _input_params(
        price_source_id=(
            price_source_id
        ),
        ownership_source_id=(
            ownership_source_id
        ),
        feature_version=(
            feature_version
        ),
        sector_model_version=(
            sector_model_version
        ),
        market_model_version=(
            market_model_version
        ),
        ownership_model_version=(
            ownership_model_version
        ),
    )

    if after_date is None:
        row = connection.execute(
            EXPECTED_COVERAGE,
            params,
        ).mappings().one()

    else:
        params[
            "after_date"
        ] = after_date

        row = connection.execute(
            EXPECTED_COVERAGE_AFTER,
            params,
        ).mappings().one()

    return dict(
        row
    )


def load_stock_inputs(
    connection: Connection,
    *,
    price_source_id,
    ownership_source_id,
    feature_version: str,
    sector_model_version: str,
    market_model_version: str,
    ownership_model_version: str,
    after_date: date | None = None,
) -> list[dict[str, Any]]:
    params = _input_params(
        price_source_id=(
            price_source_id
        ),
        ownership_source_id=(
            ownership_source_id
        ),
        feature_version=(
            feature_version
        ),
        sector_model_version=(
            sector_model_version
        ),
        market_model_version=(
            market_model_version
        ),
        ownership_model_version=(
            ownership_model_version
        ),
    )

    if after_date is None:
        rows = connection.execute(
            LOAD_ALL_INPUTS,
            params,
        ).mappings().all()

    else:
        params[
            "after_date"
        ] = after_date

        rows = connection.execute(
            LOAD_INCREMENTAL_INPUTS,
            params,
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def delete_model_rows(
    connection: Connection,
    *,
    model_version: str,
) -> int:
    result = connection.execute(
        DELETE_MODEL,
        {
            "model_version":
                model_version,
        },
    )

    return int(
        result.rowcount or 0
    )


def upsert_stock_scores(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
    batch_size: int = 1000,
) -> int:
    if not rows:
        return 0

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be "
            "greater than zero."
        )

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

        serialized = []

        for row in batch:
            item = dict(
                row
            )

            item["evidence"] = (
                json.dumps(
                    row["evidence"],
                    sort_keys=True,
                )
            )

            serialized.append(
                item
            )

        connection.execute(
            UPSERT_SCORE,
            serialized,
        )

        total += len(
            serialized
        )

    return total


def get_stored_coverage(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_COVERAGE,
        {
            "model_version":
                model_version,
        },
    ).mappings().one()

    return dict(
        row
    )


def load_latest_ranking(
    connection: Connection,
    *,
    model_version: str,
    trading_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LATEST_RANKING,
        {
            "model_version":
                model_version,
            "trading_date":
                trading_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_all_stored(
    connection: Connection,
    *,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_ALL_STORED,
        {
            "model_version":
                model_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_stored_after(
    connection: Connection,
    *,
    model_version: str,
    after_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED_AFTER,
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


def get_recent_dates(
    connection: Connection,
    *,
    model_version: str,
    limit: int,
) -> list[date]:
    rows = connection.execute(
        RECENT_DATES,
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


def get_duplicate_groups(
    connection: Connection,
    *,
    model_version: str,
) -> int:
    return int(
        connection.execute(
            DUPLICATE_GROUPS,
            {
                "model_version":
                    model_version,
            },
        ).scalar_one()
    )


def get_status_distribution(
    connection: Connection,
    *,
    model_version: str,
    trading_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        STATUS_DISTRIBUTION,
        {
            "model_version":
                model_version,
            "trading_date":
                trading_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]

