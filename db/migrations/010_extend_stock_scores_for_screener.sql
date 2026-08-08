BEGIN;

ALTER TABLE stock_scores_daily
    ADD COLUMN IF NOT EXISTS
        ownership_score NUMERIC(8,4);

ALTER TABLE stock_scores_daily
    ADD COLUMN IF NOT EXISTS
        status signal_status;

ALTER TABLE stock_scores_daily
    ADD COLUMN IF NOT EXISTS
        universe_rank INTEGER;

ALTER TABLE stock_scores_daily
    ADD COLUMN IF NOT EXISTS
        sector_rank INTEGER;

ALTER TABLE stock_scores_daily
    ADD COLUMN IF NOT EXISTS
        input_updated_at TIMESTAMPTZ;

ALTER TABLE stock_scores_daily
    ADD COLUMN IF NOT EXISTS
        evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname =
              'stock_scores_ownership_score_check'
    ) THEN
        ALTER TABLE stock_scores_daily
            ADD CONSTRAINT
                stock_scores_ownership_score_check
            CHECK (
                ownership_score IS NULL
                OR ownership_score
                   BETWEEN 0 AND 100
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
              'stock_scores_universe_rank_check'
    ) THEN
        ALTER TABLE stock_scores_daily
            ADD CONSTRAINT
                stock_scores_universe_rank_check
            CHECK (
                universe_rank IS NULL
                OR universe_rank > 0
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
              'stock_scores_sector_rank_check'
    ) THEN
        ALTER TABLE stock_scores_daily
            ADD CONSTRAINT
                stock_scores_sector_rank_check
            CHECK (
                sector_rank IS NULL
                OR sector_rank > 0
            );
    END IF;
END
$$;


CREATE INDEX IF NOT EXISTS
    idx_stock_scores_model_date_score
ON stock_scores_daily (
    model_version,
    trading_date,
    overall_score DESC
);


CREATE INDEX IF NOT EXISTS
    idx_stock_scores_model_date_status
ON stock_scores_daily (
    model_version,
    trading_date,
    status
);


CREATE INDEX IF NOT EXISTS
    idx_stock_scores_model_date_rank
ON stock_scores_daily (
    model_version,
    trading_date,
    universe_rank
);


DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'imi'
    ) THEN
        GRANT
            SELECT,
            INSERT,
            UPDATE,
            DELETE
        ON stock_scores_daily
        TO imi;
    END IF;
END
$$;

COMMIT;