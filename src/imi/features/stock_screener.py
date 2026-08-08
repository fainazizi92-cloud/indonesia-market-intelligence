from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

STOCK_SCREENER_VERSION = "stock_screener_v1"

MARKET_WEIGHT = 0.15
SECTOR_WEIGHT = 0.20
TECHNICAL_WEIGHT = 0.35
LIQUIDITY_WEIGHT = 0.10
OWNERSHIP_WEIGHT = 0.10
RISK_WEIGHT = 0.10

OWNERSHIP_STALE_DAYS = 45

RS_REFERENCE = 0.20


StockScreenerBuildMode = Literal[
    "FULL",
    "INCREMENTAL",
    "UP_TO_DATE",
]


MARKET_REGIME_BASE_SCORE = {
    "STRONG_BULL": 90.0,
    "BULL": 80.0,
    "SIDEWAYS_BULL": 65.0,
    "SIDEWAYS": 50.0,
    "SIDEWAYS_BEAR": 40.0,
    "BEAR": 30.0,
    "STRONG_BEAR": 15.0,
}


@dataclass(frozen=True)
class StockScreenerMetrics:
    market_score: float
    sector_score: float
    technical_score: float
    liquidity_score: float
    ownership_score: float
    risk_score: float

    overall_score: float
    data_completeness: float

    status: str

    trend_score: float
    momentum_score: float
    relative_strength_score: float
    volume_score: float
    breakout_score: float

    atr_pct: float

    ownership_age_days: int | None
    ownership_stale_flag: bool

    volume_available: bool
    rs_sector_available: bool


def build_stock_screener_model_version(
    universe_date: date,
) -> str:
    return (
        f"{STOCK_SCREENER_VERSION}"
        f"_current_{universe_date:%Y%m%d}"
        "_yahoo_ksei"
    )


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def _linear(
    value: float,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
) -> float:
    if x1 == x0:
        return y0

    ratio = (
        value - x0
    ) / (
        x1 - x0
    )

    return (
        y0
        + ratio
        * (
            y1 - y0
        )
    )


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    return float(
        value
    )


def calculate_market_score(
    *,
    regime: str,
    confidence: float | None,
) -> float:
    if regime not in MARKET_REGIME_BASE_SCORE:
        raise ValueError(
            "Unsupported market regime: "
            f"{regime}"
        )

    base_score = MARKET_REGIME_BASE_SCORE[
        regime
    ]

    if confidence is None:
        normalized_confidence = 0.0

    else:
        normalized_confidence = max(
            0.0,
            min(
                1.0,
                float(
                    confidence
                ),
            ),
        )

    score = (
        50.0
        + (
            base_score
            - 50.0
        )
        * normalized_confidence
    )

    return round(
        _clamp(
            score
        ),
        4,
    )


def calculate_trend_score(
    *,
    close: float,
    ema20: float,
    ema50: float,
    ema200: float,
    return_20d: float,
) -> float:
    score = 0.0

    if close > ema20:
        score += 25.0

    if ema20 > ema50:
        score += 25.0

    if ema50 > ema200:
        score += 25.0

    if return_20d > 0.0:
        score += 25.0

    return round(
        score,
        4,
    )


def calculate_momentum_score(
    rsi14: float,
) -> float:
    rsi = max(
        0.0,
        min(
            100.0,
            float(
                rsi14
            ),
        ),
    )

    if rsi <= 30.0:
        score = 20.0

    elif rsi <= 40.0:
        score = _linear(
            rsi,
            30.0,
            20.0,
            40.0,
            50.0,
        )

    elif rsi <= 50.0:
        score = _linear(
            rsi,
            40.0,
            50.0,
            50.0,
            70.0,
        )

    elif rsi <= 65.0:
        score = _linear(
            rsi,
            50.0,
            70.0,
            65.0,
            100.0,
        )

    elif rsi <= 75.0:
        score = _linear(
            rsi,
            65.0,
            100.0,
            75.0,
            80.0,
        )

    elif rsi <= 85.0:
        score = _linear(
            rsi,
            75.0,
            80.0,
            85.0,
            50.0,
        )

    else:
        score = _linear(
            rsi,
            85.0,
            50.0,
            100.0,
            20.0,
        )

    return round(
        _clamp(
            score
        ),
        4,
    )


