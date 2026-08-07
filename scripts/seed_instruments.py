import json

from sqlalchemy import text

from imi.db import engine

INSTRUMENTS = [
    {
        "symbol": "IHSG",
        "name": "Indeks Harga Saham Gabungan",
        "asset_type": "INDEX",
        "exchange": "IDX",
        "currency": "IDR",
        "metadata": json.dumps(
            {
                "english_name": "IDX Composite",
                "role": "broad_market_benchmark",
                "source_code": "IDX_OFFICIAL",
            }
        ),
    }
]


UPSERT_INSTRUMENT = text(
    """
    INSERT INTO instruments (
        symbol,
        name,
        asset_type,
        exchange,
        currency,
        metadata,
        is_active
    )
    VALUES (
        :symbol,
        :name,
        CAST(:asset_type AS asset_type),
        :exchange,
        :currency,
        CAST(:metadata AS jsonb),
        TRUE
    )
    ON CONFLICT (symbol, exchange, asset_type)
    DO UPDATE SET
        name = EXCLUDED.name,
        currency = EXCLUDED.currency,
        metadata = EXCLUDED.metadata,
        is_active = TRUE
    RETURNING
        id,
        symbol,
        name,
        asset_type,
        exchange,
        currency
    """
)


def main() -> None:
    with engine.begin() as connection:
        for instrument in INSTRUMENTS:
            row = connection.execute(
                UPSERT_INSTRUMENT,
                instrument,
            ).one()

            print(
                "Seeded instrument:"
                f" {row.symbol} |"
                f" {row.name} |"
                f" {row.asset_type} |"
                f" {row.exchange} |"
                f" {row.currency}"
            )


if __name__ == "__main__":
    main()