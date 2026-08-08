BEGIN;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS entry_filled BOOLEAN;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS entry_date DATE;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS entry_price NUMERIC(20,6);

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS exit_date DATE;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC(20,6);

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS outcome_label TEXT;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS realized_return NUMERIC(18,8);

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS realized_r NUMERIC(18,8);

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS mfe_r NUMERIC(18,8);

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS mae_r NUMERIC(18,8);

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS bars_to_entry INTEGER;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS bars_held INTEGER;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS target_hit_date DATE;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS stop_hit_date DATE;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS horizon_complete BOOLEAN
        NOT NULL
        DEFAULT FALSE;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS available_bars INTEGER
        NOT NULL
        DEFAULT 0;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS sequence_ambiguous BOOLEAN
        NOT NULL
        DEFAULT FALSE;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS evaluation_model_version TEXT;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS input_updated_at TIMESTAMPTZ;

ALTER TABLE public.signal_outcomes
    ADD COLUMN IF NOT EXISTS evidence JSONB
        NOT NULL
        DEFAULT '{}'::jsonb;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'signal_outcomes_label_check'
          AND conrelid =
              'public.signal_outcomes'::regclass
    ) THEN
        ALTER TABLE public.signal_outcomes
            ADD CONSTRAINT
                signal_outcomes_label_check
            CHECK (
                outcome_label IS NULL
                OR outcome_label IN (
                    'PENDING',
                    'NO_FILL',
                    'CANCELLED',
                    'OPEN',
                    'TARGET',
                    'STOP',
                    'EXPIRED'
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
              'signal_outcomes_available_bars_check'
          AND conrelid =
              'public.signal_outcomes'::regclass
    ) THEN
        ALTER TABLE public.signal_outcomes
            ADD CONSTRAINT
                signal_outcomes_available_bars_check
            CHECK (
                available_bars >= 0
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
              'signal_outcomes_bars_to_entry_check'
          AND conrelid =
              'public.signal_outcomes'::regclass
    ) THEN
        ALTER TABLE public.signal_outcomes
            ADD CONSTRAINT
                signal_outcomes_bars_to_entry_check
            CHECK (
                bars_to_entry IS NULL
                OR bars_to_entry >= 1
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
              'signal_outcomes_bars_held_check'
          AND conrelid =
              'public.signal_outcomes'::regclass
    ) THEN
        ALTER TABLE public.signal_outcomes
            ADD CONSTRAINT
                signal_outcomes_bars_held_check
            CHECK (
                bars_held IS NULL
                OR bars_held >= 1
            );
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    signal_outcomes_model_label_idx
ON public.signal_outcomes (
    evaluation_model_version,
    outcome_label
);


CREATE INDEX IF NOT EXISTS
    signal_outcomes_entry_date_idx
ON public.signal_outcomes (
    entry_date
);


CREATE INDEX IF NOT EXISTS
    signal_outcomes_exit_date_idx
ON public.signal_outcomes (
    exit_date
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.signal_outcomes
TO imi;


COMMIT;