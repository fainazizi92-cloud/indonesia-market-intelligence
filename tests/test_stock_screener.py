from datetime import (
    UTC,
    date,
    datetime,
)
from uuid import UUID

import pytest

from imi.features.stock_screener import (
    build_stock_screener_model_version,
    calculate_breakout_score,
    calculate_liquidity_score,
    calculate_market_score,
    calculate_momentum_score,
    calculate_overall_score,
    calculate_ownership_score,
    calculate_relative_strength_score,
    calculate_risk_score,
    calculate_stock_screener_metrics,
    calculate_trend_score,
    calculate_volume_score,
    classify_screening_status,
    prepare_stock_screener_rows,
    rank_stock_rows,
    resolve_stock_screener_build_mode,
)

INSTRUMENT_1 = UUID(
    "00000000-0000-0000-0000-000000000001"
)

INSTRUMENT_2 = UUID(
    "00000000-0000-0000-0000-000000000002"
)

INSTRUMENT_3 = UUID(
    "00000000-0000-0000-0000-000000000003"
)


def test_model_version() -> None:
    assert (
        build_stock_screener_model_version(
            date(
                2026,
                8,
                8,
            )
        )
        == (
            "stock_screener_v1_"
            "current_20260808_"
            "yahoo_ksei"
        )
    )


def test_market_bull_high_confidence() -> None:
    result = calculate_market_score(
        regime="BULL",
        confidence=1.0,
    )

    assert result == 80.0


def test_market_bear_low_confidence() -> None:
    result = calculate_market_score(
        regime="BEAR",
        confidence=0.25,
    )

    assert result == 45.0


def test_trend_score_all_positive() -> None:
    result = calculate_trend_score(
        close=120.0,
        ema20=110.0,
        ema50=100.0,
        ema200=90.0,
        return_20d=0.10,
    )

    assert result == 100.0


def test_momentum_ideal() -> None:
    result = calculate_momentum_score(
        65.0
    )

    assert result == 100.0


def test_momentum_overbought_is_lower() -> None:
    ideal = calculate_momentum_score(
        65.0
    )

    overbought = calculate_momentum_score(
        90.0
    )

    assert overbought < ideal


def test_relative_strength_positive() -> None:
    result = (
        calculate_relative_strength_score(
            rs_ihsg_20d=0.20,
            rs_sector_20d=0.20,
        )
    )

    assert result == 100.0

    fallback = (
        calculate_relative_strength_score(
            rs_ihsg_20d=0.10,
            rs_sector_20d=None,
        )
    )

    assert fallback == 75.0


def test_volume_score() -> None:
    result = calculate_volume_score(
        1.0
    )

    assert result == 65.0

    fallback = calculate_volume_score(
        None
    )

    assert fallback == 50.0


def test_breakout_score() -> None:
    result = calculate_breakout_score(
        breakout_flag=True,
        failed_breakout_flag=False,
    )

    assert result == 100.0


def test_failed_breakout_score() -> None:
    result = calculate_breakout_score(
        breakout_flag=True,
        failed_breakout_flag=True,
    )

    assert result == 0.0


def test_liquidity_score() -> None:
    result = calculate_liquidity_score(
        0.75
    )

    assert result == 75.0


def test_ownership_accumulating() -> None:
    score, age, stale = (
        calculate_ownership_score(
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
            trend_label=(
                "ACCUMULATING"
            ),
            signal_strength=80.0,
        )
    )

    assert score == 90.0
    assert age == 6
    assert stale is False


def test_ownership_distributing() -> None:
    score, _, _ = (
        calculate_ownership_score(
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
            trend_label=(
                "DISTRIBUTING"
            ),
            signal_strength=80.0,
        )
    )

    assert score == 10.0


def test_ownership_stale_becomes_neutral() -> None:
    score, age, stale = (
        calculate_ownership_score(
            trading_date=date(
                2026,
                8,
                6,
            ),
            ownership_as_of_date=date(
                2026,
                6,
                1,
            ),
            trend_label=(
                "ACCUMULATING"
            ),
            signal_strength=100.0,
        )
    )

    assert score == 50.0
    assert age is not None
    assert age > 45
    assert stale is True


def test_missing_ownership_is_neutral() -> None:
    score, age, stale = (
        calculate_ownership_score(
            trading_date=date(
                2026,
                8,
                6,
            ),
            ownership_as_of_date=None,
            trend_label=None,
            signal_strength=None,
        )
    )

    assert score == 50.0
    assert age is None
    assert stale is False


def test_moderate_volatility_risk_score() -> None:
    score, atr_pct = calculate_risk_score(
        atr14=4.0,
        close=100.0,
    )

    assert score == 70.0
    assert atr_pct == 4.0


def test_high_volatility_risk_score() -> None:
    score, atr_pct = calculate_risk_score(
        atr14=15.0,
        close=100.0,
    )

    assert score == 10.0
    assert atr_pct == 15.0


