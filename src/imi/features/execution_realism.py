import statistics
from dataclasses import dataclass
from datetime import date
from decimal import (
    ROUND_CEILING,
    ROUND_FLOOR,
    Decimal,
)
from typing import Any, Literal

EXECUTION_REALISM_VERSION = (
    "execution_realism_v1"
)

IDX_BUY_INFRASTRUCTURE_FEE_RATE = (
    0.000433
)

IDX_SELL_INFRASTRUCTURE_FEE_RATE = (
    0.001433
)

ENTRY_SLIPPAGE_TICKS = 1

TARGET_EXIT_SLIPPAGE_TICKS = 0
STOP_EXIT_SLIPPAGE_TICKS = 1
EXPIRED_EXIT_SLIPPAGE_TICKS = 1

BROKER_COMMISSION_MODELED = False
AUTO_REJECTION_MODELED = False
CORPORATE_ACTION_HISTORY_COMPLETE = False


ExecutionBuildMode = Literal[
    "FULL",
    "REFRESH",
    "UP_TO_DATE",
]


@dataclass(frozen=True)
class ExecutionResult:
    raw_entry_price: float
    raw_exit_price: float
    raw_stop_price: float

    entry_reference_price: float
    exit_reference_price: float

    entry_tick_size: float
    exit_tick_size: float

    modeled_entry_price: float
    modeled_exit_price: float
    modeled_stop_price: float

    entry_slippage_ticks: int
    exit_slippage_ticks: int

    gross_modeled_return: float
    gross_modeled_r: float

    net_modeled_return: float
    net_realized_r: float

    slippage_drag_r: float
    fee_drag_r: float
    total_cost_drag_r: float


@dataclass(frozen=True)
class ExecutionSummary:
    total_rows: int
    mature_trades: int

    execution_metrics_available: int
    strict_eligible: int

    target_trades: int
    stop_trades: int
    expired_trades: int

    raw_average_r: float | None
    gross_average_r: float | None
    net_average_r: float | None

    raw_median_r: float | None
    net_median_r: float | None

    raw_profit_factor: float | None
    net_profit_factor: float | None

    average_slippage_drag_r: float | None
    average_fee_drag_r: float | None
    average_total_drag_r: float | None

    baseline_edge_positive: bool


def build_execution_realism_model_version(
    universe_date: date,
) -> str:
    return (
        f"{EXECUTION_REALISM_VERSION}"
        f"_current_{universe_date:%Y%m%d}"
        "_idx_eod"
    )


def _decimal(
    value: float | Decimal,
) -> Decimal:
    return Decimal(
        str(
            value
        )
    )


def _round_float(
    value: float,
    digits: int = 8,
) -> float:
    return round(
        float(
            value
        ),
        digits,
    )


def idx_price_fraction(
    reference_price: float,
) -> float:
    price = float(
        reference_price
    )

    if price <= 0:
        raise ValueError(
            "reference_price must "
            "be positive."
        )

    if price < 200.0:
        return 1.0

    if price < 500.0:
        return 2.0

    if price < 2000.0:
        return 5.0

    if price < 5000.0:
        return 10.0

    return 25.0


def round_to_tick(
    *,
    price: float,
    tick_size: float,
    direction: Literal[
        "UP",
        "DOWN",
    ],
) -> float:
    if price <= 0:
        raise ValueError(
            "price must be positive."
        )

    if tick_size <= 0:
        raise ValueError(
            "tick_size must be positive."
        )

    decimal_price = _decimal(
        price
    )

    decimal_tick = _decimal(
        tick_size
    )

    units = (
        decimal_price
        / decimal_tick
    )

    if direction == "UP":
        rounded_units = (
            units.to_integral_value(
                rounding=ROUND_CEILING
            )
        )

    elif direction == "DOWN":
        rounded_units = (
            units.to_integral_value(
                rounding=ROUND_FLOOR
            )
        )

    else:
        raise ValueError(
            "direction must be "
            "UP or DOWN."
        )

    result = (
        rounded_units
        * decimal_tick
    )

    return float(
        result
    )


