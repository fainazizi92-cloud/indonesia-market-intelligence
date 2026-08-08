import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

BACKTEST_CALIBRATION_VERSION = (
    "backtest_calibration_v1"
)

MIN_MATURE_TRADES = 200
MIN_VALIDATION_TRADES = 50
MIN_TEST_TRADES = 50

STRICT_POINT_IN_TIME_READY = False
TRANSACTION_COSTS_MODELED = False
INTRADAY_SEQUENCE_AVAILABLE = False


SampleStatus = Literal[
    "MATURE_TRADE",
    "UNFILLED_COMPLETE",
    "UNRESOLVED",
]

SplitLabel = Literal[
    "TRAIN",
    "VALIDATION",
    "TEST",
    "EXCLUDED",
]

BacktestBuildMode = Literal[
    "FULL",
    "REFRESH",
    "UP_TO_DATE",
]


@dataclass(frozen=True)
class BacktestSummary:
    total_rows: int

    mature_trades: int
    unfilled_complete: int
    unresolved: int

    train_trades: int
    validation_trades: int
    test_trades: int

    entry_decided: int
    filled_signals: int

    target_trades: int
    stop_trades: int
    expired_trades: int

    positive_r_trades: int
    negative_r_trades: int
    flat_r_trades: int

    fill_rate: float | None

    target_rate: float | None
    stop_rate: float | None
    expired_rate: float | None

    win_rate: float | None

    average_r: float | None
    median_r: float | None

    average_mfe_r: float | None
    average_mae_r: float | None

    profit_factor: float | None

    calibration_ready: bool

    readiness_reasons: tuple[
        str,
        ...,
    ]


def build_backtest_calibration_version(
    universe_date: date,
) -> str:
    return (
        f"{BACKTEST_CALIBRATION_VERSION}"
        f"_current_{universe_date:%Y%m%d}"
    )


def classify_sample_status(
    *,
    outcome_label: str,
    entry_filled: bool,
    horizon_complete: bool,
    realized_r: float | None,
) -> SampleStatus:
    if outcome_label in {
        "TARGET",
        "STOP",
        "EXPIRED",
    }:
        if not entry_filled:
            raise ValueError(
                "Terminal trade outcome "
                "must have entry_filled=True."
            )

        if not horizon_complete:
            raise ValueError(
                "Terminal trade outcome "
                "must be horizon complete."
            )

        if realized_r is None:
            raise ValueError(
                "Terminal trade outcome "
                "must have realized_r."
            )

        return "MATURE_TRADE"

    if outcome_label in {
        "NO_FILL",
        "CANCELLED",
    }:
        if entry_filled:
            raise ValueError(
                "Unfilled outcome cannot "
                "have entry_filled=True."
            )

        if not horizon_complete:
            raise ValueError(
                "NO_FILL/CANCELLED must "
                "be complete."
            )

        return "UNFILLED_COMPLETE"

    if outcome_label in {
        "OPEN",
        "PENDING",
    }:
        return "UNRESOLVED"

    raise ValueError(
        "Unsupported outcome label: "
        f"{outcome_label}"
    )


def score_bucket(
    overall_score: float | None,
) -> str | None:
    if overall_score is None:
        return None

    value = float(
        overall_score
    )

    if value >= 70.0:
        return "GE_70"

    if value >= 67.0:
        return "67_TO_70"

    if value >= 65.0:
        return "65_TO_67"

    return "LT_65"


def _split_dates(
    dates: list[date],
) -> dict[
    date,
    SplitLabel,
]:
    unique_dates = sorted(
        set(
            dates
        )
    )

    count = len(
        unique_dates
    )

    if count == 0:
        return {}

    if count == 1:
        return {
            unique_dates[0]:
                "TRAIN",
        }

    if count == 2:
        return {
            unique_dates[0]:
                "TRAIN",
            unique_dates[1]:
                "TEST",
        }

    train_count = math.floor(
        count
        * 0.70
    )

    train_count = max(
        1,
        min(
            train_count,
            count - 2,
        ),
    )

    remaining = (
        count
        - train_count
    )

    validation_count = (
        math.floor(
            count
            * 0.15
        )
    )

    validation_count = max(
        1,
        min(
            validation_count,
            remaining - 1,
        ),
    )

    train_end = (
        train_count
    )

    validation_end = (
        train_count
        + validation_count
    )

    result: dict[
        date,
        SplitLabel,
    ] = {}

    for index, trading_date in enumerate(
        unique_dates
    ):
        if index < train_end:
            label: SplitLabel = (
                "TRAIN"
            )

        elif index < validation_end:
            label = "VALIDATION"

        else:
            label = "TEST"

        result[
            trading_date
        ] = label

    return result


