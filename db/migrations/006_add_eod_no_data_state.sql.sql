BEGIN;

ALTER TABLE public.eod_ingestion_state
DROP CONSTRAINT IF EXISTS
eod_ingestion_state_status_check;

ALTER TABLE public.eod_ingestion_state
ADD CONSTRAINT
eod_ingestion_state_status_check
CHECK (
    status IN (
        'PENDING',
        'RUNNING',
        'PARTIAL',
        'COMPLETE',
        'FAILED',
        'NO_DATA'
    )
);

COMMIT;