def apply_buy_slippage(
    *,
    raw_price: float,
    reference_price: float,
    slippage_ticks: int = (
        ENTRY_SLIPPAGE_TICKS
    ),
) -> tuple[
    float,
    float,
]:
    if slippage_ticks < 0:
        raise ValueError(
            "slippage_ticks cannot "
            "be negative."
        )

    tick = idx_price_fraction(
        reference_price
    )

    valid_price = round_to_tick(
        price=raw_price,
        tick_size=tick,
        direction="UP",
    )

    modeled = (
        valid_price
        + tick
        * slippage_ticks
    )

    return (
        _round_float(
            modeled,
            6,
        ),
        tick,
    )


def apply_sell_execution(
    *,
    raw_price: float,
    reference_price: float,
    slippage_ticks: int,
) -> tuple[
    float,
    float,
]:
    if slippage_ticks < 0:
        raise ValueError(
            "slippage_ticks cannot "
            "be negative."
        )

    tick = idx_price_fraction(
        reference_price
    )

    valid_price = round_to_tick(
        price=raw_price,
        tick_size=tick,
        direction="DOWN",
    )

    modeled = (
        valid_price
        - tick
        * slippage_ticks
    )

    if modeled <= 0:
        raise ValueError(
            "Modeled sell price became "
            "non-positive."
        )

    return (
        _round_float(
            modeled,
            6,
        ),
        tick,
    )


def exit_slippage_ticks_for_outcome(
    outcome_label: str,
) -> int:
    if outcome_label == "TARGET":
        return (
            TARGET_EXIT_SLIPPAGE_TICKS
        )

    if outcome_label == "STOP":
        return (
            STOP_EXIT_SLIPPAGE_TICKS
        )

    if outcome_label == "EXPIRED":
        return (
            EXPIRED_EXIT_SLIPPAGE_TICKS
        )

    raise ValueError(
        "Execution metrics only support "
        "TARGET, STOP, and EXPIRED."
    )


def calculate_profit_factor(
    values: list[float],
) -> float | None:
    gross_profit = sum(
        value
        for value in values
        if value > 0
    )

    gross_loss = abs(
        sum(
            value
            for value in values
            if value < 0
        )
    )

    if gross_loss == 0:
        return None

    return _round_float(
        gross_profit
        / gross_loss
    )


