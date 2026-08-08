import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

TRADE_SETUP_VERSION = "trade_setup_v1"

REFERENCE_CAPITAL_IDR = 100_000_000.0
RISK_BUDGET_PCT = 0.01

IDX_LOT_SIZE = 100

ENTRY_PULLBACK_ATR = 0.50
EXTENDED_ENTRY_LOW_ATR = 1.00
EXTENDED_ENTRY_HIGH_ATR = 0.50

STOP_BUFFER_ATR = 0.25

MAX_EXTENSION_ATR = 2.00
MAX_STRUCTURE_RISK_ATR = 2.50
MAX_PRICE_RISK_PCT = 0.10

TARGET_RR = 2.00
MIN_ACCEPTABLE_RR = 1.50

SETUP_HORIZON_DAYS = 10


TradeSetupDecision = Literal[
    "ACCEPT",
    "WATCH",
    "REJECT",
]

TradeSetupBuildMode = Literal[
    "FULL",
    "INCREMENTAL",
    "UP_TO_DATE",
]


@dataclass(frozen=True)
class PositionSizing:
    shares: int
    lots: int
    capital_required: float
    planned_risk_amount: float


@dataclass(frozen=True)
class TradeSetupResult:
    decision: TradeSetupDecision
    status: str

    entry_low: float | None
    entry_high: float | None
    entry_mid: float | None

    invalidation_price: float | None
    stop_price: float | None
    target_primary: float | None

    expected_rr: float | None

    risk_per_share: float | None
    risk_pct_price: float | None
    structure_risk_atr: float | None
    extension_atr: float | None

    nearest_resistance: float | None

    position_size_shares: int | None
    position_size_lots: int | None
    capital_required: float | None
    planned_risk_amount: float | None

    decision_reasons: tuple[str, ...]


def build_trade_setup_model_version(
    universe_date: date,
) -> str:
    return (
        f"{TRADE_SETUP_VERSION}"
        f"_current_{universe_date:%Y%m%d}"
        "_yahoo_ksei"
    )


def extract_current_universe_date(
    model_version: str,
) -> date:
    match = re.search(
        r"_current_(\d{8})(?:_|$)",
        model_version,
    )

    if match is None:
        raise ValueError(
            "Cannot extract universe date "
            f"from model version: {model_version}"
        )

    return date.fromisoformat(
        
            f"{match.group(1)[0:4]}-"
            f"{match.group(1)[4:6]}-"
            f"{match.group(1)[6:8]}"
        
    )


def _round_price(
    value: float,
) -> float:
    return round(
        float(value),
        6,
    )


def calculate_entry_zone(
    *,
    close: float,
    ema20: float,
    atr14: float,
) -> tuple[
    float,
    float,
    float,
    float,
]:
    if close <= 0:
        raise ValueError(
            "close must be positive."
        )

    if ema20 <= 0:
        raise ValueError(
            "ema20 must be positive."
        )

    if atr14 <= 0:
        raise ValueError(
            "atr14 must be positive."
        )

    extension_atr = (
        close - ema20
    ) / atr14

    if extension_atr > MAX_EXTENSION_ATR:
        entry_low = max(
            ema20,
            close
            - EXTENDED_ENTRY_LOW_ATR
            * atr14,
        )

        entry_high = (
            close
            - EXTENDED_ENTRY_HIGH_ATR
            * atr14
        )

    else:
        entry_low = max(
            ema20,
            close
            - ENTRY_PULLBACK_ATR
            * atr14,
        )

        entry_high = close

    entry_high = max(entry_high, entry_low)

    entry_mid = (
        entry_low
        + entry_high
    ) / 2.0

    return (
        _round_price(
            entry_low
        ),
        _round_price(
            entry_high
        ),
        _round_price(
            entry_mid
        ),
        round(
            extension_atr,
            6,
        ),
    )


