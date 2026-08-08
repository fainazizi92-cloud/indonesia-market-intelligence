from datetime import (
    UTC,
    date,
    datetime,
    timedelta,
)
from uuid import UUID

import pytest

from imi.features.backtest_calibration import (
    build_backtest_calibration_version,
    classify_sample_status,
    compute_backtest_summary,
    prepare_backtest_calibration_rows,
    resolve_backtest_build_mode,
    score_bucket,
)

SIGNAL_BASE = int(
    "10000000000000000000000000000000",
    16,
)


def signal_id(
    number: int,
) -> UUID:
    return UUID(
        int=(
            SIGNAL_BASE
            + number
        )
    )


def raw_row(
    number: int,
    *,
    signal_date: date,
    outcome_label: str = "TARGET",
    entry_filled: bool = True,
    horizon_complete: bool = True,
    realized_r: float | None = 2.0,
    realized_return: float | None = 0.10,
    target_hit: bool = True,
    stop_hit: bool = False,
    overall_score: float = 70.0,
):
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    if entry_filled:
        entry_date = (
            signal_date
            + timedelta(
                days=1
            )
        )

    else:
        entry_date = None

    if (
        outcome_label
        in {
            "TARGET",
            "STOP",
            "EXPIRED",
        }
    ):
        exit_date = (
            signal_date
            + timedelta(
                days=5
            )
        )

    else:
        exit_date = None

    return {
        "signal_id":
            signal_id(
                number
            ),

        "instrument_id":
            signal_id(
                number
            ),

        "symbol":
            f"T{number}",

        "sector_code":
            "IDXENERGY",

        "signal_date":
            signal_date,

        "outcome_model_version":
            "signal_outcome_test",

        "trade_setup_model_version":
            "trade_setup_test",

        "outcome_label":
            outcome_label,

        "entry_filled":
            entry_filled,

        "horizon_complete":
            horizon_complete,

        "entry_date":
            entry_date,

        "exit_date":
            exit_date,

        "realized_return":
            realized_return,

        "realized_r":
            realized_r,

        "mfe_r":
            (
                2.5
                if entry_filled
                else None
            ),

        "mae_r":
            (
                -0.5
                if entry_filled
                else None
            ),

        "target_hit":
            target_hit,

        "stop_hit":
            stop_hit,

        "setup_expected_rr":
            2.0,

        "setup_risk_pct":
            0.05,

        "horizon_days":
            10,

        "overall_score":
            overall_score,

        "market_score":
            45.0,

        "sector_score":
            60.0,

        "technical_score":
            80.0,

        "liquidity_score":
            90.0,

        "ownership_score":
            70.0,

        "risk_score":
            65.0,

        "data_completeness":
            95.0,

        "input_updated_at":
            timestamp,
    }


def prepared_rows():
    inputs = []

    start = date(
        2026,
        1,
        1,
    )

    for index in range(
        20
    ):
        inputs.append(
            raw_row(
                index,
                signal_date=(
                    start
                    + timedelta(
                        days=index
                    )
                ),
            )
        )

    return (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version=(
                "dataset_test"
            ),
        )
    )


def test_model_version():
    result = (
        build_backtest_calibration_version(
            date(
                2026,
                8,
                8,
            )
        )
    )

    assert result == (
        "backtest_calibration_v1_"
        "current_20260808"
    )


def test_classify_mature_target():
    result = classify_sample_status(
        outcome_label="TARGET",
        entry_filled=True,
        horizon_complete=True,
        realized_r=2.0,
    )

    assert result == "MATURE_TRADE"


def test_classify_mature_expired():
    result = classify_sample_status(
        outcome_label="EXPIRED",
        entry_filled=True,
        horizon_complete=True,
        realized_r=0.25,
    )

    assert result == "MATURE_TRADE"


def test_classify_unfilled_no_fill():
    result = classify_sample_status(
        outcome_label="NO_FILL",
        entry_filled=False,
        horizon_complete=True,
        realized_r=None,
    )

    assert result == "UNFILLED_COMPLETE"


def test_classify_unfilled_cancelled():
    result = classify_sample_status(
        outcome_label="CANCELLED",
        entry_filled=False,
        horizon_complete=True,
        realized_r=None,
    )

    assert result == "UNFILLED_COMPLETE"


def test_classify_unresolved_open():
    result = classify_sample_status(
        outcome_label="OPEN",
        entry_filled=True,
        horizon_complete=False,
        realized_r=None,
    )

    assert result == "UNRESOLVED"


