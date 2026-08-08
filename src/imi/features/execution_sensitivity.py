import statistics
from dataclasses import dataclass
from typing import Any

from imi.features.execution_realism import (
    IDX_BUY_INFRASTRUCTURE_FEE_RATE,
    IDX_SELL_INFRASTRUCTURE_FEE_RATE,
    idx_price_fraction,
    round_to_tick,
)

EXECUTION_SENSITIVITY_VERSION = (
    "execution_sensitivity_v1"
)


@dataclass(frozen=True)
class ExecutionScenario:
    name: str

    entry_slippage_ticks: int

    target_exit_slippage_ticks: int
    stop_exit_slippage_ticks: int
    expired_exit_slippage_ticks: int

    buy_fee_rate: float
    sell_fee_rate: float


@dataclass(frozen=True)
class ScenarioExecutionResult:
    scenario: str

    entry_tick_size: float
    exit_tick_size: float

    modeled_entry_price: float
    modeled_exit_price: float
    modeled_stop_price: float

    gross_r: float
    net_r: float

    total_drag_r: float


@dataclass(frozen=True)
class ScenarioSummary:
    scenario: str

    trades: int

    average_r: float | None
    median_r: float | None

    profit_factor: float | None

    positive_trades: int
    positive_rate: float | None

    average_drag_r: float | None


TICK_ONLY = ExecutionScenario(
    name="TICK_ONLY",
    entry_slippage_ticks=0,
    target_exit_slippage_ticks=0,
    stop_exit_slippage_ticks=0,
    expired_exit_slippage_ticks=0,
    buy_fee_rate=0.0,
    sell_fee_rate=0.0,
)


MIN_COST_ZERO_SLIPPAGE = ExecutionScenario(
    name="MIN_COST_ZERO_SLIPPAGE",
    entry_slippage_ticks=0,
    target_exit_slippage_ticks=0,
    stop_exit_slippage_ticks=0,
    expired_exit_slippage_ticks=0,
    buy_fee_rate=(
        IDX_BUY_INFRASTRUCTURE_FEE_RATE
    ),
    sell_fee_rate=(
        IDX_SELL_INFRASTRUCTURE_FEE_RATE
    ),
)


BASELINE_CONSERVATIVE = ExecutionScenario(
    name="BASELINE_CONSERVATIVE",
    entry_slippage_ticks=1,
    target_exit_slippage_ticks=0,
    stop_exit_slippage_ticks=1,
    expired_exit_slippage_ticks=1,
    buy_fee_rate=(
        IDX_BUY_INFRASTRUCTURE_FEE_RATE
    ),
    sell_fee_rate=(
        IDX_SELL_INFRASTRUCTURE_FEE_RATE
    ),
)


STRESS_2T = ExecutionScenario(
    name="STRESS_2T",
    entry_slippage_ticks=2,
    target_exit_slippage_ticks=1,
    stop_exit_slippage_ticks=2,
    expired_exit_slippage_ticks=2,
    buy_fee_rate=(
        IDX_BUY_INFRASTRUCTURE_FEE_RATE
    ),
    sell_fee_rate=(
        IDX_SELL_INFRASTRUCTURE_FEE_RATE
    ),
)


SCENARIOS = (
    TICK_ONLY,
    MIN_COST_ZERO_SLIPPAGE,
    BASELINE_CONSERVATIVE,
    STRESS_2T,
)


def build_execution_sensitivity_version(
    execution_model_version: str,
) -> str:
    suffix = (
        execution_model_version
        .replace(
            "execution_realism_v1_",
            "",
            1,
        )
    )

    return (
        f"{EXECUTION_SENSITIVITY_VERSION}_"
        f"{suffix}"
    )


def scenario_exit_slippage_ticks(
    *,
    scenario: ExecutionScenario,
    outcome_label: str,
) -> int:
    if outcome_label == "TARGET":
        return (
            scenario
            .target_exit_slippage_ticks
        )

    if outcome_label == "STOP":
        return (
            scenario
            .stop_exit_slippage_ticks
        )

    if outcome_label == "EXPIRED":
        return (
            scenario
            .expired_exit_slippage_ticks
        )

    raise ValueError(
        "Unsupported mature outcome: "
        f"{outcome_label}"
    )


def price_bucket(
    reference_price: float,
) -> str:
    value = float(
        reference_price
    )

    if value <= 0:
        raise ValueError(
            "reference_price must "
            "be positive."
        )

    if value < 200:
        return "LT_200"

    if value < 500:
        return "200_TO_499"

    if value < 2000:
        return "500_TO_1999"

    if value < 5000:
        return "2000_TO_4999"

    return "GE_5000"


