import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

CALIBRATION_MODEL_PREFIX = (
    "backtest_calibration_v1_current_%"
)

PIPELINE_NAME = (
    "EXECUTION_REALISM_V1"
)


LATEST_CALIBRATION_MODEL = text(
    """
    SELECT
        dataset_version,
        COUNT(*)
            AS rows,
        MAX(signal_date)
            AS latest_input_date,
        MAX(calculated_at)
            AS latest_calculated_at,
        MAX(input_updated_at)
            AS latest_input_updated_at

    FROM backtest_calibration_rows

    WHERE dataset_version
          LIKE :model_prefix

    GROUP BY dataset_version

    ORDER BY
        MAX(calculated_at) DESC,
        dataset_version DESC

    LIMIT 1
    """
)


LOAD_INPUTS = text(
    """
    SELECT
        b.signal_id,

        b.dataset_version
            AS calibration_dataset_version,

        b.outcome_model_version,

        s.model_version
            AS trade_setup_model_version,

        b.instrument_id,
        b.signal_date,
        b.sector_code,

        b.sample_status,
        b.split_label,
        b.calibration_eligible,

        b.outcome_label,

        b.realized_return
            AS raw_realized_return,

        b.realized_r
            AS raw_realized_r,

        so.entry_price
            AS raw_entry_price,

        so.exit_price
            AS raw_exit_price,

        s.stop_price
            AS raw_stop_price,

        entry_price.previous_close
            AS entry_reference_price,

        exit_price.previous_close
            AS exit_reference_price,

        b.evidence
            AS calibration_evidence,

        EXISTS (
            SELECT 1

            FROM corporate_actions ca

            WHERE ca.instrument_id =
                  b.instrument_id

              AND (
                    (
                        ca.ex_date IS NOT NULL
                        AND ca.ex_date BETWEEN
                            b.signal_date
                            AND COALESCE(
                                b.exit_date,
                                b.entry_date,
                                b.signal_date
                            )
                    )

                 OR (
                        ca.cum_date IS NOT NULL
                        AND ca.cum_date BETWEEN
                            b.signal_date
                            AND COALESCE(
                                b.exit_date,
                                b.entry_date,
                                b.signal_date
                            )
                    )

                 OR (
                        ca.record_date IS NOT NULL
                        AND ca.record_date BETWEEN
                            b.signal_date
                            AND COALESCE(
                                b.exit_date,
                                b.entry_date,
                                b.signal_date
                            )
                    )
              )
        ) AS corporate_action_overlap_detected,

        GREATEST(
            b.calculated_at,

            COALESCE(
                b.input_updated_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            ),

            so.evaluated_at,

            s.issued_at,

            COALESCE(
                entry_price.ingested_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            ),

            COALESCE(
                exit_price.ingested_at,
                TIMESTAMPTZ
                '1970-01-01 00:00:00+00'
            )
        ) AS input_updated_at

    FROM backtest_calibration_rows b

    JOIN signals s
      ON s.id =
         b.signal_id

    JOIN signal_outcomes so
      ON so.signal_id =
         b.signal_id

    LEFT JOIN market_prices_eod entry_price
      ON entry_price.instrument_id =
         b.instrument_id

     AND entry_price.trading_date =
         b.entry_date

     AND entry_price.source_id =
         :price_source_id

     AND entry_price.quality =
         'VALID'

    LEFT JOIN market_prices_eod exit_price
      ON exit_price.instrument_id =
         b.instrument_id

     AND exit_price.trading_date =
         b.exit_date

     AND exit_price.source_id =
         :price_source_id

     AND exit_price.quality =
         'VALID'

    WHERE b.dataset_version =
          :dataset_version

    ORDER BY
        b.signal_date,
        b.signal_id
    """
)


DELETE_MODEL = text(
    """
    DELETE FROM execution_realism_rows

    WHERE model_version =
          :model_version
    """
)


