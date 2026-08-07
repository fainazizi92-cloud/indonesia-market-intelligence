BEGIN;

ALTER TABLE public.market_regimes_daily
DROP CONSTRAINT IF EXISTS market_regimes_daily_pkey;

ALTER TABLE public.market_regimes_daily
ADD CONSTRAINT market_regimes_daily_pkey
PRIMARY KEY (
    trading_date,
    model_version
);

COMMIT;