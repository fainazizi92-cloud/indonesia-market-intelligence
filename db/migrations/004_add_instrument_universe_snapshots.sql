BEGIN;

CREATE TABLE IF NOT EXISTS
public.instrument_universe_snapshots (
    snapshot_date date NOT NULL,
    universe_code text NOT NULL,
    instrument_id uuid NOT NULL,
    source_id uuid NOT NULL,
    is_member boolean NOT NULL
        DEFAULT TRUE,
    listing_status text NOT NULL
        DEFAULT 'CURRENT_PROFILE',
    metadata jsonb NOT NULL
        DEFAULT '{}'::jsonb,
    ingested_at timestamptz NOT NULL
        DEFAULT NOW(),

    CONSTRAINT
        instrument_universe_snapshots_pkey
    PRIMARY KEY (
        snapshot_date,
        universe_code,
        instrument_id
    ),

    CONSTRAINT
        instrument_universe_snapshots_instrument_fkey
    FOREIGN KEY (
        instrument_id
    )
    REFERENCES public.instruments(id),

    CONSTRAINT
        instrument_universe_snapshots_source_fkey
    FOREIGN KEY (
        source_id
    )
    REFERENCES public.data_sources(id)
);

CREATE INDEX IF NOT EXISTS
idx_universe_snapshot_code_date
ON public.instrument_universe_snapshots (
    universe_code,
    snapshot_date DESC
);

CREATE INDEX IF NOT EXISTS
idx_universe_snapshot_instrument
ON public.instrument_universe_snapshots (
    instrument_id,
    snapshot_date DESC
);

COMMIT;