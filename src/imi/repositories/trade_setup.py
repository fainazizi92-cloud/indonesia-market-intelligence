import json
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

SCREENER_MODEL_PREFIX = (
    "stock_screener_v1_current_%"
)

PIPELINE_NAME = "TRADE_SETUP_V1"


LATEST_SCREENER_MODEL = text(
    """
    SELECT
        model_version,
        MAX(trading_date)
            AS latest_date,
        COUNT(*)
            AS rows

    FROM stock_scores_daily

    WHERE model_version
          LIKE :model_prefix

    GROUP BY model_version

    ORDER BY
        MAX(trading_date) DESC,
        model_version DESC

    LIMIT 1
    """
)


TRADE_SETUP_INPUT_CTE = """
WITH screener_range AS (
    SELECT
        MIN(trading_date)
            AS first_date,

        MAX(trading_date)
            AS last_date

    FROM stock_scores_daily

    WHERE model_version =
          :screener_model_version
),

price_window AS (
    SELECT
        mp.instrument_id,
        mp.trading_date,

        mp.open,
        mp.high,
        mp.low,
        mp.close,

        MIN(
            mp.low
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                10 PRECEDING
                AND 1 PRECEDING
        ) AS prior_low_10d,

        MAX(
            mp.high
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                20 PRECEDING
                AND 1 PRECEDING
        ) AS prior_high_20d,

        MAX(
            mp.high
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                55 PRECEDING
                AND 1 PRECEDING
        ) AS prior_high_55d,

        COUNT(
            mp.low
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                10 PRECEDING
                AND 1 PRECEDING
        ) AS prior_count_10d,

        MAX(
            mp.ingested_at
        ) OVER (
            PARTITION BY
                mp.instrument_id

            ORDER BY
                mp.trading_date

            ROWS BETWEEN
                55 PRECEDING
                AND CURRENT ROW
        ) AS price_input_updated_at

    FROM market_prices_eod mp

    CROSS JOIN screener_range r

    WHERE mp.source_id =
          :price_source_id

      AND mp.quality =
          'VALID'

      AND mp.trading_date
          BETWEEN
              r.first_date - 90
              AND r.last_date
),

candidate_input AS (
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

        s.model_version
            AS screener_model_version,

        tf.ema20,
        tf.ema50,
        tf.rsi14,
        tf.atr14,

        tf.breakout_flag,
        tf.failed_breakout_flag,

        p.open,
        p.high,
        p.low,
        p.close,

        p.prior_low_10d,
        p.prior_high_20d,
        p.prior_high_55d,
        p.prior_count_10d,

        GREATEST(
            s.calculated_at,

            COALESCE(
                s.input_updated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            ),

            COALESCE(
                tf.calculated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            ),

            COALESCE(
                p.price_input_updated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            )
        ) AS input_updated_at

    FROM stock_scores_daily s

    JOIN instruments i
      ON i.id =
         s.instrument_id

    LEFT JOIN technical_features_daily tf
      ON tf.instrument_id =
         s.instrument_id

     AND tf.trading_date =
         s.trading_date

     AND tf.feature_version =
         :feature_version

    LEFT JOIN price_window p
      ON p.instrument_id =
         s.instrument_id

     AND p.trading_date =
         s.trading_date

    WHERE s.model_version =
          :screener_model_version

      AND s.status =
          'BUY_SETUP'
)
"""


LOAD_ALL_INPUTS = text(
    TRADE_SETUP_INPUT_CTE
    + """
    SELECT *

    FROM candidate_input

    ORDER BY
        trading_date,
        instrument_id
    """
)


LOAD_INPUTS_AFTER = text(
    TRADE_SETUP_INPUT_CTE
    + """
    SELECT *

    FROM candidate_input

    WHERE trading_date >
          :after_date

    ORDER BY
        trading_date,
        instrument_id
    """
)


LOAD_INPUTS_FROM = text(
    TRADE_SETUP_INPUT_CTE
    + """
    SELECT *

    FROM candidate_input

    WHERE trading_date >=
          :start_date

    ORDER BY
        trading_date,
        instrument_id
    """
)