def _single_relative_strength_score(
    relative_return: float,
) -> float:
    score = (
        50.0
        + (
            float(
                relative_return
            )
            / RS_REFERENCE
            * 50.0
        )
    )

    return _clamp(
        score
    )


def calculate_relative_strength_score(
    *,
    rs_ihsg_20d: float,
    rs_sector_20d: float | None,
) -> float:
    ihsg_score = (
        _single_relative_strength_score(
            rs_ihsg_20d
        )
    )

    if rs_sector_20d is None:
        return round(
            ihsg_score,
            4,
        )

    sector_score = (
        _single_relative_strength_score(
            rs_sector_20d
        )
    )

    return round(
        (
            ihsg_score
            + sector_score
        )
        / 2.0,
        4,
    )


def calculate_volume_score(
    volume_z20: float | None,
) -> float:
    if volume_z20 is None:
        return 50.0

    score = (
        50.0
        + float(
            volume_z20
        )
        * 15.0
    )

    return round(
        _clamp(
            score
        ),
        4,
    )


def calculate_breakout_score(
    *,
    breakout_flag: bool,
    failed_breakout_flag: bool,
) -> float:
    if failed_breakout_flag:
        return 0.0

    if breakout_flag:
        return 100.0

    return 50.0


def calculate_technical_score(
    *,
    trend_score: float,
    momentum_score: float,
    relative_strength_score: float,
    volume_score: float,
    breakout_score: float,
) -> float:
    score = (
        0.35
        * trend_score
        + 0.20
        * momentum_score
        + 0.30
        * relative_strength_score
        + 0.10
        * volume_score
        + 0.05
        * breakout_score
    )

    return round(
        _clamp(
            score
        ),
        4,
    )


def calculate_liquidity_score(
    liquidity_percentile: float,
) -> float:
    percentile = max(
        0.0,
        min(
            1.0,
            float(
                liquidity_percentile
            ),
        ),
    )

    return round(
        percentile
        * 100.0,
        4,
    )


def calculate_ownership_score(
    *,
    trading_date: date,
    ownership_as_of_date: date | None,
    trend_label: str | None,
    signal_strength: float | None,
) -> tuple[
    float,
    int | None,
    bool,
]:
    if (
        ownership_as_of_date is None
        or trend_label is None
        or signal_strength is None
    ):
        return (
            50.0,
            None,
            False,
        )

    if ownership_as_of_date > trading_date:
        raise ValueError(
            "ownership_as_of_date cannot "
            "be after trading_date."
        )

    age_days = (
        trading_date
        - ownership_as_of_date
    ).days

    stale = (
        age_days
        > OWNERSHIP_STALE_DAYS
    )

    if stale:
        return (
            50.0,
            age_days,
            True,
        )

    strength = _clamp(
        float(
            signal_strength
        )
    )

    if trend_label == "ACCUMULATING":
        score = (
            50.0
            + strength
            * 0.50
        )

    elif trend_label == "DISTRIBUTING":
        score = (
            50.0
            - strength
            * 0.50
        )

    elif trend_label == "STABLE":
        score = 50.0

    else:
        raise ValueError(
            "Unsupported ownership "
            f"trend label: {trend_label}"
        )

    return (
        round(
            _clamp(
                score
            ),
            4,
        ),
        age_days,
        False,
    )