def test_classify_unresolved_pending():
    result = classify_sample_status(
        outcome_label="PENDING",
        entry_filled=False,
        horizon_complete=False,
        realized_r=None,
    )

    assert result == "UNRESOLVED"


def test_terminal_without_realized_r_rejected():
    with pytest.raises(
        ValueError
    ):
        classify_sample_status(
            outcome_label="TARGET",
            entry_filled=True,
            horizon_complete=True,
            realized_r=None,
        )


def test_score_bucket_high():
    assert (
        score_bucket(
            72.0
        )
        == "GE_70"
    )


def test_score_bucket_middle():
    assert (
        score_bucket(
            68.0
        )
        == "67_TO_70"
    )


def test_score_bucket_low_buy_setup():
    assert (
        score_bucket(
            65.5
        )
        == "65_TO_67"
    )


def test_split_has_train_validation_test():
    rows = prepared_rows()

    labels = {
        row[
            "split_label"
        ]
        for row in rows
    }

    assert "TRAIN" in labels
    assert "VALIDATION" in labels
    assert "TEST" in labels


def test_same_signal_date_same_split():
    day = date(
        2026,
        1,
        1,
    )

    inputs = [
        raw_row(
            1,
            signal_date=day,
        ),
        raw_row(
            2,
            signal_date=day,
        ),
        raw_row(
            3,
            signal_date=(
                day
                + timedelta(
                    days=1
                )
            ),
        ),
        raw_row(
            4,
            signal_date=(
                day
                + timedelta(
                    days=2
                )
            ),
        ),
    ]

    rows = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version="test",
        )
    )

    first_day_labels = {
        row[
            "split_label"
        ]
        for row in rows
        if row[
            "signal_date"
        ]
        == day
    }

    assert len(
        first_day_labels
    ) == 1


def test_unfilled_is_excluded():
    item = raw_row(
        1,
        signal_date=date(
            2026,
            1,
            1,
        ),
        outcome_label="NO_FILL",
        entry_filled=False,
        horizon_complete=True,
        realized_r=None,
        realized_return=None,
        target_hit=False,
    )

    row = (
        prepare_backtest_calibration_rows(
            inputs=[item],
            dataset_version="test",
        )[0]
    )

    assert (
        row["split_label"]
        == "EXCLUDED"
    )

    assert (
        row[
            "calibration_eligible"
        ]
        is False
    )


def test_summary_counts():
    rows = prepared_rows()

    summary = (
        compute_backtest_summary(
            rows
        )
    )

    assert summary.total_rows == 20
    assert summary.mature_trades == 20
    assert summary.unfilled_complete == 0
    assert summary.unresolved == 0


def test_summary_fill_rate():
    inputs = [
        raw_row(
            1,
            signal_date=date(
                2026,
                1,
                1,
            ),
        ),
        raw_row(
            2,
            signal_date=date(
                2026,
                1,
                2,
            ),
            outcome_label="NO_FILL",
            entry_filled=False,
            horizon_complete=True,
            realized_r=None,
            realized_return=None,
            target_hit=False,
        ),
    ]

    rows = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version="test",
        )
    )

    summary = (
        compute_backtest_summary(
            rows
        )
    )

    assert summary.fill_rate == 0.5


def test_summary_target_rate():
    inputs = [
        raw_row(
            1,
            signal_date=date(
                2026,
                1,
                1,
            ),
        ),
        raw_row(
            2,
            signal_date=date(
                2026,
                1,
                2,
            ),
            outcome_label="STOP",
            realized_r=-1.0,
            realized_return=-0.05,
            target_hit=False,
            stop_hit=True,
        ),
    ]

    rows = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version="test",
        )
    )

    summary = (
        compute_backtest_summary(
            rows
        )
    )

    assert summary.target_rate == 0.5


def test_summary_win_rate():
    inputs = [
        raw_row(
            1,
            signal_date=date(
                2026,
                1,
                1,
            ),
            realized_r=2.0,
        ),
        raw_row(
            2,
            signal_date=date(
                2026,
                1,
                2,
            ),
            outcome_label="STOP",
            realized_r=-1.0,
            target_hit=False,
            stop_hit=True,
        ),
    ]

    rows = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version="test",
        )
    )

    summary = (
        compute_backtest_summary(
            rows
        )
    )

    assert summary.win_rate == 0.5


