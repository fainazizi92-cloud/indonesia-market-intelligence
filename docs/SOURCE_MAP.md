# Source Map — v0.1

Status legend:

- **P0** required for MVP
- **P1** important after MVP
- **P2** later/intraday
- **AUDIT** endpoint/licensing must be verified before production use

## IDX / Bursa Efek Indonesia

Official product page: https://www.idx.id/en/products/idx-data-services/

| Need | Preferred source/product | Priority | Notes |
|---|---|---:|---|
| Equity EOD OHLC, volume, value, frequency | IDX Equity EOD Professional/Basic | P0 | Licensed EOD is preferred for production. Exact product choice requires current commercial/licensing audit. |
| Index EOD OHLC/value/volume/frequency | IDX Equity EoD Indices | P0 | Includes IDX indices; use for IHSG and sector/index series. |
| Index constituents/weights | IDX Equity EoD Indices Weight | P0 | Needed for index membership/weight-aware attribution. |
| Foreign/domestic buy/sell recap | IDX Equity EoD Recapitulation | P0 | Preferred source for full-day investor-flow calculations. |
| Monthly statistical cross-check | IDX Digital Statistics | P0 backup | Useful for reconciliation/backfill; not a substitute for daily production feed. |
| Index definitions/evaluation | IDX Index pages/handbook | P1 | Reference metadata. |
| Financial statements/disclosures/corporate actions | IDX Data Reference / issuer disclosures | P0/P1 | Exact machine-readable delivery must be audited. |
| Level-2/order book/ITCH | IDX real-time / ITCH products | P2 | Defer until intraday phase. |

## Bank Indonesia

Official indicators: https://www.bi.go.id/id/statistik/indikator/default.aspx
Official JISDOR: https://www.bi.go.id/id/statistik/informasi-kurs/jisdor/default.aspx

| Need | Source | Priority | Notes |
|---|---|---:|---|
| BI-Rate | BI official statistics | P0 | Event-driven policy series. |
| JISDOR USD/IDR | BI JISDOR | P0 | Daily reference FX rate. |
| INDONIA | BI | P1 | Money-market/liquidity indicator. |
| FX reserves | BI | P1 | Monthly macro feature. |
| monetary/liquidity data | BI statistics | P1 | Exact series/endpoints audited individually. |
| policy statements | BI press releases | P0 | Catalyst/event engine. |

## BPS / Statistics Indonesia

BPS states that WebAPI can integrate official BPS statistical data into applications.
Service page: https://ppid.bps.go.id/app/konten/1300/Layanan-BPS.html

| Need | Source | Priority |
|---|---|---:|
| CPI/headline inflation | BPS WebAPI/publication | P0 |
| Core inflation | BPS | P0 |
| GDP | BPS | P1 |
| exports/imports/trade balance | BPS | P1 |
| other official macro releases | BPS | P1 |

## OJK

Official capital-market statistics and corporate-action summaries can be used as regulatory/statistical cross-checks.

| Need | Source | Priority | Notes |
|---|---|---:|---|
| capital-market statistics | OJK | P1 | Cross-check/reference; publication frequency varies. |
| issuance/corporate-action summaries | OJK | P1 | Event engine/reference. |
| regulatory changes | OJK regulations/press releases | P0 | High-priority catalyst source. |

## KSEI / ownership

| Need | Source | Priority | Notes |
|---|---|---:|---|
| ownership/investor statistics | KSEI/IDX/OJK official disclosures | P1 | **AUDIT** exact production endpoint and terms before implementation. |
| free-float / concentration flags | IDX/OJK official disclosure | P1 | Retain effective date and methodology. |

## Global market layer

For the production system, use a stable licensed/official provider rather than scraping consumer websites.

| Need | Preferred approach | Priority |
|---|---|---:|
| S&P 500/Nasdaq/VIX | licensed market-data API; official exchange data where feasible | P0 |
| US Treasury yields | US Treasury/FRED official series | P0 |
| DXY or USD basket proxy | licensed provider | P0 |
| gold/oil/copper | licensed futures/market-data provider | P0 |
| coal/CPO/nickel | exchange/licensed commodity provider | P1 |
| Asian equity indices | licensed provider | P0 |

Provider selection is intentionally `TBD` in Phase 1 so that price, coverage, licensing, latency, and historical depth can be compared before paying.

## News and catalysts

Source hierarchy:

1. issuer disclosure / IDX
2. BI / BPS / OJK / Ministry / regulator
3. primary company release
4. high-quality financial news
5. other secondary sources

For each event store source URL, publication time, event time if different, ticker/sector linkage, direction, magnitude, horizon, and confidence.
