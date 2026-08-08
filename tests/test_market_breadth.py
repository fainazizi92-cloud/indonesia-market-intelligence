from datetime import date

from imi.features.market_breadth import (
    build_universe_code,
    calculate_breadth_score,
)


def test_universe_code_contains_snapshot() -> None:
    result = build_universe_code(
        date(
            2026,
            8,
            8,
        )
    )

    assert result == (
        "IDX_CURRENT_"
        "20260808_"
        "EMA200_"
        "BREADTH_V1"
    )


def test_neutral_breadth_score() -> None:
    score = calculate_breadth_score(
        advances=50,
        declines=50,
        unchanged=0,
        new_high_20d=0,
        new_low_20d=0,
        new_high_52w=0,
        new_low_52w=0,
        pct_above_ema20=50.0,
        pct_above_ema50=50.0,
        pct_above_ema200=50.0,
        up_volume=0.0,
        down_volume=0.0,
    )

    assert score == 50.0


def test_maximum_bullish_breadth_score() -> None:
    score = calculate_breadth_score(
        advances=100,
        declines=0,
        unchanged=0,
        new_high_20d=100,
        new_low_20d=0,
        new_high_52w=100,
        new_low_52w=0,
        pct_above_ema20=100.0,
        pct_above_ema50=100.0,
        pct_above_ema200=100.0,
        up_volume=1_000_000.0,
        down_volume=0.0,
    )

    assert score == 100.0


def test_maximum_bearish_breadth_score() -> None:
    score = calculate_breadth_score(
        advances=0,
        declines=100,
        unchanged=0,
        new_high_20d=0,
        new_low_20d=100,
        new_high_52w=0,
        new_low_52w=100,
        pct_above_ema20=0.0,
        pct_above_ema50=0.0,
        pct_above_ema200=0.0,
        up_volume=0.0,
        down_volume=1_000_000.0,
    )

    assert score == 0.0