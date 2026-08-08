BEGIN;


CREATE TABLE IF NOT EXISTS public.backtest_calibration_rows (
    signal_id UUID NOT NULL
        REFERENCES public.signals(id)
        ON DELETE CASCADE,

    dataset_version TEXT NOT NULL,

    outcome_model_version TEXT NOT NULL,

    instrument_id UUID NOT NULL
        REFERENCES public.instruments(id),

    signal_date DATE NOT NULL,

    sector_code TEXT,

    sample_status TEXT NOT NULL,

    split_label TEXT NOT NULL,

    calibration_eligible BOOLEAN NOT NULL,

    outcome_label TEXT NOT NULL,

    entry_filled BOOLEAN NOT NULL,

    horizon_complete BOOLEAN NOT NULL,

    entry_date DATE,

    exit_date DATE,

    realized_return NUMERIC(18,8),

    realized_r NUMERIC(18,8),

    mfe_r NUMERIC(18,8),

    mae_r NUMERIC(18,8),

    target_hit BOOLEAN NOT NULL,

    stop_hit BOOLEAN NOT NULL,

    tp_before_sl_label BOOLEAN,

    positive_r_label BOOLEAN,

    setup_expected_rr NUMERIC(18,8),

    setup_risk_pct NUMERIC(18,8),

    horizon_days INTEGER,

    overall_score NUMERIC(8,4),

    market_score NUMERIC(8,4),

    sector_score NUMERIC(8,4),

    technical_score NUMERIC(8,4),

    liquidity_score NUMERIC(8,4),

    ownership_score NUMERIC(8,4),

    risk_score NUMERIC(8,4),

    data_completeness NUMERIC(8,4),

    score_bucket TEXT,

    input_updated_at TIMESTAMPTZ,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    PRIMARY KEY (
        signal_id,
        dataset_version
    )
);


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'backtest_calibration_sample_status_check'
          AND conrelid =
              'public.backtest_calibration_rows'::regclass
    ) THEN
        ALTER TABLE public.backtest_calibration_rows
            ADD CONSTRAINT
                backtest_calibration_sample_status_check
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
              'backtest_calibration_split_check'
          AND conrelid =
              'public.backtest_calibration_rows'::regclass
    ) THEN
        ALTER TABLE public.backtest_calibration_rows
            ADD CONSTRAINT
                backtest_calibration_split_check
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
              'backtest_calibration_score_bucket_check'
          AND conrelid =
              'public.backtest_calibration_rows'::regclass
    ) THEN
        ALTER TABLE public.backtest_calibration_rows
            ADD CONSTRAINT
                backtest_calibration_score_bucket_check
            CHECK (
                score_bucket IS NULL
                OR score_bucket IN (
                    'GE_70',
                    '67_TO_70',
                    '65_TO_67',
                    'LT_65'
                )
            );
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    backtest_calibration_dataset_split_idx
ON public.backtest_calibration_rows (
    dataset_version,
    split_label
);


CREATE INDEX IF NOT EXISTS
    backtest_calibration_dataset_sample_idx
ON public.backtest_calibration_rows (
    dataset_version,
    sample_status
);


CREATE INDEX IF NOT EXISTS
    backtest_calibration_dataset_outcome_idx
ON public.backtest_calibration_rows (
    dataset_version,
    outcome_label
);


CREATE INDEX IF NOT EXISTS
    backtest_calibration_dataset_sector_idx
ON public.backtest_calibration_rows (
    dataset_version,
    sector_code
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.backtest_calibration_rows
TO imi;


COMMIT;