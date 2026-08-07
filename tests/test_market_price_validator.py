from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

from imi.market_data import MarketPriceRecord
from imi.validators.market_prices import (
    validate_market_price,
)


def make_record(
    *,
    open_: str = "7000",
    high: str = "7100",
    low: str = "6950",
    close: str = "7050",
    volume: str = "1000",
) -> MarketPriceRecord:
    return MarketPriceRecord(
        trading_date=date(
            2026,
            1,
            2,
        ),
        open=Decimal(open_),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        adjusted_close=Decimal(close),
        volume=Decimal(volume),
        observed_at=datetime(
            2026,
            1,
            2,
            tzinfo=UTC,
        ),
        raw_ref="test",
    )


def test_valid_market_price() -> None:
    result = validate_market_price(
        make_record()
    )

    assert result.record.quality == "VALID"
    assert result.reasons == ()


def test_rejects_invalid_high() -> None:
    result = validate_market_price(
        make_record(
            high="7000",
            close="7050",
        )
    )

    assert (
        result.record.quality
        == "REJECTED"
    )
    assert result.reasons


def test_rejects_negative_volume() -> None:
    result = validate_market_price(
        make_record(
            volume="-100",
        )
    )

    assert (
        result.record.quality
        == "REJECTED"
    )
    assert result.reasons

def test_rejects_weekend_date() -> None:
    record = replace(
        make_record(),
        trading_date=date(2026, 8, 1),
    )

    result = validate_market_price(record)

    assert result.record.quality == "REJECTED"
    assert result.reasons