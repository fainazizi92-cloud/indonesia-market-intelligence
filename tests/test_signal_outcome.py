from datetime import (
    UTC,
    date,
    datetime,
)
from uuid import UUID

import pytest

from imi.features.signal_outcome import (
    build_signal_outcome_model_version,
    determine_fill_price,
    evaluate_signal_outcome,
    prepare_signal_outcome_rows,
    resolve_signal_outcome_build_mode,
)

SIGNAL_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def bar(
    day: int,
    *,
    open_: float = 100.0,
    high: float = 102.0,
    low: float = 98.0,
    close: float = 101.0,
):
    return {
        "trading_date":
            date(
                2026,
                7,
                day,
            ),
        "open":
            open_,
        "high":
            high,
        "low":
            low,
        "close":
            close,
        "ingested_at":
            datetime(
                2026,
                8,
                8,
                tzinfo=UTC,
            ),
    }


def test_model_version():
    assert (
        build_signal_outcome_model_version(
            date(
                2026,
                8,
                8,
            )
        )
        == (
            "signal_outcome_v1_"
            "current_20260808_"
            "yahoo_eod"
        )
    )


def test_fill_open_in_zone():
    price, method = (
        determine_fill_price(
            bar_open=100,
            bar_high=103,
            bar_low=98,
            entry_low=99,
            entry_high=101,
        )
    )

    assert price == 100
    assert method == "OPEN_IN_ZONE"


def test_fill_pullback_from_above():
    price, method = (
        determine_fill_price(
            bar_open=105,
            bar_high=106,
            bar_low=100,
            entry_low=99,
            entry_high=101,
        )
    )

    assert price == 101
    assert method == "PULLBACK_TOUCH"


def test_fill_recovery_from_below():
    price, method = (
        determine_fill_price(
            bar_open=97,
            bar_high=100,
            bar_low=96,
            entry_low=99,
            entry_high=101,
        )
    )

    assert price == 99
    assert method == "RECOVERY_TOUCH"


def test_no_fill_intersection():
    price, method = (
        determine_fill_price(
            bar_open=105,
            bar_high=106,
            bar_low=104,
            entry_low=99,
            entry_high=101,
        )
    )

    assert price is None
    assert method is None


