# Architecture — Indonesia Market Intelligence

## 1. Production objective

The system is designed to answer four questions in order:

1. **What is the global and Indonesian market regime?**
2. **Where is capital rotating?**
3. **Which liquid stocks have the best risk-adjusted setup?**
4. **What evidence would invalidate the thesis?**

The initial horizon is daily/swing analysis. Intraday execution is deferred until reliable licensed intraday data is available.

## 2. Core architecture

```text
Official / licensed sources
        |
        v
Ingestion adapters
        |
        v
BRONZE: raw snapshots + provenance
        |
        v
Validation / reconciliation
        |
        v
SILVER: normalized canonical tables
        |
        +-----------------------+
        |                       |
        v                       v
Feature engine             Event engine
        |                       |
        +-----------+-----------+
                    v
GOLD: regimes / rotation / stock features
                    |
                    v
Statistical scoring + probability + EV
                    |
                    v
Risk engine
                    |
                    v
LLM analyst/report layer
                    |
                    v
Dashboard + alerts + journal
                    |
                    v
Outcome evaluation / backtest / calibration
```

## 3. Source-of-truth rule

Every canonical observation must store:

- `source_id`
- `observed_at`
- `ingested_at`
- `as_of_date`
- `quality_status`
- optional raw payload/hash

The LLM is not permitted to fill missing numeric fields. Missing values remain `NULL` and reports show `DATA TIDAK TERSEDIA`.

## 4. Data zones

### Bronze

Purpose: reproducibility and auditability.

Store source responses/files without reinterpretation where licensing permits. Never overwrite a prior raw snapshot; version it.

### Silver

Purpose: canonical normalized data.

Examples:

- one ticker identifier per listed security
- canonical trading date in Asia/Jakarta
- adjusted and unadjusted price fields kept separately
- standardized financial statement periods
- consistent investor-flow units

### Gold

Purpose: derived analytics.

Examples:

- EMA/ATR/RSI
- return windows
- volume z-score
- relative strength vs IHSG and sector
- breadth scores
- foreign accumulation score
- market and sector regimes
- stock setup scores
- target-before-stop probability
- expected value

## 5. Required analytics engines

### Market regime engine

Inputs include global risk assets, DXY/USDIDR, US yields, Indonesian macro, IHSG trend, breadth, flow, and volatility.

Output must be categorical plus evidence, not only a numeric score.

### Breadth engine

Minimum features:

- advances / declines / unchanged
- advance-decline ratio
- % universe above EMA20/50/200
- new 20-day and 52-week highs/lows
- up-volume/down-volume

### Foreign-flow engine

Minimum windows: 1D, 5D, 20D, 60D.

Raw value should be normalized by liquidity/free-float or ADV where appropriate so that flow is comparable across securities.

### Sector rotation engine

Minimum features:

- 1D/5D/20D/60D return
- relative strength vs IHSG
- sector breadth
- volume participation
- foreign flow
- earnings/catalyst overlay

Output: `LEADING`, `IMPROVING`, `NEUTRAL`, `WEAKENING`, `LAGGING`.

### Stock screener

Filters must include liquidity, spread/turnover proxies, trend, sector regime, relative strength, event risk, and data completeness before scoring.

### Risk engine

Must model:

- market risk
- sector risk
- company/event risk
- technical invalidation
- liquidity risk
- ownership/free-float concentration risk
- gap risk

### Evaluation engine

Every historical signal must be immutable after issue. Record T+1/T+3/T+5/T+10/T+20, MFE, MAE, stop hit, target hit, time-to-target, and regime at issue time.

## 6. Model roadmap

1. Rules first
2. Statistical validation
3. Probability calibration
4. Logistic regression baseline
5. Tree models (LightGBM/XGBoost) only after leakage-safe dataset exists

Do not start with deep learning.

## 7. Security

- secrets only in `.env`/secret manager
- `.env` must never be committed
- licensed market data must not be redistributed beyond license terms
- raw provider payloads require retention rules based on contract

## 8. MVP acceptance criteria

The first working daily pipeline is accepted only if it can produce, for a completed IDX session:

- IHSG OHLC/value/volume/frequency
- market breadth
- full-day foreign flow
- sector performance and rotation
- a liquid-stock universe
- data-quality report
- next-session watchlist without fabricated fields
- immutable signal record for later evaluation
