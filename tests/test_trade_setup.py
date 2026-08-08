from datetime import (
    UTC,
    date,
    datetime,
)
from uuid import UUID

import pytest

from imi.features.trade_setup import (
    MAX_EXTENSION_ATR,
    REFERENCE_CAPITAL_IDR,
    RISK_BUDGET_PCT,
    build_trade_setup_model_version,
    build_trade_setup_thesis,
    calculate_entry_zone,
    calculate_normalized_position_size,
    calculate_trade_setup,
    extract_current_universe_date,
    prepare_trade_setup_rows,
    resolve_trade_setup_build_mode,
    select_nearest_resistance,
)

INSTRUMENT_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def valid_setup_kwargs():
    return {
        "close":
            100.0,

        "ema20":
            95.0,

        "atr14":
            3.0,

        "prior_low_10d":
            94.5,

        "prior_high_20d":
            120.0,

        "prior_high_55d":
            125.0,

        "prior_count_10d":
            10,
    }


def test_model_version() -> None:
    result = (
        build_trade_setup_model_version(
            date(
                2026,
                8,
                8,
            )
        )
    )

    assert result == (
        "trade_setup_v1_"
        "current_20260808_"
        "yahoo_ksei"
    )


def test_extract_universe_date() -> None:
    result = (
        extract_current_universe_date(

                "stock_screener_v1_"
                "current_20260808_"
                "yahoo_ksei"

        )
    )

    assert result == date(
        2026,
        8,
        8,
    )


def test_extract_universe_date_rejects_bad_model() -> None:
    with pytest.raises(
        ValueError
    ):
        extract_current_universe_date(
            "bad_model"
        )


def test_normal_entry_zone() -> None:
    (
        entry_low,
        entry_high,
        entry_mid,
        extension,
    ) = calculate_entry_zone(
        close=100.0,
        ema20=95.0,
        atr14=4.0,
    )

    assert entry_low == 98.0
    assert entry_high == 100.0
    assert entry_mid == 99.0
    assert extension == 1.25


def test_extended_entry_zone() -> None:
    (
        entry_low,
        entry_high,
        entry_mid,
        extension,
    ) = calculate_entry_zone(
        close=110.0,
        ema20=100.0,
        atr14=4.0,
    )

    assert extension > MAX_EXTENSION_ATR
    assert entry_low == 106.0
    assert entry_high == 108.0
    assert entry_mid == 107.0


def test_nearest_resistance_uses_20d() -> None:
    result = (
        select_nearest_resistance(
            current_close=100.0,
            prior_high_20d=105.0,
            prior_high_55d=110.0,
        )
    )

    assert result == 105.0


def test_nearest_resistance_ignores_broken_levels() -> None:
    result = (
        select_nearest_resistance(
            current_close=110.0,
            prior_high_20d=105.0,
            prior_high_55d=108.0,
        )
    )

    assert result is None


def test_position_sizing_respects_risk_budget() -> None:
    result = (
        calculate_normalized_position_size(
            entry_mid=100.0,
            risk_per_share=5.0,
        )
    )

    assert result.lots > 0
    assert result.shares == (
        result.lots
        * 100
    )

    assert (
        result.planned_risk_amount
        <= REFERENCE_CAPITAL_IDR
        * RISK_BUDGET_PCT
    )


def test_position_sizing_respects_cash_cap() -> None:
    result = (
        calculate_normalized_position_size(
            entry_mid=500_000.0,
            risk_per_share=1_000.0,
        )
    )

    assert result.lots == 2
    assert result.shares == 200


def test_accept_valid_setup() -> None:
    result = calculate_trade_setup(
        **valid_setup_kwargs()
    )

    assert result.decision == "ACCEPT"
    assert result.status == "BUY_SETUP"
    assert result.expected_rr is not None
    assert result.expected_rr >= 1.5
    assert result.position_size_lots is not None
    assert result.position_size_lots > 0


def test_accept_has_empty_reasons() -> None:
    result = calculate_trade_setup(
        **valid_setup_kwargs()
    )

    assert result.decision_reasons == ()


def test_extended_setup_becomes_watch() -> None:
    values = valid_setup_kwargs()

    values.update(
        {
            "close":
                110.0,
            "ema20":
                100.0,
            "atr14":
                4.0,
            "prior_low_10d":
                100.0,
            "prior_high_20d":
                130.0,
            "prior_high_55d":
                135.0,
        }
    )

    result = calculate_trade_setup(
        **values
    )

    assert result.decision == "WATCH"
    assert result.status == "WATCH"

    assert (
        "PRICE_EXTENDED_FROM_EMA20"
        in result.decision_reasons
    )


