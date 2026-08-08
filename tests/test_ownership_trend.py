from datetime import date
from uuid import UUID

import pytest

from imi.features.ownership_trend import (
    OWNERSHIP_TREND_MODEL_VERSION,
    calculate_ownership_trend,
    calculate_signal_strength,
    classify_ownership_trend,
    prepare_ownership_trend_rows,
    resolve_ownership_trend_build_mode,
)

SOURCE_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def make_metrics(
    *,
    current_pct: float = 10.30,
    previous_pct: float = 10.00,
    current_shares: int = 1030,
    previous_shares: int = 1000,
    current_secnum: int = 10000,
    previous_secnum: int = 10000,
    current_date: date = date(
        2026,
        7,
        31,
    ),
    previous_date: date = date(
        2026,
        6,
        30,
    ),
):
    return calculate_ownership_trend(
        as_of_date=current_date,
        previous_as_of_date=(
            previous_date
        ),
        foreign_ownership_pct=(
            current_pct
        ),
        previous_foreign_ownership_pct=(
            previous_pct
        ),
        foreign_shares=current_shares,
        previous_foreign_shares=(
            previous_shares
        ),
        security_number=current_secnum,
        previous_security_number=(
            previous_secnum
        ),
    )


def test_model_version() -> None:
    assert (
        OWNERSHIP_TREND_MODEL_VERSION
        == "ownership_trend_v1_ksei_official"
    )


def test_accumulating_label() -> None:
    assert (
        classify_ownership_trend(
            0.15
        )
        == "ACCUMULATING"
    )


def test_distributing_label() -> None:
    assert (
        classify_ownership_trend(
            -0.15
        )
        == "DISTRIBUTING"
    )


def test_stable_label() -> None:
    assert (
        classify_ownership_trend(
            0.05
        )
        == "STABLE"
    )


def test_corporate_action_risk() -> None:
    metrics = make_metrics(
        current_secnum=10200,
        previous_secnum=10000,
    )

    assert (
        metrics.corporate_action_risk
        is True
    )


def test_no_corporate_action_risk() -> None:
    metrics = make_metrics(
        current_secnum=10050,
        previous_secnum=10000,
    )

    assert (
        metrics.corporate_action_risk
        is False
    )


def test_snapshot_gap_flag() -> None:
    metrics = make_metrics(
        current_date=date(
            2026,
            7,
            31,
        ),
        previous_date=date(
            2026,
            5,
            29,
        ),
    )

    assert (
        metrics.snapshot_gap_flag
        is True
    )


def test_normalized_foreign_share_change() -> None:
    metrics = make_metrics(
        current_shares=1100,
        previous_shares=1000,
        current_secnum=10000,
        previous_secnum=10000,
    )

    assert (
        metrics
        .normalized_foreign_share_change_pct
        == 1.0
    )


def test_signal_strength_is_bounded() -> None:
    strength = (
        calculate_signal_strength(
            delta_foreign_ownership_pp=(
                50.0
            ),
            corporate_action_risk=False,
            snapshot_gap_flag=False,
        )
    )

    assert strength == 100.0


def test_signal_strength_penalized_by_risk() -> None:
    normal = (
        calculate_signal_strength(
            delta_foreign_ownership_pp=(
                0.50
            ),
            corporate_action_risk=False,
            snapshot_gap_flag=False,
        )
    )

    risky = (
        calculate_signal_strength(
            delta_foreign_ownership_pp=(
                0.50
            ),
            corporate_action_risk=True,
            snapshot_gap_flag=False,
        )
    )

    assert risky < normal


def test_prepare_row() -> None:
    inputs = [
        {
            "instrument_id":
                UUID(
                    "00000000-0000-0000-0000-000000000002"
                ),
            "as_of_date":
                date(
                    2026,
                    7,
                    31,
                ),
            "previous_as_of_date":
                date(
                    2026,
                    6,
                    30,
                ),
            "foreign_ownership_pct":
                10.30,
            "previous_foreign_ownership_pct":
                10.00,
            "foreign_shares":
                1030,
            "previous_foreign_shares":
                1000,
            "security_number":
                10000,
            "previous_security_number":
                10000,
        }
    ]

    rows = (
        prepare_ownership_trend_rows(
            inputs=inputs,
            source_id=SOURCE_ID,
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["trend_label"]
        == "ACCUMULATING"
    )

    assert (
        rows[0][
            "delta_foreign_ownership_pp"
        ]
        == 0.30
    )


def test_build_mode_full_when_empty() -> None:
    mode = (
        resolve_ownership_trend_build_mode(
            existing_last_date=None,
            existing_latest_count=0,
            existing_expected_count=0,
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
        resolve_ownership_trend_build_mode(
            existing_last_date=latest,
            existing_latest_count=956,
            existing_expected_count=956,
            latest_input_date=latest,
            force=False,
        )
    )

    assert mode == "UP_TO_DATE"


def test_build_mode_incremental() -> None:
    mode = (
        resolve_ownership_trend_build_mode(
            existing_last_date=date(
                2026,
                6,
                30,
            ),
            existing_latest_count=956,
            existing_expected_count=956,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )
    )

    assert mode == "INCREMENTAL"


def test_force_build_mode_full() -> None:
    mode = (
        resolve_ownership_trend_build_mode(
            existing_last_date=date(
                2026,
                7,
                31,
            ),
            existing_latest_count=956,
            existing_expected_count=956,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=True,
        )
    )

    assert mode == "FULL"


def test_incomplete_stored_state_forces_full() -> None:
    mode = (
        resolve_ownership_trend_build_mode(
            existing_last_date=date(
                2026,
                7,
                31,
            ),
            existing_latest_count=955,
            existing_expected_count=956,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )
    )

    assert mode == "FULL"


def test_stored_data_ahead_is_rejected() -> None:
    with pytest.raises(
        RuntimeError
    ):
        resolve_ownership_trend_build_mode(
            existing_last_date=date(
                2026,
                8,
                31,
            ),
            existing_latest_count=956,
            existing_expected_count=956,
            latest_input_date=date(
                2026,
                7,
                31,
            ),
            force=False,
        )