-- Indonesia Market Intelligence — canonical Phase-1 schema
-- PostgreSQL-first. TimescaleDB can be enabled later for larger intraday/time-series workloads.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE quality_status AS ENUM ('VALID', 'WARNING', 'STALE', 'REJECTED', 'MISSING');
CREATE TYPE asset_type AS ENUM ('EQUITY', 'INDEX', 'FX', 'RATE', 'COMMODITY', 'MACRO');
CREATE TYPE signal_status AS ENUM ('BUY_SETUP', 'WATCH', 'WAIT', 'AVOID');
CREATE TYPE regime_label AS ENUM (
  'STRONG_BULL', 'BULL', 'SIDEWAYS_BULL', 'SIDEWAYS',
  'SIDEWAYS_BEAR', 'BEAR', 'STRONG_BEAR'
);

CREATE TABLE data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    authority_rank SMALLINT NOT NULL CHECK (authority_rank BETWEEN 1 AND 5),
    base_url TEXT,
    license_notes TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE instruments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_type asset_type NOT NULL,
    exchange TEXT,
    currency TEXT,
    sector_code TEXT,
    industry_code TEXT,
    listed_date DATE,
    delisted_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE(symbol, exchange, asset_type)
);

CREATE TABLE trading_calendar (
    trading_date DATE PRIMARY KEY,
    market TEXT NOT NULL DEFAULT 'IDX',
    is_trading_day BOOLEAN NOT NULL,
    session_notes TEXT
);

CREATE TABLE index_memberships (
    index_instrument_id UUID NOT NULL REFERENCES instruments(id),
    member_instrument_id UUID NOT NULL REFERENCES instruments(id),
    effective_from DATE NOT NULL,
    effective_to DATE,
    weight NUMERIC(18,10),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (index_instrument_id, member_instrument_id, effective_from)
);

CREATE TABLE market_prices_eod (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    trading_date DATE NOT NULL,
    open NUMERIC(20,6),
    high NUMERIC(20,6),
    low NUMERIC(20,6),
    close NUMERIC(20,6),
    previous_close NUMERIC(20,6),
    adjusted_close NUMERIC(20,6),
    volume NUMERIC(30,6),
    value NUMERIC(30,2),
    frequency BIGINT,
    market_cap NUMERIC(30,2),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    observed_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality quality_status NOT NULL DEFAULT 'VALID',
    raw_ref TEXT,
    PRIMARY KEY (instrument_id, trading_date, source_id)
);

CREATE INDEX idx_market_prices_date ON market_prices_eod(trading_date);
CREATE INDEX idx_market_prices_instrument_date ON market_prices_eod(instrument_id, trading_date DESC);

CREATE TABLE investor_flows_eod (
    instrument_id UUID REFERENCES instruments(id),
    trading_date DATE NOT NULL,
    investor_scope TEXT NOT NULL DEFAULT 'FOREIGN_VS_DOMESTIC',
    foreign_buy_volume NUMERIC(30,6),
    foreign_sell_volume NUMERIC(30,6),
    foreign_buy_value NUMERIC(30,2),
    foreign_sell_value NUMERIC(30,2),
    domestic_buy_volume NUMERIC(30,6),
    domestic_sell_volume NUMERIC(30,6),
    domestic_buy_value NUMERIC(30,2),
    domestic_sell_value NUMERIC(30,2),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    observed_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality quality_status NOT NULL DEFAULT 'VALID',
    PRIMARY KEY (instrument_id, trading_date, investor_scope, source_id)
);

