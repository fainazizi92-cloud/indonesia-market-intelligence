import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

OUTCOME_MODEL_PREFIX = (
    "signal_outcome_v1_current_%"
)

PIPELINE_NAME = (
    "BACKTEST_CALIBRATION_V1"
)


LATEST_OUTCOME_MODEL = text(
    """
    SELECT
        evaluation_model_version
            AS model_version,

        COUNT(*)
            AS rows,

        MAX(evaluated_through)
            AS latest_input_date,

        MAX(evaluated_at)
            AS latest_evaluated_at,

        MAX(input_updated_at)
            AS latest_input_updated_at

    FROM signal_outcomes

    WHERE evaluation_model_version
          LIKE :model_prefix

    GROUP BY
        evaluation_model_version

    ORDER BY
        MAX(evaluated_at) DESC,
        evaluation_model_version DESC

    LIMIT 1
    """
)


LOAD_INPUTS = text(
    """
    SELECT
        so.signal_id,

        s.instrument_id,

        i.symbol,
        i.sector_code,

        s.trading_date
            AS signal_date,

        so.evaluation_model_version
            AS outcome_model_version,

        s.model_version
            AS trade_setup_model_version,

        so.outcome_label,

        so.entry_filled,
        so.horizon_complete,

        so.entry_date,
        so.exit_date,

        so.realized_return,
        so.realized_r,

        so.mfe_r,
        so.mae_r,

        so.target_hit,
        so.stop_hit,

        s.expected_rr
            AS setup_expected_rr,

        s.risk_pct_price
            AS setup_risk_pct,

        s.horizon_days,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'overall_score'
            ),
            ''
        )::NUMERIC
            AS overall_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'market_score'
            ),
            ''
        )::NUMERIC
            AS market_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'sector_score'
            ),
            ''
        )::NUMERIC
            AS sector_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'technical_score'
            ),
            ''
        )::NUMERIC
            AS technical_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'liquidity_score'
            ),
            ''
        )::NUMERIC
            AS liquidity_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'ownership_score'
            ),
            ''
        )::NUMERIC
            AS ownership_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'risk_score'
            ),
            ''
        )::NUMERIC
            AS risk_score,

        NULLIF(
            jsonb_extract_path_text(
                s.evidence,
                'screening_input',
                'data_completeness'
            ),
            ''
        )::NUMERIC
            AS data_completeness,

        GREATEST(
            so.evaluated_at,

            COALESCE(
                so.input_updated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            ),

            s.issued_at,

            COALESCE(
                s.input_updated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            )
        ) AS input_updated_at

    FROM signal_outcomes so

    JOIN signals s
      ON s.id =
         so.signal_id

    JOIN instruments i
      ON i.id =
         s.instrument_id

    WHERE so.evaluation_model_version =
          :outcome_model_version

      AND s.setup_decision =
          'ACCEPT'

    ORDER BY
        s.trading_date,
        s.id
    """
)


DELETE_DATASET = text(
    """
    DELETE FROM backtest_calibration_rows

    WHERE dataset_version =
          :dataset_version
    """
)


