from datetime import (
    UTC,
    date,
    datetime,
)
from uuid import UUID

import pytest

from imi.features.execution_realism import (
    IDX_BUY_INFRASTRUCTURE_FEE_RATE,
    IDX_SELL_INFRASTRUCTURE_FEE_RATE,
    apply_buy_slippage,
    apply_sell_execution,
    build_execution_realism_model_version,
    calculate_execution_result,
    compute_execution_summary,
    exit_slippage_ticks_for_outcome,
    idx_price_fraction,
    prepare_execution_realism_rows,
    resolve_execution_build_mode,
    round_to_tick,
)

SIGNAL_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def input_row(
    *,
    sample_status="MATURE_TRADE",
    outcome_label="TARGET",
    raw_entry_price=1000.0,
    raw_exit_price=1100.0,
    raw_stop_price=950.0,
    entry_reference_price=1000.0,
    exit_reference_price=1080.0,
    raw_realized_r=2.0,
):
    return {
        "signal_id":
            SIGNAL_ID,

        "calibration_dataset_version":
            "backtest_test",

        "outcome_model_version":
            "outcome_test",

        "trade_setup_model_version":
            "trade_test",

        "instrument_id":
            SIGNAL_ID,

        "signal_date":
            date(
                2026,
                7,
                1,
            ),

        "sector_code":
            "IDXENERGY",

        "sample_status":
            sample_status,

        "split_label":
            (
                "TRAIN"
                if sample_status
                == "MATURE_TRADE"
                else "EXCLUDED"
            ),

        "calibration_eligible":
            (
                sample_status
                == "MATURE_TRADE"
            ),

        "outcome_label":
            outcome_label,

        "raw_realized_return":
            (
                0.10
                if raw_realized_r
                is not None
                else None
            ),

        "raw_realized_r":
            raw_realized_r,

        "raw_entry_price":
            raw_entry_price,

        "raw_exit_price":
            raw_exit_price,

        "raw_stop_price":
            raw_stop_price,

        "entry_reference_price":
            entry_reference_price,

        "exit_reference_price":
            exit_reference_price,

        "calibration_evidence": {
            "warnings": [
                (
                    "CURRENT_UNIVERSE_HISTORY_"
                    "IS_SURVIVORSHIP_BIASED"
                ),
                (
                    "HISTORICAL_KSEI_AS_OF_DATE_"
                    "IS_NOT_PUBLICATION_TIME_SAFE"
                ),
            ]
        },

        "corporate_action_overlap_detected":
            False,

        "input_updated_at":
            datetime(
                2026,
                8,
                8,
                tzinfo=UTC,
            ),
    }


def test_model_version():
    assert (
        build_execution_realism_model_version(
            date(
                2026,
                8,
                8,
            )
        )
        == (
            "execution_realism_v1_"
            "current_20260808_idx_eod"
        )
    )


def test_fraction_below_200():
    assert (
        idx_price_fraction(
            199
        )
        == 1
    )


def test_fraction_at_200():
    assert (
        idx_price_fraction(
            200
        )
        == 2
    )


def test_fraction_at_500():
    assert (
        idx_price_fraction(
            500
        )
        == 5
    )


def test_fraction_at_2000():
    assert (
        idx_price_fraction(
            2000
        )
        == 10
    )


def test_fraction_at_5000():
    assert (
        idx_price_fraction(
            5000
        )
        == 25
    )


def test_invalid_reference_price():
    with pytest.raises(
        ValueError
    ):
        idx_price_fraction(
            0
        )


def test_round_up_to_tick():
    assert (
        round_to_tick(
            price=503,
            tick_size=5,
            direction="UP",
        )
        == 505
    )


def test_round_down_to_tick():
    assert (
        round_to_tick(
            price=503,
            tick_size=5,
            direction="DOWN",
        )
        == 500
    )


def test_buy_execution_adds_one_tick():
    price, tick = (
        apply_buy_slippage(
            raw_price=1001,
            reference_price=1000,
        )
    )

    assert tick == 5
    assert price == 1010


def test_sell_execution_one_tick():
    price, tick = (
        apply_sell_execution(
            raw_price=1003,
            reference_price=1000,
            slippage_ticks=1,
        )
    )

    assert tick == 5
    assert price == 995


def test_target_has_zero_exit_slippage():
    assert (
        exit_slippage_ticks_for_outcome(
            "TARGET"
        )
        == 0
    )


def test_stop_has_one_exit_slippage():
    assert (
        exit_slippage_ticks_for_outcome(
            "STOP"
        )
        == 1
    )


def test_expired_has_one_exit_slippage():
    assert (
        exit_slippage_ticks_for_outcome(
            "EXPIRED"
        )
        == 1
    )


