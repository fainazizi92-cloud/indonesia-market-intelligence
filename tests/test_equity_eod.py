from datetime import date
from decimal import Decimal

import httpx

from imi.collectors.yahoo_equity_history import (
    EquityDailyBar,
    fetch_yahoo_equity_history,
    to_yahoo_symbol,
)
from imi.validators.equity_eod import (
    validate_equity_daily_bar,
)


def test_yahoo_no_data_range_is_empty() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code=400,
            request=request,
            json={
                "chart": {
                    "result": None,
                    "error": {
                        "code": (
                            "Bad Request"
                        ),
                        "description": (
                            "Data doesn't "
                            "exist for "
                            "startDate = "
                            "123"
                        ),
                    },
                }
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        result = (
            fetch_yahoo_equity_history(
                idx_symbol="TEST",
                start_date=date(
                    1990,
                    1,
                    1,
                ),
                end_date=date(
                    1998,
                    1,
                    1,
                ),
                client=client,
            )
        )

    assert result.yahoo_symbol == (
        "TEST.JK"
    )
    assert result.raw_count == 0
    assert result.bars == []

def test_yahoo_symbol() -> None:
    assert (
        to_yahoo_symbol("bbca")
        == "BBCA.JK"
    )


def test_valid_equity_bar() -> None:
    bar = EquityDailyBar(
        trading_date=date(
            2026,
            8,
            6,
        ),
        open=Decimal(9000),
        high=Decimal(9200),
        low=Decimal(8950),
        close=Decimal(9150),
        adjusted_close=(
            Decimal(9150)
        ),
        volume=Decimal(1000000),
    )

    result = (
        validate_equity_daily_bar(
            bar,
            listed_date=date(
                2000,
                1,
                1,
            ),
            target_end_date=date(
                2026,
                8,
                6,
            ),
        )
    )

    assert result.valid
    assert result.reasons == ()


def test_invalid_ohlc() -> None:
    bar = EquityDailyBar(
        trading_date=date(
            2026,
            8,
            6,
        ),
        open=Decimal(9000),
        high=Decimal(8800),
        low=Decimal(8900),
        close=Decimal(9100),
        adjusted_close=None,
        volume=Decimal(10),
    )

    result = (
        validate_equity_daily_bar(
            bar,
            listed_date=date(
                2000,
                1,
                1,
            ),
            target_end_date=date(
                2026,
                8,
                6,
            ),
        )
    )

    assert not result.valid