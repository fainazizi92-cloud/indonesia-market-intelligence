from datetime import date

import pytest

from imi.features.sector_rotation import (
    build_sector_model_version,
    calculate_relative_strength_score,
    calculate_sector_breadth_score,
    calculate_sector_composite_score,
    calculate_volume_score,
    classify_rotation,
    prepare_sector_score_rows,
    resolve_sector_build_mode,
)


def test_sector_model_version() -> None:
    result = build_sector_model_version(
        date(
            2026,
            8,
            8,
        )
    )

    assert result == (
        "sector_rotation_v1_"
        "current_20260808_"
        "yahoo_eod"
    )


def test_neutral_relative_strength() -> None:
    score = (
        calculate_relative_strength_score(
            sector_return_20d=0.10,
            sector_return_60d=0.20,
            ihsg_return_20d=0.10,
            ihsg_return_60d=0.20,
        )
    )

    assert score == 50.0


def test_sector_breadth_is_bounded() -> None:
    score = (
        calculate_sector_breadth_score(
            advances=70,
            declines=20,
            unchanged=10,
            pct_above_ema20=80.0,
            pct_above_ema50=70.0,
            pct_above_ema200=60.0,
        )
    )

    assert 0.0 <= score <= 100.0


def test_volume_score_neutral_when_zero() -> None:
    score = calculate_volume_score(
        up_volume=0.0,
        down_volume=0.0,
    )

    assert score == 50.0


def test_composite_score() -> None:
    score = (
        calculate_sector_composite_score(
            relative_strength_score=80.0,
            breadth_score=60.0,
            volume_score=50.0,
        )
    )

    assert score == 67.0


def test_leading_rotation() -> None:
    label = classify_rotation(
        score=70.0,
        score_change_20d=5.0,
    )

    assert label == "LEADING"


def test_improving_rotation() -> None:
    label = classify_rotation(
        score=45.0,
        score_change_20d=8.0,
    )

    assert label == "IMPROVING"


def test_weakening_rotation() -> None:
    label = classify_rotation(
        score=65.0,
        score_change_20d=-8.0,
    )

    assert label == "WEAKENING"


def test_lagging_rotation() -> None:
    label = classify_rotation(
        score=30.0,
        score_change_20d=-4.0,
    )

    assert label == "LAGGING"


def test_build_mode_full_when_empty() -> None:
    mode = resolve_sector_build_mode(
        existing_last_date=None,
        existing_latest_sector_count=0,
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        latest_input_sector_count=11,
        force=False,
    )

    assert mode == "FULL"


def test_build_mode_up_to_date() -> None:
    latest = date(
        2026,
        8,
        6,
    )

    mode = resolve_sector_build_mode(
        existing_last_date=latest,
        existing_latest_sector_count=11,
        latest_input_date=latest,
        latest_input_sector_count=11,
        force=False,
    )

    assert mode == "UP_TO_DATE"


def test_build_mode_incremental() -> None:
    mode = resolve_sector_build_mode(
        existing_last_date=date(
            2026,
            8,
            5,
        ),
        existing_latest_sector_count=11,
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        latest_input_sector_count=11,
        force=False,
    )

    assert mode == "INCREMENTAL"


def test_incomplete_latest_sector_state_forces_full() -> None:
    mode = resolve_sector_build_mode(
        existing_last_date=date(
            2026,
            8,
            6,
        ),
        existing_latest_sector_count=10,
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        latest_input_sector_count=11,
        force=False,
    )

    assert mode == "FULL"


def test_force_uses_full_mode() -> None:
    mode = resolve_sector_build_mode(
        existing_last_date=date(
            2026,
            8,
            6,
        ),
        existing_latest_sector_count=11,
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        latest_input_sector_count=11,
        force=True,
    )

    assert mode == "FULL"


def test_build_mode_rejects_stored_data_ahead() -> None:
    with pytest.raises(
        RuntimeError
    ):
        resolve_sector_build_mode(
            existing_last_date=date(
                2026,
                8,
                7,
            ),
            existing_latest_sector_count=11,
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            latest_input_sector_count=11,
            force=False,
        )


def test_incremental_history_affects_rotation_label() -> None:
    prior_history = {
        "IDXBASIC": [
            40.0
            for _ in range(20)
        ]
    }

    inputs = [
        {
            "trading_date":
                date(
                    2026,
                    8,
                    6,
                ),
            "sector_code":
                "IDXBASIC",
            "eligible_count":
                100,
            "sector_return_20d":
                0.10,
            "sector_return_60d":
                0.10,
            "ihsg_return_20d":
                0.10,
            "ihsg_return_60d":
                0.10,
            "advances":
                50,
            "declines":
                50,
            "unchanged":
                0,
            "pct_above_ema20":
                50.0,
            "pct_above_ema50":
                50.0,
            "pct_above_ema200":
                50.0,
            "up_volume":
                100.0,
            "down_volume":
                100.0,
        }
    ]

    rows = prepare_sector_score_rows(
        inputs=inputs,
        model_version="test",
        prior_score_history=(
            prior_history
        ),
    )

    assert len(rows) == 1
    assert rows[0]["score"] == 50.0
    assert (
        rows[0]["rotation_label"]
        == "IMPROVING"
    )