from uuid import UUID

from imi.features.execution_realism import (
    calculate_execution_result,
)
from imi.features.execution_sensitivity import (
    BASELINE_CONSERVATIVE,
    MIN_COST_ZERO_SLIPPAGE,
    SCENARIOS,
    STRESS_2T,
    TICK_ONLY,
    ScenarioSummary,
    build_execution_sensitivity_version,
    calculate_raw_risk_ticks,
    calculate_scenario_execution,
    classify_execution_fragility,
    liquidity_bucket,
    prepare_execution_sensitivity_rows,
    price_bucket,
    risk_tick_bucket,
    summarize_all_scenarios,
)

SIGNAL_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def sample_input():
    return {
        "signal_id":
            SIGNAL_ID,

        "symbol":
            "TEST",

        "instrument_id":
            SIGNAL_ID,

        "signal_date":
            None,

        "sector_code":
            "IDXENERGY",

        "split_label":
            "TRAIN",

        "outcome_label":
            "TARGET",

        "raw_entry_price":
            1000.0,

        "raw_exit_price":
            1100.0,

        "raw_stop_price":
            950.0,

        "entry_reference_price":
            1000.0,

        "exit_reference_price":
            1080.0,

        "raw_realized_r":
            2.0,

        "stored_baseline_gross_r":
            None,

        "stored_baseline_net_r":
            None,

        "stored_baseline_drag_r":
            None,

        "setup_risk_pct":
            0.05,

        "liquidity_score":
            80.0,

        "overall_score":
            70.0,

        "risk_score":
            65.0,

        "input_updated_at":
            None,
    }


def test_version():
    result = (
        build_execution_sensitivity_version(
            
                "execution_realism_v1_"
                "current_20260808_idx_eod"
            
        )
    )

    assert result == (
        "execution_sensitivity_v1_"
        "current_20260808_idx_eod"
    )


def test_price_bucket_lt_200():
    assert (
        price_bucket(
            199
        )
        == "LT_200"
    )


def test_price_bucket_200():
    assert (
        price_bucket(
            200
        )
        == "200_TO_499"
    )


def test_price_bucket_500():
    assert (
        price_bucket(
            500
        )
        == "500_TO_1999"
    )


def test_price_bucket_2000():
    assert (
        price_bucket(
            2000
        )
        == "2000_TO_4999"
    )


def test_price_bucket_5000():
    assert (
        price_bucket(
            5000
        )
        == "GE_5000"
    )


def test_risk_bucket_lt_4():
    assert (
        risk_tick_bucket(
            3.5
        )
        == "LT_4"
    )


def test_risk_bucket_4_to_6():
    assert (
        risk_tick_bucket(
            4.5
        )
        == "4_TO_LT_6"
    )


def test_risk_bucket_6_to_11():
    assert (
        risk_tick_bucket(
            8
        )
        == "6_TO_LT_11"
    )


def test_risk_bucket_11_to_21():
    assert (
        risk_tick_bucket(
            15
        )
        == "11_TO_LT_21"
    )


def test_risk_bucket_ge_21():
    assert (
        risk_tick_bucket(
            25
        )
        == "GE_21"
    )


def test_liquidity_bucket_high():
    assert (
        liquidity_bucket(
            80
        )
        == "GE_75"
    )


def test_raw_risk_ticks():
    result = (
        calculate_raw_risk_ticks(
            raw_entry_price=1000,
            raw_stop_price=950,
            entry_reference_price=1000,
        )
    )

    assert result == 10.0


def test_four_scenarios():
    assert len(
        SCENARIOS
    ) == 4


def test_tick_only_has_zero_fee():
    assert (
        TICK_ONLY.buy_fee_rate
        == 0
    )

    assert (
        TICK_ONLY.sell_fee_rate
        == 0
    )


def test_min_cost_has_zero_extra_slippage():
    assert (
        MIN_COST_ZERO_SLIPPAGE
        .entry_slippage_ticks
        == 0
    )

    assert (
        MIN_COST_ZERO_SLIPPAGE
        .stop_exit_slippage_ticks
        == 0
    )


