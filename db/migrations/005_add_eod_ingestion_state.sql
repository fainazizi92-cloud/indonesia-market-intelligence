BEGIN;

CREATE TABLE IF NOT EXISTS
public.eod_ingestion_state (
    instrument_id UUID NOT NULL,
    source_id UUID NOT NULL,

    status TEXT NOT NULL
        DEFAULT 'PENDING',

    start_date DATE NOT NULL,
    target_end_date DATE NOT NULL,

    next_start_date DATE,

    last_attempted_date DATE,
    last_success_date DATE,

    rows_loaded BIGINT NOT NULL
        DEFAULT 0,

    attempts INTEGER NOT NULL
        DEFAULT 0,

    last_error TEXT,

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT eod_ingestion_state_pkey
        PRIMARY KEY (
            instrument_id,
            source_id
        ),

    CONSTRAINT
        eod_ingestion_state_instrument_fkey
        FOREIGN KEY (
            instrument_id
        )
        REFERENCES public.instruments(id),

    CONSTRAINT
        eod_ingestion_state_source_fkey
        FOREIGN KEY (
            source_id
        )
        REFERENCES public.data_sources(id),

    CONSTRAINT
        eod_ingestion_state_status_check
        CHECK (
            status IN (
                'PENDING',
                'RUNNING',
                'PARTIAL',
                'COMPLETE',
                'FAILED'
            )
        )
);

CREATE INDEX IF NOT EXISTS
idx_eod_ingestion_state_status
ON public.eod_ingestion_state (
    status,
    updated_at
);

CREATE INDEX IF NOT EXISTS
idx_eod_ingestion_state_instrument
ON public.eod_ingestion_state (
    instrument_id
);

COMMIT;