import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

TRADE_SETUP_PREFIX = (
    "trade_setup_v1_current_%"
)

PIPELINE_NAME = (
    "SIGNAL_OUTCOME_V1"
)


LATEST_TRADE_SETUP_MODEL = text(
    """
    SELECT
        model_version,
        MAX(trading_date)
            AS latest_signal_date,
        COUNT(*)
            AS total_rows,
        COUNT(*) FILTER (
            WHERE setup_decision =
                  'ACCEPT'
        ) AS accepted_rows

    FROM signals

    WHERE model_version
          LIKE :model_prefix

    GROUP BY model_version

    ORDER BY
        MAX(trading_date) DESC,
        model_version DESC

    LIMIT 1
    """
)


LATEST_PRICE_STATE = text(
    """
    SELECT
        MAX(mp.trading_date)
            AS latest_price_date,

        MAX(mp.ingested_at)
            AS latest_price_ingested_at

    FROM market_prices_eod mp

    JOIN instruments i
      ON i.id =
         mp.instrument_id

    WHERE mp.source_id =
          :price_source_id

      AND mp.quality =
          'VALID'

      AND i.exchange =
          'IDX'

      AND i.asset_type =
          'EQUITY'
    """
)


SIGNAL_WITH_BARS = text(
    """
    SELECT
        s.id
            AS signal_id,

        s.instrument_id,

        i.symbol,
        i.sector_code,

        s.trading_date,

        s.entry_low,
        s.entry_high,

        s.stop_price,
        s.target_primary,

        s.horizon_days,

        s.issued_at,

        s.input_updated_at
            AS signal_input_updated_at,

        s.model_version
            AS signal_model_version,

        p.trading_date
            AS bar_date,

        p.open
            AS bar_open,

        p.high
            AS bar_high,

        p.low
            AS bar_low,

        p.close
            AS bar_close,

        p.ingested_at
            AS bar_ingested_at

    FROM signals s

    JOIN instruments i
      ON i.id =
         s.instrument_id

    LEFT JOIN LATERAL (
        SELECT
            mp.trading_date,
            mp.open,
            mp.high,
            mp.low,
            mp.close,
            mp.ingested_at

        FROM market_prices_eod mp

        WHERE mp.instrument_id =
              s.instrument_id

          AND mp.source_id =
              :price_source_id

          AND mp.quality =
              'VALID'

          AND mp.trading_date >
              s.trading_date

        ORDER BY
            mp.trading_date

        LIMIT :max_future_bars
    ) p
      ON TRUE

    WHERE s.model_version =
          :trade_setup_model_version

      AND s.setup_decision =
          'ACCEPT'

    ORDER BY
        s.trading_date,
        s.id,
        p.trading_date
    """
)


STORED_COVERAGE = text(
    """
    SELECT
        COUNT(*)
            AS rows,

        COUNT(*) FILTER (
            WHERE horizon_complete
        ) AS complete_rows,

        COUNT(*) FILTER (
            WHERE NOT horizon_complete
        ) AS incomplete_rows,

        MIN(evaluated_through)
            AS first_evaluated_through,

        MAX(evaluated_through)
            AS last_evaluated_through

    FROM signal_outcomes

    WHERE evaluation_model_version =
          :model_version
    """
)


DELETE_MODEL = text(
    """
    DELETE FROM signal_outcomes

    WHERE evaluation_model_version =
          :model_version
    """
)


