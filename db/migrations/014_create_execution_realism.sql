BEGIN;


CREATE TABLE IF NOT EXISTS public.execution_realism_rows (
    signal_id UUID NOT NULL
        REFERENCES public.signals(id)
        ON DELETE CASCADE,

    model_version TEXT NOT NULL,

    calibration_dataset_version TEXT NOT NULL,

    instrument_id UUID NOT NULL
        REFERENCES public.instruments(id),

    signal_date DATE NOT NULL,

    sector_code TEXT,

    sample_status TEXT NOT NULL,

    split_label TEXT NOT NULL,

    outcome_label TEXT NOT NULL,

    raw_entry_price NUMERIC(20,6),

    raw_exit_price NUMERIC(20,6),

    raw_stop_price NUMERIC(20,6),

    entry_reference_price NUMERIC(20,6),

    exit_reference_price NUMERIC(20,6),

    entry_tick_size NUMERIC(20,6),

    exit_tick_size NUMERIC(20,6),

    modeled_entry_price NUMERIC(20,6),

    modeled_exit_price NUMERIC(20,6),

    modeled_stop_price NUMERIC(20,6),

    buy_fee_rate NUMERIC(18,10),

    sell_fee_rate NUMERIC(18,10),

    entry_slippage_ticks INTEGER,

    exit_slippage_ticks INTEGER,

    raw_realized_return NUMERIC(18,8),

    raw_realized_r NUMERIC(18,8),

    gross_modeled_return NUMERIC(18,8),

    gross_modeled_r NUMERIC(18,8),

    net_modeled_return NUMERIC(18,8),

    net_realized_r NUMERIC(18,8),

    slippage_drag_r NUMERIC(18,8),

    fee_drag_r NUMERIC(18,8),

    total_cost_drag_r NUMERIC(18,8),

    execution_metrics_available BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    tick_size_modeled BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    exchange_costs_modeled BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    slippage_modeled BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    broker_commission_modeled BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    auto_rejection_modeled BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    point_in_time_safe BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    survivorship_safe BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    corporate_action_overlap_detected BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    corporate_action_history_complete BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    strict_calibration_eligible BOOLEAN
        NOT NULL
        DEFAULT FALSE,

    blocking_reasons JSONB
        NOT NULL
        DEFAULT '[]'::jsonb,

    input_updated_at TIMESTAMPTZ,

    evidence JSONB
        NOT NULL
        DEFAULT '{}'::jsonb,

    calculated_at TIMESTAMPTZ
        NOT NULL
        DEFAULT now(),

    PRIMARY KEY (
        signal_id,
        model_version
    )
);


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'execution_realism_sample_status_check'
          AND conrelid =
              'public.execution_realism_rows'::regclass
    ) THEN
        ALTER TABLE public.execution_realism_rows
            ADD CONSTRAINT
                execution_realism_sample_status_check
            CHECK (
                sample_status IN (
                    'MATURE_TRADE',
                    'UNFILLED_COMPLETE',
                    'UNRESOLVED'
                )
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'execution_realism_split_check'
          AND conrelid =
              'public.execution_realism_rows'::regclass
    ) THEN
        ALTER TABLE public.execution_realism_rows
            ADD CONSTRAINT
                execution_realism_split_check
            CHECK (
                split_label IN (
                    'TRAIN',
                    'VALIDATION',
                    'TEST',
                    'EXCLUDED'
                )
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'execution_realism_tick_check'
          AND conrelid =
              'public.execution_realism_rows'::regclass
    ) THEN
        ALTER TABLE public.execution_realism_rows
            ADD CONSTRAINT
                execution_realism_tick_check
            CHECK (
                (
                    entry_tick_size IS NULL
                    OR entry_tick_size > 0
                )
                AND
                (
                    exit_tick_size IS NULL
                    OR exit_tick_size > 0
                )
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'execution_realism_fee_check'
          AND conrelid =
              'public.execution_realism_rows'::regclass
    ) THEN
        ALTER TABLE public.execution_realism_rows
            ADD CONSTRAINT
                execution_realism_fee_check
            CHECK (
                (
                    buy_fee_rate IS NULL
                    OR (
                        buy_fee_rate >= 0
                        AND buy_fee_rate < 1
                    )
                )
                AND
                (
                    sell_fee_rate IS NULL
                    OR (
                        sell_fee_rate >= 0
                        AND sell_fee_rate < 1
                    )
                )
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'execution_realism_slippage_check'
          AND conrelid =
              'public.execution_realism_rows'::regclass
    ) THEN
        ALTER TABLE public.execution_realism_rows
            ADD CONSTRAINT
                execution_realism_slippage_check
            CHECK (
                (
                    entry_slippage_ticks IS NULL
                    OR entry_slippage_ticks >= 0
                )
                AND
                (
                    exit_slippage_ticks IS NULL
                    OR exit_slippage_ticks >= 0
                )
            );
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    execution_realism_model_sample_idx
ON public.execution_realism_rows (
    model_version,
    sample_status
);


CREATE INDEX IF NOT EXISTS
    execution_realism_model_split_idx
ON public.execution_realism_rows (
    model_version,
    split_label
);


CREATE INDEX IF NOT EXISTS
    execution_realism_model_strict_idx
ON public.execution_realism_rows (
    model_version,
    strict_calibration_eligible
);


CREATE INDEX IF NOT EXISTS
    execution_realism_model_sector_idx
ON public.execution_realism_rows (
    model_version,
    sector_code
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.execution_realism_rows
TO imi;


COMMIT;