def calculate_risk_score(
    *,
    atr14: float,
    close: float,
) -> tuple[
    float,
    float,
]:
    if close <= 0.0:
        raise ValueError(
            "close must be greater "
            "than zero."
        )

    if atr14 < 0.0:
        raise ValueError(
            "atr14 cannot be negative."
        )

    atr_pct = (
        atr14
        / close
        * 100.0
    )

    if atr_pct <= 1.0:
        score = 95.0

    elif atr_pct <= 2.5:
        score = _linear(
            atr_pct,
            1.0,
            95.0,
            2.5,
            85.0,
        )

    elif atr_pct <= 4.0:
        score = _linear(
            atr_pct,
            2.5,
            85.0,
            4.0,
            70.0,
        )

    elif atr_pct <= 6.0:
        score = _linear(
            atr_pct,
            4.0,
            70.0,
            6.0,
            50.0,
        )

    elif atr_pct <= 8.0:
        score = _linear(
            atr_pct,
            6.0,
            50.0,
            8.0,
            30.0,
        )

    elif atr_pct <= 12.0:
        score = _linear(
            atr_pct,
            8.0,
            30.0,
            12.0,
            10.0,
        )

    else:
        score = 10.0

    return (
        round(
            _clamp(
                score
            ),
            4,
        ),
        round(
            atr_pct,
            4,
        ),
    )


def calculate_overall_score(
    *,
    market_score: float,
    sector_score: float,
    technical_score: float,
    liquidity_score: float,
    ownership_score: float,
    risk_score: float,
) -> float:
    score = (
        MARKET_WEIGHT
        * market_score
        + SECTOR_WEIGHT
        * sector_score
        + TECHNICAL_WEIGHT
        * technical_score
        + LIQUIDITY_WEIGHT
        * liquidity_score
        + OWNERSHIP_WEIGHT
        * ownership_score
        + RISK_WEIGHT
        * risk_score
    )

    return round(
        _clamp(
            score
        ),
        4,
    )


def calculate_data_completeness(
    *,
    ownership_available: bool,
    ownership_stale: bool,
    sector_ownership_stale: bool,
    volume_available: bool,
    rs_sector_available: bool,
) -> float:
    completeness = 100.0

    if not ownership_available:
        completeness -= 10.0

    elif ownership_stale:
        completeness -= 5.0

    if sector_ownership_stale:
        completeness -= 5.0

    if not volume_available:
        completeness -= 5.0

    if not rs_sector_available:
        completeness -= 5.0

    return round(
        _clamp(
            completeness
        ),
        4,
    )


def classify_screening_status(
    *,
    overall_score: float,
    market_score: float,
    sector_score: float,
    technical_score: float,
    liquidity_score: float,
    risk_score: float,
    breakout_flag: bool,
    failed_breakout_flag: bool,
    rs_ihsg_20d: float,
    rsi14: float,
    close: float,
    ema20: float,
) -> str:
    if failed_breakout_flag:
        return "AVOID"

    if (
        risk_score < 20.0
        or liquidity_score < 5.0
        or sector_score < 30.0
        or market_score < 25.0
    ):
        return "AVOID"

    continuation_trigger = (
        breakout_flag
        or (
            rs_ihsg_20d >= 0.03
            and 50.0
            <= rsi14
            <= 75.0
            and close > ema20
        )
    )

    if (
        overall_score >= 65.0
        and market_score >= 40.0
        and sector_score >= 55.0
        and technical_score >= 65.0
        and liquidity_score >= 25.0
        and risk_score >= 35.0
        and continuation_trigger
    ):
        return "BUY_SETUP"

    if (
        overall_score >= 55.0
        and market_score >= 35.0
        and sector_score >= 45.0
        and technical_score >= 55.0
        and liquidity_score >= 20.0
        and risk_score >= 30.0
    ):
        return "WATCH"

    if (
        overall_score >= 45.0
        and technical_score >= 40.0
    ):
        return "WAIT"

    return "AVOID"


