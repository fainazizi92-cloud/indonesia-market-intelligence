BEGIN;


CREATE TABLE IF NOT EXISTS public.historical_source_catalog (
    source_key TEXT PRIMARY KEY,

    source_id UUID NOT NULL
        REFERENCES public.data_sources(id),

    dataset_family TEXT NOT NULL,

    source_kind TEXT NOT NULL,

    authority_class TEXT NOT NULL,

    base_url TEXT NOT NULL,

    probe_url TEXT NOT NULL,

    historical_access TEXT NOT NULL,

    access_mode TEXT NOT NULL,

    supports_download BOOLEAN NOT NULL
        DEFAULT FALSE,

    supports_date_filter BOOLEAN NOT NULL
        DEFAULT FALSE,

    point_in_time_potential BOOLEAN NOT NULL
        DEFAULT FALSE,

    automation_status TEXT NOT NULL
        DEFAULT 'DISCOVERY_ONLY',

    priority SMALLINT NOT NULL
        DEFAULT 3,

    probe_config JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    updated_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    CONSTRAINT
        historical_source_family_check
    CHECK (
        dataset_family IN (
            'LIFECYCLE',
            'BOARD_HISTORY',
            'CORPORATE_ACTION',
            'CURRENT_CROSSCHECK'
        )
    ),

    CONSTRAINT
        historical_source_kind_check
    CHECK (
        source_kind IN (
            'HTML_PAGE',
            'DIGITAL_STAT',
            'ANNOUNCEMENT_ARCHIVE',
            'UNDOCUMENTED_API'
        )
    ),

    CONSTRAINT
        historical_source_authority_check
    CHECK (
        authority_class IN (
            'PRIMARY_OFFICIAL',
            'PRIMARY_OFFICIAL_LIMITED',
            'OFFICIAL_UNDOCUMENTED'
        )
    ),

    CONSTRAINT
        historical_source_access_check
    CHECK (
        historical_access IN (
            'CURRENT_ONLY',
            'YEAR_FILTER',
            'MONTHLY_ARCHIVE',
            'DATE_FILTER',
            'THREE_YEAR_WINDOW'
        )
    ),

    CONSTRAINT
        historical_source_mode_check
    CHECK (
        access_mode IN (
            'PUBLIC_WEB',
            'PUBLIC_DOWNLOAD',
            'UNDOCUMENTED_API'
        )
    ),

    CONSTRAINT
        historical_source_automation_check
    CHECK (
        automation_status IN (
            'DISCOVERY_ONLY',
            'CANDIDATE',
            'APPROVED',
            'BLOCKED'
        )
    ),

    CONSTRAINT
        historical_source_priority_check
    CHECK (
        priority BETWEEN 1 AND 5
    )
);


CREATE TABLE IF NOT EXISTS public.historical_source_probe_runs (
    id UUID PRIMARY KEY
        DEFAULT gen_random_uuid(),

    source_key TEXT NOT NULL
        REFERENCES public.historical_source_catalog(source_key)
        ON DELETE CASCADE,

    checked_at TIMESTAMPTZ NOT NULL
        DEFAULT NOW(),

    success BOOLEAN NOT NULL,

    http_status SMALLINT,

    final_url TEXT,

    content_type TEXT,

    content_length BIGINT,

    marker_hits INTEGER NOT NULL
        DEFAULT 0,

    marker_total INTEGER NOT NULL
        DEFAULT 0,

    elapsed_ms NUMERIC(14,3),

    error_type TEXT,

    error_message TEXT,

    marker_details JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    evidence JSONB NOT NULL
        DEFAULT '{}'::jsonb,

    CONSTRAINT
        historical_probe_marker_check
    CHECK (
        marker_hits >= 0
        AND marker_total >= 0
        AND marker_hits <= marker_total
    ),

    CONSTRAINT
        historical_probe_http_check
    CHECK (
        http_status IS NULL
        OR http_status BETWEEN 100 AND 599
    ),

    CONSTRAINT
        historical_probe_length_check
    CHECK (
        content_length IS NULL
        OR content_length >= 0
    )
);


CREATE INDEX IF NOT EXISTS
    historical_source_family_priority_idx
ON public.historical_source_catalog (
    dataset_family,
    priority,
    source_key
);


CREATE INDEX IF NOT EXISTS
    historical_source_probe_latest_idx
ON public.historical_source_probe_runs (
    source_key,
    checked_at DESC
);


CREATE INDEX IF NOT EXISTS
    historical_source_probe_success_idx
ON public.historical_source_probe_runs (
    success,
    checked_at DESC
);


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.historical_source_catalog
TO imi;


GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE public.historical_source_probe_runs
TO imi;


COMMIT;