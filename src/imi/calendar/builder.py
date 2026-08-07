from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True, slots=True)
class CalendarRecord:
    trading_date: date
    market: str
    is_trading_day: bool
    day_type: str
    session_notes: str | None
    source_code: str | None
    verified: bool
    evidence: dict[str, object]


def build_derived_idx_calendar(
    *,
    observed_dates: set[date],
    start: date,
    end: date,
) -> list[CalendarRecord]:
    if end < start:
        raise ValueError(
            "End date must not be earlier than start date."
        )

    records: list[CalendarRecord] = []

    current = start

    while current <= end:
        if current in observed_dates:
            records.append(
                CalendarRecord(
                    trading_date=current,
                    market="IDX",
                    is_trading_day=True,
                    day_type="OBSERVED_TRADING",
                    session_notes=(
                        "Observed from validated IHSG EOD data."
                    ),
                    source_code="YAHOO_FINANCE",
                    verified=False,
                    evidence={
                        "builder": "ihsg_derived_v1",
                        "basis": (
                            "validated IHSG daily bar"
                        ),
                    },
                )
            )

        elif current.weekday() >= 5:
            records.append(
                CalendarRecord(
                    trading_date=current,
                    market="IDX",
                    is_trading_day=False,
                    day_type="WEEKEND",
                    session_notes=(
                        "Weekend rule; historical official "
                        "validation pending."
                    ),
                    source_code=None,
                    verified=False,
                    evidence={
                        "builder": "ihsg_derived_v1",
                        "basis": "calendar weekend",
                    },
                )
            )

        else:
            records.append(
                CalendarRecord(
                    trading_date=current,
                    market="IDX",
                    is_trading_day=False,
                    day_type=(
                        "UNVERIFIED_NON_TRADING"
                    ),
                    session_notes=(
                        "Weekday without validated IHSG EOD "
                        "bar. Official holiday or closure "
                        "validation pending."
                    ),
                    source_code=None,
                    verified=False,
                    evidence={
                        "builder": "ihsg_derived_v1",
                        "basis": (
                            "weekday without validated "
                            "IHSG bar"
                        ),
                    },
                )
            )

        current += timedelta(days=1)

    return records