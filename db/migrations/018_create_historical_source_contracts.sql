BEGIN;


CREATE TABLE IF NOT EXISTS public.historical_source_contract_snapshots (
    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    source_key TEXT NOT NULL
        REFERENCES public.historical_source_catalog(source_key)
        ON DELETE CASCADE,

    inspected_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    requested_url TEXT NOT NULL,

    final_url TEXT,

    http_status SMALLINT,

    content_type TEXT,

    body_sha256 TEXT,

    body_length BIGINT,

    anchor_count INTEGER NOT NULL
        DEFAULT 0,

    script_count INTEGER NOT NULL
        DEFAULT 0,

    form_count INTEGER NOT NULL
        DEFAULT 0,

    candidate_url_count INTEGER NOT NULL
        DEFAULT 0,

    candidate_urls JSONB NOT NULL
        DEFAULT '[]'::jsonb,

    endpoint_hints JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    parser_ready BOOLEAN NOT NULL
        DEFAULT FALSE,

    parser_status TEXT NOT NULL
        DEFAULT 'DISCOVERY',

    error_type TEXT,

    error_message TEXT,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    CONSTRAINT
        historical_contract_http_check
    CHECK (
        http_status IS NULL
        OR http_status BETWEEN 100 AND 599
    ),

    CONSTRAINT
        historical_contract_length_check
    CHECK (
        body_length IS NULL
        OR body_length >= 0
    ),

    CONSTRAINT
        historical_contract_count_check
    CHECK (
        anchor_count >= 0
        AND script_count >= 0
        AND form_count >= 0
        AND candidate_url_count >= 0
    ),

    CONSTRAINT
        historical_contract_parser_status_check
    CHECK (
        parser_status IN (
            'DISCOVERY',
            'CANDIDATE',
            'READY',
            'BLOCKED'
        )
    ),

    CONSTRAINT
        historical_contract_hash_check
    CHECK (
        body_sha256 IS NULL
        OR length(body_sha256) = 64
    )
);


CREATE INDEX IF NOT EXISTS
    historical_source_contract_latest_idx
ON public.historical_source_contract_snapshots (
    source_key,
    inspected_at DESC
);


CREATE INDEX IF NOT EXISTS
    historical_source_contract_status_idx
ON public.historical_source_contract_snapshots (
    parser_status,
    inspected_at DESC
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.historical_source_contract_snapshots
TO imi;


COMMIT;