def select_nearest_resistance(
    *,
    current_close: float,
    prior_high_20d: float | None,
    prior_high_55d: float | None,
) -> float | None:
    candidates: list[
        float
    ] = []

    for value in (
        prior_high_20d,
        prior_high_55d,
    ):
        if value is None:
            continue

        number = float(
            value
        )

        if number > current_close:
            candidates.append(
                number
            )

    if not candidates:
        return None

    return _round_price(
        min(
            candidates
        )
    )


def calculate_normalized_position_size(
    *,
    entry_mid: float,
    risk_per_share: float,
    reference_capital: float = (
        REFERENCE_CAPITAL_IDR
    ),
    risk_budget_pct: float = (
        RISK_BUDGET_PCT
    ),
    lot_size: int = IDX_LOT_SIZE,
) -> PositionSizing:
    if entry_mid <= 0:
        raise ValueError(
            "entry_mid must be positive."
        )

    if risk_per_share <= 0:
        raise ValueError(
            "risk_per_share must "
            "be positive."
        )

    if reference_capital <= 0:
        raise ValueError(
            "reference_capital must "
            "be positive."
        )

    if not (
        0
        < risk_budget_pct
        <= 1
    ):
        raise ValueError(
            "risk_budget_pct must be "
            "between zero and one."
        )

    if lot_size <= 0:
        raise ValueError(
            "lot_size must be positive."
        )

    risk_budget = (
        reference_capital
        * risk_budget_pct
    )

    risk_per_lot = (
        risk_per_share
        * lot_size
    )

    capital_per_lot = (
        entry_mid
        * lot_size
    )

    lots_by_risk = math.floor(
        risk_budget
        / risk_per_lot
    )

    lots_by_cash = math.floor(
        reference_capital
        / capital_per_lot
    )

    lots = max(
        0,
        min(
            lots_by_risk,
            lots_by_cash,
        ),
    )

    shares = (
        lots
        * lot_size
    )

    capital_required = (
        shares
        * entry_mid
    )

    planned_risk_amount = (
        shares
        * risk_per_share
    )

    return PositionSizing(
        shares=shares,
        lots=lots,
        capital_required=round(
            capital_required,
            2,
        ),
        planned_risk_amount=round(
            planned_risk_amount,
            2,
        ),
    )


def _empty_rejected_result(
    reasons: list[str],
) -> TradeSetupResult:
    return TradeSetupResult(
        decision="REJECT",
        status="AVOID",
        entry_low=None,
        entry_high=None,
        entry_mid=None,
        invalidation_price=None,
        stop_price=None,
        target_primary=None,
        expected_rr=None,
        risk_per_share=None,
        risk_pct_price=None,
        structure_risk_atr=None,
        extension_atr=None,
        nearest_resistance=None,
        position_size_shares=None,
        position_size_lots=None,
        capital_required=None,
        planned_risk_amount=None,
        decision_reasons=tuple(
            reasons
        ),
    )


