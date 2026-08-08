BEGIN;

CREATE TABLE IF NOT EXISTS integrated_sector_intelligence (
    trading_date DATE NOT NULL,
    sector_code TEXT NOT NULL,

    technical_score NUMERIC(12, 6) NOT NULL,
    technical_rotation_label TEXT NOT NULL,

    ownership_as_of_date DATE NOT NULL,
    ownership_score NUMERIC(12, 6) NOT NULL,
    ownership_signal_label TEXT NOT NULL,

    ownership_age_days INTEGER NOT NULL,
    ownership_low_coverage_flag BOOLEAN NOT NULL,
    ownership_stale_flag BOOLEAN NOT NULL,

    technical_weight NUMERIC(8, 6) NOT NULL,
    ownership_weight NUMERIC(8, 6) NOT NULL,

    integrated_score NUMERIC(12, 6) NOT NULL,

    integrated_label TEXT NOT NULL,
    alignment_label TEXT NOT NULL,

    technical_model_version TEXT NOT NULL,
    ownership_model_version TEXT NOT NULL,
    model_version TEXT NOT NULL,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT integrated_sector_intelligence_pkey
        PRIMARY KEY (
            trading_date,
            sector_code,
            model_version
        ),

    CONSTRAINT integrated_sector_date_check
        CHECK (
            ownership_as_of_date
            <= trading_date
        ),

    CONSTRAINT integrated_sector_age_check
        CHECK (
            ownership_age_days >= 0
        ),

    CONSTRAINT integrated_sector_score_check
        CHECK (
            technical_score
                BETWEEN 0 AND 100
            AND ownership_score
                BETWEEN 0 AND 100
            AND integrated_score
                BETWEEN 0 AND 100
        ),

    CONSTRAINT integrated_sector_weight_check
        CHECK (
            technical_weight
                BETWEEN 0 AND 1
            AND ownership_weight
                BETWEEN 0 AND 1
            AND (
                technical_weight
                + ownership_weight
            )
            BETWEEN 0.999999
                AND 1.000001
        ),

    CONSTRAINT integrated_sector_technical_label_check
        CHECK (
            technical_rotation_label IN (
                'LEADING',
                'IMPROVING',
                'NEUTRAL',
                'WEAKENING',
                'LAGGING'
            )
        ),

    CONSTRAINT integrated_sector_ownership_label_check
        CHECK (
            ownership_signal_label IN (
                'STRONG_ACCUMULATION',
                'ACCUMULATION',
                'NEUTRAL',
                'DISTRIBUTION',
                'STRONG_DISTRIBUTION'
            )
        ),

    CONSTRAINT integrated_sector_label_check
        CHECK (
            integrated_label IN (
                'STRONG_BULLISH',
                'BULLISH',
                'NEUTRAL',
                'BEARISH',
                'STRONG_BEARISH'
            )
        ),

    CONSTRAINT integrated_sector_alignment_check
        CHECK (
            alignment_label IN (
                'CONFIRMED_BULLISH',
                'CONFIRMED_BEARISH',
                'TECHNICAL_LEAD',
                'OWNERSHIP_LEAD',
                'DIVERGENCE',
                'NEUTRAL',
                'OWNERSHIP_STALE'
            )
        )
);

CREATE INDEX IF NOT EXISTS
    idx_integrated_sector_date
ON integrated_sector_intelligence (
    trading_date
);

CREATE INDEX IF NOT EXISTS
    idx_integrated_sector_model_date
ON integrated_sector_intelligence (
    model_version,
    trading_date
);

CREATE INDEX IF NOT EXISTS
    idx_integrated_sector_score_date
ON integrated_sector_intelligence (
    trading_date,
    integrated_score DESC
);

CREATE INDEX IF NOT EXISTS
    idx_integrated_sector_sector_date
ON integrated_sector_intelligence (
    sector_code,
    trading_date
);

CREATE INDEX IF NOT EXISTS
    idx_integrated_sector_alignment_date
ON integrated_sector_intelligence (
    trading_date,
    alignment_label
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
        ON integrated_sector_intelligence
        TO imi;
    END IF;
END
$$;

COMMIT;