def calculate_execution_result(
    *,
    raw_entry_price: float,
    raw_exit_price: float,
    raw_stop_price: float,
    entry_reference_price: float,
    exit_reference_price: float,
    raw_realized_r: float,
    outcome_label: str,
) -> ExecutionResult:
    if outcome_label not in {
        "TARGET",
        "STOP",
        "EXPIRED",
    }:
        raise ValueError(
            "Execution result requires "
            "a mature trade outcome."
        )

    if raw_entry_price <= 0:
        raise ValueError(
            "raw_entry_price must "
            "be positive."
        )

    if raw_exit_price <= 0:
        raise ValueError(
            "raw_exit_price must "
            "be positive."
        )

    if raw_stop_price <= 0:
        raise ValueError(
            "raw_stop_price must "
            "be positive."
        )

    modeled_entry, entry_tick = (
        apply_buy_slippage(
            raw_price=(
                raw_entry_price
            ),
            reference_price=(
                entry_reference_price
            ),
        )
    )

    modeled_stop = round_to_tick(
        price=raw_stop_price,
        tick_size=entry_tick,
        direction="DOWN",
    )

    exit_ticks = (
        exit_slippage_ticks_for_outcome(
            outcome_label
        )
    )

    modeled_exit, exit_tick = (
        apply_sell_execution(
            raw_price=(
                raw_exit_price
            ),
            reference_price=(
                exit_reference_price
            ),
            slippage_ticks=(
                exit_ticks
            ),
        )
    )

    modeled_risk = (
        modeled_entry
        - modeled_stop
    )

    if modeled_risk <= 0:
        raise ValueError(
            "Modeled risk per share "
            "must be positive."
        )

    gross_pnl = (
        modeled_exit
        - modeled_entry
    )

    gross_return = (
        gross_pnl
        / modeled_entry
    )

    gross_r = (
        gross_pnl
        / modeled_risk
    )

    buy_cost = (
        modeled_entry
        * IDX_BUY_INFRASTRUCTURE_FEE_RATE
    )

    sell_cost = (
        modeled_exit
        * IDX_SELL_INFRASTRUCTURE_FEE_RATE
    )

    net_pnl = (
        modeled_exit
        - sell_cost
        - modeled_entry
        - buy_cost
    )

    invested_cash = (
        modeled_entry
        + buy_cost
    )

    net_return = (
        net_pnl
        / invested_cash
    )

    net_r = (
        net_pnl
        / modeled_risk
    )

    slippage_drag_r = (
        raw_realized_r
        - gross_r
    )

    fee_drag_r = (
        gross_r
        - net_r
    )

    total_cost_drag_r = (
        raw_realized_r
        - net_r
    )

    return ExecutionResult(
        raw_entry_price=(
            _round_float(
                raw_entry_price,
                6,
            )
        ),
        raw_exit_price=(
            _round_float(
                raw_exit_price,
                6,
            )
        ),
        raw_stop_price=(
            _round_float(
                raw_stop_price,
                6,
            )
        ),
        entry_reference_price=(
            _round_float(
                entry_reference_price,
                6,
            )
        ),
        exit_reference_price=(
            _round_float(
                exit_reference_price,
                6,
            )
        ),
        entry_tick_size=(
            entry_tick
        ),
        exit_tick_size=(
            exit_tick
        ),
        modeled_entry_price=(
            modeled_entry
        ),
        modeled_exit_price=(
            modeled_exit
        ),
        modeled_stop_price=(
            _round_float(
                modeled_stop,
                6,
            )
        ),
        entry_slippage_ticks=(
            ENTRY_SLIPPAGE_TICKS
        ),
        exit_slippage_ticks=(
            exit_ticks
        ),
        gross_modeled_return=(
            _round_float(
                gross_return
            )
        ),
        gross_modeled_r=(
            _round_float(
                gross_r
            )
        ),
        net_modeled_return=(
            _round_float(
                net_return
            )
        ),
        net_realized_r=(
            _round_float(
                net_r
            )
        ),
        slippage_drag_r=(
            _round_float(
                slippage_drag_r
            )
        ),
        fee_drag_r=(
            _round_float(
                fee_drag_r
            )
        ),
        total_cost_drag_r=(
            _round_float(
                total_cost_drag_r
            )
        ),
    )


def _warning_set(
    evidence: Any,
) -> set[str]:
    if not isinstance(
        evidence,
        dict,
    ):
        return set()

    warnings = evidence.get(
        "warnings",
        [],
    )

    if not isinstance(
        warnings,
        list,
    ):
        return set()

    return {
        str(
            warning
        )
        for warning in warnings
    }


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    return float(
        value
    )