UPSERT_ROW = text(
    """
    INSERT INTO backtest_calibration_rows (
        signal_id,
        dataset_version,
        outcome_model_version,

        instrument_id,
        signal_date,
        sector_code,

        sample_status,
        split_label,
        calibration_eligible,

        outcome_label,

        entry_filled,
        horizon_complete,

        entry_date,
        exit_date,

        realized_return,
        realized_r,

        mfe_r,
        mae_r,

        target_hit,
        stop_hit,

        tp_before_sl_label,
        positive_r_label,

        setup_expected_rr,
        setup_risk_pct,

        horizon_days,

        overall_score,
        market_score,
        sector_score,
        technical_score,
        liquidity_score,
        ownership_score,
        risk_score,
        data_completeness,

        score_bucket,

        input_updated_at,
        evidence,

        calculated_at
    )
    VALUES (
        :signal_id,
        :dataset_version,
        :outcome_model_version,

        :instrument_id,
        :signal_date,
        :sector_code,

        :sample_status,
        :split_label,
        :calibration_eligible,

        :outcome_label,

        :entry_filled,
        :horizon_complete,

        :entry_date,
        :exit_date,

        :realized_return,
        :realized_r,

        :mfe_r,
        :mae_r,

        :target_hit,
        :stop_hit,

        :tp_before_sl_label,
        :positive_r_label,

        :setup_expected_rr,
        :setup_risk_pct,

        :horizon_days,

        :overall_score,
        :market_score,
        :sector_score,
        :technical_score,
        :liquidity_score,
        :ownership_score,
        :risk_score,
        :data_completeness,

        :score_bucket,

        :input_updated_at,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        signal_id,
        dataset_version
    )
    DO UPDATE SET
        outcome_model_version =
            EXCLUDED.outcome_model_version,

        instrument_id =
            EXCLUDED.instrument_id,

        signal_date =
            EXCLUDED.signal_date,

        sector_code =
            EXCLUDED.sector_code,

        sample_status =
            EXCLUDED.sample_status,

        split_label =
            EXCLUDED.split_label,

        calibration_eligible =
            EXCLUDED.calibration_eligible,

        outcome_label =
            EXCLUDED.outcome_label,

        entry_filled =
            EXCLUDED.entry_filled,

        horizon_complete =
            EXCLUDED.horizon_complete,

        entry_date =
            EXCLUDED.entry_date,

        exit_date =
            EXCLUDED.exit_date,

        realized_return =
            EXCLUDED.realized_return,

        realized_r =
            EXCLUDED.realized_r,

        mfe_r =
            EXCLUDED.mfe_r,

        mae_r =
            EXCLUDED.mae_r,

        target_hit =
            EXCLUDED.target_hit,

        stop_hit =
            EXCLUDED.stop_hit,

        tp_before_sl_label =
            EXCLUDED.tp_before_sl_label,

        positive_r_label =
            EXCLUDED.positive_r_label,

        setup_expected_rr =
            EXCLUDED.setup_expected_rr,

        setup_risk_pct =
            EXCLUDED.setup_risk_pct,

        horizon_days =
            EXCLUDED.horizon_days,

        overall_score =
            EXCLUDED.overall_score,

        market_score =
            EXCLUDED.market_score,

        sector_score =
            EXCLUDED.sector_score,

        technical_score =
            EXCLUDED.technical_score,

        liquidity_score =
            EXCLUDED.liquidity_score,

        ownership_score =
            EXCLUDED.ownership_score,

        risk_score =
            EXCLUDED.risk_score,

        data_completeness =
            EXCLUDED.data_completeness,

        score_bucket =
            EXCLUDED.score_bucket,

        input_updated_at =
            EXCLUDED.input_updated_at,

        evidence =
            EXCLUDED.evidence,

        calculated_at =
            NOW()
    """
)


STORED_COVERAGE = text(
    """
    SELECT
        COUNT(*)
            AS rows,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'MATURE_TRADE'
        ) AS mature_trades,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'UNFILLED_COMPLETE'
        ) AS unfilled_complete,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'UNRESOLVED'
        ) AS unresolved,

        COUNT(*) FILTER (
            WHERE split_label =
                  'TRAIN'
        ) AS train_rows,

        COUNT(*) FILTER (
            WHERE split_label =
                  'VALIDATION'
        ) AS validation_rows,

        COUNT(*) FILTER (
            WHERE split_label =
                  'TEST'
        ) AS test_rows,

        COUNT(*) FILTER (
            WHERE split_label =
                  'EXCLUDED'
        ) AS excluded_rows,

        MIN(signal_date)
            AS first_signal_date,

        MAX(signal_date)
            AS last_signal_date

    FROM backtest_calibration_rows

    WHERE dataset_version =
          :dataset_version
    """
)


LOAD_STORED = text(
    """
    SELECT
        signal_id,
        dataset_version,
        outcome_model_version,

        instrument_id,
        signal_date,
        sector_code,

        sample_status,
        split_label,
        calibration_eligible,

        outcome_label,

        entry_filled,
        horizon_complete,

        entry_date,
        exit_date,

        realized_return,
        realized_r,

        mfe_r,
        mae_r,

        target_hit,
        stop_hit,

        tp_before_sl_label,
        positive_r_label,

        setup_expected_rr,
        setup_risk_pct,

        horizon_days,

        overall_score,
        market_score,
        sector_score,
        technical_score,
        liquidity_score,
        ownership_score,
        risk_score,
        data_completeness,

        score_bucket,

        input_updated_at,
        evidence

    FROM backtest_calibration_rows

    WHERE dataset_version =
          :dataset_version

    ORDER BY
        signal_date,
        signal_id
    """
)


QUALITY_COUNTS = text(
    """
    SELECT
        COUNT(*) FILTER (
            WHERE calibration_eligible
              AND sample_status !=
                  'MATURE_TRADE'
        ) AS invalid_eligible_sample,

        COUNT(*) FILTER (
            WHERE calibration_eligible
              AND split_label =
                  'EXCLUDED'
        ) AS eligible_excluded,

        COUNT(*) FILTER (
            WHERE NOT calibration_eligible
              AND split_label !=
                  'EXCLUDED'
        ) AS excluded_with_split,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'MATURE_TRADE'

              AND (
                    NOT entry_filled
                 OR NOT horizon_complete
                 OR realized_r IS NULL
                 OR tp_before_sl_label
                    IS NULL
                 OR positive_r_label
                    IS NULL
              )
        ) AS invalid_mature,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'UNFILLED_COMPLETE'

              AND (
                    entry_filled
                 OR NOT horizon_complete
                 OR realized_r IS NOT NULL
              )
        ) AS invalid_unfilled,

        COUNT(*) FILTER (
            WHERE entry_date IS NOT NULL
              AND entry_date <= signal_date
        ) AS invalid_entry_date,

        COUNT(*) FILTER (
            WHERE exit_date IS NOT NULL
              AND entry_date IS NOT NULL
              AND exit_date < entry_date
        ) AS invalid_exit_date

    FROM backtest_calibration_rows

    WHERE dataset_version =
          :dataset_version
    """
)