def risk_tick_bucket(
    risk_ticks: float,
) -> str:
    value = float(
        risk_ticks
    )

    if value <= 0:
        raise ValueError(
            "risk_ticks must "
            "be positive."
        )

    if value < 4:
        return "LT_4"

    if value < 6:
        return "4_TO_LT_6"

    if value < 11:
        return "6_TO_LT_11"

    if value < 21:
        return "11_TO_LT_21"

    return "GE_21"


def liquidity_bucket(
    liquidity_score: float | None,
) -> str:
    if liquidity_score is None:
        return "MISSING"

    value = float(
        liquidity_score
    )

    if value < 25:
        return "LT_25"

    if value < 50:
        return "25_TO_LT_50"

    if value < 75:
        return "50_TO_LT_75"

    return "GE_75"


def calculate_raw_risk_ticks(
    *,
    raw_entry_price: float,
    raw_stop_price: float,
    entry_reference_price: float,
) -> float:
    entry = float(
        raw_entry_price
    )

    stop = float(
        raw_stop_price
    )

    risk = (
        entry
        - stop
    )

    if risk <= 0:
        raise ValueError(
            "Raw risk per share must "
            "be positive."
        )

    tick = idx_price_fraction(
        entry_reference_price
    )

    return round(
        risk
        / tick,
        6,
    )


def calculate_profit_factor(
    values: list[float],
) -> float | None:
    positive = sum(
        value
        for value in values
        if value > 0
    )

    negative = abs(
        sum(
            value
            for value in values
            if value < 0
        )
    )

    if negative == 0:
        return None

    return round(
        positive
        / negative,
        8,
    )


def calculate_scenario_execution(
    *,
    raw_entry_price: float,
    raw_exit_price: float,
    raw_stop_price: float,
    entry_reference_price: float,
    exit_reference_price: float,
    raw_realized_r: float,
    outcome_label: str,
    scenario: ExecutionScenario,
) -> ScenarioExecutionResult:
    raw_entry = float(
        raw_entry_price
    )

    raw_exit = float(
        raw_exit_price
    )

    raw_stop = float(
        raw_stop_price
    )

    raw_r = float(
        raw_realized_r
    )

    entry_tick = idx_price_fraction(
        entry_reference_price
    )

    exit_tick = idx_price_fraction(
        exit_reference_price
    )

    valid_entry = round_to_tick(
        price=raw_entry,
        tick_size=entry_tick,
        direction="UP",
    )

    modeled_entry = (
        valid_entry
        + (
            entry_tick
            * scenario
            .entry_slippage_ticks
        )
    )

    modeled_stop = round_to_tick(
        price=raw_stop,
        tick_size=entry_tick,
        direction="DOWN",
    )

    exit_slippage_ticks = (
        scenario_exit_slippage_ticks(
            scenario=scenario,
            outcome_label=(
                outcome_label
            ),
        )
    )

    valid_exit = round_to_tick(
        price=raw_exit,
        tick_size=exit_tick,
        direction="DOWN",
    )

    modeled_exit = (
        valid_exit
        - (
            exit_tick
            * exit_slippage_ticks
        )
    )

    if modeled_exit <= 0:
        raise ValueError(
            "Modeled exit became "
            "non-positive."
        )

    modeled_risk = (
        modeled_entry
        - modeled_stop
    )

    if modeled_risk <= 0:
        raise ValueError(
            "Modeled risk must "
            "be positive."
        )

    gross_pnl = (
        modeled_exit
        - modeled_entry
    )

    gross_r = (
        gross_pnl
        / modeled_risk
    )

    buy_cost = (
        modeled_entry
        * scenario.buy_fee_rate
    )

    sell_cost = (
        modeled_exit
        * scenario.sell_fee_rate
    )

    net_pnl = (
        modeled_exit
        - sell_cost
        - modeled_entry
        - buy_cost
    )

    net_r = (
        net_pnl
        / modeled_risk
    )

    total_drag_r = (
        raw_r
        - net_r
    )

    return ScenarioExecutionResult(
        scenario=(
            scenario.name
        ),
        entry_tick_size=(
            entry_tick
        ),
        exit_tick_size=(
            exit_tick
        ),
        modeled_entry_price=round(
            modeled_entry,
            6,
        ),
        modeled_exit_price=round(
            modeled_exit,
            6,
        ),
        modeled_stop_price=round(
            modeled_stop,
            6,
        ),
        gross_r=round(
            gross_r,
            8,
        ),
        net_r=round(
            net_r,
            8,
        ),
        total_drag_r=round(
            total_drag_r,
            8,
        ),
    )