UPSERT_ROW = text(
    """
    INSERT INTO execution_realism_rows (
        signal_id,
        model_version,
        calibration_dataset_version,

        instrument_id,
        signal_date,
        sector_code,

        sample_status,
        split_label,
        outcome_label,

        raw_entry_price,
        raw_exit_price,
        raw_stop_price,

        entry_reference_price,
        exit_reference_price,

        entry_tick_size,
        exit_tick_size,

        modeled_entry_price,
        modeled_exit_price,
        modeled_stop_price,

        buy_fee_rate,
        sell_fee_rate,

        entry_slippage_ticks,
        exit_slippage_ticks,

        raw_realized_return,
        raw_realized_r,

        gross_modeled_return,
        gross_modeled_r,

        net_modeled_return,
        net_realized_r,

        slippage_drag_r,
        fee_drag_r,
        total_cost_drag_r,

        execution_metrics_available,

        tick_size_modeled,
        exchange_costs_modeled,
        slippage_modeled,

        broker_commission_modeled,
        auto_rejection_modeled,

        point_in_time_safe,
        survivorship_safe,

        corporate_action_overlap_detected,
        corporate_action_history_complete,

        strict_calibration_eligible,

        blocking_reasons,

        input_updated_at,
        evidence,

        calculated_at
    )
    VALUES (
        :signal_id,
        :model_version,
        :calibration_dataset_version,

        :instrument_id,
        :signal_date,
        :sector_code,

        :sample_status,
        :split_label,
        :outcome_label,

        :raw_entry_price,
        :raw_exit_price,
        :raw_stop_price,

        :entry_reference_price,
        :exit_reference_price,

        :entry_tick_size,
        :exit_tick_size,

        :modeled_entry_price,
        :modeled_exit_price,
        :modeled_stop_price,

        :buy_fee_rate,
        :sell_fee_rate,

        :entry_slippage_ticks,
        :exit_slippage_ticks,

        :raw_realized_return,
        :raw_realized_r,

        :gross_modeled_return,
        :gross_modeled_r,

        :net_modeled_return,
        :net_realized_r,

        :slippage_drag_r,
        :fee_drag_r,
        :total_cost_drag_r,

        :execution_metrics_available,

        :tick_size_modeled,
        :exchange_costs_modeled,
        :slippage_modeled,

        :broker_commission_modeled,
        :auto_rejection_modeled,

        :point_in_time_safe,
        :survivorship_safe,

        :corporate_action_overlap_detected,
        :corporate_action_history_complete,

        :strict_calibration_eligible,

        CAST(
            :blocking_reasons
            AS JSONB
        ),

        :input_updated_at,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        signal_id,
        model_version
    )
    DO UPDATE SET
        calibration_dataset_version =
            EXCLUDED.calibration_dataset_version,

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

        outcome_label =
            EXCLUDED.outcome_label,

        raw_entry_price =
            EXCLUDED.raw_entry_price,

        raw_exit_price =
            EXCLUDED.raw_exit_price,

        raw_stop_price =
            EXCLUDED.raw_stop_price,

        entry_reference_price =
            EXCLUDED.entry_reference_price,

        exit_reference_price =
            EXCLUDED.exit_reference_price,

        entry_tick_size =
            EXCLUDED.entry_tick_size,

        exit_tick_size =
            EXCLUDED.exit_tick_size,

        modeled_entry_price =
            EXCLUDED.modeled_entry_price,

        modeled_exit_price =
            EXCLUDED.modeled_exit_price,

        modeled_stop_price =
            EXCLUDED.modeled_stop_price,

        buy_fee_rate =
            EXCLUDED.buy_fee_rate,

        sell_fee_rate =
            EXCLUDED.sell_fee_rate,

        entry_slippage_ticks =
            EXCLUDED.entry_slippage_ticks,

        exit_slippage_ticks =
            EXCLUDED.exit_slippage_ticks,

        raw_realized_return =
            EXCLUDED.raw_realized_return,

        raw_realized_r =
            EXCLUDED.raw_realized_r,

        gross_modeled_return =
            EXCLUDED.gross_modeled_return,

        gross_modeled_r =
            EXCLUDED.gross_modeled_r,

        net_modeled_return =
            EXCLUDED.net_modeled_return,

        net_realized_r =
            EXCLUDED.net_realized_r,

        slippage_drag_r =
            EXCLUDED.slippage_drag_r,

        fee_drag_r =
            EXCLUDED.fee_drag_r,

        total_cost_drag_r =
            EXCLUDED.total_cost_drag_r,

        execution_metrics_available =
            EXCLUDED.execution_metrics_available,

        tick_size_modeled =
            EXCLUDED.tick_size_modeled,

        exchange_costs_modeled =
            EXCLUDED.exchange_costs_modeled,

        slippage_modeled =
            EXCLUDED.slippage_modeled,

        broker_commission_modeled =
            EXCLUDED.broker_commission_modeled,

        auto_rejection_modeled =
            EXCLUDED.auto_rejection_modeled,

        point_in_time_safe =
            EXCLUDED.point_in_time_safe,

        survivorship_safe =
            EXCLUDED.survivorship_safe,

        corporate_action_overlap_detected =
            EXCLUDED
            .corporate_action_overlap_detected,

        corporate_action_history_complete =
            EXCLUDED
            .corporate_action_history_complete,

        strict_calibration_eligible =
            EXCLUDED.strict_calibration_eligible,

        blocking_reasons =
            EXCLUDED.blocking_reasons,

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
            WHERE execution_metrics_available
        ) AS execution_available,

        COUNT(*) FILTER (
            WHERE strict_calibration_eligible
        ) AS strict_eligible,

        MIN(signal_date)
            AS first_signal_date,

        MAX(signal_date)
            AS last_signal_date

    FROM execution_realism_rows

    WHERE model_version =
          :model_version
    """
)