EXPECTED_COVERAGE = text(
    TRADE_SETUP_INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS expected_instruments,

        COUNT(
            DISTINCT trading_date
        ) AS expected_candidate_dates,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM candidate_input
    """
)


EXPECTED_COVERAGE_AFTER = text(
    TRADE_SETUP_INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS expected_instruments,

        COUNT(
            DISTINCT trading_date
        ) AS expected_candidate_dates,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM candidate_input

    WHERE trading_date >
          :after_date
    """
)


INPUT_STATE_FOR_DATE = text(
    TRADE_SETUP_INPUT_CTE
    + """
    SELECT
        CAST(
            :as_of_date
            AS DATE
        ) AS trading_date,

        (
            SELECT COUNT(*)

            FROM candidate_input

            WHERE trading_date =
                  :as_of_date
        ) AS candidate_count,

        GREATEST(
            COALESCE(
                (
                    SELECT MAX(
                        input_updated_at
                    )

                    FROM candidate_input

                    WHERE trading_date =
                          :as_of_date
                ),
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            ),

            COALESCE(
                (
                    SELECT MAX(
                        GREATEST(
                            s.calculated_at,

                            COALESCE(
                                s.input_updated_at,
                                TIMESTAMPTZ
                                '1970-01-01 00:00:00+00'
                            )
                        )
                    )

                    FROM stock_scores_daily s

                    WHERE s.model_version =
                          :screener_model_version

                      AND s.trading_date =
                          :as_of_date
                ),
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            )
        ) AS input_updated_at
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
        ) AS output_dates,

        MIN(trading_date)
            AS first_date,

        MAX(trading_date)
            AS last_date

    FROM signals

    WHERE model_version =
          :model_version
    """
)


OUTPUT_COUNT_FOR_DATE = text(
    """
    SELECT COUNT(*)

    FROM signals

    WHERE model_version =
          :model_version

      AND trading_date =
          :trading_date
    """
)


DELETE_MODEL = text(
    """
    DELETE FROM signals

    WHERE model_version =
          :model_version
    """
)


UPSERT_SIGNAL = text(
    """
    INSERT INTO signals (
        instrument_id,
        issued_at,
        trading_date,

        status,

        entry_low,
        entry_high,

        invalidation_price,
        stop_price,
        target_primary,

        expected_rr,

        probability_tp_before_sl,
        expected_value_r,

        horizon_days,
        confidence,

        thesis,
        evidence,

        model_version,
        is_frozen,

        setup_decision,

        risk_per_share,
        risk_pct_price,

        reference_capital,
        risk_budget_pct,

        position_size_shares,
        position_size_lots,

        capital_required,

        input_updated_at,
        decision_reasons
    )
    VALUES (
        :instrument_id,
        NOW(),
        :trading_date,

        CAST(
            :status
            AS signal_status
        ),

        :entry_low,
        :entry_high,

        :invalidation_price,
        :stop_price,
        :target_primary,

        :expected_rr,

        :probability_tp_before_sl,
        :expected_value_r,

        :horizon_days,
        :confidence,

        :thesis,

        CAST(
            :evidence
            AS JSONB
        ),

        :model_version,
        :is_frozen,

        :setup_decision,

        :risk_per_share,
        :risk_pct_price,

        :reference_capital,
        :risk_budget_pct,

        :position_size_shares,
        :position_size_lots,

        :capital_required,

        :input_updated_at,

        CAST(
            :decision_reasons
            AS JSONB
        )
    )

    ON CONFLICT (
        instrument_id,
        trading_date,
        model_version
    )
    DO UPDATE SET
        issued_at =
            NOW(),

        status =
            EXCLUDED.status,

        entry_low =
            EXCLUDED.entry_low,

        entry_high =
            EXCLUDED.entry_high,

        invalidation_price =
            EXCLUDED.invalidation_price,

        stop_price =
            EXCLUDED.stop_price,

        target_primary =
            EXCLUDED.target_primary,

        expected_rr =
            EXCLUDED.expected_rr,

        probability_tp_before_sl =
            EXCLUDED
            .probability_tp_before_sl,

        expected_value_r =
            EXCLUDED.expected_value_r,

        horizon_days =
            EXCLUDED.horizon_days,

        confidence =
            EXCLUDED.confidence,

        thesis =
            EXCLUDED.thesis,

        evidence =
            EXCLUDED.evidence,

        is_frozen =
            EXCLUDED.is_frozen,

        setup_decision =
            EXCLUDED.setup_decision,

        risk_per_share =
            EXCLUDED.risk_per_share,

        risk_pct_price =
            EXCLUDED.risk_pct_price,

        reference_capital =
            EXCLUDED.reference_capital,

        risk_budget_pct =
            EXCLUDED.risk_budget_pct,

        position_size_shares =
            EXCLUDED.position_size_shares,

        position_size_lots =
            EXCLUDED.position_size_lots,

        capital_required =
            EXCLUDED.capital_required,

        input_updated_at =
            EXCLUDED.input_updated_at,

        decision_reasons =
            EXCLUDED.decision_reasons
    """
)


