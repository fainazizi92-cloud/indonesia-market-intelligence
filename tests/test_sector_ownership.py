from datetime import date
from uuid import UUID

import pytest

from imi.features.sector_ownership import (
    build_sector_ownership_model_version,
    calculate_coverage_pct,
    calculate_ownership_breadth_score,
    calculate_ownership_intensity_score,
    calculate_sector_ownership_score,
    classify_sector_ownership_signal,
    prepare_sector_ownership_rows,
    resolve_sector_ownership_build_mode,
)

SOURCE_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def test_model_version() -> None:
    result = (
        build_sector_ownership_model_version(
            date(
                2026,
                8,
                8,
            )
        )
    )

    assert result == (
        "sector_ownership_v1_"
        "current_20260808_"
        "ksei_official"
    )


def test_coverage_pct() -> None:
    result = calculate_coverage_pct(
        eligible_count=95,
        current_universe_count=100,
    )

    assert result == 95.0


def test_zero_clean_breadth_is_neutral() -> None:
    result = (
        calculate_ownership_breadth_score(
            clean_count=0,
            accumulating_count=0,
            distributing_count=0,
        )
    )

    assert result == 50.0


def test_positive_breadth() -> None:
    result = (
        calculate_ownership_breadth_score(
            clean_count=100,
            accumulating_count=60,
            distributing_count=20,
        )
    )

    assert result == 70.0


def test_neutral_intensity() -> None:
    result = (
        calculate_ownership_intensity_score(
            avg_clean_clipped_delta_pp=0.0
        )
    )

    assert result == 50.0


def test_high_intensity_is_capped() -> None:
    result = (
        calculate_ownership_intensity_score(
            avg_clean_clipped_delta_pp=2.0
        )
    )

    assert result == 100.0


def test_composite_score() -> None:
    result = (
        calculate_sector_ownership_score(
            breadth_score=70.0,
            intensity_score=60.0,
            coverage_pct=100.0,
        )
    )

    assert result == 66.5


def test_low_coverage_penalty() -> None:
    result = (
        calculate_sector_ownership_score(
            breadth_score=70.0,
            intensity_score=60.0,
            coverage_pct=70.0,
        )
    )

    assert result == 58.25


def test_strong_accumulation_label() -> None:
    assert (
        classify_sector_ownership_signal(
            70.0
        )
        == "STRONG_ACCUMULATION"
    )


def test_accumulation_label() -> None:
    assert (
        classify_sector_ownership_signal(
            60.0
        )
        == "ACCUMULATION"
    )


def test_neutral_label() -> None:
    assert (
        classify_sector_ownership_signal(
            50.0
        )
        == "NEUTRAL"
    )


def test_distribution_label() -> None:
    assert (
        classify_sector_ownership_signal(
            40.0
        )
        == "DISTRIBUTION"
    )


def test_strong_distribution_label() -> None:
    assert (
        classify_sector_ownership_signal(
            30.0
        )
        == "STRONG_DISTRIBUTION"
    )


def test_prepare_sector_row() -> None:
    inputs = [
        {
            "as_of_date":
                date(
                    2026,
                    7,
                    31,
                ),
            "sector_code":
                "IDXENERGY",
            "eligible_count":
                90,
            "current_universe_count":
                91,
            "clean_count":
                80,
            "accumulating_count":
                45,
            "stable_count":
                25,
            "distributing_count":
                10,
            "corporate_action_risk_count":
                8,
            "snapshot_gap_count":
                2,
            "extreme_move_count":
                3,
            "avg_delta_foreign_ownership_pp":
                0.40,
            "avg_clean_clipped_delta_pp":
                0.10,
        }
    ]

    rows = (
        prepare_sector_ownership_rows(
            inputs=inputs,
            source_id=SOURCE_ID,
            input_model_version=(
                "ownership_trend_test"
            ),
            model_version=(
                "sector_ownership_test"
            ),
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["sector_code"]
        == "IDXENERGY"
    )

    assert (
        rows[0][
            "accumulating_count"
        ]
        == 45
    )

    assert (
        0.0
        <= rows[0]["score"]
        <= 100.0
    )


def test_prepare_zero_clean_population() -> None:
    inputs = [
        {
            "as_of_date":
                date(
                    2026,
                    7,
                    31,
                ),
            "sector_code":
                "IDXENERGY",
            "eligible_count":
                10,
            "current_universe_count":
                10,
            "clean_count":
                0,
            "accumulating_count":
                0,
            "stable_count":
                0,
            "distributing_count":
                0,
            "corporate_action_risk_count":
                10,
            "snapshot_gap_count":
                0,
            "extreme_move_count":
                2,
            "avg_delta_foreign_ownership_pp":
                3.0,
            "avg_clean_clipped_delta_pp":
                None,
        }
    ]

    rows = (
        prepare_sector_ownership_rows(
            inputs=inputs,
            source_id=SOURCE_ID,
            input_model_version="input",
            model_version="model",
        )
    )

    assert (
        rows[0]["breadth_score"]
        == 50.0
    )

    assert (
        rows[0]["intensity_score"]
        == 50.0
    )

    assert (
        rows[0]["signal_label"]
        == "NEUTRAL"
    )


def test_build_mode_full_when_empty() -> None:
    mode = (
        resolve_sector_ownership_build_mode(
            existing_last_date=None,
            existing_latest_sector_count=0,
            existing_expected_sector_count=0,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )
    )

    assert mode == "FULL"


def test_build_mode_up_to_date() -> None:
    latest = date(
        2026,
        7,
        31,
    )

    mode = (
        resolve_sector_ownership_build_mode(
            existing_last_date=latest,
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            latest_input_date=latest,
            force=False,
        )
    )

    assert mode == "UP_TO_DATE"


def test_build_mode_incremental() -> None:
    mode = (
        resolve_sector_ownership_build_mode(
            existing_last_date=date(
                2026,
                6,
                30,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )
    )

    assert mode == "INCREMENTAL"


def test_incomplete_state_forces_full() -> None:
    mode = (
        resolve_sector_ownership_build_mode(
            existing_last_date=date(
                2026,
                7,
                31,
            ),
            existing_latest_sector_count=10,
            existing_expected_sector_count=11,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )
    )

    assert mode == "FULL"


def test_force_full() -> None:
    mode = (
        resolve_sector_ownership_build_mode(
            existing_last_date=date(
                2026,
                7,
                31,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=True,
        )
    )

    assert mode == "FULL"


def test_stored_data_ahead_rejected() -> None:
    with pytest.raises(
        RuntimeError
    ):
        resolve_sector_ownership_build_mode(
            existing_last_date=date(
                2026,
                8,
                31,
            ),
            existing_latest_sector_count=11,
            existing_expected_sector_count=11,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )