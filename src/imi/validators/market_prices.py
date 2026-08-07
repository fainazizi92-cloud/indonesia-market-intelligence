from dataclasses import dataclass, replace

from imi.market_data import MarketPriceRecord


@dataclass(frozen=True, slots=True)
class ValidationResult:
    record: MarketPriceRecord
    reasons: tuple[str, ...]


def validate_market_price(
    record: MarketPriceRecord,
) -> ValidationResult:
    reasons: list[str] = []

    if record.trading_date.weekday() >= 5:
        reasons.append(
        "Trading date falls on a weekend."
    )

    prices = (
        record.open,
        record.high,
        record.low,
        record.close,
    )

    if any(price <= 0 for price in prices):
        reasons.append(
            "OHLC contains zero or negative price."
        )

    if record.high < max(prices):
        reasons.append(
            "High is lower than another OHLC value."
        )

    if record.low > min(prices):
        reasons.append(
            "Low is higher than another OHLC value."
        )
    
    if (
        record.adjusted_close is not None
        and record.adjusted_close <= 0
    ):
        reasons.append(
            "Adjusted close is zero or negative."
        )

    if (
        record.volume is not None
        and record.volume < 0
    ):
        reasons.append(
            "Volume is negative."
        )

    if reasons:
        validated = replace(
            record,
            quality="REJECTED",
        )
    else:
        validated = replace(
            record,
            quality="VALID",
        )

    return ValidationResult(
        record=validated,
        reasons=tuple(reasons),
    )