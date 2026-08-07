from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from imi.market_data import MarketPriceRecord

GET_INSTRUMENT_ID = text(
    """
    SELECT id
    FROM instruments
    WHERE symbol = :symbol
      AND exchange = :exchange
      AND asset_type = CAST(
          :asset_type AS asset_type
      )
    """
)


GET_SOURCE_ID = text(
    """
    SELECT id
    FROM data_sources
    WHERE code = :code
      AND is_active = TRUE
    """
)


UPSERT_MARKET_PRICE = text(
    """
    INSERT INTO market_prices_eod (
        instrument_id,
        trading_date,
        open,
        high,
        low,
        close,
        previous_close,
        adjusted_close,
        volume,
        value,
        frequency,
        market_cap,
        source_id,
        observed_at,
        quality,
        raw_ref
    )
    VALUES (
        :instrument_id,
        :trading_date,
        :open,
        :high,
        :low,
        :close,
        :previous_close,
        :adjusted_close,
        :volume,
        :value,
        :frequency,
        :market_cap,
        :source_id,
        :observed_at,
        CAST(:quality AS quality_status),
        :raw_ref
    )
    ON CONFLICT (
        instrument_id,
        trading_date,
        source_id
    )
    DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        previous_close = EXCLUDED.previous_close,
        adjusted_close = EXCLUDED.adjusted_close,
        volume = EXCLUDED.volume,
        value = EXCLUDED.value,
        frequency = EXCLUDED.frequency,
        market_cap = EXCLUDED.market_cap,
        observed_at = EXCLUDED.observed_at,
        ingested_at = NOW(),
        quality = EXCLUDED.quality,
        raw_ref = EXCLUDED.raw_ref
    """
)


def get_instrument_id(
    connection: Connection,
    *,
    symbol: str,
    exchange: str,
    asset_type: str,
) -> UUID:
    instrument_id = connection.execute(
        GET_INSTRUMENT_ID,
        {
            "symbol": symbol,
            "exchange": exchange,
            "asset_type": asset_type,
        },
    ).scalar_one_or_none()

    if instrument_id is None:
        raise LookupError(
            "Instrument not found: "
            f"{symbol}/{exchange}/{asset_type}"
        )

    return instrument_id


def get_source_id(
    connection: Connection,
    *,
    code: str,
) -> UUID:
    source_id = connection.execute(
        GET_SOURCE_ID,
        {"code": code},
    ).scalar_one_or_none()

    if source_id is None:
        raise LookupError(
            f"Data source not found: {code}"
        )

    return source_id


def upsert_market_prices(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
    records: list[MarketPriceRecord],
) -> int:
    if not records:
        return 0

    parameters = [
        {
            "instrument_id": instrument_id,
            "trading_date": record.trading_date,
            "open": record.open,
            "high": record.high,
            "low": record.low,
            "close": record.close,
            "previous_close": (
                record.previous_close
            ),
            "adjusted_close": (
                record.adjusted_close
            ),
            "volume": record.volume,
            "value": record.value,
            "frequency": record.frequency,
            "market_cap": record.market_cap,
            "source_id": source_id,
            "observed_at": record.observed_at,
            "quality": record.quality,
            "raw_ref": record.raw_ref,
        }
        for record in records
    ]

    connection.execute(
        UPSERT_MARKET_PRICE,
        parameters,
    )

    return len(records)


REBUILD_PREVIOUS_CLOSE = text(
    """
    WITH ordered AS (
        SELECT
            instrument_id,
            trading_date,
            source_id,
            LAG(close) OVER (
                PARTITION BY
                    instrument_id,
                    source_id
                ORDER BY trading_date
            ) AS expected_previous_close
        FROM market_prices_eod
        WHERE instrument_id = :instrument_id
          AND source_id = :source_id
    )
    UPDATE market_prices_eod AS mp
    SET previous_close =
        ordered.expected_previous_close
    FROM ordered
    WHERE mp.instrument_id =
            ordered.instrument_id
      AND mp.trading_date =
            ordered.trading_date
      AND mp.source_id =
            ordered.source_id
    """
)


def rebuild_previous_close(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
) -> None:
    connection.execute(
        REBUILD_PREVIOUS_CLOSE,
        {
            "instrument_id": instrument_id,
            "source_id": source_id,
        },
    )