LOAD_STORED = text(
    """
    SELECT
        signal_id,
        model_version,
        calibration_dataset_version,

        instrument_id,
        signal_date,
        sector_code,

        sample_status,
        split_label,
        outcome_label,

        raw_entry_price,
        raw_exit_price,
        raw_stop_price,

        entry_reference_price,
        exit_reference_price,

        entry_tick_size,
        exit_tick_size,

        modeled_entry_price,
        modeled_exit_price,
        modeled_stop_price,

        buy_fee_rate,
        sell_fee_rate,

        entry_slippage_ticks,
        exit_slippage_ticks,

        raw_realized_return,
        raw_realized_r,

        gross_modeled_return,
        gross_modeled_r,

        net_modeled_return,
        net_realized_r,

        slippage_drag_r,
        fee_drag_r,
        total_cost_drag_r,

        execution_metrics_available,

        tick_size_modeled,
        exchange_costs_modeled,
        slippage_modeled,

        broker_commission_modeled,
        auto_rejection_modeled,

        point_in_time_safe,
        survivorship_safe,

        corporate_action_overlap_detected,
        corporate_action_history_complete,

        strict_calibration_eligible,

        blocking_reasons,

        input_updated_at,
        evidence

    FROM execution_realism_rows

    WHERE model_version =
          :model_version

    ORDER BY
        signal_date,
        signal_id
    """
)


QUALITY_COUNTS = text(
    """
    SELECT
        COUNT(*) FILTER (
            WHERE sample_status =
                  'MATURE_TRADE'

              AND execution_metrics_available

              AND (
                    modeled_entry_price IS NULL
                 OR modeled_exit_price IS NULL
                 OR modeled_stop_price IS NULL
                 OR entry_tick_size IS NULL
                 OR exit_tick_size IS NULL
                 OR net_realized_r IS NULL
              )
        ) AS invalid_available_execution,

        COUNT(*) FILTER (
            WHERE sample_status !=
                  'MATURE_TRADE'

              AND execution_metrics_available
        ) AS execution_on_non_mature,

        COUNT(*) FILTER (
            WHERE strict_calibration_eligible

              AND jsonb_array_length(
                    blocking_reasons
                  ) != 0
        ) AS strict_with_blockers,

        COUNT(*) FILTER (
            WHERE strict_calibration_eligible
              AND NOT execution_metrics_available
        ) AS strict_without_execution,

        COUNT(*) FILTER (
            WHERE entry_tick_size IS NOT NULL
              AND entry_tick_size <= 0
        ) AS invalid_entry_tick,

        COUNT(*) FILTER (
            WHERE exit_tick_size IS NOT NULL
              AND exit_tick_size <= 0
        ) AS invalid_exit_tick,

        COUNT(*) FILTER (
            WHERE buy_fee_rate IS NOT NULL
              AND buy_fee_rate < 0
        ) AS invalid_buy_fee,

        COUNT(*) FILTER (
            WHERE sell_fee_rate IS NOT NULL
              AND sell_fee_rate < 0
        ) AS invalid_sell_fee,

        COUNT(*) FILTER (
            WHERE blocking_reasons IS NULL
               OR jsonb_typeof(
                    blocking_reasons
                  ) != 'array'
        ) AS invalid_blocking_json

    FROM execution_realism_rows

    WHERE model_version =
          :model_version
    """
)


DUPLICATE_GROUPS = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            signal_id,
            model_version

        FROM execution_realism_rows

        WHERE model_version =
              :model_version

        GROUP BY
            signal_id,
            model_version

        HAVING COUNT(*) > 1
    ) duplicates
    """
)


SECTOR_SUMMARY = text(
    """
    SELECT
        sector_code,

        COUNT(*) FILTER (
            WHERE execution_metrics_available
        ) AS trades,

        ROUND(
            AVG(raw_realized_r) FILTER (
                WHERE execution_metrics_available
            ),
            4
        ) AS raw_avg_r,

        ROUND(
            AVG(net_realized_r) FILTER (
                WHERE execution_metrics_available
            ),
            4
        ) AS net_avg_r,

        ROUND(
            AVG(total_cost_drag_r) FILTER (
                WHERE execution_metrics_available
            ),
            4
        ) AS avg_drag_r

    FROM execution_realism_rows

    WHERE model_version =
          :model_version

    GROUP BY sector_code

    HAVING COUNT(*) FILTER (
        WHERE execution_metrics_available
    ) > 0

    ORDER BY
        trades DESC,
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
            EXCLUDED.processed_input_updated_at,

        output_rows =
            EXCLUDED.output_rows,

        updated_at =
            NOW()
    """
)


def get_latest_calibration_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_CALIBRATION_MODEL,
        {
            "model_prefix":
                CALIBRATION_MODEL_PREFIX,
        },
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "No Phase 3K calibration "
            "dataset is available."
        )

    return dict(
        row
    )


def load_execution_inputs(
    connection: Connection,
    *,
    dataset_version: str,
    price_source_id,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_INPUTS,
        {
            "dataset_version":
                dataset_version,

            "price_source_id":
                price_source_id,
        },
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
        result.rowcount
        or 0
    )


def upsert_execution_rows(
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
                "blocking_reasons"
            ] = json.dumps(
                row[
                    "blocking_reasons"
                ]
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


def load_stored_rows(
    connection: Connection,
    *,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED,
        {
            "model_version":
                model_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


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


def get_sector_summary(
    connection: Connection,
    *,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        SECTOR_SUMMARY,
        {
            "model_version":
                model_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


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
    processed_through,
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