BUILD_STATE = text(
    """
    SELECT
        model_version,
        pipeline_name,
        input_model_version,
        processed_through,
        processed_input_updated_at,
        output_rows,
        updated_at

    FROM pipeline_build_state

    WHERE model_version =
          :model_version
    """
)


UPSERT_BUILD_STATE = text(
    """
    INSERT INTO pipeline_build_state (
        model_version,
        pipeline_name,
        input_model_version,
        processed_through,
        processed_input_updated_at,
        output_rows,
        updated_at
    )
    VALUES (
        :model_version,
        :pipeline_name,
        :input_model_version,
        :processed_through,
        :processed_input_updated_at,
        :output_rows,
        NOW()
    )

    ON CONFLICT (
        model_version
    )
    DO UPDATE SET
        pipeline_name =
            EXCLUDED.pipeline_name,

        input_model_version =
            EXCLUDED.input_model_version,

        processed_through =
            EXCLUDED.processed_through,

        processed_input_updated_at =
            EXCLUDED
            .processed_input_updated_at,

        output_rows =
            EXCLUDED.output_rows,

        updated_at =
            NOW()
    """
)


LATEST_OUTPUT = text(
    """
    SELECT
        s.instrument_id,
        i.symbol,
        i.sector_code,

        s.trading_date,

        s.setup_decision,
        s.status,

        s.entry_low,
        s.entry_high,

        s.invalidation_price,
        s.stop_price,
        s.target_primary,

        s.expected_rr,

        s.risk_per_share,
        s.risk_pct_price,

        s.position_size_lots,
        s.position_size_shares,
        s.capital_required,

        s.decision_reasons

    FROM signals s

    JOIN instruments i
      ON i.id =
         s.instrument_id

    WHERE s.model_version =
          :model_version

      AND s.trading_date =
          :trading_date

    ORDER BY
        CASE
            WHEN s.setup_decision =
                 'ACCEPT'
                THEN 1

            WHEN s.setup_decision =
                 'WATCH'
                THEN 2

            ELSE 3
        END,

        s.expected_rr DESC NULLS LAST,
        i.symbol
    """
)


DECISION_DISTRIBUTION = text(
    """
    SELECT
        setup_decision,
        status,
        COUNT(*)
            AS rows

    FROM signals

    WHERE model_version =
          :model_version

      AND trading_date =
          :trading_date

    GROUP BY
        setup_decision,
        status

    ORDER BY
        setup_decision,
        status
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

        FROM signals

        WHERE model_version =
              :model_version

        GROUP BY
            instrument_id,
            trading_date,
            model_version

        HAVING COUNT(*) > 1
    ) duplicates
    """
)