def test_pending_when_less_than_five_bars():
    bars = [
        bar(
            1,
            open_=110,
            high=112,
            low=108,
            close=109,
        ),
        bar(
            2,
            open_=109,
            high=111,
            low=107,
            close=108,
        ),
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert (
        result.outcome_label
        == "PENDING"
    )

    assert not result.entry_filled
    assert not result.horizon_complete


def test_no_fill_after_entry_window():
    bars = [
        bar(
            day,
            open_=110,
            high=112,
            low=108,
            close=109,
        )
        for day in range(
            1,
            6,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert (
        result.outcome_label
        == "NO_FILL"
    )

    assert result.horizon_complete


def test_cancelled_before_entry():
    bars = [
        bar(
            1,
            open_=110,
            high=112,
            low=94,
            close=96,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    # Range intersects the entry zone,
    # therefore conservative evaluation
    # assumes entry first. It is a STOP,
    # not pre-entry cancellation.
    assert (
        result.outcome_label
        == "STOP"
    )


def test_true_pre_entry_cancel():
    bars = [
        bar(
            1,
            open_=94,
            high=98,
            low=90,
            close=92,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert (
        result.outcome_label
        == "CANCELLED"
    )


def test_target_hit():
    bars = [
        bar(
            1,
            open_=100,
            high=111,
            low=98,
            close=109,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.outcome_label == "TARGET"
    assert result.target_hit
    assert not result.stop_hit
    assert result.realized_r is not None
    assert result.realized_r > 0


def test_stop_hit():
    bars = [
        bar(
            1,
            open_=100,
            high=103,
            low=94,
            close=95,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.outcome_label == "STOP"
    assert result.stop_hit
    assert not result.target_hit
    assert result.realized_r == -1.0


def test_both_target_stop_uses_stop_first():
    bars = [
        bar(
            1,
            open_=100,
            high=112,
            low=94,
            close=105,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.outcome_label == "STOP"

    assert (
        result.sequence_ambiguous
        is True
    )


def test_open_when_horizon_incomplete():
    bars = [
        bar(
            day,
            high=104,
            low=98,
            close=102,
        )
        for day in range(
            1,
            5,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.outcome_label == "OPEN"
    assert not result.horizon_complete


def test_expired_after_ten_bars():
    bars = [
        bar(
            day,
            high=104,
            low=98,
            close=102,
        )
        for day in range(
            1,
            12,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.outcome_label == "EXPIRED"
    assert result.horizon_complete
    assert result.exit_date is not None
    assert result.realized_return is not None


def test_return_t1():
    bars = [
        bar(
            1,
            open_=100,
            high=104,
            low=98,
            close=100,
        ),
        bar(
            2,
            open_=101,
            high=105,
            low=99,
            close=102,
        ),
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.return_t1 == 0.02


def test_mfe_mae_exist_after_fill():
    bars = [
        bar(
            1,
            open_=100,
            high=104,
            low=97,
            close=101,
        )
    ]

    result = evaluate_signal_outcome(
        entry_low=99,
        entry_high=101,
        stop_price=95,
        target_primary=110,
        horizon_days=10,
        bars=bars,
    )

    assert result.mfe == 0.04
    assert result.mae == -0.03
    assert result.mfe_r is not None
    assert result.mae_r is not None


def test_invalid_entry_zone_rejected():
    with pytest.raises(
        ValueError
    ):
        evaluate_signal_outcome(
            entry_low=101,
            entry_high=99,
            stop_price=95,
            target_primary=110,
            horizon_days=10,
            bars=[],
        )


def test_invalid_stop_rejected():
    with pytest.raises(
        ValueError
    ):
        evaluate_signal_outcome(
            entry_low=99,
            entry_high=101,
            stop_price=100,
            target_primary=110,
            horizon_days=10,
            bars=[],
        )


def test_invalid_target_rejected():
    with pytest.raises(
        ValueError
    ):
        evaluate_signal_outcome(
            entry_low=99,
            entry_high=101,
            stop_price=95,
            target_primary=100,
            horizon_days=10,
            bars=[],
        )


def test_prepare_row_keeps_intraday_times_null():
    item = {
        "signal_id":
            SIGNAL_ID,

        "instrument_id":
            SIGNAL_ID,

        "symbol":
            "TEST",

        "sector_code":
            "IDXENERGY",

        "trading_date":
            date(
                2026,
                7,
                1,
            ),

        "entry_low":
            99.0,

        "entry_high":
            101.0,

        "stop_price":
            95.0,

        "target_primary":
            110.0,

        "horizon_days":
            10,

        "issued_at":
            datetime(
                2026,
                7,
                1,
                tzinfo=UTC,
            ),

        "signal_input_updated_at":
            datetime(
                2026,
                7,
                1,
                tzinfo=UTC,
            ),

        "signal_model_version":
            "trade_setup_test",

        "bars": [
            bar(
                2,
                open_=100,
                high=111,
                low=98,
                close=109,
            )
        ],
    }

    row = (
        prepare_signal_outcome_rows(
            inputs=[item],
            evaluation_model_version=(
                "outcome_test"
            ),
        )[0]
    )

    assert row[
        "target_hit_at"
    ] is None

    assert row[
        "stop_hit_at"
    ] is None

    assert row[
        "time_to_target_hours"
    ] is None


def test_prepare_row_has_evidence():
    item = {
        "signal_id":
            SIGNAL_ID,
        "instrument_id":
            SIGNAL_ID,
        "symbol":
            "TEST",
        "sector_code":
            "IDXENERGY",
        "trading_date":
            date(
                2026,
                7,
                1,
            ),
        "entry_low":
            99.0,
        "entry_high":
            101.0,
        "stop_price":
            95.0,
        "target_primary":
            110.0,
        "horizon_days":
            10,
        "issued_at":
            datetime(
                2026,
                7,
                1,
                tzinfo=UTC,
            ),
        "signal_input_updated_at":
            datetime(
                2026,
                7,
                1,
                tzinfo=UTC,
            ),
        "signal_model_version":
            "trade_setup_test",
        "bars": [],
    }

    row = (
        prepare_signal_outcome_rows(
            inputs=[item],
            evaluation_model_version=(
                "outcome_test"
            ),
        )[0]
    )

    assert (
        row[
            "evaluation_model_version"
        ]
        == "outcome_test"
    )

    assert (
        row["evidence"]["scope"]
        == "signal_outcome_v1"
    )


def test_build_mode_full_without_state():
    mode = (
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=False,
            input_model_matches=False,
            stored_rows=0,
            expected_rows=10,
            processed_through=None,
            latest_price_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=None,
            current_input_updated_at=None,
        )
    )

    assert mode == "FULL"


def test_build_mode_force_full():
    mode = (
        resolve_signal_outcome_build_mode(
            force=True,
            state_exists=True,
            input_model_matches=True,
            stored_rows=10,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                6,
            ),
            latest_price_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=1,
            current_input_updated_at=1,
        )
    )

    assert mode == "FULL"


def test_build_mode_up_to_date():
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            stored_rows=10,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                6,
            ),
            latest_price_date=date(
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
    )

    assert mode == "UP_TO_DATE"


def test_new_price_requires_refresh():
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            stored_rows=10,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                5,
            ),
            latest_price_date=date(
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
    )

    assert mode == "REFRESH"


def test_input_change_requires_refresh():
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

    mode = (
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            stored_rows=10,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                6,
            ),
            latest_price_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=old,
            current_input_updated_at=new,
        )
    )

    assert mode == "REFRESH"


def test_count_mismatch_forces_full():
    mode = (
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            stored_rows=9,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                6,
            ),
            latest_price_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=1,
            current_input_updated_at=1,
        )
    )

    assert mode == "FULL"


def test_wrong_input_model_forces_full():
    mode = (
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=False,
            stored_rows=10,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                6,
            ),
            latest_price_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=1,
            current_input_updated_at=1,
        )
    )

    assert mode == "FULL"


def test_state_ahead_rejected():
    with pytest.raises(
        RuntimeError
    ):
        resolve_signal_outcome_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            stored_rows=10,
            expected_rows=10,
            processed_through=date(
                2026,
                8,
                7,
            ),
            latest_price_date=date(
                2026,
                8,
                6,
            ),
            stored_input_updated_at=1,
            current_input_updated_at=1,
        )