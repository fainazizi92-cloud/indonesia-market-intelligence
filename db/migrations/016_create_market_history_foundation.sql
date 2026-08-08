BEGIN;


CREATE TABLE IF NOT EXISTS public.instrument_board_history (
    instrument_id UUID NOT NULL
        REFERENCES public.instruments(id)
        ON DELETE CASCADE,

    effective_from DATE NOT NULL,
    effective_to DATE,

    board_code TEXT NOT NULL,
    raw_board_name TEXT,

    source_code TEXT NOT NULL,

    available_at TIMESTAMPTZ,

    availability_status TEXT NOT NULL
        DEFAULT 'UNKNOWN',

    point_in_time_safe BOOLEAN NOT NULL
        DEFAULT FALSE,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    PRIMARY KEY (
        instrument_id,
        effective_from,
        source_code
    ),

    CONSTRAINT
        instrument_board_date_check
    CHECK (
        effective_to IS NULL
        OR effective_to >= effective_from
    ),

    CONSTRAINT
        instrument_board_code_check
    CHECK (
        board_code IN (
            'MAIN',
            'DEVELOPMENT',
            'NEW_ECONOMY',
            'ACCELERATION',
            'WATCHLIST',
            'UNKNOWN'
        )
    ),

    CONSTRAINT
        instrument_board_availability_check
    CHECK (
        availability_status IN (
            'KNOWN',
            'UNKNOWN',
            'ESTIMATED'
        )
    )
);


CREATE TABLE IF NOT EXISTS public.idx_market_rule_history (
    rule_key TEXT PRIMARY KEY,

    rule_type TEXT NOT NULL,

    market TEXT NOT NULL
        DEFAULT 'REGULAR_CASH',

    board_group TEXT NOT NULL
        DEFAULT 'ALL',

    effective_from DATE NOT NULL,
    effective_to DATE,

    price_min NUMERIC(20,6),
    price_min_inclusive BOOLEAN,

    price_max NUMERIC(20,6),
    price_max_inclusive BOOLEAN,

    lot_size INTEGER,

    tick_size NUMERIC(20,6),

    ara_pct NUMERIC(12,8),
    arb_pct NUMERIC(12,8),

    ara_absolute NUMERIC(20,6),
    arb_absolute NUMERIC(20,6),

    source_reference TEXT NOT NULL,

    verification_status TEXT NOT NULL,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT
        idx_rule_type_check
    CHECK (
        rule_type IN (
            'LOT_SIZE',
            'TICK_SIZE',
            'AUTO_REJECTION'
        )
    ),

    CONSTRAINT
        idx_rule_date_check
    CHECK (
        effective_to IS NULL
        OR effective_to >= effective_from
    ),

    CONSTRAINT
        idx_rule_verification_check
    CHECK (
        verification_status IN (
            'OFFICIAL',
            'REFERENCE_ONLY'
        )
    ),

    CONSTRAINT
        idx_rule_lot_check
    CHECK (
        lot_size IS NULL
        OR lot_size > 0
    ),

    CONSTRAINT
        idx_rule_tick_check
    CHECK (
        tick_size IS NULL
        OR tick_size > 0
    )
);


CREATE TABLE IF NOT EXISTS public.historical_data_coverage_state (
    dataset_code TEXT PRIMARY KEY,

    observed_rows BIGINT NOT NULL
        DEFAULT 0,

    distinct_instruments BIGINT NOT NULL
        DEFAULT 0,

    point_in_time_safe_rows BIGINT NOT NULL
        DEFAULT 0,

    first_observation_date DATE,
    last_observation_date DATE,

    complete_history BOOLEAN NOT NULL
        DEFAULT FALSE,

    blocking_reason TEXT,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    calculated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT
        historical_coverage_counts_check
    CHECK (
        observed_rows >= 0
        AND distinct_instruments >= 0
        AND point_in_time_safe_rows >= 0
    )
);


CREATE INDEX IF NOT EXISTS
    instrument_board_history_date_idx
ON public.instrument_board_history (
    effective_from,
    effective_to,
    board_code
);


CREATE INDEX IF NOT EXISTS
    instrument_board_history_instrument_idx
ON public.instrument_board_history (
    instrument_id,
    effective_from DESC
);


CREATE INDEX IF NOT EXISTS
    idx_market_rule_history_type_date_idx
ON public.idx_market_rule_history (
    rule_type,
    effective_from,
    effective_to
);


CREATE INDEX IF NOT EXISTS
    idx_market_rule_history_board_idx
ON public.idx_market_rule_history (
    board_group,
    effective_from
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.instrument_board_history
TO imi;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.idx_market_rule_history
TO imi;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.historical_data_coverage_state
TO imi;


COMMIT;