QUALITY_COUNTS = text(
    """
    SELECT
        COUNT(*) FILTER (
            WHERE probability_tp_before_sl
                  IS NOT NULL
               OR expected_value_r
                  IS NOT NULL
        ) AS forbidden_probability_ev,

        COUNT(*) FILTER (
            WHERE confidence
                  IS NOT NULL
        ) AS nonnull_confidence,

        COUNT(*) FILTER (
            WHERE setup_decision
                  IS NULL
               OR setup_decision
                  NOT IN (
                      'ACCEPT',
                      'WATCH',
                      'REJECT'
                  )
        ) AS invalid_decision,

        COUNT(*) FILTER (
            WHERE setup_decision =
                  'ACCEPT'

              AND (
                    status !=
                    'BUY_SETUP'

                 OR entry_low
                    IS NULL

                 OR entry_high
                    IS NULL

                 OR stop_price
                    IS NULL

                 OR target_primary
                    IS NULL

                 OR expected_rr
                    IS NULL

                 OR expected_rr <
                    1.5

                 OR position_size_lots
                    IS NULL

                 OR position_size_lots <
                    1

                 OR jsonb_array_length(
                        decision_reasons
                    ) != 0
              )
        ) AS invalid_accept,

        COUNT(*) FILTER (
            WHERE setup_decision =
                  'WATCH'

              AND (
                    status !=
                    'WATCH'

                 OR jsonb_array_length(
                        decision_reasons
                    ) = 0
              )
        ) AS invalid_watch,

        COUNT(*) FILTER (
            WHERE setup_decision =
                  'REJECT'

              AND (
                    status !=
                    'AVOID'

                 OR jsonb_array_length(
                        decision_reasons
                    ) = 0
              )
        ) AS invalid_reject,

        COUNT(*) FILTER (
            WHERE is_frozen = TRUE
        ) AS frozen_rows,

        COUNT(*) FILTER (
            WHERE jsonb_typeof(
                decision_reasons
            ) != 'array'
        ) AS invalid_reason_json

    FROM signals

    WHERE model_version =
          :model_version
    """
)


LOAD_ALL_STORED = text(
    """
    SELECT
        instrument_id,
        trading_date,

        status,

        entry_low,
        entry_high,

        invalidation_price,
        stop_price,
        target_primary,

        expected_rr,

        probability_tp_before_sl,
        expected_value_r,

        horizon_days,
        confidence,

        thesis,
        model_version,
        is_frozen,

        setup_decision,

        risk_per_share,
        risk_pct_price,

        reference_capital,
        risk_budget_pct,

        position_size_shares,
        position_size_lots,

        capital_required,

        input_updated_at,
        decision_reasons

    FROM signals

    WHERE model_version =
          :model_version

    ORDER BY
        trading_date,
        instrument_id
    """
)


LOAD_STORED_FROM = text(
    """
    SELECT
        instrument_id,
        trading_date,

        status,

        entry_low,
        entry_high,

        invalidation_price,
        stop_price,
        target_primary,

        expected_rr,

        probability_tp_before_sl,
        expected_value_r,

        horizon_days,
        confidence,

        thesis,
        model_version,
        is_frozen,

        setup_decision,

        risk_per_share,
        risk_pct_price,

        reference_capital,
        risk_budget_pct,

        position_size_shares,
        position_size_lots,

        capital_required,

        input_updated_at,
        decision_reasons

    FROM signals

    WHERE model_version =
          :model_version

      AND trading_date >=
          :start_date

    ORDER BY
        trading_date,
        instrument_id
    """
)


RECENT_SCREENER_DATES = text(
    """
    SELECT DISTINCT
        trading_date

    FROM stock_scores_daily

    WHERE model_version =
          :screener_model_version

    ORDER BY trading_date DESC

    LIMIT :limit
    """
)


def get_latest_screener_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_SCREENER_MODEL,
        {
            "model_prefix":
                SCREENER_MODEL_PREFIX,
        },
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "No Phase 3H stock screener "
            "model is available."
        )

    return dict(
        row
    )


def _input_params(
    *,
    screener_model_version: str,
    feature_version: str,
    price_source_id,
) -> dict[str, Any]:
    return {
        "screener_model_version":
            screener_model_version,

        "feature_version":
            feature_version,

        "price_source_id":
            price_source_id,
    }


