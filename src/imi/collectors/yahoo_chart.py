from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from statistics import median
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from imi.market_data import MarketPriceRecord

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")


class YahooChartError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class YahooFetchResult:
    symbol: str
    currency: str | None
    bars: list[MarketPriceRecord]
    skipped_incomplete: int
    data_granularity: str | None
    median_gap_days: float | None


def _decimal_or_none(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    return Decimal(str(value))


def _value_at(
    values: list[Any],
    index: int,
) -> Any:
    if index >= len(values):
        return None

    return values[index]


def _request_chart(
    *,
    symbol: str,
    params: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    encoded_symbol = quote(symbol, safe="")

    url = (
        "https://query1.finance.yahoo.com/"
        f"v8/finance/chart/{encoded_symbol}"
    )

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }

    with httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = client.get(
            url,
            params=params,
        )

    response.raise_for_status()

    payload = response.json()

    chart = payload.get("chart")

    if not isinstance(chart, dict):
        raise YahooChartError(
            "Yahoo response does not contain chart data."
        )

    chart_error = chart.get("error")

    if chart_error:
        raise YahooChartError(
            f"Yahoo returned an error: {chart_error}"
        )

    results = chart.get("result") or []

    if not results:
        raise YahooChartError(
            "Yahoo returned no chart result."
        )

    return results[0]


def _parse_result(
    *,
    result: dict[str, Any],
    requested_symbol: str,
) -> YahooFetchResult:
    meta = result.get("meta") or {}

    timestamps = result.get("timestamp") or []

    data_granularity = meta.get(
        "dataGranularity"
    )

    sorted_timestamps = sorted(
        int(value) for value in timestamps
    )

    gaps = [
        (
            sorted_timestamps[index]
            - sorted_timestamps[index - 1]
        )
        / 86400
        for index in range(
            1,
            len(sorted_timestamps),
        )
        if (
            sorted_timestamps[index]
            > sorted_timestamps[index - 1]
        )
    ]

    median_gap_days = (
        float(median(gaps))
        if gaps
        else None
    )

    if (
        data_granularity is not None
        and data_granularity != "1d"
    ):
        raise YahooChartError(
            "Yahoo returned non-daily data: "
            f"{data_granularity}"
        )

    if (
        median_gap_days is not None
        and median_gap_days > 7
    ):
        raise YahooChartError(
            "Yahoo response does not appear "
            "to contain daily observations. "
            "Median gap: "
            f"{median_gap_days:.2f} days."
        )

    indicators = result.get(
        "indicators"
    ) or {}

    quote_blocks = indicators.get(
        "quote"
    ) or []

    if not quote_blocks:
        raise YahooChartError(
            "Yahoo response has no quote block."
        )

    quote_block = quote_blocks[0]

    opens = quote_block.get("open") or []
    highs = quote_block.get("high") or []
    lows = quote_block.get("low") or []
    closes = quote_block.get("close") or []
    volumes = quote_block.get("volume") or []

    adjusted_blocks = (
        indicators.get("adjclose") or []
    )

    adjusted_closes: list[Any] = []

    if adjusted_blocks:
        adjusted_closes = (
            adjusted_blocks[0].get(
                "adjclose"
            )
            or []
        )

    bars: list[MarketPriceRecord] = []
    skipped_incomplete = 0

    for index, timestamp in enumerate(
        timestamps
    ):
        open_value = _decimal_or_none(
            _value_at(opens, index)
        )
        high_value = _decimal_or_none(
            _value_at(highs, index)
        )
        low_value = _decimal_or_none(
            _value_at(lows, index)
        )
        close_value = _decimal_or_none(
            _value_at(closes, index)
        )

        if (
            open_value is None
            or high_value is None
            or low_value is None
            or close_value is None
        ):
            skipped_incomplete += 1
            continue

        adjusted_close = _decimal_or_none(
            _value_at(
                adjusted_closes,
                index,
            )
        )

        if adjusted_close is None:
            adjusted_close = close_value

        volume = _decimal_or_none(
            _value_at(
                volumes,
                index,
            )
        )

        observed_at = (
            datetime.fromtimestamp(
                int(timestamp),
                tz=UTC,
            )
        )

        trading_date = (
            observed_at.astimezone(
                JAKARTA_TZ
            ).date()
        )

        bars.append(
            MarketPriceRecord(
                trading_date=trading_date,
                open=open_value,
                high=high_value,
                low=low_value,
                close=close_value,
                adjusted_close=adjusted_close,
                volume=volume,
                observed_at=observed_at,
                raw_ref=(
                    "yahoo:"
                    f"{requested_symbol}:"
                    f"{timestamp}"
                ),
            )
        )

    provider_symbol = str(
        meta.get("symbol")
        or requested_symbol
    )

    currency = meta.get("currency")

    return YahooFetchResult(
        symbol=provider_symbol,
        currency=(
            str(currency)
            if currency is not None
            else None
        ),
        bars=bars,
        skipped_incomplete=skipped_incomplete,
        data_granularity=(
            str(data_granularity)
            if data_granularity
            else None
        ),
        median_gap_days=median_gap_days,
    )


def fetch_yahoo_daily(
    symbol: str,
    range_: str = "10y",
    timeout: float = 30.0,
) -> YahooFetchResult:
    if range_.lower() == "max":
        raise YahooChartError(
            "range=max is disabled for "
            "daily ingestion because the "
            "provider may return aggregated "
            "historical bars. Use explicit "
            "date-period ingestion instead."
        )

    result = _request_chart(
        symbol=symbol,
        params={
            "range": range_,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
        timeout=timeout,
    )

    return _parse_result(
        result=result,
        requested_symbol=symbol,
    )


def fetch_yahoo_daily_period(
    *,
    symbol: str,
    start: date,
    end: date,
    timeout: float = 30.0,
) -> YahooFetchResult:
    if end < start:
        raise ValueError(
            "End date must not be "
            "earlier than start date."
        )

    period1 = int(
        datetime(
            start.year,
            start.month,
            start.day,
            tzinfo=UTC,
        ).timestamp()
    )

    exclusive_end = (
        end + timedelta(days=1)
    )

    period2 = int(
        datetime(
            exclusive_end.year,
            exclusive_end.month,
            exclusive_end.day,
            tzinfo=UTC,
        ).timestamp()
    )

    result = _request_chart(
        symbol=symbol,
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
        timeout=timeout,
    )

    return _parse_result(
        result=result,
        requested_symbol=symbol,
    )