BEGIN;

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS setup_decision TEXT;

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS risk_per_share NUMERIC(20,6);

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS risk_pct_price NUMERIC(12,8);

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS reference_capital NUMERIC(20,2);

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS risk_budget_pct NUMERIC(12,8);

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS position_size_shares BIGINT;

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS position_size_lots INTEGER;

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS capital_required NUMERIC(20,2);

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS input_updated_at TIMESTAMPTZ;

ALTER TABLE public.signals
    ADD COLUMN IF NOT EXISTS decision_reasons JSONB
        NOT NULL
        DEFAULT '[]'::jsonb;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_setup_decision_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_setup_decision_check
            CHECK (
                setup_decision IS NULL
                OR setup_decision IN (
                    'ACCEPT',
                    'WATCH',
                    'REJECT'
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
        WHERE conname = 'signals_risk_per_share_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_risk_per_share_check
            CHECK (
                risk_per_share IS NULL
                OR risk_per_share >= 0
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_risk_pct_price_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_risk_pct_price_check
            CHECK (
                risk_pct_price IS NULL
                OR (
                    risk_pct_price >= 0
                    AND risk_pct_price <= 1
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
        WHERE conname = 'signals_reference_capital_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_reference_capital_check
            CHECK (
                reference_capital IS NULL
                OR reference_capital > 0
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_risk_budget_pct_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_risk_budget_pct_check
            CHECK (
                risk_budget_pct IS NULL
                OR (
                    risk_budget_pct > 0
                    AND risk_budget_pct <= 1
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
        WHERE conname = 'signals_position_size_shares_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_position_size_shares_check
            CHECK (
                position_size_shares IS NULL
                OR position_size_shares >= 0
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_position_size_lots_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_position_size_lots_check
            CHECK (
                position_size_lots IS NULL
                OR position_size_lots >= 0
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'signals_capital_required_check'
          AND conrelid = 'public.signals'::regclass
    ) THEN
        ALTER TABLE public.signals
            ADD CONSTRAINT signals_capital_required_check
            CHECK (
                capital_required IS NULL
                OR capital_required >= 0
            );
    END IF;
END
$$;


DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.signals
        GROUP BY
            instrument_id,
            trading_date,
            model_version
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION
            'Cannot add signal model uniqueness: duplicate signal groups exist.';
    END IF;
END
$$;


CREATE UNIQUE INDEX IF NOT EXISTS
    signals_instrument_date_model_uidx
ON public.signals (
    instrument_id,
    trading_date,
    model_version
);


CREATE INDEX IF NOT EXISTS
    signals_model_date_decision_idx
ON public.signals (
    model_version,
    trading_date,
    setup_decision
);


CREATE INDEX IF NOT EXISTS
    signals_model_date_status_idx
ON public.signals (
    model_version,
    trading_date,
    status
);


CREATE TABLE IF NOT EXISTS public.pipeline_build_state (
    model_version TEXT PRIMARY KEY,
    pipeline_name TEXT NOT NULL,
    input_model_version TEXT NOT NULL,
    processed_through DATE,
    processed_input_updated_at TIMESTAMPTZ,
    output_rows BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'pipeline_build_state_output_rows_check'
          AND conrelid = 'public.pipeline_build_state'::regclass
    ) THEN
        ALTER TABLE public.pipeline_build_state
            ADD CONSTRAINT pipeline_build_state_output_rows_check
            CHECK (output_rows >= 0);
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    pipeline_build_state_pipeline_idx
ON public.pipeline_build_state (
    pipeline_name,
    processed_through
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.pipeline_build_state
TO imi;


COMMIT;