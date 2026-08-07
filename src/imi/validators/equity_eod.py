from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from imi.collectors.yahoo_equity_history import (
    EquityDailyBar,
)


@dataclass(frozen=True)
class EquityBarValidation:
    valid: bool
    reasons: tuple[str, ...]


def validate_equity_daily_bar(
    bar: EquityDailyBar,
    *,
    listed_date: date | None,
    target_end_date: date,
) -> EquityBarValidation:
    reasons: list[str] = []

    if bar.trading_date.weekday() >= 5:
        reasons.append(
            "WEEKEND_BAR"
        )

    if (
        listed_date is not None
        and bar.trading_date
        < listed_date
    ):
        reasons.append(
            "BEFORE_LISTING_DATE"
        )

    if (
        bar.trading_date
        > target_end_date
    ):
        reasons.append(
            "AFTER_TARGET_END_DATE"
        )

    if bar.open <= Decimal(0):
        reasons.append(
            "NON_POSITIVE_OPEN"
        )

    if bar.high <= Decimal(0):
        reasons.append(
            "NON_POSITIVE_HIGH"
        )

    if bar.low <= Decimal(0):
        reasons.append(
            "NON_POSITIVE_LOW"
        )

    if bar.close <= Decimal(0):
        reasons.append(
            "NON_POSITIVE_CLOSE"
        )

    if bar.high < bar.low:
        reasons.append(
            "HIGH_BELOW_LOW"
        )

    if bar.high < bar.open:
        reasons.append(
            "HIGH_BELOW_OPEN"
        )

    if bar.high < bar.close:
        reasons.append(
            "HIGH_BELOW_CLOSE"
        )

    if bar.low > bar.open:
        reasons.append(
            "LOW_ABOVE_OPEN"
        )

    if bar.low > bar.close:
        reasons.append(
            "LOW_ABOVE_CLOSE"
        )

    if (
        bar.volume is not None
        and bar.volume < Decimal(0)
    ):
        reasons.append(
            "NEGATIVE_VOLUME"
        )

    return EquityBarValidation(
        valid=not reasons,
        reasons=tuple(reasons),
    )