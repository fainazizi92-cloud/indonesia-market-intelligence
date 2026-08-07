from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class MarketPriceRecord:
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: Decimal | None
    observed_at: datetime | None
    raw_ref: str | None
    previous_close: Decimal | None = None
    value: Decimal | None = None
    frequency: int | None = None
    market_cap: Decimal | None = None
    quality: str = "VALID"