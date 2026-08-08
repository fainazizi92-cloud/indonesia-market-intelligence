from datetime import date

BREADTH_VERSION = "BREADTH_V1"

TREND_WEIGHT = 0.40
ADVANCE_DECLINE_WEIGHT = 0.25
HIGH_LOW_52W_WEIGHT = 0.15
HIGH_LOW_20D_WEIGHT = 0.10
VOLUME_WEIGHT = 0.10


def build_universe_code(
    snapshot_date: date,
) -> str:
    return (
        "IDX_CURRENT_"
        f"{snapshot_date:%Y%m%d}"
        "_EMA200_"
        f"{BREADTH_VERSION}"
    )


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def _count_balance(
    positive: int,
    negative: int,
    total: int,
) -> float:
    if total <= 0:
        return 0.0

    return (
        positive - negative
    ) / total


def _volume_balance(
    up_volume: float,
    down_volume: float,
) -> float:
    total_volume = (
        up_volume
        + down_volume
    )

    if total_volume <= 0:
        return 0.0

    return (
        up_volume
        - down_volume
    ) / total_volume


def _trend_component(
    *,
    pct_above_ema20: float,
    pct_above_ema50: float,
    pct_above_ema200: float,
) -> float:
    percentages = (
        pct_above_ema20,
        pct_above_ema50,
        pct_above_ema200,
    )

    normalized = [
        _clamp(
            (value - 50.0) / 50.0,
            -1.0,
            1.0,
        )
        for value in percentages
    ]

    return sum(normalized) / len(
        normalized
    )


def calculate_breadth_score(
    *,
    advances: int,
    declines: int,
    unchanged: int,
    new_high_20d: int,
    new_low_20d: int,
    new_high_52w: int,
    new_low_52w: int,
    pct_above_ema20: float,
    pct_above_ema50: float,
    pct_above_ema200: float,
    up_volume: float,
    down_volume: float,
) -> float:
    total = (
        advances
        + declines
        + unchanged
    )

    if total <= 0:
        return 50.0

    advance_decline = _count_balance(
        advances,
        declines,
        total,
    )

    trend = _trend_component(
        pct_above_ema20=(
            pct_above_ema20
        ),
        pct_above_ema50=(
            pct_above_ema50
        ),
        pct_above_ema200=(
            pct_above_ema200
        ),
    )

    high_low_20d = _count_balance(
        new_high_20d,
        new_low_20d,
        total,
    )

    high_low_52w = _count_balance(
        new_high_52w,
        new_low_52w,
        total,
    )

    volume = _volume_balance(
        up_volume,
        down_volume,
    )

    composite = (
        TREND_WEIGHT
        * trend
        + ADVANCE_DECLINE_WEIGHT
        * advance_decline
        + HIGH_LOW_52W_WEIGHT
        * high_low_52w
        + HIGH_LOW_20D_WEIGHT
        * high_low_20d
        + VOLUME_WEIGHT
        * volume
    )

    score = (
        composite + 1.0
    ) * 50.0

    return round(
        _clamp(
            score,
            0.0,
            100.0,
        ),
        4,
    )