def test_below_ema20_is_rejected() -> None:
    values = valid_setup_kwargs()

    values[
        "close"
    ] = 94.0

    result = calculate_trade_setup(
        **values
    )

    assert result.decision == "REJECT"
    assert result.status == "AVOID"

    assert (
        "CLOSE_NOT_ABOVE_EMA20"
        in result.decision_reasons
    )


def test_missing_close_is_rejected() -> None:
    values = valid_setup_kwargs()

    values[
        "close"
    ] = None

    result = calculate_trade_setup(
        **values
    )

    assert result.decision == "REJECT"

    assert (
        "MISSING_CLOSE"
        in result.decision_reasons
    )


def test_missing_atr_is_rejected() -> None:
    values = valid_setup_kwargs()

    values[
        "atr14"
    ] = None

    result = calculate_trade_setup(
        **values
    )

    assert (
        "MISSING_ATR14"
        in result.decision_reasons
    )


def test_insufficient_history_is_rejected() -> None:
    values = valid_setup_kwargs()

    values[
        "prior_count_10d"
    ] = 5

    result = calculate_trade_setup(
        **values
    )

    assert (
        "INSUFFICIENT_PRIOR_HISTORY"
        in result.decision_reasons
    )


def test_stop_must_be_below_entry_zone() -> None:
    values = valid_setup_kwargs()

    values.update(
        {
            "close":
                100.0,
            "ema20":
                95.0,
            "atr14":
                2.0,
            "prior_low_10d":
                99.5,
        }
    )

    result = calculate_trade_setup(
        **values
    )

    assert (
        "STOP_NOT_BELOW_ENTRY_ZONE"
        in result.decision_reasons
    )


def test_structure_stop_too_wide_atr() -> None:
    values = valid_setup_kwargs()

    values.update(
        {
            "close":
                100.0,
            "ema20":
                95.0,
            "atr14":
                2.0,
            "prior_low_10d":
                90.0,
        }
    )

    result = calculate_trade_setup(
        **values
    )

    assert (
        "STRUCTURE_STOP_TOO_WIDE_ATR"
        in result.decision_reasons
    )


def test_structure_stop_too_wide_pct() -> None:
    values = valid_setup_kwargs()

    values.update(
        {
            "close":
                100.0,
            "ema20":
                95.0,
            "atr14":
                6.0,
            "prior_low_10d":
                87.0,
            "prior_high_20d":
                140.0,
            "prior_high_55d":
                150.0,
        }
    )

    result = calculate_trade_setup(
        **values
    )

    assert (
        "STRUCTURE_STOP_TOO_WIDE_PCT"
        in result.decision_reasons
    )


def test_resistance_can_reject_rr() -> None:
    values = valid_setup_kwargs()

    values.update(
        {
            "prior_high_20d":
                105.0,
            "prior_high_55d":
                110.0,
        }
    )

    result = calculate_trade_setup(
        **values
    )

    assert result.decision == "REJECT"

    assert (
        "INSUFFICIENT_REWARD_RISK"
        in result.decision_reasons
    )


def test_probability_is_not_part_of_calculation() -> None:
    result = calculate_trade_setup(
        **valid_setup_kwargs()
    )

    assert not hasattr(
        result,
        "probability_tp_before_sl",
    )


def test_accept_thesis() -> None:
    result = calculate_trade_setup(
        **valid_setup_kwargs()
    )

    thesis = (
        build_trade_setup_thesis(
            result
        )
    )

    assert "passed" in thesis


def test_reject_thesis_contains_reason() -> None:
    values = valid_setup_kwargs()

    values[
        "close"
    ] = 94.0

    result = calculate_trade_setup(
        **values
    )

    thesis = (
        build_trade_setup_thesis(
            result
        )
    )

    assert (
        "CLOSE_NOT_ABOVE_EMA20"
        in thesis
    )


def test_prepare_trade_setup_row() -> None:
    item = {
        "instrument_id":
            INSTRUMENT_ID,

        "symbol":
            "TEST",

        "sector_code":
            "IDXENERGY",

        "trading_date":
            date(
                2026,
                8,
                6,
            ),

        "overall_score":
            70.0,

        "market_score":
            43.666,

        "sector_score":
            58.5,

        "technical_score":
            80.0,

        "liquidity_score":
            90.0,

        "ownership_score":
            75.0,

        "risk_score":
            70.0,

        "data_completeness":
            95.0,

        "screener_model_version":
            "stock_test",

        "ema20":
            95.0,

        "ema50":
            90.0,

        "rsi14":
            60.0,

        "atr14":
            3.0,

        "breakout_flag":
            True,

        "failed_breakout_flag":
            False,

        "open":
            98.0,

        "high":
            102.0,

        "low":
            97.0,

        "close":
            100.0,

        "prior_low_10d":
            94.5,

        "prior_high_20d":
            120.0,

        "prior_high_55d":
            125.0,

        "prior_count_10d":
            10,

        "input_updated_at":
            datetime(
                2026,
                8,
                8,
                tzinfo=UTC,
            ),
    }

    rows = prepare_trade_setup_rows(
        inputs=[item],
        model_version="trade_test",
    )

    assert len(rows) == 1

    row = rows[0]

    assert (
        row["setup_decision"]
        == "ACCEPT"
    )

    assert (
        row["status"]
        == "BUY_SETUP"
    )

    assert (
        row[
            "probability_tp_before_sl"
        ]
        is None
    )

    assert (
        row["expected_value_r"]
        is None
    )

    assert (
        row["confidence"]
        is None
    )

    assert (
        row["is_frozen"]
        is False
    )