CREATE TABLE market_breadth_daily (
    trading_date DATE NOT NULL,
    universe_code TEXT NOT NULL,
    advances INTEGER,
    declines INTEGER,
    unchanged INTEGER,
    new_high_20d INTEGER,
    new_low_20d INTEGER,
    new_high_52w INTEGER,
    new_low_52w INTEGER,
    pct_above_ema20 NUMERIC(8,4),
    pct_above_ema50 NUMERIC(8,4),
    pct_above_ema200 NUMERIC(8,4),
    up_volume NUMERIC(30,6),
    down_volume NUMERIC(30,6),
    breadth_score NUMERIC(8,4),
    source_id UUID REFERENCES data_sources(id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (trading_date, universe_code)
);

CREATE TABLE fundamentals_periodic (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    period_end DATE NOT NULL,
    period_type TEXT NOT NULL,
    filing_date DATE,
    revenue NUMERIC(30,2),
    gross_profit NUMERIC(30,2),
    operating_income NUMERIC(30,2),
    ebitda NUMERIC(30,2),
    net_income NUMERIC(30,2),
    eps NUMERIC(20,8),
    operating_cash_flow NUMERIC(30,2),
    capex NUMERIC(30,2),
    free_cash_flow NUMERIC(30,2),
    cash NUMERIC(30,2),
    total_debt NUMERIC(30,2),
    total_assets NUMERIC(30,2),
    total_equity NUMERIC(30,2),
    roe NUMERIC(12,6),
    roa NUMERIC(12,6),
    roic NUMERIC(12,6),
    gross_margin NUMERIC(12,6),
    operating_margin NUMERIC(12,6),
    net_margin NUMERIC(12,6),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality quality_status NOT NULL DEFAULT 'VALID',
    PRIMARY KEY (instrument_id, period_end, period_type, source_id)
);

CREATE TABLE valuation_daily (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    trading_date DATE NOT NULL,
    pe NUMERIC(18,6),
    forward_pe NUMERIC(18,6),
    pbv NUMERIC(18,6),
    ev_ebitda NUMERIC(18,6),
    dividend_yield NUMERIC(18,8),
    fcf_yield NUMERIC(18,8),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, trading_date, source_id)
);

CREATE TABLE ownership_snapshots (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    as_of_date DATE NOT NULL,
    free_float_pct NUMERIC(10,6),
    foreign_ownership_pct NUMERIC(10,6),
    hsc_flag BOOLEAN,
    concentration_score NUMERIC(10,6),
    holder_details JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_id UUID NOT NULL REFERENCES data_sources(id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, as_of_date, source_id)
);

CREATE TABLE corporate_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID REFERENCES instruments(id),
    action_type TEXT NOT NULL,
    announcement_at TIMESTAMPTZ,
    cum_date DATE,
    ex_date DATE,
    record_date DATE,
    payment_date DATE,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_id UUID NOT NULL REFERENCES data_sources(id),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE macro_series (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    unit TEXT,
    frequency TEXT,
    country_code TEXT NOT NULL DEFAULT 'ID',
    source_id UUID NOT NULL REFERENCES data_sources(id)
);

CREATE TABLE macro_observations (
    series_id UUID NOT NULL REFERENCES macro_series(id),
    observation_date DATE NOT NULL,
    value NUMERIC(30,10),
    release_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    quality quality_status NOT NULL DEFAULT 'VALID',
    PRIMARY KEY (series_id, observation_date)
);

CREATE TABLE news_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    published_at TIMESTAMPTZ NOT NULL,
    event_at TIMESTAMPTZ,
    headline TEXT NOT NULL,
    source_url TEXT,
    source_id UUID REFERENCES data_sources(id),
    instrument_id UUID REFERENCES instruments(id),
    sector_code TEXT,
    event_type TEXT,
    direction TEXT CHECK (direction IN ('POSITIVE', 'NEGATIVE', 'MIXED', 'NEUTRAL')),
    magnitude TEXT CHECK (magnitude IN ('LOW', 'MEDIUM', 'HIGH')),
    horizon TEXT,
    confidence NUMERIC(8,4),
    summary TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE technical_features_daily (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    trading_date DATE NOT NULL,
    return_1d NUMERIC(18,8),
    return_5d NUMERIC(18,8),
    return_20d NUMERIC(18,8),
    return_60d NUMERIC(18,8),
    ema20 NUMERIC(20,6),
    ema50 NUMERIC(20,6),
    ema100 NUMERIC(20,6),
    ema200 NUMERIC(20,6),
    rsi14 NUMERIC(12,6),
    atr14 NUMERIC(20,6),
    volume_z20 NUMERIC(18,8),
    rs_ihsg_20d NUMERIC(18,8),
    rs_sector_20d NUMERIC(18,8),
    breakout_flag BOOLEAN,
    failed_breakout_flag BOOLEAN,
    feature_version TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, trading_date, feature_version)
);

