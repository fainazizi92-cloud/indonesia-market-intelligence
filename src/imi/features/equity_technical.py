from collections.abc import Mapping
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from imi.features.technical import FEATURE_VERSION

RSI_PERIOD = 14
ATR_PERIOD = 14
VOLUME_Z_PERIOD = 20
BREAKOUT_PERIOD = 20


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    if pd.isna(value):
        return None

    return float(value)


def _optional_bool(
    value: Any,
) -> bool | None:
    if value is None:
        return None

    if pd.isna(value):
        return None

    return bool(value)


def _wilder_average(
    series: pd.Series,
    *,
    period: int,
) -> pd.Series:
    return series.ewm(
        alpha=1.0 / period,
        adjust=False,
        min_periods=period,
    ).mean()


def _calculate_rsi(
    close: pd.Series,
    *,
    period: int = RSI_PERIOD,
) -> pd.Series:
    delta = close.diff()

    gain = delta.clip(
        lower=0.0
    )

    loss = (
        -delta.clip(
            upper=0.0
        )
    )

    average_gain = _wilder_average(
        gain,
        period=period,
    )

    average_loss = _wilder_average(
        loss,
        period=period,
    )

    relative_strength = (
        average_gain
        / average_loss.replace(
            0.0,
            np.nan,
        )
    )

    rsi = (
        100.0
        - (
            100.0
            / (
                1.0
                + relative_strength
            )
        )
    )

    gain_only = (
        (average_gain > 0.0)
        & (average_loss == 0.0)
    )

    loss_only = (
        (average_gain == 0.0)
        & (average_loss > 0.0)
    )

    flat = (
        (average_gain == 0.0)
        & (average_loss == 0.0)
    )

    rsi = rsi.mask(
        gain_only,
        100.0,
    )

    rsi = rsi.mask(
        loss_only,
        0.0,
    )

    rsi = rsi.mask(
        flat,
        50.0,
    )

    return rsi


def _calculate_atr(
    *,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = ATR_PERIOD,
) -> pd.Series:
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (
                high
                - previous_close
            ).abs(),
            (
                low
                - previous_close
            ).abs(),
        ],
        axis=1,
    ).max(
        axis=1
    )

    return _wilder_average(
        true_range,
        period=period,
    )


def _calculate_volume_zscore(
    volume: pd.Series,
    *,
    period: int = VOLUME_Z_PERIOD,
) -> pd.Series:
    rolling_mean = volume.rolling(
        window=period,
        min_periods=period,
    ).mean()

    rolling_std = volume.rolling(
        window=period,
        min_periods=period,
    ).std(
        ddof=0
    )

    rolling_std = rolling_std.replace(
        0.0,
        np.nan,
    )

    return (
        volume
        - rolling_mean
    ) / rolling_std


def calculate_equity_technical_features(
    prices: pd.DataFrame,
    *,
    ihsg_return20_by_date: Mapping[
        date,
        float | None,
    ],
) -> list[dict[str, Any]]:
    if prices.empty:
        return []

    frame = (
        prices.copy()
        .sort_values(
            "trading_date"
        )
        .reset_index(
            drop=True
        )
    )

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    for column in numeric_columns:
        frame[column] = (
            pd.to_numeric(
                frame[column],
                errors="coerce",
            )
        )

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    frame["return_1d"] = (
        close.pct_change(
            periods=1,
            fill_method=None,
        )
    )

    frame["return_5d"] = (
        close.pct_change(
            periods=5,
            fill_method=None,
        )
    )

    frame["return_20d"] = (
        close.pct_change(
            periods=20,
            fill_method=None,
        )
    )

    frame["return_60d"] = (
        close.pct_change(
            periods=60,
            fill_method=None,
        )
    )

    frame["ema20"] = close.ewm(
        span=20,
        adjust=False,
        min_periods=20,
    ).mean()

    frame["ema50"] = close.ewm(
        span=50,
        adjust=False,
        min_periods=50,
    ).mean()

    frame["ema100"] = close.ewm(
        span=100,
        adjust=False,
        min_periods=100,
    ).mean()

    frame["ema200"] = close.ewm(
        span=200,
        adjust=False,
        min_periods=200,
    ).mean()

    frame["rsi14"] = _calculate_rsi(
        close
    )

    frame["atr14"] = _calculate_atr(
        high=high,
        low=low,
        close=close,
    )

    frame["volume_z20"] = (
        _calculate_volume_zscore(
            volume
        )
    )

    prior_high20 = (
        high.shift(1)
        .rolling(
            window=BREAKOUT_PERIOD,
            min_periods=(
                BREAKOUT_PERIOD
            ),
        )
        .max()
    )

    breakout_available = (
        prior_high20.notna()
    )

    breakout = (
        close
        > prior_high20
    ).where(
        breakout_available
    )

    failed_breakout = (
        (
            high
            > prior_high20
        )
        & (
            close
            <= prior_high20
        )
    ).where(
        breakout_available
    )

    frame[
        "breakout_flag"
    ] = breakout

    frame[
        "failed_breakout_flag"
    ] = failed_breakout

    benchmark_values = []

    for trading_date in frame[
        "trading_date"
    ]:
        benchmark_value = (
            ihsg_return20_by_date.get(
                trading_date
            )
        )

        benchmark_values.append(
            benchmark_value
        )

    benchmark = pd.Series(
        benchmark_values,
        index=frame.index,
        dtype="float64",
    )

    frame[
        "rs_ihsg_20d"
    ] = (
        frame["return_20d"]
        - benchmark
    )

    records: list[
        dict[str, Any]
    ] = []

    for row in frame.itertuples(
        index=False
    ):
        records.append(
            {
                "trading_date":
                    row.trading_date,
                "return_1d":
                    _optional_float(
                        row.return_1d
                    ),
                "return_5d":
                    _optional_float(
                        row.return_5d
                    ),
                "return_20d":
                    _optional_float(
                        row.return_20d
                    ),
                "return_60d":
                    _optional_float(
                        row.return_60d
                    ),
                "ema20":
                    _optional_float(
                        row.ema20
                    ),
                "ema50":
                    _optional_float(
                        row.ema50
                    ),
                "ema100":
                    _optional_float(
                        row.ema100
                    ),
                "ema200":
                    _optional_float(
                        row.ema200
                    ),
                "rsi14":
                    _optional_float(
                        row.rsi14
                    ),
                "atr14":
                    _optional_float(
                        row.atr14
                    ),
                "volume_z20":
                    _optional_float(
                        row.volume_z20
                    ),
                "rs_ihsg_20d":
                    _optional_float(
                        row.rs_ihsg_20d
                    ),
                "rs_sector_20d":
                    None,
                "breakout_flag":
                    _optional_bool(
                        row.breakout_flag
                    ),
                "failed_breakout_flag":
                    _optional_bool(
                        row.failed_breakout_flag
                    ),
                "feature_version":
                    FEATURE_VERSION,
            }
        )

    return records