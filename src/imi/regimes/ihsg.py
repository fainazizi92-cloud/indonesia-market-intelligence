import numpy as np
import pandas as pd

MODEL_VERSION = "ihsg_partial_v1"


def _percentile_of_last(
    values: np.ndarray,
) -> float:
    current = values[-1]

    if not np.isfinite(current):
        return np.nan

    clean_values = values[
        np.isfinite(values)
    ]

    if len(clean_values) == 0:
        return np.nan

    return float(
        np.mean(
            clean_values
            <= current
        )
    )


def compute_ihsg_partial_regimes(
    features: pd.DataFrame,
) -> pd.DataFrame:
    frame = features.copy()

    required = [
        "close",
        "return_20d",
        "return_60d",
        "ema20",
        "ema50",
        "ema200",
        "rsi14",
        "atr14",
    ]

    valid_trend = (
        frame[required]
        .notna()
        .all(axis=1)
    )

    trend_score = pd.Series(
        50.0,
        index=frame.index,
    )

    trend_score += np.where(
        frame["close"]
        > frame["ema20"],
        5.0,
        -5.0,
    )

    trend_score += np.where(
        frame["close"]
        > frame["ema50"],
        7.0,
        -7.0,
    )

    trend_score += np.where(
        frame["close"]
        > frame["ema200"],
        10.0,
        -10.0,
    )

    trend_score += np.where(
        frame["ema20"]
        > frame["ema50"],
        7.0,
        -7.0,
    )

    trend_score += np.where(
        frame["ema50"]
        > frame["ema200"],
        8.0,
        -8.0,
    )

    trend_score += np.where(
        frame["return_20d"] > 0,
        5.0,
        -5.0,
    )

    trend_score += np.where(
        frame["return_60d"] > 0,
        5.0,
        -5.0,
    )

    rsi_component = np.select(
        [
            frame["rsi14"] >= 55,
            frame["rsi14"] <= 45,
        ],
        [
            3.0,
            -3.0,
        ],
        default=0.0,
    )

    trend_score += rsi_component

    trend_score = (
        trend_score.clip(
            lower=0.0,
            upper=100.0,
        )
    )

    trend_score.loc[
        ~valid_trend
    ] = np.nan

    frame[
        "ihsg_trend_score"
    ] = trend_score

    atr_percentage = (
        frame["atr14"]
        / frame["close"]
    )

    atr_percentile = (
        atr_percentage.rolling(
            window=252,
            min_periods=60,
        )
        .apply(
            _percentile_of_last,
            raw=True,
        )
    )

    volatility_support = (
        100.0
        - (
            atr_percentile
            * 100.0
        )
    )

    rolling_high = (
        frame["close"]
        .rolling(
            window=252,
            min_periods=60,
        )
        .max()
    )

    drawdown = (
        frame["close"]
        / rolling_high
        - 1.0
    )

    drawdown_score = (
        100.0
        + (
            drawdown
            * 333.333333
        )
    ).clip(
        lower=0.0,
        upper=100.0,
    )

    volatility_score = (
        0.70
        * volatility_support
        + 0.30
        * drawdown_score
    )

    frame[
        "volatility_score"
    ] = volatility_score

    frame[
        "composite_score"
    ] = (
        0.75
        * frame[
            "ihsg_trend_score"
        ]
        + 0.25
        * frame[
            "volatility_score"
        ]
    )

    frame["direction"] = pd.NA

    valid_composite = (
        frame[
            "composite_score"
        ].notna()
    )

    frame.loc[
        valid_composite
        & (
            frame[
                "composite_score"
            ]
            >= 60
        ),
        "direction",
    ] = "BULLISH"

    frame.loc[
        valid_composite
        & (
            frame[
                "composite_score"
            ]
            <= 40
        ),
        "direction",
    ] = "BEARISH"

    frame.loc[
        valid_composite
        & (
            frame[
                "composite_score"
            ]
            > 40
        )
        & (
            frame[
                "composite_score"
            ]
            < 60
        ),
        "direction",
    ] = "NEUTRAL"

    confidence = (
        0.25
        + (
            (
                frame[
                    "composite_score"
                ]
                - 50
            ).abs()
            / 50
        )
        * 0.30
    )

    frame["confidence"] = (
        confidence.clip(
            lower=0.25,
            upper=0.55,
        )
    )

    return frame.loc[
        valid_composite
    ].copy()