CREATE TABLE market_regimes_daily (
    trading_date DATE PRIMARY KEY,
    regime regime_label NOT NULL,
    confidence NUMERIC(8,4),
    global_score NUMERIC(8,4),
    indonesia_macro_score NUMERIC(8,4),
    ihsg_trend_score NUMERIC(8,4),
    breadth_score NUMERIC(8,4),
    flow_score NUMERIC(8,4),
    volatility_score NUMERIC(8,4),
    model_version TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sector_scores_daily (
    trading_date DATE NOT NULL,
    sector_code TEXT NOT NULL,
    rotation_label TEXT NOT NULL CHECK (rotation_label IN ('LEADING','IMPROVING','NEUTRAL','WEAKENING','LAGGING')),
    score NUMERIC(8,4),
    relative_strength_score NUMERIC(8,4),
    breadth_score NUMERIC(8,4),
    flow_score NUMERIC(8,4),
    volume_score NUMERIC(8,4),
    catalyst_score NUMERIC(8,4),
    model_version TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (trading_date, sector_code, model_version)
);

CREATE TABLE stock_scores_daily (
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    trading_date DATE NOT NULL,
    overall_score NUMERIC(8,4),
    market_score NUMERIC(8,4),
    sector_score NUMERIC(8,4),
    fundamental_score NUMERIC(8,4),
    valuation_score NUMERIC(8,4),
    technical_score NUMERIC(8,4),
    liquidity_score NUMERIC(8,4),
    flow_score NUMERIC(8,4),
    catalyst_score NUMERIC(8,4),
    risk_score NUMERIC(8,4),
    data_completeness NUMERIC(8,4),
    model_version TEXT NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (instrument_id, trading_date, model_version)
);

CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    instrument_id UUID NOT NULL REFERENCES instruments(id),
    issued_at TIMESTAMPTZ NOT NULL,
    trading_date DATE NOT NULL,
    status signal_status NOT NULL,
    entry_low NUMERIC(20,6),
    entry_high NUMERIC(20,6),
    invalidation_price NUMERIC(20,6),
    stop_price NUMERIC(20,6),
    target_primary NUMERIC(20,6),
    expected_rr NUMERIC(18,8),
    probability_tp_before_sl NUMERIC(10,8),
    expected_value_r NUMERIC(18,8),
    horizon_days INTEGER,
    confidence NUMERIC(8,4),
    thesis TEXT NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    model_version TEXT NOT NULL,
    is_frozen BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE signal_outcomes (
    signal_id UUID PRIMARY KEY REFERENCES signals(id),
    evaluated_through DATE,
    return_t1 NUMERIC(18,8),
    return_t3 NUMERIC(18,8),
    return_t5 NUMERIC(18,8),
    return_t10 NUMERIC(18,8),
    return_t20 NUMERIC(18,8),
    mfe NUMERIC(18,8),
    mae NUMERIC(18,8),
    target_hit BOOLEAN,
    stop_hit BOOLEAN,
    target_hit_at TIMESTAMPTZ,
    stop_hit_at TIMESTAMPTZ,
    time_to_target_hours NUMERIC(18,4),
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE ingestion_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    pipeline_name TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    rows_seen BIGINT NOT NULL DEFAULT 0,
    rows_loaded BIGINT NOT NULL DEFAULT 0,
    rows_rejected BIGINT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE data_quality_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ingestion_run_id UUID REFERENCES ingestion_runs(id),
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    severity TEXT NOT NULL CHECK (severity IN ('INFO','WARNING','ERROR','CRITICAL')),
    dataset TEXT NOT NULL,
    rule_code TEXT NOT NULL,
    message TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