def prepare_execution_sensitivity_rows(
    *,
    inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for item in inputs:
        raw_risk_ticks = (
            calculate_raw_risk_ticks(
                raw_entry_price=float(
                    item[
                        "raw_entry_price"
                    ]
                ),
                raw_stop_price=float(
                    item[
                        "raw_stop_price"
                    ]
                ),
                entry_reference_price=float(
                    item[
                        "entry_reference_price"
                    ]
                ),
            )
        )

        reference_price = float(
            item[
                "entry_reference_price"
            ]
        )

        for scenario in SCENARIOS:
            result = (
                calculate_scenario_execution(
                    raw_entry_price=float(
                        item[
                            "raw_entry_price"
                        ]
                    ),
                    raw_exit_price=float(
                        item[
                            "raw_exit_price"
                        ]
                    ),
                    raw_stop_price=float(
                        item[
                            "raw_stop_price"
                        ]
                    ),
                    entry_reference_price=(
                        reference_price
                    ),
                    exit_reference_price=float(
                        item[
                            "exit_reference_price"
                        ]
                    ),
                    raw_realized_r=float(
                        item[
                            "raw_realized_r"
                        ]
                    ),
                    outcome_label=str(
                        item[
                            "outcome_label"
                        ]
                    ),
                    scenario=scenario,
                )
            )

            rows.append(
                {
                    "signal_id":
                        item[
                            "signal_id"
                        ],

                    "symbol":
                        item[
                            "symbol"
                        ],

                    "sector_code":
                        item[
                            "sector_code"
                        ],

                    "split_label":
                        item[
                            "split_label"
                        ],

                    "outcome_label":
                        item[
                            "outcome_label"
                        ],

                    "scenario":
                        result.scenario,

                    "raw_entry_price":
                        float(
                            item[
                                "raw_entry_price"
                            ]
                        ),

                    "raw_exit_price":
                        float(
                            item[
                                "raw_exit_price"
                            ]
                        ),

                    "raw_stop_price":
                        float(
                            item[
                                "raw_stop_price"
                            ]
                        ),

                    "entry_reference_price":
                        reference_price,

                    "entry_tick_size":
                        result
                        .entry_tick_size,

                    "exit_tick_size":
                        result
                        .exit_tick_size,

                    "raw_risk_ticks":
                        raw_risk_ticks,

                    "price_bucket":
                        price_bucket(
                            reference_price
                        ),

                    "risk_tick_bucket":
                        risk_tick_bucket(
                            raw_risk_ticks
                        ),

                    "liquidity_bucket":
                        liquidity_bucket(
                            item[
                                "liquidity_score"
                            ]
                        ),

                    "setup_risk_pct":
                        (
                            None
                            if item[
                                "setup_risk_pct"
                            ]
                            is None
                            else float(
                                item[
                                    "setup_risk_pct"
                                ]
                            )
                        ),

                    "liquidity_score":
                        (
                            None
                            if item[
                                "liquidity_score"
                            ]
                            is None
                            else float(
                                item[
                                    "liquidity_score"
                                ]
                            )
                        ),

                    "overall_score":
                        (
                            None
                            if item[
                                "overall_score"
                            ]
                            is None
                            else float(
                                item[
                                    "overall_score"
                                ]
                            )
                        ),

                    "raw_realized_r":
                        float(
                            item[
                                "raw_realized_r"
                            ]
                        ),

                    "gross_r":
                        result.gross_r,

                    "net_r":
                        result.net_r,

                    "total_drag_r":
                        result
                        .total_drag_r,

                    "stored_baseline_gross_r":
                        (
                            None
                            if item[
                                "stored_baseline_gross_r"
                            ]
                            is None
                            else float(
                                item[
                                    "stored_baseline_gross_r"
                                ]
                            )
                        ),

                    "stored_baseline_net_r":
                        (
                            None
                            if item[
                                "stored_baseline_net_r"
                            ]
                            is None
                            else float(
                                item[
                                    "stored_baseline_net_r"
                                ]
                            )
                        ),

                    "stored_baseline_drag_r":
                        (
                            None
                            if item[
                                "stored_baseline_drag_r"
                            ]
                            is None
                            else float(
                                item[
                                    "stored_baseline_drag_r"
                                ]
                            )
                        ),
                }
            )

    return rows


def summarize_scenario(
    *,
    rows: list[dict[str, Any]],
    scenario: str,
) -> ScenarioSummary:
    selected = [
        row
        for row in rows
        if row[
            "scenario"
        ]
        == scenario
    ]

    values = [
        float(
            row[
                "net_r"
            ]
        )
        for row in selected
    ]

    drags = [
        float(
            row[
                "total_drag_r"
            ]
        )
        for row in selected
    ]

    positive = sum(
        value > 0
        for value in values
    )

    if values:
        average_r = round(
            statistics.fmean(
                values
            ),
            8,
        )

        median_r = round(
            statistics.median(
                values
            ),
            8,
        )

        positive_rate = round(
            positive
            / len(
                values
            ),
            8,
        )

    else:
        average_r = None
        median_r = None
        positive_rate = None

    average_drag = (
        None
        if not drags
        else round(
            statistics.fmean(
                drags
            ),
            8,
        )
    )

    return ScenarioSummary(
        scenario=scenario,
        trades=len(
            values
        ),
        average_r=(
            average_r
        ),
        median_r=(
            median_r
        ),
        profit_factor=(
            calculate_profit_factor(
                values
            )
        ),
        positive_trades=(
            positive
        ),
        positive_rate=(
            positive_rate
        ),
        average_drag_r=(
            average_drag
        ),
    )


def summarize_all_scenarios(
    rows: list[dict[str, Any]],
) -> list[ScenarioSummary]:
    return [
        summarize_scenario(
            rows=rows,
            scenario=(
                scenario.name
            ),
        )
        for scenario in SCENARIOS
    ]


def summarize_group(
    *,
    rows: list[dict[str, Any]],
    scenario: str,
    group_field: str,
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row[
            "scenario"
        ]
        == scenario
    ]

    grouped: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in selected:
        key = str(
            row[
                group_field
            ]
        )

        grouped.setdefault(
            key,
            [],
        ).append(
            row
        )

    results = []

    for key, group_rows in (
        grouped.items()
    ):
        net_values = [
            float(
                row[
                    "net_r"
                ]
            )
            for row in group_rows
        ]

        raw_values = [
            float(
                row[
                    "raw_realized_r"
                ]
            )
            for row in group_rows
        ]

        drag_values = [
            float(
                row[
                    "total_drag_r"
                ]
            )
            for row in group_rows
        ]

        results.append(
            {
                group_field:
                    key,

                "trades":
                    len(
                        group_rows
                    ),

                "raw_avg_r":
                    round(
                        statistics.fmean(
                            raw_values
                        ),
                        8,
                    ),

                "net_avg_r":
                    round(
                        statistics.fmean(
                            net_values
                        ),
                        8,
                    ),

                "avg_drag_r":
                    round(
                        statistics.fmean(
                            drag_values
                        ),
                        8,
                    ),

                "net_profit_factor":
                    calculate_profit_factor(
                        net_values
                    ),

                "positive_rate":
                    round(
                        sum(
                            value > 0
                            for value
                            in net_values
                        )
                        / len(
                            net_values
                        ),
                        8,
                    ),
            }
        )

    return sorted(
        results,
        key=lambda item: (
            -int(
                item[
                    "trades"
                ]
            ),
            str(
                item[
                    group_field
                ]
            ),
        ),
    )


def _summary_is_positive(
    summary: ScenarioSummary,
) -> bool:
    return (
        summary.average_r
        is not None
        and summary.average_r > 0
        and summary.profit_factor
        is not None
        and summary.profit_factor > 1
    )


def classify_execution_fragility(
    summaries: list[
        ScenarioSummary
    ],
) -> str:
    by_name = {
        summary.scenario:
            summary
        for summary in summaries
    }

    stress = by_name[
        "STRESS_2T"
    ]

    baseline = by_name[
        "BASELINE_CONSERVATIVE"
    ]

    minimum = by_name[
        "MIN_COST_ZERO_SLIPPAGE"
    ]

    tick_only = by_name[
        "TICK_ONLY"
    ]

    if _summary_is_positive(
        stress
    ):
        return "ROBUST_TO_STRESS_2T"

    if _summary_is_positive(
        baseline
    ):
        return "ROBUST_TO_BASELINE"

    if _summary_is_positive(
        minimum
    ):
        return (
            "FRAGILE_TO_EXTRA_"
            "SLIPPAGE"
        )

    if _summary_is_positive(
        tick_only
    ):
        return (
            "NEGATIVE_AFTER_MINIMUM_"
            "FEES_ZERO_EXTRA_SLIPPAGE"
        )

    return (
        "NEGATIVE_AFTER_TICK_"
        "ROUNDING_ONLY"
    )