def _mean(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return _round_float(
        statistics.fmean(
            values
        )
    )


def _median(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return _round_float(
        statistics.median(
            values
        )
    )


def prepare_execution_realism_rows(
    *,
    inputs: list[dict[str, Any]],
    model_version: str,
) -> list[dict[str, Any]]:
    rows = []

    for item in inputs:
        warnings = _warning_set(
            item[
                "calibration_evidence"
            ]
        )

        point_in_time_safe = (
            (
                "HISTORICAL_KSEI_AS_OF_DATE_"
                "IS_NOT_PUBLICATION_TIME_SAFE"
            )
            not in warnings
        )

        survivorship_safe = (
            (
                "CURRENT_UNIVERSE_HISTORY_"
                "IS_SURVIVORSHIP_BIASED"
            )
            not in warnings
        )

        sample_status = str(
            item[
                "sample_status"
            ]
        )

        outcome_label = str(
            item[
                "outcome_label"
            ]
        )

        blocking_reasons = []

        if not point_in_time_safe:
            blocking_reasons.append(
                
                    "POINT_IN_TIME_KSEI_"
                    "NOT_SAFE"
                
            )

        if not survivorship_safe:
            blocking_reasons.append(
                
                    "CURRENT_UNIVERSE_"
                    "SURVIVORSHIP_BIAS"
                
            )

        if not CORPORATE_ACTION_HISTORY_COMPLETE:
            blocking_reasons.append(
                
                    "CORPORATE_ACTION_"
                    "HISTORY_NOT_COMPLETE"
                
            )

        if bool(
            item[
                "corporate_action_overlap_detected"
            ]
        ):
            blocking_reasons.append(
                
                    "CORPORATE_ACTION_"
                    "OVERLAP_DETECTED"
                
            )

        if not BROKER_COMMISSION_MODELED:
            blocking_reasons.append(
                
                    "BROKER_COMMISSION_"
                    "NOT_MODELED"
                
            )

        if not AUTO_REJECTION_MODELED:
            blocking_reasons.append(
                
                    "BOARD_SPECIFIC_"
                    "AUTO_REJECTION_NOT_MODELED"
                
            )

        execution_result = None

        if (
            sample_status
            == "MATURE_TRADE"
        ):
            required = {
                "raw_entry_price":
                    item[
                        "raw_entry_price"
                    ],
                "raw_exit_price":
                    item[
                        "raw_exit_price"
                    ],
                "raw_stop_price":
                    item[
                        "raw_stop_price"
                    ],
                "entry_reference_price":
                    item[
                        "entry_reference_price"
                    ],
                "exit_reference_price":
                    item[
                        "exit_reference_price"
                    ],
                "raw_realized_r":
                    item[
                        "raw_realized_r"
                    ],
            }

            missing = [
                key
                for key, value
                in required.items()
                if value is None
            ]

            if missing:
                blocking_reasons.append(
                    
                        "EXECUTION_INPUT_MISSING:"
                        + ",".join(
                            sorted(
                                missing
                            )
                        )
                    
                )

            else:
                execution_result = (
                    calculate_execution_result(
                        raw_entry_price=float(
                            required[
                                "raw_entry_price"
                            ]
                        ),
                        raw_exit_price=float(
                            required[
                                "raw_exit_price"
                            ]
                        ),
                        raw_stop_price=float(
                            required[
                                "raw_stop_price"
                            ]
                        ),
                        entry_reference_price=float(
                            required[
                                "entry_reference_price"
                            ]
                        ),
                        exit_reference_price=float(
                            required[
                                "exit_reference_price"
                            ]
                        ),
                        raw_realized_r=float(
                            required[
                                "raw_realized_r"
                            ]
                        ),
                        outcome_label=(
                            outcome_label
                        ),
                    )
                )

        execution_metrics_available = (
            execution_result
            is not None
        )

        tick_size_modeled = (
            execution_metrics_available
        )

        exchange_costs_modeled = (
            execution_metrics_available
        )

        slippage_modeled = (
            execution_metrics_available
        )

        strict_calibration_eligible = (
            bool(
                item[
                    "calibration_eligible"
                ]
            )
            and execution_metrics_available
            and point_in_time_safe
            and survivorship_safe
            and CORPORATE_ACTION_HISTORY_COMPLETE
            and not bool(
                item[
                    "corporate_action_overlap_detected"
                ]
            )
            and BROKER_COMMISSION_MODELED
            and AUTO_REJECTION_MODELED
        )

        if (
            bool(
                item[
                    "calibration_eligible"
                ]
            )
            and not execution_metrics_available
        ):
            blocking_reasons.append(
                
                    "EXECUTION_METRICS_"
                    "UNAVAILABLE"
                
            )

        evidence = {
            "scope":
                "execution_realism_v1",

            "execution_assumptions": {
                "price_fraction":
                    (
                        "IDX regular/cash "
                        "market fraction ladder"
                    ),
                "fraction_reference":
                    (
                        "previous_close for "
                        "the execution day"
                    ),
                "entry_slippage_ticks":
                    ENTRY_SLIPPAGE_TICKS,
                "target_exit_slippage_ticks":
                    (
                        TARGET_EXIT_SLIPPAGE_TICKS
                    ),
                "stop_exit_slippage_ticks":
                    (
                        STOP_EXIT_SLIPPAGE_TICKS
                    ),
                "expired_exit_slippage_ticks":
                    (
                        EXPIRED_EXIT_SLIPPAGE_TICKS
                    ),
                "buy_infrastructure_fee_rate":
                    (
                        IDX_BUY_INFRASTRUCTURE_FEE_RATE
                    ),
                "sell_infrastructure_fee_rate":
                    (
                        IDX_SELL_INFRASTRUCTURE_FEE_RATE
                    ),
                "broker_commission_included":
                    False,
            },

            "data_quality": {
                "point_in_time_safe":
                    point_in_time_safe,
                "survivorship_safe":
                    survivorship_safe,
                "corporate_action_history_complete":
                    (
                        CORPORATE_ACTION_HISTORY_COMPLETE
                    ),
                "corporate_action_overlap_detected":
                    bool(
                        item[
                            "corporate_action_overlap_detected"
                        ]
                    ),
                "board_specific_auto_rejection_modeled":
                    AUTO_REJECTION_MODELED,
            },

            "source_versions": {
                "calibration_dataset_version":
                    item[
                        "calibration_dataset_version"
                    ],
                "outcome_model_version":
                    item[
                        "outcome_model_version"
                    ],
                "trade_setup_model_version":
                    item[
                        "trade_setup_model_version"
                    ],
            },

            "blocking_reasons":
                blocking_reasons,

            "warnings": [
                (
                    "RESEARCH_EXECUTION_"
                    "REALISM_LAYER_ONLY"
                ),
                (
                    "BROKER_SPECIFIC_FEE_"
                    "NOT_INCLUDED"
                ),
                (
                    "ORDER_BOOK_AND_INTRADAY_"
                    "SEQUENCE_NOT_AVAILABLE"
                ),
            ],
        }

        if execution_result is None:
            raw_entry_price = (
                _optional_float(
                    item[
                        "raw_entry_price"
                    ]
                )
            )

            raw_exit_price = (
                _optional_float(
                    item[
                        "raw_exit_price"
                    ]
                )
            )

            raw_stop_price = (
                _optional_float(
                    item[
                        "raw_stop_price"
                    ]
                )
            )

            entry_reference_price = (
                _optional_float(
                    item[
                        "entry_reference_price"
                    ]
                )
            )

            exit_reference_price = (
                _optional_float(
                    item[
                        "exit_reference_price"
                    ]
                )
            )

            entry_tick_size = None
            exit_tick_size = None

            modeled_entry_price = None
            modeled_exit_price = None
            modeled_stop_price = None

            entry_slippage_ticks = None
            exit_slippage_ticks = None

            gross_modeled_return = None
            gross_modeled_r = None
            net_modeled_return = None
            net_realized_r = None

            slippage_drag_r = None
            fee_drag_r = None
            total_cost_drag_r = None

        else:
            raw_entry_price = (
                execution_result
                .raw_entry_price
            )

            raw_exit_price = (
                execution_result
                .raw_exit_price
            )

            raw_stop_price = (
                execution_result
                .raw_stop_price
            )

            entry_reference_price = (
                execution_result
                .entry_reference_price
            )

            exit_reference_price = (
                execution_result
                .exit_reference_price
            )

            entry_tick_size = (
                execution_result
                .entry_tick_size
            )

            exit_tick_size = (
                execution_result
                .exit_tick_size
            )

            modeled_entry_price = (
                execution_result
                .modeled_entry_price
            )

            modeled_exit_price = (
                execution_result
                .modeled_exit_price
            )

            modeled_stop_price = (
                execution_result
                .modeled_stop_price
            )

            entry_slippage_ticks = (
                execution_result
                .entry_slippage_ticks
            )

            exit_slippage_ticks = (
                execution_result
                .exit_slippage_ticks
            )

            gross_modeled_return = (
                execution_result
                .gross_modeled_return
            )

            gross_modeled_r = (
                execution_result
                .gross_modeled_r
            )

            net_modeled_return = (
                execution_result
                .net_modeled_return
            )

            net_realized_r = (
                execution_result
                .net_realized_r
            )

            slippage_drag_r = (
                execution_result
                .slippage_drag_r
            )

            fee_drag_r = (
                execution_result
                .fee_drag_r
            )

            total_cost_drag_r = (
                execution_result
                .total_cost_drag_r
            )

        rows.append(
            {
                "signal_id":
                    item["signal_id"],

                "model_version":
                    model_version,

                "calibration_dataset_version":
                    item[
                        "calibration_dataset_version"
                    ],

                "instrument_id":
                    item[
                        "instrument_id"
                    ],

                "signal_date":
                    item[
                        "signal_date"
                    ],

                "sector_code":
                    item[
                        "sector_code"
                    ],

                "sample_status":
                    sample_status,

                "split_label":
                    item[
                        "split_label"
                    ],

                "outcome_label":
                    outcome_label,

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

                "entry_tick_size":
                    entry_tick_size,

                "exit_tick_size":
                    exit_tick_size,

                "modeled_entry_price":
                    modeled_entry_price,

                "modeled_exit_price":
                    modeled_exit_price,

                "modeled_stop_price":
                    modeled_stop_price,

                "buy_fee_rate":
                    (
                        IDX_BUY_INFRASTRUCTURE_FEE_RATE
                        if execution_metrics_available
                        else None
                    ),

                "sell_fee_rate":
                    (
                        IDX_SELL_INFRASTRUCTURE_FEE_RATE
                        if execution_metrics_available
                        else None
                    ),

                "entry_slippage_ticks":
                    entry_slippage_ticks,

                "exit_slippage_ticks":
                    exit_slippage_ticks,

                "raw_realized_return":
                    _optional_float(
                        item[
                            "raw_realized_return"
                        ]
                    ),

                "raw_realized_r":
                    _optional_float(
                        item[
                            "raw_realized_r"
                        ]
                    ),

                "gross_modeled_return":
                    gross_modeled_return,

                "gross_modeled_r":
                    gross_modeled_r,

                "net_modeled_return":
                    net_modeled_return,

                "net_realized_r":
                    net_realized_r,

                "slippage_drag_r":
                    slippage_drag_r,

                "fee_drag_r":
                    fee_drag_r,

                "total_cost_drag_r":
                    total_cost_drag_r,

                "execution_metrics_available":
                    execution_metrics_available,

                "tick_size_modeled":
                    tick_size_modeled,

                "exchange_costs_modeled":
                    exchange_costs_modeled,

                "slippage_modeled":
                    slippage_modeled,

                "broker_commission_modeled":
                    BROKER_COMMISSION_MODELED,

                "auto_rejection_modeled":
                    AUTO_REJECTION_MODELED,

                "point_in_time_safe":
                    point_in_time_safe,

                "survivorship_safe":
                    survivorship_safe,

                "corporate_action_overlap_detected":
                    bool(
                        item[
                            "corporate_action_overlap_detected"
                        ]
                    ),

                "corporate_action_history_complete":
                    (
                        CORPORATE_ACTION_HISTORY_COMPLETE
                    ),

                "strict_calibration_eligible":
                    strict_calibration_eligible,

                "blocking_reasons":
                    blocking_reasons,

                "input_updated_at":
                    item[
                        "input_updated_at"
                    ],

                "evidence":
                    evidence,
            }
        )

    return rows


def compute_execution_summary(
    rows: list[dict[str, Any]],
) -> ExecutionSummary:
    mature = [
        row
        for row in rows
        if row[
            "sample_status"
        ]
        == "MATURE_TRADE"
    ]

    available = [
        row
        for row in mature
        if bool(
            row[
                "execution_metrics_available"
            ]
        )
    ]

    raw_values = [
        float(
            row[
                "raw_realized_r"
            ]
        )
        for row in available
        if row[
            "raw_realized_r"
        ]
        is not None
    ]

    gross_values = [
        float(
            row[
                "gross_modeled_r"
            ]
        )
        for row in available
        if row[
            "gross_modeled_r"
        ]
        is not None
    ]

    net_values = [
        float(
            row[
                "net_realized_r"
            ]
        )
        for row in available
        if row[
            "net_realized_r"
        ]
        is not None
    ]

    slippage_drags = [
        float(
            row[
                "slippage_drag_r"
            ]
        )
        for row in available
        if row[
            "slippage_drag_r"
        ]
        is not None
    ]

    fee_drags = [
        float(
            row[
                "fee_drag_r"
            ]
        )
        for row in available
        if row[
            "fee_drag_r"
        ]
        is not None
    ]

    total_drags = [
        float(
            row[
                "total_cost_drag_r"
            ]
        )
        for row in available
        if row[
            "total_cost_drag_r"
        ]
        is not None
    ]

    target_count = sum(
        row[
            "outcome_label"
        ]
        == "TARGET"
        for row in mature
    )

    stop_count = sum(
        row[
            "outcome_label"
        ]
        == "STOP"
        for row in mature
    )

    expired_count = sum(
        row[
            "outcome_label"
        ]
        == "EXPIRED"
        for row in mature
    )

    strict_eligible = sum(
        bool(
            row[
                "strict_calibration_eligible"
            ]
        )
        for row in rows
    )

    net_average = _mean(
        net_values
    )

    net_profit_factor = (
        calculate_profit_factor(
            net_values
        )
    )

    baseline_edge_positive = (
        net_average is not None
        and net_average > 0
        and net_profit_factor is not None
        and net_profit_factor > 1
    )

    return ExecutionSummary(
        total_rows=len(
            rows
        ),
        mature_trades=len(
            mature
        ),
        execution_metrics_available=len(
            available
        ),
        strict_eligible=(
            strict_eligible
        ),
        target_trades=(
            target_count
        ),
        stop_trades=(
            stop_count
        ),
        expired_trades=(
            expired_count
        ),
        raw_average_r=_mean(
            raw_values
        ),
        gross_average_r=_mean(
            gross_values
        ),
        net_average_r=(
            net_average
        ),
        raw_median_r=_median(
            raw_values
        ),
        net_median_r=_median(
            net_values
        ),
        raw_profit_factor=(
            calculate_profit_factor(
                raw_values
            )
        ),
        net_profit_factor=(
            net_profit_factor
        ),
        average_slippage_drag_r=(
            _mean(
                slippage_drags
            )
        ),
        average_fee_drag_r=(
            _mean(
                fee_drags
            )
        ),
        average_total_drag_r=(
            _mean(
                total_drags
            )
        ),
        baseline_edge_positive=(
            baseline_edge_positive
        ),
    )


def resolve_execution_build_mode(
    *,
    force: bool,
    state_exists: bool,
    input_model_matches: bool,
    stored_rows: int,
    expected_rows: int,
    processed_through: date | None,
    latest_input_date: date,
    stored_input_updated_at: Any,
    current_input_updated_at: Any,
) -> ExecutionBuildMode:
    if force:
        return "FULL"

    if not state_exists:
        return "FULL"

    if not input_model_matches:
        return "FULL"

    if stored_rows != expected_rows:
        return "FULL"

    if processed_through is None:
        return "FULL"

    if processed_through > latest_input_date:
        raise RuntimeError(
            "Execution realism build "
            "state is ahead of input."
        )

    if (
        processed_through
        == latest_input_date
        and stored_input_updated_at
        == current_input_updated_at
    ):
        return "UP_TO_DATE"

    return "REFRESH"