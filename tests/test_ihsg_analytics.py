import numpy as np
import pandas as pd

from imi.features.technical import (
    compute_ihsg_technical_features,
)
from imi.regimes.ihsg import (
    compute_ihsg_partial_regimes,
)


def make_prices() -> pd.DataFrame:
    rows = 320

    close = (
        np.arange(
            rows,
            dtype=float,
        )
        * 2.0
        + 1000.0
    )

    return pd.DataFrame(
        {
            "trading_date": (
                pd.bdate_range(
                    "2025-01-01",
                    periods=rows,
                ).date
            ),
            "open": close - 0.25,
            "high": close + 0.50,
            "low": close - 0.50,
            "close": close,
            "volume": (
                np.full(
                    rows,
                    1000.0,
                )
            ),
        }
    )


def test_technical_features() -> None:
    prices = make_prices()

    features = (
        compute_ihsg_technical_features(
            prices
        )
    )

    assert len(features) == len(prices)

    latest = features.iloc[-1]

    assert pd.notna(
        latest["ema200"]
    )

    assert pd.notna(
        latest["rsi14"]
    )

    assert pd.notna(
        latest["atr14"]
    )

    assert features[
        "volume_z20"
    ].isna().all()

    assert bool(
        latest["breakout_flag"]
    )


def test_partial_regime() -> None:
    prices = make_prices()

    features = (
        compute_ihsg_technical_features(
            prices
        )
    )

    regimes = (
        compute_ihsg_partial_regimes(
            features
        )
    )

    assert not regimes.empty

    latest = regimes.iloc[-1]

    assert (
        latest["direction"]
        == "BULLISH"
    )

    assert (
        0
        <= latest[
            "ihsg_trend_score"
        ]
        <= 100
    )

    assert (
        0
        <= latest[
            "volatility_score"
        ]
        <= 100
    )

    assert (
        latest["confidence"]
        <= 0.55
    )