def test_prepare_row_uses_normalized_capital() -> None:
    item = {
        "instrument_id":
            INSTRUMENT_ID,
        "symbol":
            "TEST",
        "sector_code":
            "IDXENERGY",
        "trading_date":
            date(
                2026,
                8,
                6,
            ),
        "overall_score":
            70.0,
        "market_score":
            50.0,
        "sector_score":
            60.0,
        "technical_score":
            80.0,
        "liquidity_score":
            80.0,
        "ownership_score":
            50.0,
        "risk_score":
            70.0,
        "data_completeness":
            95.0,
        "screener_model_version":
            "stock_test",
        "ema20":
            95.0,
        "ema50":
            90.0,
        "rsi14":
            60.0,
        "atr14":
            3.0,
        "breakout_flag":
            False,
        "failed_breakout_flag":
            False,
        "open":
            98.0,
        "high":
            102.0,
        "low":
            97.0,
        "close":
            100.0,
        "prior_low_10d":
            94.5,
        "prior_high_20d":
            120.0,
        "prior_high_55d":
            125.0,
        "prior_count_10d":
            10,
        "input_updated_at":
            datetime(
                2026,
                8,
                8,
                tzinfo=UTC,
            ),
    }

    row = prepare_trade_setup_rows(
        inputs=[item],
        model_version="trade_test",
    )[0]

    assert (
        row["reference_capital"]
        == REFERENCE_CAPITAL_IDR
    )

    assert (
        row["risk_budget_pct"]
        == RISK_BUDGET_PCT
    )


def test_build_mode_full_without_state() -> None:
    mode = (
        resolve_trade_setup_build_mode(
            force=False,
            state_exists=False,
            input_model_matches=False,
            processed_through=None,
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            stored_rows=0,
            state_output_rows=0,
            expected_rows=100,
            stored_processed_input_updated_at=None,
            current_processed_input_updated_at=None,
        )
    )

    assert mode == "FULL"


def test_build_mode_force_full() -> None:
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_trade_setup_build_mode(
            force=True,
            state_exists=True,
            input_model_matches=True,
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
            stored_rows=100,
            state_output_rows=100,
            expected_rows=100,
            stored_processed_input_updated_at=(
                timestamp
            ),
            current_processed_input_updated_at=(
                timestamp
            ),
        )
    )

    assert mode == "FULL"


def test_build_mode_up_to_date() -> None:
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_trade_setup_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
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
            stored_rows=100,
            state_output_rows=100,
            expected_rows=100,
            stored_processed_input_updated_at=(
                timestamp
            ),
            current_processed_input_updated_at=(
                timestamp
            ),
        )
    )

    assert mode == "UP_TO_DATE"


def test_build_mode_incremental() -> None:
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_trade_setup_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
            processed_through=date(
                2026,
                8,
                5,
            ),
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            stored_rows=90,
            state_output_rows=90,
            expected_rows=100,
            stored_processed_input_updated_at=(
                timestamp
            ),
            current_processed_input_updated_at=(
                timestamp
            ),
        )
    )

    assert mode == "INCREMENTAL"


def test_build_mode_input_change_forces_full() -> None:
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
        resolve_trade_setup_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
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
            stored_rows=100,
            state_output_rows=100,
            expected_rows=100,
            stored_processed_input_updated_at=(
                old
            ),
            current_processed_input_updated_at=(
                new
            ),
        )
    )

    assert mode == "FULL"


def test_build_mode_wrong_input_model_forces_full() -> None:
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_trade_setup_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=False,
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
            stored_rows=100,
            state_output_rows=100,
            expected_rows=100,
            stored_processed_input_updated_at=(
                timestamp
            ),
            current_processed_input_updated_at=(
                timestamp
            ),
        )
    )

    assert mode == "FULL"


def test_build_state_ahead_is_rejected() -> None:
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    with pytest.raises(
        RuntimeError
    ):
        resolve_trade_setup_build_mode(
            force=False,
            state_exists=True,
            input_model_matches=True,
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
            stored_rows=100,
            state_output_rows=100,
            expected_rows=100,
            stored_processed_input_updated_at=(
                timestamp
            ),
            current_processed_input_updated_at=(
                timestamp
            ),
        )