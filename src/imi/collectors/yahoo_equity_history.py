from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

MAX_RETRIES = 4
BASE_RETRY_DELAY = 1.0

RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}

import httpx

YAHOO_CHART_URL = (
    "https://query1.finance.yahoo.com/"
    "v8/finance/chart/{symbol}"
)

DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class EquityDailyBar:
    trading_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: Decimal | None


@dataclass(frozen=True)
class YahooHistoryResult:
    yahoo_symbol: str
    bars: list[EquityDailyBar]
    raw_count: int

    @property
    def parsed_count(self) -> int:
        return len(self.bars)

    @property
    def incomplete_count(self) -> int:
        return (
            self.raw_count
            - self.parsed_count
        )


def to_yahoo_symbol(
    idx_symbol: str,
) -> str:
    return f"{idx_symbol.strip().upper()}.JK"


def _unix_timestamp(
    value: date,
) -> int:
    dt = datetime.combine(
        value,
        time.min,
        tzinfo=UTC,
    )

    return int(dt.timestamp())


def _decimal_or_none(
    value: Any,
) -> Decimal | None:
    if value is None:
        return None

    return Decimal(str(value))


def _parse_payload(
    payload: dict[str, Any],
    *,
    yahoo_symbol: str,
) -> YahooHistoryResult:
    chart = payload.get("chart")

    if not isinstance(chart, dict):
        raise TypeError(
        "Yahoo response does not "
        "contain chart object."
    )

    error = chart.get("error")

    if error:
        raise RuntimeError(
            f"Yahoo returned error: {error}"
        )

    results = chart.get("result")

    if not isinstance(results, list):
        return YahooHistoryResult(
            yahoo_symbol=yahoo_symbol,
            bars=[],
            raw_count=0,
        )

    if not results:
        return YahooHistoryResult(
            yahoo_symbol=yahoo_symbol,
            bars=[],
            raw_count=0,
        )

    result = results[0]

    timestamps = result.get(
        "timestamp"
    ) or []

    indicators = result.get(
        "indicators"
    ) or {}

    quotes = indicators.get(
        "quote"
    ) or []

    adjusted = indicators.get(
        "adjclose"
    ) or []

    if not quotes:
        return YahooHistoryResult(
            yahoo_symbol=yahoo_symbol,
            bars=[],
            raw_count=0,
        )

    quote = quotes[0]

    adjusted_values: list[Any] = []

    if adjusted:
        adjusted_values = (
            adjusted[0].get(
                "adjclose"
            )
            or []
        )

    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []

    bars: list[EquityDailyBar] = []

    for index, timestamp in enumerate(
        timestamps
    ):
        if (
            index >= len(opens)
            or index >= len(highs)
            or index >= len(lows)
            or index >= len(closes)
        ):
            continue

        open_value = _decimal_or_none(
            opens[index]
        )
        high_value = _decimal_or_none(
            highs[index]
        )
        low_value = _decimal_or_none(
            lows[index]
        )
        close_value = _decimal_or_none(
            closes[index]
        )

        if (
            open_value is None
            or high_value is None
            or low_value is None
            or close_value is None
        ):
            continue

        adjusted_close = None

        if index < len(adjusted_values):
            adjusted_close = (
                _decimal_or_none(
                    adjusted_values[index]
                )
            )

        volume = None

        if index < len(volumes):
            volume = _decimal_or_none(
                volumes[index]
            )

        trading_date = (
            datetime.fromtimestamp(
                timestamp,
                tz=UTC,
            ).date()
        )

        bars.append(
            EquityDailyBar(
                trading_date=trading_date,
                open=open_value,
                high=high_value,
                low=low_value,
                close=close_value,
                adjusted_close=(
                    adjusted_close
                ),
                volume=volume,
            )
        )

    return YahooHistoryResult(
        yahoo_symbol=yahoo_symbol,
        bars=bars,
        raw_count=len(timestamps),
    )

def _is_no_data_response(
    response: httpx.Response,
) -> bool:
    if (
        response.status_code
        != httpx.codes.BAD_REQUEST
    ):
        return False

    try:
        payload = response.json()
    except ValueError:
        return False

    if not isinstance(payload, dict):
        return False

    chart = payload.get("chart")

    if not isinstance(chart, dict):
        return False

    error = chart.get("error")

    if not isinstance(error, dict):
        return False

    code = error.get("code")
    description = error.get(
        "description"
    )

    if not isinstance(
        description,
        str,
    ):
        return False

    normalized = (
        description
        .strip()
        .casefold()
    )

    return (
        code == "Bad Request"
        and (
            "data doesn't exist "
            "for startdate"
            in normalized
        )
    )

def _request_with_retry(
    client: httpx.Client,
    *,
    url: str,
    params: dict[str, object],
) -> httpx.Response:
    last_error: Exception | None = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            response = client.get(
                url,
                params=params,
            )

            if (
                response.status_code
                not in RETRYABLE_STATUS_CODES
            ):
                return response

            if attempt == MAX_RETRIES:
                return response

        except (
            httpx.ConnectError,
            httpx.ReadError,
            httpx.TimeoutException,
        ) as exc:
            last_error = exc

            if attempt == MAX_RETRIES:
                raise

        delay = (
            BASE_RETRY_DELAY
            * (2 ** (attempt - 1))
        )

        time.sleep(delay)

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "Yahoo request retry loop "
        "ended unexpectedly."
    )

def fetch_yahoo_equity_history(
    *,
    idx_symbol: str,
    start_date: date,
    end_date: date,
    client: httpx.Client,
) -> YahooHistoryResult:
    yahoo_symbol = to_yahoo_symbol(
        idx_symbol
    )

    period1 = _unix_timestamp(
        start_date
    )

    # Yahoo period2 behaves as an
    # exclusive upper boundary.
    period2 = _unix_timestamp(
        end_date + timedelta(days=1)
    )

    url = YAHOO_CHART_URL.format(
        symbol=yahoo_symbol
    )

    response = _request_with_retry(
        client,
        url=url,
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        },
    )

    if _is_no_data_response(
    response
    ):
        return YahooHistoryResult(
        yahoo_symbol=yahoo_symbol,
        bars=[],
        raw_count=0,
    )

    response.raise_for_status()

    payload = response.json()

    return _parse_payload(
        payload,
        yahoo_symbol=yahoo_symbol,
        )