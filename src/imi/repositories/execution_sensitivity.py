from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

EXECUTION_MODEL_PREFIX = (
    "execution_realism_v1_current_%"
)


LATEST_EXECUTION_MODEL = text(
    """
    SELECT
        model_version,
        calibration_dataset_version,

        COUNT(*)
            AS rows,

        COUNT(*) FILTER (
            WHERE sample_status =
                  'MATURE_TRADE'
              AND execution_metrics_available
        ) AS mature_execution_rows,

        MAX(signal_date)
            AS latest_signal_date,

        MAX(calculated_at)
            AS latest_calculated_at

    FROM execution_realism_rows

    WHERE model_version
          LIKE :model_prefix

    GROUP BY
        model_version,
        calibration_dataset_version

    ORDER BY
        MAX(calculated_at) DESC,
        model_version DESC

    LIMIT 1
    """
)


LOAD_MATURE_EXECUTION_INPUTS = text(
    """
    SELECT
        e.signal_id,

        i.symbol,

        e.instrument_id,
        e.signal_date,
        e.sector_code,

        e.split_label,
        e.outcome_label,

        e.raw_entry_price,
        e.raw_exit_price,
        e.raw_stop_price,

        e.entry_reference_price,
        e.exit_reference_price,

        e.raw_realized_r,

        e.gross_modeled_r
            AS stored_baseline_gross_r,

        e.net_realized_r
            AS stored_baseline_net_r,

        e.total_cost_drag_r
            AS stored_baseline_drag_r,

        b.setup_risk_pct,
        b.liquidity_score,
        b.overall_score,
        b.risk_score,

        e.input_updated_at

    FROM execution_realism_rows e

    JOIN instruments i
      ON i.id =
         e.instrument_id

    JOIN backtest_calibration_rows b
      ON b.signal_id =
         e.signal_id

     AND b.dataset_version =
         e.calibration_dataset_version

    WHERE e.model_version =
          :model_version

      AND e.sample_status =
          'MATURE_TRADE'

      AND e.execution_metrics_available

    ORDER BY
        e.signal_date,
        e.signal_id
    """
)


def get_latest_execution_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_EXECUTION_MODEL,
        {
            "model_prefix":
                EXECUTION_MODEL_PREFIX,
        },
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "No Phase 3L execution "
            "realism model is available."
        )

    return dict(
        row
    )


def load_mature_execution_inputs(
    connection: Connection,
    *,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_MATURE_EXECUTION_INPUTS,
        {
            "model_version":
                model_version,
        },
    ).mappings().all()

    return [
        dict(
            row
        )
        for row in rows
    ]