def test_target_execution_result():
    result = (
        calculate_execution_result(
            raw_entry_price=1000,
            raw_exit_price=1100,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1080,
            raw_realized_r=2.0,
            outcome_label="TARGET",
        )
    )

    assert (
        result.modeled_entry_price
        == 1005
    )

    assert (
        result.modeled_exit_price
        == 1100
    )

    assert (
        result.net_realized_r
        < result.gross_modeled_r
    )


def test_stop_execution_result():
    result = (
        calculate_execution_result(
            raw_entry_price=1000,
            raw_exit_price=950,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=960,
            raw_realized_r=-1.0,
            outcome_label="STOP",
        )
    )

    assert (
        result.modeled_exit_price
        == 945
    )

    assert (
        result.net_realized_r
        < 0
    )


def test_expired_execution_result():
    result = (
        calculate_execution_result(
            raw_entry_price=1000,
            raw_exit_price=1020,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1010,
            raw_realized_r=0.4,
            outcome_label="EXPIRED",
        )
    )

    assert (
        result.exit_slippage_ticks
        == 1
    )


def test_exchange_fee_constants():
    assert (
        IDX_BUY_INFRASTRUCTURE_FEE_RATE
        == 0.000433
    )

    assert (
        IDX_SELL_INFRASTRUCTURE_FEE_RATE
        == 0.001433
    )


def test_prepare_mature_execution():
    row = (
        prepare_execution_realism_rows(
            inputs=[
                input_row()
            ],
            model_version=(
                "execution_test"
            ),
        )[0]
    )

    assert (
        row[
            "execution_metrics_available"
        ]
        is True
    )

    assert (
        row[
            "net_realized_r"
        ]
        is not None
    )


def test_prepare_unfilled_has_no_execution():
    item = input_row(
        sample_status=(
            "UNFILLED_COMPLETE"
        ),
        outcome_label="NO_FILL",
        raw_entry_price=None,
        raw_exit_price=None,
        raw_stop_price=950,
        entry_reference_price=None,
        exit_reference_price=None,
        raw_realized_r=None,
    )

    row = (
        prepare_execution_realism_rows(
            inputs=[item],
            model_version="test",
        )[0]
    )

    assert (
        row[
            "execution_metrics_available"
        ]
        is False
    )


def test_point_in_time_is_blocked():
    row = (
        prepare_execution_realism_rows(
            inputs=[
                input_row()
            ],
            model_version="test",
        )[0]
    )

    assert (
        row[
            "point_in_time_safe"
        ]
        is False
    )

    assert (
        "POINT_IN_TIME_KSEI_NOT_SAFE"
        in row[
            "blocking_reasons"
        ]
    )


def test_survivorship_is_blocked():
    row = (
        prepare_execution_realism_rows(
            inputs=[
                input_row()
            ],
            model_version="test",
        )[0]
    )

    assert (
        row[
            "survivorship_safe"
        ]
        is False
    )


def test_strict_calibration_stays_false():
    row = (
        prepare_execution_realism_rows(
            inputs=[
                input_row()
            ],
            model_version="test",
        )[0]
    )

    assert (
        row[
            "strict_calibration_eligible"
        ]
        is False
    )


def test_corporate_action_overlap_blocker():
    item = input_row()

    item[
        "corporate_action_overlap_detected"
    ] = True

    row = (
        prepare_execution_realism_rows(
            inputs=[item],
            model_version="test",
        )[0]
    )

    assert (
        "CORPORATE_ACTION_OVERLAP_DETECTED"
        in row[
            "blocking_reasons"
        ]
    )


def test_summary_counts():
    rows = (
        prepare_execution_realism_rows(
            inputs=[
                input_row()
            ],
            model_version="test",
        )
    )

    summary = (
        compute_execution_summary(
            rows
        )
    )

    assert summary.total_rows == 1
    assert summary.mature_trades == 1

    assert (
        summary.execution_metrics_available
        == 1
    )


def test_summary_net_is_below_gross():
    rows = (
        prepare_execution_realism_rows(
            inputs=[
                input_row()
            ],
            model_version="test",
        )
    )

    summary = (
        compute_execution_summary(
            rows
        )
    )

    assert (
        summary.net_average_r
        < summary.gross_average_r
    )


def test_build_mode_full_without_state():
    result = (
        resolve_execution_build_mode(
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
    )

    assert result == "FULL"


def test_build_mode_up_to_date():
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    result = (
        resolve_execution_build_mode(
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
    )

    assert result == "UP_TO_DATE"


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

    result = (
        resolve_execution_build_mode(
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
    )

    assert result == "REFRESH"


def test_count_mismatch_forces_full():
    result = (
        resolve_execution_build_mode(
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
    )

    assert result == "FULL"


def test_wrong_input_model_forces_full():
    result = (
        resolve_execution_build_mode(
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
    )

    assert result == "FULL"


def test_state_ahead_is_rejected():
    with pytest.raises(
        RuntimeError
    ):
        resolve_execution_build_mode(
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