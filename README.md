# Indonesia Market Intelligence (IMI)

Foundation repository for an Indonesia-focused market intelligence and decision-support system.

## Initial scope

The first production scope is intentionally narrow:

1. Indonesia pre-market review
2. Indonesia after-market review
3. Market regime classification
4. Sector rotation analysis
5. Swing-stock screening
6. Signal journaling and outcome evaluation

Intraday Level-2/order-book analysis and automated execution are **out of scope for v1**.

## Design principle

> Data computes. Statistical models estimate. GPT explains and structures decisions.

LLMs must not invent prices, flows, fundamentals, indicators, or news. Every production datapoint must have a source, observation timestamp, ingestion timestamp, and quality status.

## Repository layout

```text
config/              Source and system configuration
db/                  PostgreSQL schema
docs/                Architecture, data dictionary, source map
scripts/             Setup/validation utilities
src/imi/             Python package
tests/               Tests
```

## Data layers

- **Bronze** — immutable/raw source records and ingestion metadata
- **Silver** — normalized, validated market/fundamental/macro tables
- **Gold** — derived features, regimes, scores, signals, and evaluation results

## Phase 1 deliverables

- `docs/ARCHITECTURE.md`
- `docs/SOURCE_MAP.md`
- `docs/DATA_DICTIONARY.csv`
- `db/schema.sql`
- `config/sources.example.yml`
- `.env.example`
- `pyproject.toml`
- `scripts/validate_setup.py`

## Next phase

Phase 2 implements the first real ingestion pipeline:

1. instrument master
2. IDX/IHSG/index EOD data
3. market recap and foreign flow
4. BI + BPS macro data
5. daily quality checks

No paid market-data subscription should be purchased before the endpoint/licensing audit is complete.