UPSERT_OUTCOME = text(
    """
    INSERT INTO signal_outcomes (
        signal_id,

        evaluated_through,

        return_t1,
        return_t3,
        return_t5,
        return_t10,
        return_t20,

        mfe,
        mae,

        target_hit,
        stop_hit,

        target_hit_at,
        stop_hit_at,

        time_to_target_hours,

        entry_filled,
        entry_date,
        entry_price,

        exit_date,
        exit_price,

        outcome_label,

        realized_return,
        realized_r,

        mfe_r,
        mae_r,

        bars_to_entry,
        bars_held,

        target_hit_date,
        stop_hit_date,

        horizon_complete,
        available_bars,

        sequence_ambiguous,

        evaluation_model_version,

        input_updated_at,

        evidence,

        evaluated_at
    )
    VALUES (
        :signal_id,

        :evaluated_through,

        :return_t1,
        :return_t3,
        :return_t5,
        :return_t10,
        :return_t20,

        :mfe,
        :mae,

        :target_hit,
        :stop_hit,

        :target_hit_at,
        :stop_hit_at,

        :time_to_target_hours,

        :entry_filled,
        :entry_date,
        :entry_price,

        :exit_date,
        :exit_price,

        :outcome_label,

        :realized_return,
        :realized_r,

        :mfe_r,
        :mae_r,

        :bars_to_entry,
        :bars_held,

        :target_hit_date,
        :stop_hit_date,

        :horizon_complete,
        :available_bars,

        :sequence_ambiguous,

        :evaluation_model_version,

        :input_updated_at,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        signal_id
    )
    DO UPDATE SET
        evaluated_through =
            EXCLUDED.evaluated_through,

        return_t1 =
            EXCLUDED.return_t1,

        return_t3 =
            EXCLUDED.return_t3,

        return_t5 =
            EXCLUDED.return_t5,

        return_t10 =
            EXCLUDED.return_t10,

        return_t20 =
            EXCLUDED.return_t20,

        mfe =
            EXCLUDED.mfe,

        mae =
            EXCLUDED.mae,

        target_hit =
            EXCLUDED.target_hit,

        stop_hit =
            EXCLUDED.stop_hit,

        target_hit_at =
            EXCLUDED.target_hit_at,

        stop_hit_at =
            EXCLUDED.stop_hit_at,

        time_to_target_hours =
            EXCLUDED.time_to_target_hours,

        entry_filled =
            EXCLUDED.entry_filled,

        entry_date =
            EXCLUDED.entry_date,

        entry_price =
            EXCLUDED.entry_price,

        exit_date =
            EXCLUDED.exit_date,

        exit_price =
            EXCLUDED.exit_price,

        outcome_label =
            EXCLUDED.outcome_label,

        realized_return =
            EXCLUDED.realized_return,

        realized_r =
            EXCLUDED.realized_r,

        mfe_r =
            EXCLUDED.mfe_r,

        mae_r =
            EXCLUDED.mae_r,

        bars_to_entry =
            EXCLUDED.bars_to_entry,

        bars_held =
            EXCLUDED.bars_held,

        target_hit_date =
            EXCLUDED.target_hit_date,

        stop_hit_date =
            EXCLUDED.stop_hit_date,

        horizon_complete =
            EXCLUDED.horizon_complete,

        available_bars =
            EXCLUDED.available_bars,

        sequence_ambiguous =
            EXCLUDED.sequence_ambiguous,

        evaluation_model_version =
            EXCLUDED.evaluation_model_version,

        input_updated_at =
            EXCLUDED.input_updated_at,

        evidence =
            EXCLUDED.evidence,

        evaluated_at =
            NOW()
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


LOAD_ALL_STORED = text(
    """
    SELECT
        so.signal_id,

        so.evaluated_through,

        so.return_t1,
        so.return_t3,
        so.return_t5,
        so.return_t10,
        so.return_t20,

        so.mfe,
        so.mae,

        so.target_hit,
        so.stop_hit,

        so.target_hit_at,
        so.stop_hit_at,

        so.time_to_target_hours,

        so.entry_filled,
        so.entry_date,
        so.entry_price,

        so.exit_date,
        so.exit_price,

        so.outcome_label,

        so.realized_return,
        so.realized_r,

        so.mfe_r,
        so.mae_r,

        so.bars_to_entry,
        so.bars_held,

        so.target_hit_date,
        so.stop_hit_date,

        so.horizon_complete,
        so.available_bars,

        so.sequence_ambiguous,

        so.evaluation_model_version,

        so.input_updated_at,

        so.evidence

    FROM signal_outcomes so

    WHERE so.evaluation_model_version =
          :model_version

    ORDER BY
        so.signal_id
    """
)


OUTCOME_DISTRIBUTION = text(
    """
    SELECT
        outcome_label,
        COUNT(*)
            AS rows

    FROM signal_outcomes

    WHERE evaluation_model_version =
          :model_version

    GROUP BY outcome_label

    ORDER BY outcome_label
    """
)


QUALITY_COUNTS = text(
    """
    SELECT
        COUNT(*) FILTER (
            WHERE outcome_label
                  IS NULL
               OR outcome_label
                  NOT IN (
                      'PENDING',
                      'NO_FILL',
                      'CANCELLED',
                      'OPEN',
                      'TARGET',
                      'STOP',
                      'EXPIRED'
                  )
        ) AS invalid_label,

        COUNT(*) FILTER (
            WHERE entry_filled
              AND (
                    entry_date IS NULL
                 OR entry_price IS NULL
                 OR bars_to_entry IS NULL
              )
        ) AS invalid_filled,

        COUNT(*) FILTER (
            WHERE NOT entry_filled
              AND (
                    entry_date IS NOT NULL
                 OR entry_price IS NOT NULL
                 OR bars_to_entry IS NOT NULL
              )
        ) AS invalid_unfilled,

        COUNT(*) FILTER (
            WHERE outcome_label =
                  'TARGET'
              AND (
                    NOT target_hit
                 OR stop_hit
                 OR exit_date IS NULL
                 OR exit_price IS NULL
                 OR realized_r IS NULL
                 OR realized_r <= 0
              )
        ) AS invalid_target,

        COUNT(*) FILTER (
            WHERE outcome_label =
                  'STOP'
              AND (
                    NOT stop_hit
                 OR target_hit
                 OR exit_date IS NULL
                 OR exit_price IS NULL
                 OR realized_r IS NULL
                 OR realized_r > 0
              )
        ) AS invalid_stop,

        COUNT(*) FILTER (
            WHERE outcome_label IN (
                'PENDING',
                'OPEN'
            )
              AND horizon_complete
        ) AS invalid_incomplete,

        COUNT(*) FILTER (
            WHERE target_hit_at
                  IS NOT NULL
               OR stop_hit_at
                  IS NOT NULL
               OR time_to_target_hours
                  IS NOT NULL
        ) AS fabricated_intraday_time,

        COUNT(*) FILTER (
            WHERE available_bars < 0
        ) AS invalid_available_bars

    FROM signal_outcomes

    WHERE evaluation_model_version =
          :model_version
    """
)


RECENT_OUTCOMES = text(
    """
    SELECT
        i.symbol,
        s.trading_date
            AS signal_date,

        so.outcome_label,

        so.entry_date,
        so.entry_price,

        so.exit_date,
        so.exit_price,

        so.realized_return,
        so.realized_r,

        so.mfe_r,
        so.mae_r,

        so.bars_to_entry,
        so.bars_held,

        so.horizon_complete,
        so.sequence_ambiguous

    FROM signal_outcomes so

    JOIN signals s
      ON s.id =
         so.signal_id

    JOIN instruments i
      ON i.id =
         s.instrument_id

    WHERE so.evaluation_model_version =
          :model_version

    ORDER BY
        s.trading_date DESC,
        i.symbol

    LIMIT :limit
    """
)


def get_latest_trade_setup_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_TRADE_SETUP_MODEL,
        {
            "model_prefix":
                TRADE_SETUP_PREFIX,
        },
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "No Phase 3I trade setup "
            "model is available."
        )

    return dict(
        row
    )


def get_latest_price_state(
    connection: Connection,
    *,
    price_source_id,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_PRICE_STATE,
        {
            "price_source_id":
                price_source_id,
        },
    ).mappings().one()

    result = dict(
        row
    )

    if result[
        "latest_price_date"
    ] is None:
        raise RuntimeError(
            "No valid IDX equity EOD "
            "prices are available."
        )

    return result


def load_signal_outcome_inputs(
    connection: Connection,
    *,
    trade_setup_model_version: str,
    price_source_id,
    max_future_bars: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        SIGNAL_WITH_BARS,
        {
            "trade_setup_model_version":
                trade_setup_model_version,

            "price_source_id":
                price_source_id,

            "max_future_bars":
                max_future_bars,
        },
    ).mappings().all()

    grouped: dict[
        Any,
        dict[str, Any],
    ] = {}

    for raw in rows:
        row = dict(
            raw
        )

        signal_id = row[
            "signal_id"
        ]

        if signal_id not in grouped:
            grouped[
                signal_id
            ] = {
                "signal_id":
                    signal_id,

                "instrument_id":
                    row[
                        "instrument_id"
                    ],

                "symbol":
                    row["symbol"],

                "sector_code":
                    row[
                        "sector_code"
                    ],

                "trading_date":
                    row[
                        "trading_date"
                    ],

                "entry_low":
                    row[
                        "entry_low"
                    ],

                "entry_high":
                    row[
                        "entry_high"
                    ],

                "stop_price":
                    row[
                        "stop_price"
                    ],

                "target_primary":
                    row[
                        "target_primary"
                    ],

                "horizon_days":
                    row[
                        "horizon_days"
                    ],

                "issued_at":
                    row[
                        "issued_at"
                    ],

                "signal_input_updated_at":
                    row[
                        "signal_input_updated_at"
                    ],

                "signal_model_version":
                    row[
                        "signal_model_version"
                    ],

                "bars":
                    [],
            }

        if row[
            "bar_date"
        ] is not None:
            grouped[
                signal_id
            ][
                "bars"
            ].append(
                {
                    "trading_date":
                        row[
                            "bar_date"
                        ],

                    "open":
                        row[
                            "bar_open"
                        ],

                    "high":
                        row[
                            "bar_high"
                        ],

                    "low":
                        row[
                            "bar_low"
                        ],

                    "close":
                        row[
                            "bar_close"
                        ],

                    "ingested_at":
                        row[
                            "bar_ingested_at"
                        ],
                }
            )

    return sorted(
        grouped.values(),
        key=lambda item: (
            item[
                "trading_date"
            ],
            str(
                item[
                    "signal_id"
                ]
            ),
        ),
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


def upsert_outcomes(
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
                row["evidence"],
                sort_keys=True,
            )

            serialized.append(
                item
            )

        connection.execute(
            UPSERT_OUTCOME,
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


def get_outcome_distribution(
    connection: Connection,
    *,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        OUTCOME_DISTRIBUTION,
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


def load_recent_outcomes(
    connection: Connection,
    *,
    model_version: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        RECENT_OUTCOMES,
        {
            "model_version":
                model_version,

            "limit":
                limit,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]