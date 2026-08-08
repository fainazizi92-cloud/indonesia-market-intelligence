from datetime import date

import pytest

from imi.features.integrated_sector import (
    BASE_OWNERSHIP_WEIGHT,
    BASE_TECHNICAL_WEIGHT,
    build_integrated_sector_model_version,
    calculate_effective_weights,
    calculate_integrated_sector_metrics,
    classify_alignment,
    classify_integrated_score,
    extract_current_universe_date,
    prepare_integrated_sector_rows,
    resolve_integrated_sector_build_mode,
)


def test_extract_current_universe_date() -> None:
    result = (
        extract_current_universe_date(
            "sector_rotation_v1_"
            "current_20260808_"
            "yahoo_eod"
        )
    )

    assert result == date(
        2026,
        8,
        8,
    )


def test_extract_current_universe_rejects_missing() -> None:
    with pytest.raises(
        ValueError
    ):
        extract_current_universe_date(
            "sector_rotation_v1"
        )


def test_build_model_version() -> None:
    result = (
        build_integrated_sector_model_version(
            date(
                2026,
                8,
                8,
            )
        )
    )

    assert result == (
        "integrated_sector_v1_"
        "current_20260808"
    )


def test_strong_bullish_label() -> None:
    assert (
        classify_integrated_score(
            70.0
        )
        == "STRONG_BULLISH"
    )


def test_bullish_label() -> None:
    assert (
        classify_integrated_score(
            60.0
        )
        == "BULLISH"
    )


def test_neutral_label() -> None:
    assert (
        classify_integrated_score(
            50.0
        )
        == "NEUTRAL"
    )


def test_bearish_label() -> None:
    assert (
        classify_integrated_score(
            40.0
        )
        == "BEARISH"
    )


def test_strong_bearish_label() -> None:
    assert (
        classify_integrated_score(
            30.0
        )
        == "STRONG_BEARISH"
    )


def test_fresh_weights() -> None:
    (
        technical_weight,
        ownership_weight,
        stale,
    ) = calculate_effective_weights(
        ownership_age_days=30
    )

    assert (
        technical_weight
        == BASE_TECHNICAL_WEIGHT
    )

    assert (
        ownership_weight
        == BASE_OWNERSHIP_WEIGHT
    )

    assert stale is False


def test_stale_weights() -> None:
    (
        technical_weight,
        ownership_weight,
        stale,
    ) = calculate_effective_weights(
        ownership_age_days=46
    )

    assert technical_weight == 1.0
    assert ownership_weight == 0.0
    assert stale is True


def test_fresh_integrated_score() -> None:
    metrics = (
        calculate_integrated_sector_metrics(
            trading_date=date(
                2026,
                8,
                6,
            ),
            ownership_as_of_date=date(
                2026,
                7,
                31,
            ),
            technical_score=70.0,
            ownership_score=50.0,
        )
    )

    assert (
        metrics.integrated_score
        == 66.0
    )

    assert (
        metrics.ownership_stale_flag
        is False
    )


def test_stale_score_uses_technical_only() -> None:
    metrics = (
        calculate_integrated_sector_metrics(
            trading_date=date(
                2026,
                8,
                1,
            ),
            ownership_as_of_date=date(
                2026,
                6,
                1,
            ),
            technical_score=70.0,
            ownership_score=10.0,
        )
    )

    assert (
        metrics.integrated_score
        == 70.0
    )

    assert (
        metrics.ownership_stale_flag
        is True
    )


def test_confirmed_bullish_alignment() -> None:
    result = classify_alignment(
        technical_score=60.0,
        ownership_score=60.0,
        ownership_stale_flag=False,
    )

    assert (
        result
        == "CONFIRMED_BULLISH"
    )


def test_confirmed_bearish_alignment() -> None:
    result = classify_alignment(
        technical_score=40.0,
        ownership_score=40.0,
        ownership_stale_flag=False,
    )

    assert (
        result
        == "CONFIRMED_BEARISH"
    )


def test_divergence_alignment() -> None:
    result = classify_alignment(
        technical_score=60.0,
        ownership_score=40.0,
        ownership_stale_flag=False,
    )

    assert result == "DIVERGENCE"


