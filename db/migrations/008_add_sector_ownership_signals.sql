BEGIN;

CREATE TABLE IF NOT EXISTS sector_ownership_signals (
    as_of_date DATE NOT NULL,
    sector_code TEXT NOT NULL,

    eligible_count INTEGER NOT NULL,
    current_universe_count INTEGER NOT NULL,
    coverage_pct NUMERIC(12, 6) NOT NULL,

    clean_count INTEGER NOT NULL,

    accumulating_count INTEGER NOT NULL,
    stable_count INTEGER NOT NULL,
    distributing_count INTEGER NOT NULL,

    corporate_action_risk_count INTEGER NOT NULL,
    snapshot_gap_count INTEGER NOT NULL,
    extreme_move_count INTEGER NOT NULL,

    avg_delta_foreign_ownership_pp
        NUMERIC(18, 8) NOT NULL,

    avg_clean_clipped_delta_pp
        NUMERIC(18, 8) NOT NULL,

    breadth_score NUMERIC(12, 6) NOT NULL,
    intensity_score NUMERIC(12, 6) NOT NULL,
    score NUMERIC(12, 6) NOT NULL,

    signal_label TEXT NOT NULL,
    low_coverage_flag BOOLEAN NOT NULL,

    source_id UUID NOT NULL,
    input_model_version TEXT NOT NULL,
    model_version TEXT NOT NULL,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT sector_ownership_signals_pkey
        PRIMARY KEY (
            as_of_date,
            sector_code,
            source_id,
            model_version
        ),

    CONSTRAINT sector_ownership_signals_source_fkey
        FOREIGN KEY (source_id)
        REFERENCES data_sources(id),

    CONSTRAINT sector_ownership_counts_check
        CHECK (
            eligible_count > 0
            AND current_universe_count > 0
            AND clean_count >= 0
            AND clean_count <= eligible_count
            AND accumulating_count >= 0
            AND stable_count >= 0
            AND distributing_count >= 0
            AND corporate_action_risk_count >= 0
            AND snapshot_gap_count >= 0
            AND extreme_move_count >= 0
        ),

    CONSTRAINT sector_ownership_clean_population_check
        CHECK (
            accumulating_count
            + stable_count
            + distributing_count
            =
            clean_count
        ),

    CONSTRAINT sector_ownership_risk_count_check
        CHECK (
            corporate_action_risk_count
            <= eligible_count
            AND snapshot_gap_count
            <= eligible_count
            AND extreme_move_count
            <= eligible_count
        ),

    CONSTRAINT sector_ownership_coverage_check
        CHECK (
            coverage_pct
            BETWEEN 0 AND 100
        ),

    CONSTRAINT sector_ownership_score_check
        CHECK (
            breadth_score
            BETWEEN 0 AND 100
            AND intensity_score
            BETWEEN 0 AND 100
            AND score
            BETWEEN 0 AND 100
        ),

    CONSTRAINT sector_ownership_label_check
        CHECK (
            signal_label IN (
                'STRONG_ACCUMULATION',
                'ACCUMULATION',
                'NEUTRAL',
                'DISTRIBUTION',
                'STRONG_DISTRIBUTION'
            )
        )
);

CREATE INDEX IF NOT EXISTS
    idx_sector_ownership_date
ON sector_ownership_signals (
    as_of_date
);

CREATE INDEX IF NOT EXISTS
    idx_sector_ownership_model_date
ON sector_ownership_signals (
    model_version,
    as_of_date
);

CREATE INDEX IF NOT EXISTS
    idx_sector_ownership_score_date
ON sector_ownership_signals (
    as_of_date,
    score DESC
);

CREATE INDEX IF NOT EXISTS
    idx_sector_ownership_sector_date
ON sector_ownership_signals (
    sector_code,
    as_of_date
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
        ON sector_ownership_signals
        TO imi;
    END IF;
END
$$;

COMMIT;