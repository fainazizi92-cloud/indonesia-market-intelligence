BEGIN;

CREATE TABLE IF NOT EXISTS ownership_trends (
    instrument_id UUID NOT NULL,
    as_of_date DATE NOT NULL,
    previous_as_of_date DATE NOT NULL,

    foreign_ownership_pct NUMERIC(18, 8) NOT NULL,
    previous_foreign_ownership_pct NUMERIC(18, 8) NOT NULL,
    delta_foreign_ownership_pp NUMERIC(18, 8) NOT NULL,

    foreign_shares NUMERIC(30, 0) NOT NULL,
    previous_foreign_shares NUMERIC(30, 0) NOT NULL,
    delta_foreign_shares NUMERIC(30, 0) NOT NULL,

    security_number NUMERIC(30, 0) NOT NULL,
    previous_security_number NUMERIC(30, 0) NOT NULL,

    delta_security_number_pct NUMERIC(18, 8) NOT NULL,
    normalized_foreign_share_change_pct NUMERIC(18, 8) NOT NULL,

    days_between_snapshots INTEGER NOT NULL,

    trend_label TEXT NOT NULL,
    signal_strength NUMERIC(8, 4) NOT NULL,

    corporate_action_risk BOOLEAN NOT NULL,
    snapshot_gap_flag BOOLEAN NOT NULL,

    source_id UUID NOT NULL,
    model_version TEXT NOT NULL,

    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT ownership_trends_pkey
        PRIMARY KEY (
            instrument_id,
            as_of_date,
            source_id,
            model_version
        ),

    CONSTRAINT ownership_trends_instrument_fkey
        FOREIGN KEY (instrument_id)
        REFERENCES instruments(id),

    CONSTRAINT ownership_trends_source_fkey
        FOREIGN KEY (source_id)
        REFERENCES data_sources(id),

    CONSTRAINT ownership_trends_current_snapshot_fkey
        FOREIGN KEY (
            instrument_id,
            as_of_date,
            source_id
        )
        REFERENCES ownership_snapshots (
            instrument_id,
            as_of_date,
            source_id
        )
        ON DELETE CASCADE,

    CONSTRAINT ownership_trends_previous_snapshot_fkey
        FOREIGN KEY (
            instrument_id,
            previous_as_of_date,
            source_id
        )
        REFERENCES ownership_snapshots (
            instrument_id,
            as_of_date,
            source_id
        )
        ON DELETE CASCADE,

    CONSTRAINT ownership_trends_date_order_check
        CHECK (
            previous_as_of_date < as_of_date
        ),

    CONSTRAINT ownership_trends_foreign_pct_check
        CHECK (
            foreign_ownership_pct
            BETWEEN 0 AND 100
        ),

    CONSTRAINT ownership_trends_previous_foreign_pct_check
        CHECK (
            previous_foreign_ownership_pct
            BETWEEN 0 AND 100
        ),

    CONSTRAINT ownership_trends_security_number_check
        CHECK (
            security_number > 0
            AND previous_security_number > 0
        ),

    CONSTRAINT ownership_trends_foreign_shares_check
        CHECK (
            foreign_shares >= 0
            AND previous_foreign_shares >= 0
        ),

    CONSTRAINT ownership_trends_days_check
        CHECK (
            days_between_snapshots > 0
        ),

    CONSTRAINT ownership_trends_label_check
        CHECK (
            trend_label IN (
                'ACCUMULATING',
                'STABLE',
                'DISTRIBUTING'
            )
        ),

    CONSTRAINT ownership_trends_strength_check
        CHECK (
            signal_strength
            BETWEEN 0 AND 100
        )
);

CREATE INDEX IF NOT EXISTS
    idx_ownership_trends_date
ON ownership_trends (
    as_of_date
);

CREATE INDEX IF NOT EXISTS
    idx_ownership_trends_model_date
ON ownership_trends (
    model_version,
    as_of_date
);

CREATE INDEX IF NOT EXISTS
    idx_ownership_trends_label_date
ON ownership_trends (
    trend_label,
    as_of_date
);

CREATE INDEX IF NOT EXISTS
    idx_ownership_trends_instrument_date
ON ownership_trends (
    instrument_id,
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
        ON ownership_trends
        TO imi;
    END IF;
END
$$;

COMMIT;