def test_technical_lead_alignment() -> None:
    result = classify_alignment(
        technical_score=60.0,
        ownership_score=50.0,
        ownership_stale_flag=False,
    )

    assert (
        result
        == "TECHNICAL_LEAD"
    )


def test_ownership_lead_alignment() -> None:
    result = classify_alignment(
        technical_score=50.0,
        ownership_score=60.0,
        ownership_stale_flag=False,
    )

    assert (
        result
        == "OWNERSHIP_LEAD"
    )


def test_neutral_alignment() -> None:
    result = classify_alignment(
        technical_score=50.0,
        ownership_score=50.0,
        ownership_stale_flag=False,
    )

    assert result == "NEUTRAL"


def test_stale_alignment() -> None:
    result = classify_alignment(
        technical_score=60.0,
        ownership_score=60.0,
        ownership_stale_flag=True,
    )

    assert (
        result
        == "OWNERSHIP_STALE"
    )


def test_build_mode_full_when_empty() -> None:
    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=None,
            existing_latest_sector_count=0,
            existing_expected_sector_count=0,
            existing_ownership_signature=None,
            expected_ownership_signature=None,
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=False,
        )
    )

    assert mode == "FULL"


def test_build_mode_up_to_date() -> None:
    latest = date(
        2026,
        8,
        6,
    )

    signature = (
        "IDXENERGY:2026-07-31"
    )

    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=latest,
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            existing_ownership_signature=(
                signature
            ),
            expected_ownership_signature=(
                signature
            ),
            latest_input_date=latest,
            force=False,
        )
    )

    assert mode == "UP_TO_DATE"


def test_build_mode_incremental() -> None:
    signature = (
        "IDXENERGY:2026-06-30"
    )

    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=date(
                2026,
                7,
                31,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            existing_ownership_signature=(
                signature
            ),
            expected_ownership_signature=(
                signature
            ),
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=False,
        )
    )

    assert mode == "INCREMENTAL"


def test_incomplete_state_forces_full() -> None:
    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=date(
                2026,
                8,
                6,
            ),
            existing_latest_sector_count=10,
            existing_expected_sector_count=11,
            existing_ownership_signature=(
                "a"
            ),
            expected_ownership_signature=(
                "a"
            ),
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=False,
        )
    )

    assert mode == "FULL"


def test_signature_change_forces_full() -> None:
    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=date(
                2026,
                8,
                6,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            existing_ownership_signature=(
                "IDXENERGY:2026-06-30"
            ),
            expected_ownership_signature=(
                "IDXENERGY:2026-07-31"
            ),
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=False,
        )
    )

    assert mode == "FULL"


def test_force_full() -> None:
    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=date(
                2026,
                8,
                6,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            existing_ownership_signature="a",
            expected_ownership_signature="a",
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=True,
        )
    )

    assert mode == "FULL"


def test_stored_data_ahead_rejected() -> None:
    with pytest.raises(
        RuntimeError
    ):
        resolve_integrated_sector_build_mode(
            existing_last_date=date(
                2026,
                8,
                7,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            existing_ownership_signature="a",
            expected_ownership_signature="a",
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=False,
        )


def test_prepare_integrated_row() -> None:
    inputs = [
        {
            "trading_date":
                date(
                    2026,
                    8,
                    6,
                ),
            "sector_code":
                "IDXENERGY",
            "technical_score":
                60.0,
            "technical_rotation_label":
                "LEADING",
            "ownership_as_of_date":
                date(
                    2026,
                    7,
                    31,
                ),
            "ownership_score":
                60.0,
            "ownership_signal_label":
                "ACCUMULATION",
            "ownership_low_coverage_flag":
                False,
        }
    ]

    rows = (
        prepare_integrated_sector_rows(
            inputs=inputs,
            technical_model_version=(
                "sector_rotation_v1_"
                "current_20260808_"
                "yahoo_eod"
            ),
            ownership_model_version=(
                "sector_ownership_v1_"
                "current_20260808_"
                "ksei_official"
            ),
            model_version=(
                "integrated_sector_v1_"
                "current_20260808"
            ),
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["sector_code"]
        == "IDXENERGY"
    )

    assert (
        rows[0]["integrated_score"]
        == 60.0
    )

    assert (
        rows[0]["alignment_label"]
        == "CONFIRMED_BULLISH"
    )