def test_overall_score_all_100() -> None:
    result = calculate_overall_score(
        market_score=100.0,
        sector_score=100.0,
        technical_score=100.0,
        liquidity_score=100.0,
        ownership_score=100.0,
        risk_score=100.0,
    )

    assert result == 100.0


def test_buy_setup_status() -> None:
    result = classify_screening_status(
        overall_score=75.0,
        market_score=55.0,
        sector_score=65.0,
        technical_score=80.0,
        liquidity_score=70.0,
        risk_score=70.0,
        breakout_flag=True,
        failed_breakout_flag=False,
        rs_ihsg_20d=0.10,
        rsi14=60.0,
        close=120.0,
        ema20=110.0,
    )

    assert result == "BUY_SETUP"


def test_failed_breakout_is_avoid() -> None:
    result = classify_screening_status(
        overall_score=90.0,
        market_score=90.0,
        sector_score=90.0,
        technical_score=90.0,
        liquidity_score=90.0,
        risk_score=90.0,
        breakout_flag=True,
        failed_breakout_flag=True,
        rs_ihsg_20d=0.20,
        rsi14=60.0,
        close=120.0,
        ema20=110.0,
    )

    assert result == "AVOID"


def test_watch_status() -> None:
    result = classify_screening_status(
        overall_score=60.0,
        market_score=45.0,
        sector_score=55.0,
        technical_score=60.0,
        liquidity_score=50.0,
        risk_score=60.0,
        breakout_flag=False,
        failed_breakout_flag=False,
        rs_ihsg_20d=0.01,
        rsi14=55.0,
        close=105.0,
        ema20=100.0,
    )

    assert result == "WATCH"


def test_wait_status() -> None:
    result = classify_screening_status(
        overall_score=50.0,
        market_score=45.0,
        sector_score=45.0,
        technical_score=50.0,
        liquidity_score=30.0,
        risk_score=40.0,
        breakout_flag=False,
        failed_breakout_flag=False,
        rs_ihsg_20d=0.0,
        rsi14=50.0,
        close=100.0,
        ema20=100.0,
    )

    assert result == "WAIT"


def test_rank_stock_rows() -> None:
    rows = [
        {
            "trading_date":
                date(
                    2026,
                    8,
                    6,
                ),
            "instrument_id":
                INSTRUMENT_1,
            "symbol":
                "AAA",
            "sector_code":
                "IDXENERGY",
            "overall_score":
                70.0,
            "technical_score":
                70.0,
        },
        {
            "trading_date":
                date(
                    2026,
                    8,
                    6,
                ),
            "instrument_id":
                INSTRUMENT_2,
            "symbol":
                "BBB",
            "sector_code":
                "IDXENERGY",
            "overall_score":
                80.0,
            "technical_score":
                80.0,
        },
        {
            "trading_date":
                date(
                    2026,
                    8,
                    6,
                ),
            "instrument_id":
                INSTRUMENT_3,
            "symbol":
                "CCC",
            "sector_code":
                "IDXFINANCE",
            "overall_score":
                75.0,
            "technical_score":
                75.0,
        },
    ]

    ranked = rank_stock_rows(
        rows
    )

    by_symbol = {
        row["symbol"]:
            row
        for row in ranked
    }

    assert (
        by_symbol["BBB"][
            "universe_rank"
        ]
        == 1
    )

    assert (
        by_symbol["CCC"][
            "universe_rank"
        ]
        == 2
    )

    assert (
        by_symbol["AAA"][
            "universe_rank"
        ]
        == 3
    )

    assert (
        by_symbol["BBB"][
            "sector_rank"
        ]
        == 1
    )

    assert (
        by_symbol["AAA"][
            "sector_rank"
        ]
        == 2
    )

    assert (
        by_symbol["CCC"][
            "sector_rank"
        ]
        == 1
    )