def test_baseline_matches_phase3l_calculation():
    existing = (
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

    sensitivity = (
        calculate_scenario_execution(
            raw_entry_price=1000,
            raw_exit_price=1100,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1080,
            raw_realized_r=2.0,
            outcome_label="TARGET",
            scenario=(
                BASELINE_CONSERVATIVE
            ),
        )
    )

    assert abs(
        existing.gross_modeled_r
        - sensitivity.gross_r
    ) <= 0.0001

    assert abs(
        existing.net_realized_r
        - sensitivity.net_r
    ) <= 0.0001


def test_stress_worse_than_baseline():
    baseline = (
        calculate_scenario_execution(
            raw_entry_price=1000,
            raw_exit_price=1100,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1080,
            raw_realized_r=2.0,
            outcome_label="TARGET",
            scenario=(
                BASELINE_CONSERVATIVE
            ),
        )
    )

    stress = (
        calculate_scenario_execution(
            raw_entry_price=1000,
            raw_exit_price=1100,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1080,
            raw_realized_r=2.0,
            outcome_label="TARGET",
            scenario=STRESS_2T,
        )
    )

    assert (
        stress.net_r
        < baseline.net_r
    )


def test_min_cost_below_tick_only():
    tick_only = (
        calculate_scenario_execution(
            raw_entry_price=1000,
            raw_exit_price=1100,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1080,
            raw_realized_r=2.0,
            outcome_label="TARGET",
            scenario=TICK_ONLY,
        )
    )

    minimum = (
        calculate_scenario_execution(
            raw_entry_price=1000,
            raw_exit_price=1100,
            raw_stop_price=950,
            entry_reference_price=1000,
            exit_reference_price=1080,
            raw_realized_r=2.0,
            outcome_label="TARGET",
            scenario=(
                MIN_COST_ZERO_SLIPPAGE
            ),
        )
    )

    assert (
        minimum.net_r
        < tick_only.net_r
    )


def test_prepare_rows_generates_four():
    rows = (
        prepare_execution_sensitivity_rows(
            inputs=[
                sample_input()
            ]
        )
    )

    assert len(
        rows
    ) == 4


def test_prepare_rows_has_risk_ticks():
    rows = (
        prepare_execution_sensitivity_rows(
            inputs=[
                sample_input()
            ]
        )
    )

    assert all(
        row[
            "raw_risk_ticks"
        ]
        == 10
        for row in rows
    )


def test_prepare_rows_price_bucket():
    rows = (
        prepare_execution_sensitivity_rows(
            inputs=[
                sample_input()
            ]
        )
    )

    assert all(
        row[
            "price_bucket"
        ]
        == "500_TO_1999"
        for row in rows
    )


def test_summary_all_scenarios():
    rows = (
        prepare_execution_sensitivity_rows(
            inputs=[
                sample_input()
            ]
        )
    )

    summaries = (
        summarize_all_scenarios(
            rows
        )
    )

    assert len(
        summaries
    ) == 4

    assert all(
        summary.trades == 1
        for summary in summaries
    )


def test_fragility_robust_to_stress():
    summaries = [
        ScenarioSummary(
            scenario="TICK_ONLY",
            trades=100,
            average_r=0.5,
            median_r=0.4,
            profit_factor=2.0,
            positive_trades=60,
            positive_rate=0.6,
            average_drag_r=0.0,
        ),
        ScenarioSummary(
            scenario=(
                "MIN_COST_ZERO_SLIPPAGE"
            ),
            trades=100,
            average_r=0.4,
            median_r=0.3,
            profit_factor=1.8,
            positive_trades=58,
            positive_rate=0.58,
            average_drag_r=0.1,
        ),
        ScenarioSummary(
            scenario=(
                "BASELINE_CONSERVATIVE"
            ),
            trades=100,
            average_r=0.3,
            median_r=0.2,
            profit_factor=1.5,
            positive_trades=55,
            positive_rate=0.55,
            average_drag_r=0.2,
        ),
        ScenarioSummary(
            scenario="STRESS_2T",
            trades=100,
            average_r=0.1,
            median_r=0.05,
            profit_factor=1.1,
            positive_trades=51,
            positive_rate=0.51,
            average_drag_r=0.4,
        ),
    ]

    assert (
        classify_execution_fragility(
            summaries
        )
        == "ROBUST_TO_STRESS_2T"
    )


def test_fragility_extra_slippage():
    summaries = [
        ScenarioSummary(
            scenario="TICK_ONLY",
            trades=100,
            average_r=0.3,
            median_r=0.2,
            profit_factor=1.4,
            positive_trades=55,
            positive_rate=0.55,
            average_drag_r=0.0,
        ),
        ScenarioSummary(
            scenario=(
                "MIN_COST_ZERO_SLIPPAGE"
            ),
            trades=100,
            average_r=0.1,
            median_r=0.05,
            profit_factor=1.1,
            positive_trades=51,
            positive_rate=0.51,
            average_drag_r=0.2,
        ),
        ScenarioSummary(
            scenario=(
                "BASELINE_CONSERVATIVE"
            ),
            trades=100,
            average_r=-0.1,
            median_r=-0.1,
            profit_factor=0.8,
            positive_trades=45,
            positive_rate=0.45,
            average_drag_r=0.4,
        ),
        ScenarioSummary(
            scenario="STRESS_2T",
            trades=100,
            average_r=-0.3,
            median_r=-0.2,
            profit_factor=0.6,
            positive_trades=40,
            positive_rate=0.4,
            average_drag_r=0.6,
        ),
    ]

    assert (
        classify_execution_fragility(
            summaries
        )
        == (
            "FRAGILE_TO_EXTRA_"
            "SLIPPAGE"
        )
    )