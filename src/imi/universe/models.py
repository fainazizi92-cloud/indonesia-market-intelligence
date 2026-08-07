from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class InstrumentProfile:
    symbol: str
    name: str
    listed_date: date | None
    sector_code: str | None
    industry_code: str | None
    metadata: dict[str, object]