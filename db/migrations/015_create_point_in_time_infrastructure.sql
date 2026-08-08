BEGIN;


CREATE TABLE IF NOT EXISTS public.instrument_lifecycle_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    instrument_id UUID NOT NULL
        REFERENCES public.instruments(id)
        ON DELETE CASCADE,

    effective_from DATE NOT NULL,

    effective_to DATE,

    lifecycle_status TEXT NOT NULL,

    listing_date DATE,

    delisting_date DATE,

    source_code TEXT NOT NULL,

    source_reference TEXT,

    available_at TIMESTAMPTZ,

    availability_status TEXT NOT NULL
        DEFAULT 'UNKNOWN',

    quality quality_status NOT NULL
        DEFAULT 'VALID',

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    ingested_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    CONSTRAINT
        instrument_lifecycle_date_check
    CHECK (
        effective_to IS NULL
        OR effective_to >= effective_from
    ),

    CONSTRAINT
        instrument_lifecycle_status_check
    CHECK (
        lifecycle_status IN (
            'LISTED',
            'SUSPENDED',
            'DELISTED',
            'UNKNOWN'
        )
    ),

    CONSTRAINT
        instrument_lifecycle_availability_check
    CHECK (
        availability_status IN (
            'KNOWN',
            'UNKNOWN',
            'ESTIMATED'
        )
    ),

    UNIQUE (
        instrument_id,
        effective_from,
        source_code
    )
);


CREATE TABLE IF NOT EXISTS public.historical_universe_membership (
    instrument_id UUID NOT NULL
        REFERENCES public.instruments(id)
        ON DELETE CASCADE,

    universe_code TEXT NOT NULL,

    valid_from DATE NOT NULL,

    valid_to DATE,

    membership_status TEXT NOT NULL,

    source_code TEXT NOT NULL,

    available_at TIMESTAMPTZ,

    availability_status TEXT NOT NULL
        DEFAULT 'UNKNOWN',

    point_in_time_safe BOOLEAN NOT NULL
        DEFAULT FALSE,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    PRIMARY KEY (
        instrument_id,
        universe_code,
        valid_from,
        source_code
    ),

    CONSTRAINT
        historical_universe_date_check
    CHECK (
        valid_to IS NULL
        OR valid_to >= valid_from
    ),

    CONSTRAINT
        historical_universe_status_check
    CHECK (
        membership_status IN (
            'ACTIVE',
            'INACTIVE',
            'UNKNOWN'
        )
    ),

    CONSTRAINT
        historical_universe_availability_check
    CHECK (
        availability_status IN (
            'KNOWN',
            'UNKNOWN',
            'ESTIMATED'
        )
    )
);


CREATE TABLE IF NOT EXISTS public.data_publication_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    dataset_code TEXT NOT NULL,

    observation_key TEXT NOT NULL,

    observation_date DATE NOT NULL,

    published_at TIMESTAMPTZ,

    available_at TIMESTAMPTZ,

    availability_status TEXT NOT NULL,

    source_code TEXT NOT NULL,

    source_reference TEXT,

    point_in_time_safe BOOLEAN NOT NULL
        DEFAULT FALSE,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    ingested_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    CONSTRAINT
        publication_availability_status_check
    CHECK (
        availability_status IN (
            'KNOWN',
            'UNKNOWN',
            'ESTIMATED'
        )
    ),

    CONSTRAINT
        publication_available_order_check
    CHECK (
        published_at IS NULL
        OR available_at IS NULL
        OR available_at >= published_at
    ),

    UNIQUE (
        dataset_code,
        observation_key,
        observation_date,
        source_code
    )
);


CREATE TABLE IF NOT EXISTS public.point_in_time_audit_state (
    dataset_code TEXT PRIMARY KEY,

    total_observations BIGINT NOT NULL,

    known_availability BIGINT NOT NULL,

    unknown_availability BIGINT NOT NULL,

    estimated_availability BIGINT NOT NULL,

    pit_safe_observations BIGINT NOT NULL,

    first_observation_date DATE,

    last_observation_date DATE,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT now(),

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    CONSTRAINT
        point_in_time_counts_check
    CHECK (
        total_observations >= 0
        AND known_availability >= 0
        AND unknown_availability >= 0
        AND estimated_availability >= 0
        AND pit_safe_observations >= 0
    )
);


CREATE INDEX IF NOT EXISTS
    instrument_lifecycle_instrument_date_idx
ON public.instrument_lifecycle_history (
    instrument_id,
    effective_from,
    effective_to
);


CREATE INDEX IF NOT EXISTS
    historical_universe_date_idx
ON public.historical_universe_membership (
    universe_code,
    valid_from,
    valid_to
);


CREATE INDEX IF NOT EXISTS
    historical_universe_pit_idx
ON public.historical_universe_membership (
    universe_code,
    point_in_time_safe,
    valid_from
);


CREATE INDEX IF NOT EXISTS
    publication_dataset_date_idx
ON public.data_publication_availability (
    dataset_code,
    observation_date
);


CREATE INDEX IF NOT EXISTS
    publication_pit_idx
ON public.data_publication_availability (
    dataset_code,
    point_in_time_safe,
    observation_date
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.instrument_lifecycle_history
TO imi;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.historical_universe_membership
TO imi;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.data_publication_availability
TO imi;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.point_in_time_audit_state
TO imi;


COMMIT;