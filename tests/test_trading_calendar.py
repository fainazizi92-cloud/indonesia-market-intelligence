from datetime import date

from imi.calendar.builder import (
    build_derived_idx_calendar,
)


def test_calendar_classification() -> None:
    observed = {
        date(2026, 8, 6),
    }

    records = (
        build_derived_idx_calendar(
            observed_dates=observed,
            start=date(
                2026,
                8,
                6,
            ),
            end=date(
                2026,
                8,
                10,
            ),
        )
    )

    by_date = {
        row.trading_date: row
        for row in records
    }

    assert (
        by_date[
            date(2026, 8, 6)
        ].day_type
        == "OBSERVED_TRADING"
    )

    assert (
        by_date[
            date(2026, 8, 8)
        ].day_type
        == "WEEKEND"
    )

    assert (
        by_date[
            date(2026, 8, 10)
        ].day_type
        == "UNVERIFIED_NON_TRADING"
    )