def calculate_trade_setup(
    *,
    close: float | None,
    ema20: float | None,
    atr14: float | None,
    prior_low_10d: float | None,
    prior_high_20d: float | None,
    prior_high_55d: float | None,
    prior_count_10d: int | None,
) -> TradeSetupResult:
    missing_reasons: list[
        str
    ] = []

    if close is None:
        missing_reasons.append(
            "MISSING_CLOSE"
        )

    if ema20 is None:
        missing_reasons.append(
            "MISSING_EMA20"
        )

    if atr14 is None:
        missing_reasons.append(
            "MISSING_ATR14"
        )

    if prior_low_10d is None:
        missing_reasons.append(
            "MISSING_PRIOR_LOW_10D"
        )

    if prior_count_10d is None:
        missing_reasons.append(
            "MISSING_PRIOR_HISTORY_COUNT"
        )

    if missing_reasons:
        return _empty_rejected_result(
            missing_reasons
        )

    close_value = float(
        close
    )

    ema20_value = float(
        ema20
    )

    atr_value = float(
        atr14
    )

    prior_low = float(
        prior_low_10d
    )

    history_count = int(
        prior_count_10d
    )

    reasons: list[
        str
    ] = []

    if close_value <= 0:
        reasons.append(
            "INVALID_CLOSE"
        )

    if ema20_value <= 0:
        reasons.append(
            "INVALID_EMA20"
        )

    if atr_value <= 0:
        reasons.append(
            "INVALID_ATR14"
        )

    if prior_low <= 0:
        reasons.append(
            "INVALID_PRIOR_LOW_10D"
        )

    if history_count < 10:
        reasons.append(
            "INSUFFICIENT_PRIOR_HISTORY"
        )

    if reasons:
        return _empty_rejected_result(
            reasons
        )

    if close_value <= ema20_value:
        reasons.append(
            "CLOSE_NOT_ABOVE_EMA20"
        )

    (
        entry_low,
        entry_high,
        entry_mid,
        extension_atr,
    ) = calculate_entry_zone(
        close=close_value,
        ema20=ema20_value,
        atr14=atr_value,
    )

    invalidation_price = (
        _round_price(
            prior_low
        )
    )

    stop_price = _round_price(
        prior_low
        - STOP_BUFFER_ATR
        * atr_value
    )

    if stop_price <= 0:
        reasons.append(
            "INVALID_STOP_PRICE"
        )

    if stop_price >= entry_low:
        reasons.append(
            "STOP_NOT_BELOW_ENTRY_ZONE"
        )

    risk_per_share = (
        entry_mid
        - stop_price
    )

    risk_pct_price: (
        float | None
    ) = None

    structure_risk_atr: (
        float | None
    ) = None

    expected_rr: (
        float | None
    ) = None

    target_primary: (
        float | None
    ) = None

    position_size_shares: (
        int | None
    ) = None

    position_size_lots: (
        int | None
    ) = None

    capital_required: (
        float | None
    ) = None

    planned_risk_amount: (
        float | None
    ) = None

    nearest_resistance = (
        select_nearest_resistance(
            current_close=close_value,
            prior_high_20d=(
                prior_high_20d
            ),
            prior_high_55d=(
                prior_high_55d
            ),
        )
    )

    if risk_per_share <= 0:
        reasons.append(
            "NON_POSITIVE_RISK_PER_SHARE"
        )

    else:
        risk_per_share = (
            _round_price(
                risk_per_share
            )
        )

        risk_pct_price = (
            risk_per_share
            / entry_mid
        )

        structure_risk_atr = (
            risk_per_share
            / atr_value
        )

        if (
            structure_risk_atr
            > MAX_STRUCTURE_RISK_ATR
        ):
            reasons.append(
                "STRUCTURE_STOP_TOO_WIDE_ATR"
            )

        if (
            risk_pct_price
            > MAX_PRICE_RISK_PCT
        ):
            reasons.append(
                "STRUCTURE_STOP_TOO_WIDE_PCT"
            )

        rr_target = (
            entry_mid
            + TARGET_RR
            * risk_per_share
        )

        if (
            nearest_resistance
            is None
        ):
            target_primary = (
                rr_target
            )

        else:
            target_primary = min(
                rr_target,
                nearest_resistance,
            )

        target_primary = (
            _round_price(
                target_primary
            )
        )

        if (
            target_primary
            <= entry_high
        ):
            reasons.append(
                "TARGET_NOT_ABOVE_ENTRY_ZONE"
            )

        else:
            expected_rr = (
                target_primary
                - entry_mid
            ) / risk_per_share

            if (
                expected_rr
                < MIN_ACCEPTABLE_RR
            ):
                reasons.append(
                    "INSUFFICIENT_REWARD_RISK"
                )

        sizing = (
            calculate_normalized_position_size(
                entry_mid=entry_mid,
                risk_per_share=(
                    risk_per_share
                ),
            )
        )

        position_size_shares = (
            sizing.shares
        )

        position_size_lots = (
            sizing.lots
        )

        capital_required = (
            sizing.capital_required
        )

        planned_risk_amount = (
            sizing.planned_risk_amount
        )

        if sizing.lots < 1:
            reasons.append(
                
                    "REFERENCE_CAPITAL_"
                    "CANNOT_SIZE_ONE_LOT"
                
            )

    if reasons:
        decision: (
            TradeSetupDecision
        ) = "REJECT"

        status = "AVOID"

        decision_reasons = tuple(
            reasons
        )

    elif (
        extension_atr
        > MAX_EXTENSION_ATR
    ):
        decision = "WATCH"
        status = "WATCH"

        decision_reasons = (
            "PRICE_EXTENDED_FROM_EMA20",
        )

    else:
        decision = "ACCEPT"
        status = "BUY_SETUP"
        decision_reasons = ()

    return TradeSetupResult(
        decision=decision,
        status=status,
        entry_low=entry_low,
        entry_high=entry_high,
        entry_mid=entry_mid,
        invalidation_price=(
            invalidation_price
        ),
        stop_price=stop_price,
        target_primary=(
            target_primary
        ),
        expected_rr=(
            None
            if expected_rr is None
            else round(
                expected_rr,
                6,
            )
        ),
        risk_per_share=(
            None
            if risk_per_share <= 0
            else risk_per_share
        ),
        risk_pct_price=(
            None
            if risk_pct_price is None
            else round(
                risk_pct_price,
                8,
            )
        ),
        structure_risk_atr=(
            None
            if structure_risk_atr
            is None
            else round(
                structure_risk_atr,
                6,
            )
        ),
        extension_atr=round(
            extension_atr,
            6,
        ),
        nearest_resistance=(
            nearest_resistance
        ),
        position_size_shares=(
            position_size_shares
        ),
        position_size_lots=(
            position_size_lots
        ),
        capital_required=(
            capital_required
        ),
        planned_risk_amount=(
            planned_risk_amount
        ),
        decision_reasons=(
            decision_reasons
        ),
    )