def calculate_stock_screener_metrics(
    *,
    trading_date: date,
    market_regime: str,
    market_confidence: float | None,
    sector_score: float,
    sector_ownership_stale_flag: bool,
    close: float,
    return_20d: float,
    ema20: float,
    ema50: float,
    ema200: float,
    rsi14: float,
    atr14: float,
    volume_z20: float | None,
    rs_ihsg_20d: float,
    rs_sector_20d: float | None,
    breakout_flag: bool,
    failed_breakout_flag: bool,
    liquidity_percentile: float,
    ownership_as_of_date: date | None,
    ownership_trend_label: str | None,
    ownership_signal_strength: float | None,
) -> StockScreenerMetrics:
    market_score = calculate_market_score(
        regime=market_regime,
        confidence=market_confidence,
    )

    trend_score = calculate_trend_score(
        close=close,
        ema20=ema20,
        ema50=ema50,
        ema200=ema200,
        return_20d=return_20d,
    )

    momentum_score = calculate_momentum_score(
        rsi14
    )

    relative_strength_score = (
        calculate_relative_strength_score(
            rs_ihsg_20d=rs_ihsg_20d,
            rs_sector_20d=rs_sector_20d,
        )
    )

    volume_score = calculate_volume_score(
        volume_z20
    )

    breakout_score = calculate_breakout_score(
        breakout_flag=breakout_flag,
        failed_breakout_flag=(
            failed_breakout_flag
        ),
    )

    technical_score = calculate_technical_score(
        trend_score=trend_score,
        momentum_score=momentum_score,
        relative_strength_score=(
            relative_strength_score
        ),
        volume_score=volume_score,
        breakout_score=breakout_score,
    )

    liquidity_score = calculate_liquidity_score(
        liquidity_percentile
    )

    (
        ownership_score,
        ownership_age_days,
        ownership_stale_flag,
    ) = calculate_ownership_score(
        trading_date=trading_date,
        ownership_as_of_date=(
            ownership_as_of_date
        ),
        trend_label=(
            ownership_trend_label
        ),
        signal_strength=(
            ownership_signal_strength
        ),
    )

    (
        risk_score,
        atr_pct,
    ) = calculate_risk_score(
        atr14=atr14,
        close=close,
    )

    overall_score = calculate_overall_score(
        market_score=market_score,
        sector_score=sector_score,
        technical_score=technical_score,
        liquidity_score=liquidity_score,
        ownership_score=ownership_score,
        risk_score=risk_score,
    )

    ownership_available = (
        ownership_as_of_date is not None
        and ownership_trend_label is not None
        and ownership_signal_strength is not None
    )

    volume_available = (
        volume_z20 is not None
    )

    rs_sector_available = (
        rs_sector_20d is not None
    )

    data_completeness = (
        calculate_data_completeness(
            ownership_available=(
                ownership_available
            ),
            ownership_stale=(
                ownership_stale_flag
            ),
            sector_ownership_stale=(
                sector_ownership_stale_flag
            ),
            volume_available=(
                volume_available
            ),
            rs_sector_available=(
                rs_sector_available
            ),
        )
    )

    status = classify_screening_status(
        overall_score=overall_score,
        market_score=market_score,
        sector_score=sector_score,
        technical_score=technical_score,
        liquidity_score=liquidity_score,
        risk_score=risk_score,
        breakout_flag=breakout_flag,
        failed_breakout_flag=(
            failed_breakout_flag
        ),
        rs_ihsg_20d=rs_ihsg_20d,
        rsi14=rsi14,
        close=close,
        ema20=ema20,
    )

    return StockScreenerMetrics(
        market_score=market_score,
        sector_score=round(
            _clamp(
                sector_score
            ),
            4,
        ),
        technical_score=technical_score,
        liquidity_score=liquidity_score,
        ownership_score=ownership_score,
        risk_score=risk_score,
        overall_score=overall_score,
        data_completeness=(
            data_completeness
        ),
        status=status,
        trend_score=trend_score,
        momentum_score=momentum_score,
        relative_strength_score=(
            relative_strength_score
        ),
        volume_score=volume_score,
        breakout_score=breakout_score,
        atr_pct=atr_pct,
        ownership_age_days=(
            ownership_age_days
        ),
        ownership_stale_flag=(
            ownership_stale_flag
        ),
        volume_available=(
            volume_available
        ),
        rs_sector_available=(
            rs_sector_available
        ),
    )


