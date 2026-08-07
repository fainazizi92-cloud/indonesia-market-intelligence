BEGIN;

ALTER TABLE public.trading_calendar
ADD COLUMN IF NOT EXISTS day_type text;

ALTER TABLE public.trading_calendar
ADD COLUMN IF NOT EXISTS source_id uuid;

ALTER TABLE public.trading_calendar
ADD COLUMN IF NOT EXISTS verified boolean;

ALTER TABLE public.trading_calendar
ADD COLUMN IF NOT EXISTS evidence jsonb;

ALTER TABLE public.trading_calendar
ADD COLUMN IF NOT EXISTS updated_at timestamptz;

UPDATE public.trading_calendar
SET day_type = CASE
    WHEN is_trading_day THEN 'OBSERVED_TRADING'
    ELSE 'UNKNOWN'
END
WHERE day_type IS NULL;

UPDATE public.trading_calendar
SET verified = FALSE
WHERE verified IS NULL;

UPDATE public.trading_calendar
SET evidence = '{}'::jsonb
WHERE evidence IS NULL;

UPDATE public.trading_calendar
SET updated_at = NOW()
WHERE updated_at IS NULL;

ALTER TABLE public.trading_calendar
ALTER COLUMN day_type
SET DEFAULT 'UNKNOWN';

ALTER TABLE public.trading_calendar
ALTER COLUMN day_type
SET NOT NULL;

ALTER TABLE public.trading_calendar
ALTER COLUMN verified
SET DEFAULT FALSE;

ALTER TABLE public.trading_calendar
ALTER COLUMN verified
SET NOT NULL;

ALTER TABLE public.trading_calendar
ALTER COLUMN evidence
SET DEFAULT '{}'::jsonb;

ALTER TABLE public.trading_calendar
ALTER COLUMN evidence
SET NOT NULL;

ALTER TABLE public.trading_calendar
ALTER COLUMN updated_at
SET DEFAULT NOW();

ALTER TABLE public.trading_calendar
ALTER COLUMN updated_at
SET NOT NULL;

ALTER TABLE public.trading_calendar
DROP CONSTRAINT IF EXISTS trading_calendar_day_type_check;

ALTER TABLE public.trading_calendar
ADD CONSTRAINT trading_calendar_day_type_check
CHECK (
    day_type IN (
        'OBSERVED_TRADING',
        'OFFICIAL_TRADING',
        'WEEKEND',
        'OFFICIAL_HOLIDAY',
        'SPECIAL_CLOSURE',
        'UNVERIFIED_NON_TRADING',
        'UNKNOWN'
    )
);

ALTER TABLE public.trading_calendar
DROP CONSTRAINT IF EXISTS trading_calendar_source_id_fkey;

ALTER TABLE public.trading_calendar
ADD CONSTRAINT trading_calendar_source_id_fkey
FOREIGN KEY (source_id)
REFERENCES public.data_sources(id);

ALTER TABLE public.trading_calendar
DROP CONSTRAINT IF EXISTS trading_calendar_pkey;

ALTER TABLE public.trading_calendar
ADD CONSTRAINT trading_calendar_pkey
PRIMARY KEY (
    trading_date,
    market
);

COMMIT;