def test_summary_average_r():
    inputs = [
        raw_row(
            1,
            signal_date=date(
                2026,
                1,
                1,
            ),
            realized_r=2.0,
        ),
        raw_row(
            2,
            signal_date=date(
                2026,
                1,
                2,
            ),
            outcome_label="STOP",
            realized_r=-1.0,
            target_hit=False,
            stop_hit=True,
        ),
    ]

    rows = (
        prepare_backtest_calibration_rows(
            inputs=inputs,
            dataset_version="test",
        )
    )

    summary = (
        compute_backtest_summary(
            rows
        )
    )

    assert summary.average_r == 0.5


def test_calibration_not_ready_small_sample():
    summary = (
        compute_backtest_summary(
            prepared_rows()
        )
    )

    assert (
        summary.calibration_ready
        is False
    )

    assert (
        "MATURE_TRADES_BELOW_200"
        in summary.readiness_reasons
    )


def test_calibration_point_in_time_gate():
    summary = (
        compute_backtest_summary(
            prepared_rows()
        )
    )

    assert (
        "STRICT_POINT_IN_TIME_"
        "DATA_NOT_READY"
        in summary.readiness_reasons
    )


def test_prepare_target_label_true():
    item = raw_row(
        1,
        signal_date=date(
            2026,
            1,
            1,
        ),
    )

    row = (
        prepare_backtest_calibration_rows(
            inputs=[item],
            dataset_version="test",
        )[0]
    )

    assert (
        row[
            "tp_before_sl_label"
        ]
        is True
    )

    assert (
        row[
            "positive_r_label"
        ]
        is True
    )


def test_prepare_expired_target_label_false():
    item = raw_row(
        1,
        signal_date=date(
            2026,
            1,
            1,
        ),
        outcome_label="EXPIRED",
        realized_r=0.25,
        target_hit=False,
        stop_hit=False,
    )

    row = (
        prepare_backtest_calibration_rows(
            inputs=[item],
            dataset_version="test",
        )[0]
    )

    assert (
        row[
            "tp_before_sl_label"
        ]
        is False
    )

    assert (
        row[
            "positive_r_label"
        ]
        is True
    )


def test_build_mode_full_without_state():
    result = resolve_backtest_build_mode(
        force=False,
        state_exists=False,
        input_model_matches=False,
        stored_rows=0,
        expected_rows=65,
        processed_through=None,
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        stored_input_updated_at=None,
        current_input_updated_at=None,
    )

    assert result == "FULL"


def test_build_mode_up_to_date():
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    result = resolve_backtest_build_mode(
        force=False,
        state_exists=True,
        input_model_matches=True,
        stored_rows=65,
        expected_rows=65,
        processed_through=date(
            2026,
            8,
            6,
        ),
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        stored_input_updated_at=(
            timestamp
        ),
        current_input_updated_at=(
            timestamp
        ),
    )

    assert result == "UP_TO_DATE"


def test_build_mode_refresh_on_change():
    old = datetime(
        2026,
        8,
        8,
        1,
        tzinfo=UTC,
    )

    new = datetime(
        2026,
        8,
        8,
        2,
        tzinfo=UTC,
    )

    result = resolve_backtest_build_mode(
        force=False,
        state_exists=True,
        input_model_matches=True,
        stored_rows=65,
        expected_rows=65,
        processed_through=date(
            2026,
            8,
            6,
        ),
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        stored_input_updated_at=old,
        current_input_updated_at=new,
    )

    assert result == "REFRESH"


def test_count_mismatch_forces_full():
    result = resolve_backtest_build_mode(
        force=False,
        state_exists=True,
        input_model_matches=True,
        stored_rows=64,
        expected_rows=65,
        processed_through=date(
            2026,
            8,
            6,
        ),
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        stored_input_updated_at=1,
        current_input_updated_at=1,
    )

    assert result == "FULL"


def test_wrong_input_model_forces_full():
    result = resolve_backtest_build_mode(
        force=False,
        state_exists=True,
        input_model_matches=False,
        stored_rows=65,
        expected_rows=65,
        processed_through=date(
            2026,
            8,
            6,
        ),
        latest_input_date=date(
            2026,
            8,
            6,
        ),
        stored_input_updated_at=1,
        current_input_updated_at=1,
    )

    assert result == "FULL"


def test_state_ahead_rejected():
    with pytest.raises(
        RuntimeError
    ):
        resolve_backtest_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            stored_rows=65,
            expected_rows=65,
            processed_through=date(
                2026,
                8,
                7,
            ),
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=1,
            current_input_updated_at=1,
        )