def prepare_stock_screener_rows(
    *,
    inputs: list[dict[str, Any]],
    model_version: str,
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        volume_z20 = _optional_float(
            item["volume_z20"]
        )

        rs_sector_20d = _optional_float(
            item["rs_sector_20d"]
        )

        metrics = (
            calculate_stock_screener_metrics(
                trading_date=(
                    item["trading_date"]
                ),
                market_regime=str(
                    item[
                        "market_regime"
                    ]
                ),
                market_confidence=(
                    _optional_float(
                        item[
                            "market_confidence"
                        ]
                    )
                ),
                sector_score=float(
                    item[
                        "sector_score"
                    ]
                ),
                sector_ownership_stale_flag=bool(
                    item[
                        "sector_ownership_stale_flag"
                    ]
                ),
                close=float(
                    item["close"]
                ),
                return_20d=float(
                    item[
                        "return_20d"
                    ]
                ),
                ema20=float(
                    item["ema20"]
                ),
                ema50=float(
                    item["ema50"]
                ),
                ema200=float(
                    item["ema200"]
                ),
                rsi14=float(
                    item["rsi14"]
                ),
                atr14=float(
                    item["atr14"]
                ),
                volume_z20=volume_z20,
                rs_ihsg_20d=float(
                    item[
                        "rs_ihsg_20d"
                    ]
                ),
                rs_sector_20d=(
                    rs_sector_20d
                ),
                breakout_flag=bool(
                    item[
                        "breakout_flag"
                    ]
                ),
                failed_breakout_flag=bool(
                    item[
                        "failed_breakout_flag"
                    ]
                ),
                liquidity_percentile=float(
                    item[
                        "liquidity_percentile"
                    ]
                ),
                ownership_as_of_date=(
                    item[
                        "ownership_as_of_date"
                    ]
                ),
                ownership_trend_label=(
                    item[
                        "ownership_trend_label"
                    ]
                ),
                ownership_signal_strength=(
                    _optional_float(
                        item[
                            "ownership_signal_strength"
                        ]
                    )
                ),
            )
        )

        warnings = [
            (
                "SCREENING_ONLY_"
                "NOT_EXECUTABLE_SIGNAL"
            ),
            (
                "YAHOO_EOD_IS_THIRD_PARTY_"
                "MARKET_DATA"
            ),
            (
                "HISTORICAL_KSEI_AS_OF_DATE_"
                "IS_NOT_PUBLICATION_TIME_SAFE"
            ),
        ]

        if not metrics.rs_sector_available:
            warnings.append(
                
                    "RS_SECTOR_20D_UNAVAILABLE_"
                    "USING_IHSG_ONLY"
                
            )

        if not metrics.volume_available:
            warnings.append(
                
                    "VOLUME_Z20_UNAVAILABLE_"
                    "NEUTRAL_FALLBACK"
                
            )

        if (
            item[
                "ownership_as_of_date"
            ]
            is None
        ):
            warnings.append(
                "STOCK_OWNERSHIP_UNAVAILABLE"
            )

        if metrics.ownership_stale_flag:
            warnings.append(
                "STOCK_OWNERSHIP_STALE"
            )

        if bool(
            item[
                "sector_ownership_stale_flag"
            ]
        ):
            warnings.append(
                "SECTOR_OWNERSHIP_STALE"
            )

        if bool(
            item[
                "ownership_corporate_action_risk"
            ]
            or False
        ):
            warnings.append(
                
                    "OWNERSHIP_"
                    "CORPORATE_ACTION_RISK"
                
            )

        if bool(
            item[
                "failed_breakout_flag"
            ]
        ):
            warnings.append(
                "FAILED_BREAKOUT"
            )

        evidence = {
            "scope":
                "stock_screener_v1",

            "status_semantics":
                "candidate_screening_only",

            "symbol":
                item["symbol"],

            "sector_code":
                item["sector_code"],

            "market": {
                "regime":
                    str(
                        item[
                            "market_regime"
                        ]
                    ),
                "confidence":
                    (
                        None
                        if item[
                            "market_confidence"
                        ]
                        is None
                        else round(
                            float(
                                item[
                                    "market_confidence"
                                ]
                            ),
                            6,
                        )
                    ),
                "model_version":
                    item[
                        "market_model_version"
                    ],
            },

            "sector": {
                "integrated_score":
                    round(
                        float(
                            item[
                                "sector_score"
                            ]
                        ),
                        6,
                    ),
                "integrated_label":
                    item[
                        "sector_integrated_label"
                    ],
                "alignment_label":
                    item[
                        "sector_alignment_label"
                    ],
                "ownership_stale":
                    bool(
                        item[
                            "sector_ownership_stale_flag"
                        ]
                    ),
                "model_version":
                    item[
                        "sector_model_version"
                    ],
            },

            "technical": {
                "close":
                    float(
                        item["close"]
                    ),
                "return_20d":
                    float(
                        item[
                            "return_20d"
                        ]
                    ),
                "ema20":
                    float(
                        item["ema20"]
                    ),
                "ema50":
                    float(
                        item["ema50"]
                    ),
                "ema200":
                    float(
                        item["ema200"]
                    ),
                "rsi14":
                    float(
                        item["rsi14"]
                    ),
                "atr14":
                    float(
                        item["atr14"]
                    ),
                "atr_pct":
                    metrics.atr_pct,
                "volume_z20":
                    volume_z20,
                "rs_ihsg_20d":
                    float(
                        item[
                            "rs_ihsg_20d"
                        ]
                    ),
                "rs_sector_20d":
                    rs_sector_20d,
                "rs_sector_available":
                    metrics
                    .rs_sector_available,
                "relative_strength_source":
                    (
                        "IHSG_AND_SECTOR"
                        if metrics
                        .rs_sector_available
                        else "IHSG_ONLY"
                    ),
                "volume_available":
                    metrics
                    .volume_available,
                "breakout_flag":
                    bool(
                        item[
                            "breakout_flag"
                        ]
                    ),
                "failed_breakout_flag":
                    bool(
                        item[
                            "failed_breakout_flag"
                        ]
                    ),
                "feature_version":
                    item[
                        "feature_version"
                    ],
            },

            "technical_components": {
                "trend":
                    metrics.trend_score,
                "momentum":
                    metrics.momentum_score,
                "relative_strength":
                    metrics
                    .relative_strength_score,
                "volume":
                    metrics.volume_score,
                "breakout":
                    metrics.breakout_score,
            },

            "liquidity": {
                "avg_turnover_20d":
                    float(
                        item[
                            "avg_turnover_20d"
                        ]
                    ),
                "percentile":
                    round(
                        float(
                            item[
                                "liquidity_percentile"
                            ]
                        ),
                        6,
                    ),
            },

            "ownership": {
                "as_of_date":
                    (
                        None
                        if item[
                            "ownership_as_of_date"
                        ]
                        is None
                        else item[
                            "ownership_as_of_date"
                        ].isoformat()
                    ),
                "trend_label":
                    item[
                        "ownership_trend_label"
                    ],
                "signal_strength":
                    (
                        None
                        if item[
                            "ownership_signal_strength"
                        ]
                        is None
                        else round(
                            float(
                                item[
                                    "ownership_signal_strength"
                                ]
                            ),
                            4,
                        )
                    ),
                "age_days":
                    metrics
                    .ownership_age_days,
                "stale":
                    metrics
                    .ownership_stale_flag,
                "corporate_action_risk":
                    bool(
                        item[
                            "ownership_corporate_action_risk"
                        ]
                        or False
                    ),
                "snapshot_gap_flag":
                    bool(
                        item[
                            "ownership_snapshot_gap_flag"
                        ]
                        or False
                    ),
            },

            "weights": {
                "market":
                    MARKET_WEIGHT,
                "sector":
                    SECTOR_WEIGHT,
                "technical":
                    TECHNICAL_WEIGHT,
                "liquidity":
                    LIQUIDITY_WEIGHT,
                "ownership":
                    OWNERSHIP_WEIGHT,
                "risk":
                    RISK_WEIGHT,
            },

            "optional_fallbacks": {
                "volume_z20":
                    (
                        "ACTUAL"
                        if metrics
                        .volume_available
                        else "NEUTRAL_50"
                    ),
                "rs_sector_20d":
                    (
                        "ACTUAL"
                        if metrics
                        .rs_sector_available
                        else "IHSG_ONLY"
                    ),
            },

            "unused_v1_components": [
                "fundamental",
                "valuation",
                "daily_foreign_flow",
                "catalyst",
            ],

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

                "overall_score":
                    metrics
                    .overall_score,

                "market_score":
                    metrics
                    .market_score,

                "sector_score":
                    metrics
                    .sector_score,

                "fundamental_score":
                    None,

                "valuation_score":
                    None,

                "technical_score":
                    metrics
                    .technical_score,

                "liquidity_score":
                    metrics
                    .liquidity_score,

                "flow_score":
                    None,

                "catalyst_score":
                    None,

                "risk_score":
                    metrics
                    .risk_score,

                "ownership_score":
                    metrics
                    .ownership_score,

                "data_completeness":
                    metrics
                    .data_completeness,

                "status":
                    metrics.status,

                "universe_rank":
                    None,

                "sector_rank":
                    None,

                "input_updated_at":
                    item[
                        "input_updated_at"
                    ],

                "evidence":
                    evidence,

                "model_version":
                    model_version,
            }
        )

    return rows


