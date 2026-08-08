from datetime import date, timedelta

import pandas as pd

from imi.features.equity_technical import (
    calculate_equity_technical_features,
)


def make_trending_prices(
    rows: int,
) -> pd.DataFrame:
    start = date(
        2025,
        1,
        1,
    )

    data = []

    for index in range(rows):
        close = (
            100.0
            + index
        )

        data.append(
            {
                "trading_date":
                    start
                    + timedelta(
                        days=index
                    ),
                "open":
                    close - 0.5,
                "high":
                    close + 1.0,
                "low":
                    close - 1.0,
                "close":
                    close,
                "volume":
                    1_000_000
                    + (
                        index
                        * 1000
                    ),
            }
        )

    return pd.DataFrame(
        data
    )


def test_long_history_builds_features() -> None:
    prices = make_trending_prices(
        250
    )

    benchmark = {
        row.trading_date: 0.02
        for row
        in prices.itertuples(
            index=False
        )
    }

    features = (
        calculate_equity_technical_features(
            prices,
            ihsg_return20_by_date=(
                benchmark
            ),
        )
    )

    assert len(features) == 250

    latest = features[-1]

    assert latest["return_20d"] is not None
    assert latest["ema20"] is not None
    assert latest["ema50"] is not None
    assert latest["ema100"] is not None
    assert latest["ema200"] is not None
    assert latest["rsi14"] is not None
    assert latest["atr14"] is not None
    assert latest["volume_z20"] is not None
    assert latest["rs_ihsg_20d"] is not None


def test_rsi_is_bounded() -> None:
    prices = make_trending_prices(
        100
    )

    benchmark = {
        row.trading_date: 0.0
        for row
        in prices.itertuples(
            index=False
        )
    }

    features = (
        calculate_equity_technical_features(
            prices,
            ihsg_return20_by_date=(
                benchmark
            ),
        )
    )

    rsi_values = [
        row["rsi14"]
        for row in features
        if row["rsi14"]
        is not None
    ]

    assert rsi_values

    assert all(
        0.0 <= value <= 100.0
        for value
        in rsi_values
    )


def test_failed_breakout_detection() -> None:
    prices = make_trending_prices(
        25
    )

    prior_high = float(
        prices.iloc[
            -2
        ]["high"]
    )

    prices.loc[
        prices.index[-1],
        "high",
    ] = (
        prior_high
        + 20.0
    )

    prices.loc[
        prices.index[-1],
        "close",
    ] = (
        prior_high
        - 1.0
    )

    prices.loc[
        prices.index[-1],
        "open",
    ] = (
        prior_high
        - 2.0
    )

    prices.loc[
        prices.index[-1],
        "low",
    ] = (
        prior_high
        - 3.0
    )

    benchmark = {
        row.trading_date: 0.0
        for row
        in prices.itertuples(
            index=False
        )
    }

    features = (
        calculate_equity_technical_features(
            prices,
            ihsg_return20_by_date=(
                benchmark
            ),
        )
    )

    latest = features[-1]

    assert (
        latest[
            "failed_breakout_flag"
        ]
        is True
    )

    assert (
        latest[
            "breakout_flag"
        ]
        is False
    )