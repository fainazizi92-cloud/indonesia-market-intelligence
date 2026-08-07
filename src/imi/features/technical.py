import numpy as np
import pandas as pd

FEATURE_VERSION = "technical_v1_yahoo_eod"


def _calculate_rsi14(
    close: pd.Series,
) -> pd.Series:
    delta = close.diff()

    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    average_gain = gain.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14,
    ).mean()

    average_loss = loss.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14,
    ).mean()

    relative_strength = (
        average_gain
        / average_loss.replace(
            0,
            np.nan,
        )
    )

    rsi = (
        100
        - (
            100
            / (
                1
                + relative_strength
            )
        )
    )

    rsi = rsi.mask(
        (
            average_loss == 0
        )
        & (
            average_gain > 0
        ),
        100.0,
    )

    rsi = rsi.mask(
        (
            average_loss == 0
        )
        & (
            average_gain == 0
        ),
        50.0,
    )

    return rsi


def _calculate_atr14(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
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
    ).max(axis=1)

    return true_range.ewm(
        alpha=1 / 14,
        adjust=False,
        min_periods=14,
    ).mean()


def compute_ihsg_technical_features(
    prices: pd.DataFrame,
) -> pd.DataFrame:
    required_columns = {
        "trading_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    missing_columns = (
        required_columns
        - set(prices.columns)
    )

    if missing_columns:
        raise ValueError(
            "Missing price columns: "
            f"{sorted(missing_columns)}"
        )

    frame = (
        prices.copy()
        .sort_values(
            "trading_date"
        )
        .reset_index(
            drop=True
        )
    )

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
    ):
        frame[column] = (
            pd.to_numeric(
                frame[column],
                errors="coerce",
            )
        )

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]

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

    for period in (
        20,
        50,
        100,
        200,
    ):
        frame[f"ema{period}"] = (
            close.ewm(
                span=period,
                adjust=False,
                min_periods=period,
            ).mean()
        )

    frame["rsi14"] = (
        _calculate_rsi14(
            close
        )
    )

    frame["atr14"] = (
        _calculate_atr14(
            high,
            low,
            close,
        )
    )

    # Yahoo index volume tidak dipakai untuk
    # IHSG regime karena kualitas historisnya
    # tidak konsisten.
    frame["volume_z20"] = np.nan

    # Untuk IHSG sendiri, relative strength
    # terhadap IHSG/sector tidak memiliki
    # interpretasi yang berguna.
    frame["rs_ihsg_20d"] = np.nan
    frame["rs_sector_20d"] = np.nan

    previous_20d_high = (
        high.rolling(
            window=20,
            min_periods=20,
        )
        .max()
        .shift(1)
    )

    breakout = pd.Series(
        pd.NA,
        index=frame.index,
        dtype="boolean",
    )

    failed_breakout = (
        pd.Series(
            pd.NA,
            index=frame.index,
            dtype="boolean",
        )
    )

    valid_breakout_window = (
        previous_20d_high.notna()
    )

    breakout.loc[
        valid_breakout_window
    ] = (
        close.loc[
            valid_breakout_window
        ]
        > previous_20d_high.loc[
            valid_breakout_window
        ]
    )

    failed_breakout.loc[
        valid_breakout_window
    ] = (
        (
            high.loc[
                valid_breakout_window
            ]
            > previous_20d_high.loc[
                valid_breakout_window
            ]
        )
        & (
            close.loc[
                valid_breakout_window
            ]
            <= previous_20d_high.loc[
                valid_breakout_window
            ]
        )
    )

    frame[
        "breakout_flag"
    ] = breakout

    frame[
        "failed_breakout_flag"
    ] = failed_breakout

    return frame