def build_trade_setup_thesis(
    result: TradeSetupResult,
) -> str:
    if result.decision == "ACCEPT":
        return (
            "Phase 3I V1 long swing setup "
            "passed deterministic structure, "
            "extension, stop-width, "
            "reward/risk, and normalized "
            "position-sizing gates."
        )

    if result.decision == "WATCH":
        return (
            "Phase 3I V1 candidate remains "
            "on watch because price is "
            "extended from EMA20. The setup "
            "requires a pullback toward the "
            "proposed entry zone before it "
            "can be reconsidered."
        )

    reasons = (
        ", ".join(
            result.decision_reasons
        )
        or "UNSPECIFIED_REJECTION"
    )

    return (
        "Phase 3I V1 candidate was rejected "
        "by deterministic risk or structure "
        f"gates: {reasons}."
    )


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    return float(
        value
    )


def prepare_trade_setup_rows(
    *,
    inputs: list[dict[str, Any]],
    model_version: str,
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        result = calculate_trade_setup(
            close=_optional_float(
                item["close"]
            ),
            ema20=_optional_float(
                item["ema20"]
            ),
            atr14=_optional_float(
                item["atr14"]
            ),
            prior_low_10d=(
                _optional_float(
                    item[
                        "prior_low_10d"
                    ]
                )
            ),
            prior_high_20d=(
                _optional_float(
                    item[
                        "prior_high_20d"
                    ]
                )
            ),
            prior_high_55d=(
                _optional_float(
                    item[
                        "prior_high_55d"
                    ]
                )
            ),
            prior_count_10d=(
                None
                if item[
                    "prior_count_10d"
                ]
                is None
                else int(
                    item[
                        "prior_count_10d"
                    ]
                )
            ),
        )

        warnings = [
            (
                "PHASE3H_BUY_SETUP_IS_"
                "SCREENING_INPUT_ONLY"
            ),
            (
                "YAHOO_EOD_IS_THIRD_PARTY_"
                "MARKET_DATA"
            ),
            (
                "HISTORICAL_KSEI_AS_OF_DATE_"
                "IS_NOT_PUBLICATION_TIME_SAFE"
            ),
            (
                "CURRENT_UNIVERSE_HISTORY_"
                "IS_SURVIVORSHIP_BIASED"
            ),
            (
                "IDX_PRICE_TICK_LADDER_"
                "NOT_MODELED_IN_V1"
            ),
            (
                "IDX_DAILY_PRICE_LIMITS_"
                "NOT_MODELED_IN_V1"
            ),
            (
                "POSITION_SIZING_IS_"
                "NORMALIZED_NOT_ACCOUNT_SPECIFIC"
            ),
            (
                "PROBABILITY_AND_EXPECTED_VALUE_"
                "ARE_NOT_CALIBRATED"
            ),
        ]

        if result.decision == "WATCH":
            warnings.append(
                "WAIT_FOR_PULLBACK_CONFIRMATION"
            )

        evidence = {
            "scope":
                "trade_setup_v1",

            "semantics":
                (
                    "deterministic_research_"
                    "trade_setup"
                ),

            "symbol":
                item["symbol"],

            "sector_code":
                item["sector_code"],

            "screening_input": {
                "model_version":
                    item[
                        "screener_model_version"
                    ],
                "overall_score":
                    _optional_float(
                        item[
                            "overall_score"
                        ]
                    ),
                "market_score":
                    _optional_float(
                        item[
                            "market_score"
                        ]
                    ),
                "sector_score":
                    _optional_float(
                        item[
                            "sector_score"
                        ]
                    ),
                "technical_score":
                    _optional_float(
                        item[
                            "technical_score"
                        ]
                    ),
                "liquidity_score":
                    _optional_float(
                        item[
                            "liquidity_score"
                        ]
                    ),
                "ownership_score":
                    _optional_float(
                        item[
                            "ownership_score"
                        ]
                    ),
                "risk_score":
                    _optional_float(
                        item[
                            "risk_score"
                        ]
                    ),
                "data_completeness":
                    _optional_float(
                        item[
                            "data_completeness"
                        ]
                    ),
            },

            "price_structure": {
                "close":
                    _optional_float(
                        item["close"]
                    ),
                "ema20":
                    _optional_float(
                        item["ema20"]
                    ),
                "ema50":
                    _optional_float(
                        item["ema50"]
                    ),
                "rsi14":
                    _optional_float(
                        item["rsi14"]
                    ),
                "atr14":
                    _optional_float(
                        item["atr14"]
                    ),
                "prior_low_10d":
                    _optional_float(
                        item[
                            "prior_low_10d"
                        ]
                    ),
                "prior_high_20d":
                    _optional_float(
                        item[
                            "prior_high_20d"
                        ]
                    ),
                "prior_high_55d":
                    _optional_float(
                        item[
                            "prior_high_55d"
                        ]
                    ),
                "prior_count_10d":
                    (
                        None
                        if item[
                            "prior_count_10d"
                        ]
                        is None
                        else int(
                            item[
                                "prior_count_10d"
                            ]
                        )
                    ),
                "extension_atr":
                    result.extension_atr,
                "structure_risk_atr":
                    result
                    .structure_risk_atr,
                "nearest_resistance":
                    result
                    .nearest_resistance,
                "breakout_flag":
                    (
                        None
                        if item[
                            "breakout_flag"
                        ]
                        is None
                        else bool(
                            item[
                                "breakout_flag"
                            ]
                        )
                    ),
                "failed_breakout_flag":
                    (
                        None
                        if item[
                            "failed_breakout_flag"
                        ]
                        is None
                        else bool(
                            item[
                                "failed_breakout_flag"
                            ]
                        )
                    ),
            },

            "setup": {
                "decision":
                    result.decision,
                "entry_low":
                    result.entry_low,
                "entry_high":
                    result.entry_high,
                "entry_mid":
                    result.entry_mid,
                "invalidation_price":
                    result
                    .invalidation_price,
                "stop_price":
                    result.stop_price,
                "target_primary":
                    result
                    .target_primary,
                "expected_rr":
                    result.expected_rr,
                "risk_per_share":
                    result
                    .risk_per_share,
                "risk_pct_price":
                    result
                    .risk_pct_price,
                "horizon_days":
                    SETUP_HORIZON_DAYS,
                "decision_reasons":
                    list(
                        result
                        .decision_reasons
                    ),
            },

            "position_sizing": {
                "reference_capital":
                    REFERENCE_CAPITAL_IDR,
                "risk_budget_pct":
                    RISK_BUDGET_PCT,
                "lot_size":
                    IDX_LOT_SIZE,
                "position_size_shares":
                    result
                    .position_size_shares,
                "position_size_lots":
                    result
                    .position_size_lots,
                "capital_required":
                    result
                    .capital_required,
                "planned_risk_amount":
                    result
                    .planned_risk_amount,
                "normalization_only":
                    True,
            },

            "rules": {
                "entry_pullback_atr":
                    ENTRY_PULLBACK_ATR,
                "stop_buffer_atr":
                    STOP_BUFFER_ATR,
                "max_extension_atr":
                    MAX_EXTENSION_ATR,
                "max_structure_risk_atr":
                    MAX_STRUCTURE_RISK_ATR,
                "max_price_risk_pct":
                    MAX_PRICE_RISK_PCT,
                "target_rr":
                    TARGET_RR,
                "minimum_rr":
                    MIN_ACCEPTABLE_RR,
            },

            "warnings":
                warnings,
        }

        rows.append(
            {
                "instrument_id":
                    item[
                        "instrument_id"
                    ],

                "symbol":
                    item["symbol"],

                "sector_code":
                    item[
                        "sector_code"
                    ],

                "trading_date":
                    item[
                        "trading_date"
                    ],

                "status":
                    result.status,

                "entry_low":
                    result.entry_low,

                "entry_high":
                    result.entry_high,

                "invalidation_price":
                    result
                    .invalidation_price,

                "stop_price":
                    result.stop_price,

                "target_primary":
                    result
                    .target_primary,

                "expected_rr":
                    result.expected_rr,

                "probability_tp_before_sl":
                    None,

                "expected_value_r":
                    None,

                "horizon_days":
                    SETUP_HORIZON_DAYS,

                "confidence":
                    None,

                "thesis":
                    build_trade_setup_thesis(
                        result
                    ),

                "evidence":
                    evidence,

                "model_version":
                    model_version,

                "is_frozen":
                    False,

                "setup_decision":
                    result.decision,

                "risk_per_share":
                    result
                    .risk_per_share,

                "risk_pct_price":
                    result
                    .risk_pct_price,

                "reference_capital":
                    REFERENCE_CAPITAL_IDR,

                "risk_budget_pct":
                    RISK_BUDGET_PCT,

                "position_size_shares":
                    result
                    .position_size_shares,

                "position_size_lots":
                    result
                    .position_size_lots,

                "capital_required":
                    result
                    .capital_required,

                "input_updated_at":
                    item[
                        "input_updated_at"
                    ],

                "decision_reasons":
                    list(
                        result
                        .decision_reasons
                    ),
            }
        )

    return rows


def resolve_trade_setup_build_mode(
    *,
    force: bool,
    state_exists: bool,
    input_model_matches: bool,
    processed_through: date | None,
    latest_input_date: date,
    stored_rows: int,
    state_output_rows: int,
    expected_rows: int,
    stored_processed_input_updated_at: Any,
    current_processed_input_updated_at: Any,
) -> TradeSetupBuildMode:
    if force:
        return "FULL"

    if not state_exists:
        return "FULL"

    if not input_model_matches:
        return "FULL"

    if processed_through is None:
        return "FULL"

    if processed_through > latest_input_date:
        raise RuntimeError(
            "Trade setup build state is "
            "ahead of upstream stock "
            "screener input."
        )

    if stored_rows != state_output_rows:
        return "FULL"

    if processed_through == latest_input_date:
        if stored_rows != expected_rows:
            return "FULL"

        if (
            stored_processed_input_updated_at
            != current_processed_input_updated_at
        ):
            return "FULL"

        return "UP_TO_DATE"

    if (
        stored_processed_input_updated_at
        != current_processed_input_updated_at
    ):
        return "FULL"

    return "INCREMENTAL"