def assign_chronological_splits(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mature_dates = [
        row["signal_date"]
        for row in rows
        if row[
            "sample_status"
        ]
        == "MATURE_TRADE"
    ]

    date_splits = (
        _split_dates(
            mature_dates
        )
    )

    output = []

    for row in rows:
        item = dict(
            row
        )

        if (
            item[
                "sample_status"
            ]
            == "MATURE_TRADE"
        ):
            item[
                "split_label"
            ] = date_splits[
                item[
                    "signal_date"
                ]
            ]

            item[
                "calibration_eligible"
            ] = True

        else:
            item[
                "split_label"
            ] = "EXCLUDED"

            item[
                "calibration_eligible"
            ] = False

        output.append(
            item
        )

    return output


def _average(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return round(
        statistics.fmean(
            values
        ),
        8,
    )


def _median(
    values: list[float],
) -> float | None:
    if not values:
        return None

    return round(
        statistics.median(
            values
        ),
        8,
    )


def calculate_profit_factor(
    realized_r_values: list[
        float
    ],
) -> float | None:
    positive = sum(
        value
        for value
        in realized_r_values
        if value > 0
    )

    negative = abs(
        sum(
            value
            for value
            in realized_r_values
            if value < 0
        )
    )

    if negative == 0:
        if positive > 0:
            return None

        return None

    return round(
        positive
        / negative,
        8,
    )


def compute_backtest_summary(
    rows: list[dict[str, Any]],
) -> BacktestSummary:
    mature = [
        row
        for row in rows
        if row[
            "sample_status"
        ]
        == "MATURE_TRADE"
    ]

    unfilled = [
        row
        for row in rows
        if row[
            "sample_status"
        ]
        == "UNFILLED_COMPLETE"
    ]

    unresolved = [
        row
        for row in rows
        if row[
            "sample_status"
        ]
        == "UNRESOLVED"
    ]

    train = [
        row
        for row in mature
        if row[
            "split_label"
        ]
        == "TRAIN"
    ]

    validation = [
        row
        for row in mature
        if row[
            "split_label"
        ]
        == "VALIDATION"
    ]

    test = [
        row
        for row in mature
        if row[
            "split_label"
        ]
        == "TEST"
    ]

    entry_decided_rows = [
        row
        for row in rows
        if (
            bool(
                row[
                    "entry_filled"
                ]
            )
            or row[
                "sample_status"
            ]
            == "UNFILLED_COMPLETE"
        )
    ]

    filled = [
        row
        for row in rows
        if bool(
            row[
                "entry_filled"
            ]
        )
    ]

    target = [
        row
        for row in mature
        if row[
            "outcome_label"
        ]
        == "TARGET"
    ]

    stop = [
        row
        for row in mature
        if row[
            "outcome_label"
        ]
        == "STOP"
    ]

    expired = [
        row
        for row in mature
        if row[
            "outcome_label"
        ]
        == "EXPIRED"
    ]

    realized_r_values = [
        float(
            row["realized_r"]
        )
        for row in mature
        if row[
            "realized_r"
        ]
        is not None
    ]

    mfe_values = [
        float(
            row["mfe_r"]
        )
        for row in mature
        if row[
            "mfe_r"
        ]
        is not None
    ]

    mae_values = [
        float(
            row["mae_r"]
        )
        for row in mature
        if row[
            "mae_r"
        ]
        is not None
    ]

    positive_count = sum(
        value > 0
        for value in realized_r_values
    )

    negative_count = sum(
        value < 0
        for value in realized_r_values
    )

    flat_count = sum(
        value == 0
        for value in realized_r_values
    )

    fill_rate = (
        None
        if not entry_decided_rows
        else round(
            len(
                filled
            )
            / len(
                entry_decided_rows
            ),
            8,
        )
    )

    mature_count = len(
        mature
    )

    if mature_count == 0:
        target_rate = None
        stop_rate = None
        expired_rate = None
        win_rate = None

    else:
        target_rate = round(
            len(target)
            / mature_count,
            8,
        )

        stop_rate = round(
            len(stop)
            / mature_count,
            8,
        )

        expired_rate = round(
            len(expired)
            / mature_count,
            8,
        )

        win_rate = round(
            positive_count
            / mature_count,
            8,
        )

    readiness_reasons = []

    if (
        mature_count
        < MIN_MATURE_TRADES
    ):
        readiness_reasons.append(
            
                "MATURE_TRADES_BELOW_"
                f"{MIN_MATURE_TRADES}"
            
        )

    if (
        len(validation)
        < MIN_VALIDATION_TRADES
    ):
        readiness_reasons.append(
            
                "VALIDATION_TRADES_BELOW_"
                f"{MIN_VALIDATION_TRADES}"
            
        )

    if (
        len(test)
        < MIN_TEST_TRADES
    ):
        readiness_reasons.append(
            
                "TEST_TRADES_BELOW_"
                f"{MIN_TEST_TRADES}"
            
        )

    if not STRICT_POINT_IN_TIME_READY:
        readiness_reasons.append(
            
                "STRICT_POINT_IN_TIME_"
                "DATA_NOT_READY"
            
        )

    if not TRANSACTION_COSTS_MODELED:
        readiness_reasons.append(
            "TRANSACTION_COSTS_NOT_MODELED"
        )

    if not INTRADAY_SEQUENCE_AVAILABLE:
        readiness_reasons.append(
            
                "INTRADAY_SEQUENCE_"
                "NOT_AVAILABLE"
            
        )

    calibration_ready = (
        len(
            readiness_reasons
        )
        == 0
    )

    return BacktestSummary(
        total_rows=len(
            rows
        ),
        mature_trades=(
            mature_count
        ),
        unfilled_complete=len(
            unfilled
        ),
        unresolved=len(
            unresolved
        ),
        train_trades=len(
            train
        ),
        validation_trades=len(
            validation
        ),
        test_trades=len(
            test
        ),
        entry_decided=len(
            entry_decided_rows
        ),
        filled_signals=len(
            filled
        ),
        target_trades=len(
            target
        ),
        stop_trades=len(
            stop
        ),
        expired_trades=len(
            expired
        ),
        positive_r_trades=(
            positive_count
        ),
        negative_r_trades=(
            negative_count
        ),
        flat_r_trades=(
            flat_count
        ),
        fill_rate=(
            fill_rate
        ),
        target_rate=(
            target_rate
        ),
        stop_rate=(
            stop_rate
        ),
        expired_rate=(
            expired_rate
        ),
        win_rate=(
            win_rate
        ),
        average_r=_average(
            realized_r_values
        ),
        median_r=_median(
            realized_r_values
        ),
        average_mfe_r=_average(
            mfe_values
        ),
        average_mae_r=_average(
            mae_values
        ),
        profit_factor=(
            calculate_profit_factor(
                realized_r_values
            )
        ),
        calibration_ready=(
            calibration_ready
        ),
        readiness_reasons=tuple(
            readiness_reasons
        ),
    )


def _optional_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    return float(
        value
    )


def prepare_backtest_calibration_rows(
    *,
    inputs: list[dict[str, Any]],
    dataset_version: str,
) -> list[dict[str, Any]]:
    prepared = []

    for item in inputs:
        realized_r = (
            _optional_float(
                item[
                    "realized_r"
                ]
            )
        )

        sample_status = (
            classify_sample_status(
                outcome_label=str(
                    item[
                        "outcome_label"
                    ]
                ),
                entry_filled=bool(
                    item[
                        "entry_filled"
                    ]
                ),
                horizon_complete=bool(
                    item[
                        "horizon_complete"
                    ]
                ),
                realized_r=(
                    realized_r
                ),
            )
        )

        overall_score = (
            _optional_float(
                item[
                    "overall_score"
                ]
            )
        )

        if (
            sample_status
            == "MATURE_TRADE"
        ):
            tp_before_sl_label = bool(
                item[
                    "target_hit"
                ]
            )

            positive_r_label = (
                realized_r is not None
                and realized_r > 0
            )

        else:
            tp_before_sl_label = None
            positive_r_label = None

        warnings = [
            (
                "RESEARCH_CALIBRATION_"
                "DATASET_ONLY"
            ),
            (
                "DO_NOT_PUBLISH_"
                "CALIBRATED_PROBABILITY_YET"
            ),
            (
                "CURRENT_UNIVERSE_HISTORY_"
                "IS_SURVIVORSHIP_BIASED"
            ),
            (
                "HISTORICAL_KSEI_AS_OF_DATE_"
                "IS_NOT_PUBLICATION_TIME_SAFE"
            ),
            (
                "TRANSACTION_COSTS_"
                "NOT_MODELED"
            ),
            (
                "INTRADAY_SEQUENCE_"
                "NOT_AVAILABLE"
            ),
        ]

        evidence = {
            "scope":
                "backtest_calibration_v1",

            "sample_status":
                sample_status,

            "source": {
                "outcome_model_version":
                    item[
                        "outcome_model_version"
                    ],
                "trade_setup_model_version":
                    item[
                        "trade_setup_model_version"
                    ],
            },

            "labels": {
                "outcome_label":
                    item[
                        "outcome_label"
                    ],
                "tp_before_sl_label":
                    tp_before_sl_label,
                "positive_r_label":
                    positive_r_label,
            },

            "warnings":
                warnings,
        }

        prepared.append(
            {
                "signal_id":
                    item[
                        "signal_id"
                    ],

                "dataset_version":
                    dataset_version,

                "outcome_model_version":
                    item[
                        "outcome_model_version"
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
                    "EXCLUDED",

                "calibration_eligible":
                    False,

                "outcome_label":
                    item[
                        "outcome_label"
                    ],

                "entry_filled":
                    bool(
                        item[
                            "entry_filled"
                        ]
                    ),

                "horizon_complete":
                    bool(
                        item[
                            "horizon_complete"
                        ]
                    ),

                "entry_date":
                    item[
                        "entry_date"
                    ],

                "exit_date":
                    item[
                        "exit_date"
                    ],

                "realized_return":
                    _optional_float(
                        item[
                            "realized_return"
                        ]
                    ),

                "realized_r":
                    realized_r,

                "mfe_r":
                    _optional_float(
                        item[
                            "mfe_r"
                        ]
                    ),

                "mae_r":
                    _optional_float(
                        item[
                            "mae_r"
                        ]
                    ),

                "target_hit":
                    bool(
                        item[
                            "target_hit"
                        ]
                    ),

                "stop_hit":
                    bool(
                        item[
                            "stop_hit"
                        ]
                    ),

                "tp_before_sl_label":
                    tp_before_sl_label,

                "positive_r_label":
                    positive_r_label,

                "setup_expected_rr":
                    _optional_float(
                        item[
                            "setup_expected_rr"
                        ]
                    ),

                "setup_risk_pct":
                    _optional_float(
                        item[
                            "setup_risk_pct"
                        ]
                    ),

                "horizon_days":
                    (
                        None
                        if item[
                            "horizon_days"
                        ]
                        is None
                        else int(
                            item[
                                "horizon_days"
                            ]
                        )
                    ),

                "overall_score":
                    overall_score,

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

                "score_bucket":
                    score_bucket(
                        overall_score
                    ),

                "input_updated_at":
                    item[
                        "input_updated_at"
                    ],

                "evidence":
                    evidence,
            }
        )

    prepared = (
        assign_chronological_splits(
            prepared
        )
    )

    for row in prepared:
        row[
            "evidence"
        ][
            "split"
        ] = {
            "label":
                row[
                    "split_label"
                ],
            "chronological":
                True,
            "same_signal_date_grouped":
                True,
        }

    return prepared


def resolve_backtest_build_mode(
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
) -> BacktestBuildMode:
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

    if (
        processed_through
        > latest_input_date
    ):
        raise RuntimeError(
            "Backtest calibration state "
            "is ahead of outcome input."
        )

    if (
        processed_through
        == latest_input_date
        and stored_input_updated_at
        == current_input_updated_at
    ):
        return "UP_TO_DATE"

    return "REFRESH"