def load_trade_setup_inputs(
    connection: Connection,
    *,
    screener_model_version: str,
    feature_version: str,
    price_source_id,
    after_date: date | None = None,
    start_date: date | None = None,
) -> list[dict[str, Any]]:
    if (
        after_date is not None
        and start_date is not None
    ):
        raise ValueError(
            "Use after_date or start_date, "
            "not both."
        )

    params = _input_params(
        screener_model_version=(
            screener_model_version
        ),
        feature_version=(
            feature_version
        ),
        price_source_id=(
            price_source_id
        ),
    )

    if after_date is not None:
        params[
            "after_date"
        ] = after_date

        statement = (
            LOAD_INPUTS_AFTER
        )

    elif start_date is not None:
        params[
            "start_date"
        ] = start_date

        statement = (
            LOAD_INPUTS_FROM
        )

    else:
        statement = (
            LOAD_ALL_INPUTS
        )

    rows = connection.execute(
        statement,
        params,
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_expected_coverage(
    connection: Connection,
    *,
    screener_model_version: str,
    feature_version: str,
    price_source_id,
    after_date: date | None = None,
) -> dict[str, Any]:
    params = _input_params(
        screener_model_version=(
            screener_model_version
        ),
        feature_version=(
            feature_version
        ),
        price_source_id=(
            price_source_id
        ),
    )

    if after_date is None:
        statement = (
            EXPECTED_COVERAGE
        )

    else:
        statement = (
            EXPECTED_COVERAGE_AFTER
        )

        params[
            "after_date"
        ] = after_date

    row = connection.execute(
        statement,
        params,
    ).mappings().one()

    return dict(
        row
    )


def get_input_state_for_date(
    connection: Connection,
    *,
    screener_model_version: str,
    feature_version: str,
    price_source_id,
    as_of_date: date,
) -> dict[str, Any]:
    params = _input_params(
        screener_model_version=(
            screener_model_version
        ),
        feature_version=(
            feature_version
        ),
        price_source_id=(
            price_source_id
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


def get_output_count_for_date(
    connection: Connection,
    *,
    model_version: str,
    trading_date: date,
) -> int:
    return int(
        connection.execute(
            OUTPUT_COUNT_FOR_DATE,
            {
                "model_version":
                    model_version,

                "trading_date":
                    trading_date,
            },
        ).scalar_one()
    )


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


def upsert_trade_setup_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
    batch_size: int = 1000,
) -> int:
    if not rows:
        return 0

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be positive."
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

        serialized: list[
            dict[str, Any]
        ] = []

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

            item[
                "decision_reasons"
            ] = json.dumps(
                row[
                    "decision_reasons"
                ]
            )

            serialized.append(
                item
            )

        connection.execute(
            UPSERT_SIGNAL,
            serialized,
        )

        total += len(
            serialized
        )

    return total


def get_build_state(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        BUILD_STATE,
        {
            "model_version":
                model_version,
        },
    ).mappings().first()

    if row is None:
        return None

    return dict(
        row
    )


def upsert_build_state(
    connection: Connection,
    *,
    model_version: str,
    input_model_version: str,
    processed_through: date,
    processed_input_updated_at,
    output_rows: int,
) -> None:
    connection.execute(
        UPSERT_BUILD_STATE,
        {
            "model_version":
                model_version,

            "pipeline_name":
                PIPELINE_NAME,

            "input_model_version":
                input_model_version,

            "processed_through":
                processed_through,

            "processed_input_updated_at":
                processed_input_updated_at,

            "output_rows":
                output_rows,
        },
    )


def load_latest_output(
    connection: Connection,
    *,
    model_version: str,
    trading_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LATEST_OUTPUT,
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


def get_decision_distribution(
    connection: Connection,
    *,
    model_version: str,
    trading_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        DECISION_DISTRIBUTION,
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


def get_quality_counts(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        QUALITY_COUNTS,
        {
            "model_version":
                model_version,
        },
    ).mappings().one()

    return dict(
        row
    )


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


def load_stored_from(
    connection: Connection,
    *,
    model_version: str,
    start_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED_FROM,
        {
            "model_version":
                model_version,

            "start_date":
                start_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_recent_screener_dates(
    connection: Connection,
    *,
    screener_model_version: str,
    limit: int,
) -> list[date]:
    rows = connection.execute(
        RECENT_SCREENER_DATES,
        {
            "screener_model_version":
                screener_model_version,

            "limit":
                limit,
        },
    )

    return [
        row.trading_date
        for row in rows
    ]