DUPLICATE_GROUPS = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            signal_id,
            dataset_version

        FROM backtest_calibration_rows

        WHERE dataset_version =
              :dataset_version

        GROUP BY
            signal_id,
            dataset_version

        HAVING COUNT(*) > 1
    ) duplicates
    """
)


OUTCOME_DISTRIBUTION = text(
    """
    SELECT
        outcome_label,
        COUNT(*)
            AS rows

    FROM backtest_calibration_rows

    WHERE dataset_version =
          :dataset_version

    GROUP BY outcome_label

    ORDER BY outcome_label
    """
)


SECTOR_SUMMARY = text(
    """
    SELECT
        sector_code,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'MATURE_TRADE'
        ) AS mature_trades,

        ROUND(
            AVG(realized_r) FILTER (
                WHERE sample_status =
                      'MATURE_TRADE'
            ),
            4
        ) AS avg_r,

        ROUND(
            AVG(
                CASE
                    WHEN tp_before_sl_label
                        THEN 1.0
                    ELSE 0.0
                END
            ) FILTER (
                WHERE sample_status =
                      'MATURE_TRADE'
            ),
            4
        ) AS target_rate

    FROM backtest_calibration_rows

    WHERE dataset_version =
          :dataset_version

    GROUP BY sector_code

    HAVING COUNT(*) FILTER (
        WHERE sample_status =
              'MATURE_TRADE'
    ) > 0

    ORDER BY
        mature_trades DESC,
        sector_code
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
          :dataset_version
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
        :dataset_version,
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
            EXCLUDED.processed_input_updated_at,

        output_rows =
            EXCLUDED.output_rows,

        updated_at =
            NOW()
    """
)


def get_latest_outcome_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_OUTCOME_MODEL,
        {
            "model_prefix":
                OUTCOME_MODEL_PREFIX,
        },
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "No Phase 3J outcome model "
            "is available."
        )

    return dict(
        row
    )


def load_backtest_inputs(
    connection: Connection,
    *,
    outcome_model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_INPUTS,
        {
            "outcome_model_version":
                outcome_model_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def delete_dataset_rows(
    connection: Connection,
    *,
    dataset_version: str,
) -> int:
    result = connection.execute(
        DELETE_DATASET,
        {
            "dataset_version":
                dataset_version,
        },
    )

    return int(
        result.rowcount
        or 0
    )


def upsert_backtest_rows(
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

        serialized = []

        for row in batch:
            item = dict(
                row
            )

            item[
                "evidence"
            ] = json.dumps(
                row[
                    "evidence"
                ],
                sort_keys=True,
            )

            serialized.append(
                item
            )

        connection.execute(
            UPSERT_ROW,
            serialized,
        )

        total += len(
            serialized
        )

    return total


def get_stored_coverage(
    connection: Connection,
    *,
    dataset_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_COVERAGE,
        {
            "dataset_version":
                dataset_version,
        },
    ).mappings().one()

    return dict(
        row
    )


def load_stored_rows(
    connection: Connection,
    *,
    dataset_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED,
        {
            "dataset_version":
                dataset_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_quality_counts(
    connection: Connection,
    *,
    dataset_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        QUALITY_COUNTS,
        {
            "dataset_version":
                dataset_version,
        },
    ).mappings().one()

    return dict(
        row
    )


def get_duplicate_groups(
    connection: Connection,
    *,
    dataset_version: str,
) -> int:
    return int(
        connection.execute(
            DUPLICATE_GROUPS,
            {
                "dataset_version":
                    dataset_version,
            },
        ).scalar_one()
    )


def get_outcome_distribution(
    connection: Connection,
    *,
    dataset_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        OUTCOME_DISTRIBUTION,
        {
            "dataset_version":
                dataset_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_sector_summary(
    connection: Connection,
    *,
    dataset_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        SECTOR_SUMMARY,
        {
            "dataset_version":
                dataset_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_build_state(
    connection: Connection,
    *,
    dataset_version: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        BUILD_STATE,
        {
            "dataset_version":
                dataset_version,
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
    dataset_version: str,
    input_model_version: str,
    processed_through,
    processed_input_updated_at,
    output_rows: int,
) -> None:
    connection.execute(
        UPSERT_BUILD_STATE,
        {
            "dataset_version":
                dataset_version,

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