def test_build_mode_full_when_empty() -> None:
    mode = (
        resolve_stock_screener_build_mode(
            existing_last_date=None,
            existing_latest_count=0,
            existing_expected_count=0,
            existing_input_updated_at=None,
            expected_input_updated_at=None,
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
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    latest = date(
        2026,
        8,
        6,
    )

    mode = (
        resolve_stock_screener_build_mode(
            existing_last_date=latest,
            existing_latest_count=900,
            existing_expected_count=900,
            existing_input_updated_at=(
                timestamp
            ),
            expected_input_updated_at=(
                timestamp
            ),
            latest_input_date=latest,
            force=False,
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
        resolve_stock_screener_build_mode(
            existing_last_date=date(
                2026,
                8,
                5,
            ),
            existing_latest_count=900,
            existing_expected_count=900,
            existing_input_updated_at=(
                timestamp
            ),
            expected_input_updated_at=(
                timestamp
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


def test_upstream_change_forces_full() -> None:
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
        resolve_stock_screener_build_mode(
            existing_last_date=date(
                2026,
                8,
                6,
            ),
            existing_latest_count=900,
            existing_expected_count=900,
            existing_input_updated_at=(
                old
            ),
            expected_input_updated_at=(
                new
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


def test_force_build_mode_full() -> None:
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    mode = (
        resolve_stock_screener_build_mode(
            existing_last_date=date(
                2026,
                8,
                6,
            ),
            existing_latest_count=900,
            existing_expected_count=900,
            existing_input_updated_at=(
                timestamp
            ),
            expected_input_updated_at=(
                timestamp
            ),
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
    timestamp = datetime(
        2026,
        8,
        8,
        tzinfo=UTC,
    )

    with pytest.raises(
        RuntimeError
    ):
        resolve_stock_screener_build_mode(
            existing_last_date=date(
                2026,
                8,
                7,
            ),
            existing_latest_count=900,
            existing_expected_count=900,
            existing_input_updated_at=(
                timestamp
            ),
            expected_input_updated_at=(
                timestamp
            ),
            latest_input_date=date(
                2026,
                8,
                6,
            ),
            force=False,
        )


def test_prepare_stock_row() -> None:
    item = {
        "instrument_id":
            INSTRUMENT_1,

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

        "close":
            120.0,

        "avg_turnover_20d":
            10_000_000_000.0,

        "liquidity_percentile":
            0.80,

        "return_1d":
            0.01,

        "return_5d":
            0.05,

        "return_20d":
            0.10,

        "return_60d":
            0.20,

        "ema20":
            110.0,

        "ema50":
            100.0,

        "ema100":
            95.0,

        "ema200":
            90.0,

        "rsi14":
            60.0,

        "atr14":
            4.0,

        "volume_z20":
            None,

        "rs_ihsg_20d":
            0.10,

        "rs_sector_20d":
            None,

        "breakout_flag":
            True,

        "failed_breakout_flag":
            False,

        "feature_version":
            "technical_v1_yahoo_eod",

        "sector_score":
            65.0,

        "sector_integrated_label":
            "STRONG_BULLISH",

        "sector_alignment_label":
            "TECHNICAL_LEAD",

        "sector_ownership_stale_flag":
            False,

        "sector_model_version":
            "integrated_test",

        "market_regime":
            "BULL",

        "market_confidence":
            0.8,

        "market_model_version":
            "market_test",

        "ownership_as_of_date":
            date(
                2026,
                7,
                31,
            ),

        "ownership_trend_label":
            "ACCUMULATING",

        "ownership_signal_strength":
            80.0,

        "ownership_corporate_action_risk":
            False,

        "ownership_snapshot_gap_flag":
            False,

        "input_updated_at":
            datetime(
                2026,
                8,
                8,
                tzinfo=UTC,
            ),
    }

    rows = prepare_stock_screener_rows(
        inputs=[item],
        model_version="stock_test",
    )

    assert len(rows) == 1

    row = rows[0]

    assert (
        row["instrument_id"]
        == INSTRUMENT_1
    )

    assert (
        row["ownership_score"]
        == 90.0
    )

    assert (
        row["flow_score"]
        is None
    )

    assert (
        row["fundamental_score"]
        is None
    )

    assert (
        row["valuation_score"]
        is None
    )

    assert (
        row["catalyst_score"]
        is None
    )

    assert (
        row["status"]
        in {
            "BUY_SETUP",
            "WATCH",
            "WAIT",
            "AVOID",
        }
    )

    warnings = row[
        "evidence"
    ][
        "warnings"
    ]

    assert (
        "RS_SECTOR_20D_UNAVAILABLE_"
        "USING_IHSG_ONLY"
        in warnings
    )

    assert (
        "VOLUME_Z20_UNAVAILABLE_"
        "NEUTRAL_FALLBACK"
        in warnings
    )

    assert (
        row[
            "evidence"
        ][
            "technical"
        ][
            "relative_strength_source"
        ]
        == "IHSG_ONLY"
    )

    assert (
        row[
            "evidence"
        ][
            "technical_components"
        ][
            "volume"
        ]
        == 50.0
    )


def test_calculate_full_metrics() -> None:
    metrics = (
        calculate_stock_screener_metrics(
            trading_date=date(
                2026,
                8,
                6,
            ),
            market_regime="BULL",
            market_confidence=0.8,
            sector_score=65.0,
            sector_ownership_stale_flag=False,
            close=120.0,
            return_20d=0.10,
            ema20=110.0,
            ema50=100.0,
            ema200=90.0,
            rsi14=60.0,
            atr14=4.0,
            volume_z20=1.0,
            rs_ihsg_20d=0.10,
            rs_sector_20d=0.05,
            breakout_flag=True,
            failed_breakout_flag=False,
            liquidity_percentile=0.80,
            ownership_as_of_date=date(
                2026,
                7,
                31,
            ),
            ownership_trend_label=(
                "ACCUMULATING"
            ),
            ownership_signal_strength=(
                80.0
            ),
        )
    )

    assert (
        0.0
        <= metrics.overall_score
        <= 100.0
    )

    assert (
        metrics.ownership_score
        == 90.0
    )

    assert (
        metrics.ownership_age_days
        == 6
    )

    assert (
        metrics.volume_available
        is True
    )

    assert (
        metrics.rs_sector_available
        is True
    )