def rank_stock_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_date: dict[
        date,
        list[dict[str, Any]],
    ] = defaultdict(
        list
    )

    for row in rows:
        by_date[
            row["trading_date"]
        ].append(
            row
        )

    for date_rows in by_date.values():
        ordered = sorted(
            date_rows,
            key=lambda row: (
                -float(
                    row[
                        "overall_score"
                    ]
                ),
                -float(
                    row[
                        "technical_score"
                    ]
                ),
                str(
                    row["symbol"]
                ),
            ),
        )

        for rank, row in enumerate(
            ordered,
            start=1,
        ):
            row[
                "universe_rank"
            ] = rank

        by_sector: dict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(
            list
        )

        for row in date_rows:
            by_sector[
                str(
                    row[
                        "sector_code"
                    ]
                )
            ].append(
                row
            )

        for sector_rows in (
            by_sector.values()
        ):
            ordered_sector = sorted(
                sector_rows,
                key=lambda row: (
                    -float(
                        row[
                            "overall_score"
                        ]
                    ),
                    -float(
                        row[
                            "technical_score"
                        ]
                    ),
                    str(
                        row["symbol"]
                    ),
                ),
            )

            for rank, row in enumerate(
                ordered_sector,
                start=1,
            ):
                row[
                    "sector_rank"
                ] = rank

    return rows


def resolve_stock_screener_build_mode(
    *,
    existing_last_date: date | None,
    existing_latest_count: int,
    existing_expected_count: int,
    existing_input_updated_at: Any,
    expected_input_updated_at: Any,
    latest_input_date: date,
    force: bool,
) -> StockScreenerBuildMode:
    if force:
        return "FULL"

    if existing_last_date is None:
        return "FULL"

    if existing_last_date > latest_input_date:
        raise RuntimeError(
            "Stock screener data is "
            "ahead of upstream input: "
            f"stored={existing_last_date}, "
            f"input={latest_input_date}."
        )

    if (
        existing_latest_count
        != existing_expected_count
    ):
        return "FULL"

    if (
        existing_input_updated_at
        != expected_input_updated_at
    ):
        return "FULL"

    if (
        existing_last_date
        == latest_input_date
    ):
        return "UP_TO_DATE"

    return "INCREMENTAL"

