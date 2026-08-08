from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

SIGNAL_OUTCOME_VERSION = "signal_outcome_v1"

ENTRY_WINDOW_DAYS = 5
MAX_FUTURE_BARS = 25

RETURN_HORIZONS = (
    1,
    3,
    5,
    10,
    20,
)


OutcomeLabel = Literal[
    "PENDING",
    "NO_FILL",
    "CANCELLED",
    "OPEN",
    "TARGET",
    "STOP",
    "EXPIRED",
]

OutcomeBuildMode = Literal[
    "FULL",
    "REFRESH",
    "UP_TO_DATE",
]


@dataclass(frozen=True)
class SignalOutcomeResult:
    evaluated_through: date | None

    return_t1: float | None
    return_t3: float | None
    return_t5: float | None
    return_t10: float | None
    return_t20: float | None

    mfe: float | None
    mae: float | None

    target_hit: bool
    stop_hit: bool

    entry_filled: bool
    entry_date: date | None
    entry_price: float | None

    exit_date: date | None
    exit_price: float | None

    outcome_label: OutcomeLabel

    realized_return: float | None
    realized_r: float | None

    mfe_r: float | None
    mae_r: float | None

    bars_to_entry: int | None
    bars_held: int | None

    target_hit_date: date | None
    stop_hit_date: date | None

    horizon_complete: bool
    available_bars: int

    sequence_ambiguous: bool

    fill_method: str | None


def build_signal_outcome_model_version(
    universe_date: date,
) -> str:
    return (
        f"{SIGNAL_OUTCOME_VERSION}"
        f"_current_{universe_date:%Y%m%d}"
        "_yahoo_eod"
    )


def _float(
    value: Any,
) -> float:
    return float(
        value
    )


def _round(
    value: float | None,
    digits: int = 8,
) -> float | None:
    if value is None:
        return None

    return round(
        float(value),
        digits,
    )


def determine_fill_price(
    *,
    bar_open: float,
    bar_high: float,
    bar_low: float,
    entry_low: float,
    entry_high: float,
) -> tuple[
    float | None,
    str | None,
]:
    if (
        bar_high < entry_low
        or bar_low > entry_high
    ):
        return (
            None,
            None,
        )

    if (
        entry_low
        <= bar_open
        <= entry_high
    ):
        return (
            bar_open,
            "OPEN_IN_ZONE",
        )

    if bar_open > entry_high:
        return (
            entry_high,
            "PULLBACK_TOUCH",
        )

    return (
        entry_low,
        "RECOVERY_TOUCH",
    )


def _mark_to_market_return(
    *,
    bars: list[dict[str, Any]],
    fill_index: int,
    horizon: int,
    entry_price: float,
) -> float | None:
    target_index = (
        fill_index
        + horizon
    )

    if target_index >= len(
        bars
    ):
        return None

    close = bars[
        target_index
    ].get(
        "close"
    )

    if close is None:
        return None

    return _round(
        _float(
            close
        )
        / entry_price
        - 1.0
    )


def _empty_outcome(
    *,
    label: OutcomeLabel,
    evaluated_through: date | None,
    available_bars: int,
    horizon_complete: bool,
) -> SignalOutcomeResult:
    return SignalOutcomeResult(
        evaluated_through=(
            evaluated_through
        ),
        return_t1=None,
        return_t3=None,
        return_t5=None,
        return_t10=None,
        return_t20=None,
        mfe=None,
        mae=None,
        target_hit=False,
        stop_hit=False,
        entry_filled=False,
        entry_date=None,
        entry_price=None,
        exit_date=None,
        exit_price=None,
        outcome_label=label,
        realized_return=None,
        realized_r=None,
        mfe_r=None,
        mae_r=None,
        bars_to_entry=None,
        bars_held=None,
        target_hit_date=None,
        stop_hit_date=None,
        horizon_complete=(
            horizon_complete
        ),
        available_bars=(
            available_bars
        ),
        sequence_ambiguous=False,
        fill_method=None,
    )


def evaluate_signal_outcome(
    *,
    entry_low: float,
    entry_high: float,
    stop_price: float,
    target_primary: float,
    horizon_days: int,
    bars: list[dict[str, Any]],
) -> SignalOutcomeResult:
    entry_low = _float(
        entry_low
    )

    entry_high = _float(
        entry_high
    )

    stop_price = _float(
        stop_price
    )

    target_primary = _float(
        target_primary
    )

    if entry_low <= 0:
        raise ValueError(
            "entry_low must be positive."
        )

    if entry_high < entry_low:
        raise ValueError(
            "entry_high cannot be below "
            "entry_low."
        )

    if stop_price <= 0:
        raise ValueError(
            "stop_price must be positive."
        )

    if stop_price >= entry_low:
        raise ValueError(
            "stop_price must be below "
            "entry zone."
        )

    if target_primary <= entry_high:
        raise ValueError(
            "target_primary must be above "
            "entry zone."
        )

    if horizon_days <= 0:
        raise ValueError(
            "horizon_days must be positive."
        )

    bars = sorted(
        bars,
        key=lambda row:
            row["trading_date"],
    )

    available_bars = len(
        bars
    )

    evaluated_through = (
        None
        if not bars
        else bars[-1][
            "trading_date"
        ]
    )

    entry_search = bars[
        :ENTRY_WINDOW_DAYS
    ]

    fill_index: int | None = None
    fill_price: float | None = None
    fill_method: str | None = None

    for index, bar in enumerate(
        entry_search
    ):
        bar_open = _float(
            bar["open"]
        )

        bar_high = _float(
            bar["high"]
        )

        bar_low = _float(
            bar["low"]
        )

        (
            candidate_fill,
            candidate_method,
        ) = determine_fill_price(
            bar_open=bar_open,
            bar_high=bar_high,
            bar_low=bar_low,
            entry_low=entry_low,
            entry_high=entry_high,
        )

        if candidate_fill is not None:
            fill_index = index
            fill_price = candidate_fill
            fill_method = candidate_method
            break

        if bar_low <= stop_price:
            return _empty_outcome(
                label="CANCELLED",
                evaluated_through=(
                    evaluated_through
                ),
                available_bars=(
                    available_bars
                ),
                horizon_complete=True,
            )

    if fill_index is None:
        if (
            available_bars
            >= ENTRY_WINDOW_DAYS
        ):
            return _empty_outcome(
                label="NO_FILL",
                evaluated_through=(
                    evaluated_through
                ),
                available_bars=(
                    available_bars
                ),
                horizon_complete=True,
            )

        return _empty_outcome(
            label="PENDING",
            evaluated_through=(
                evaluated_through
            ),
            available_bars=(
                available_bars
            ),
            horizon_complete=False,
        )

    if fill_price is None:
        raise RuntimeError(
            "Fill index exists without "
            "fill price."
        )

    entry_date = bars[
        fill_index
    ][
        "trading_date"
    ]

    risk_per_share = (
        fill_price
        - stop_price
    )

    if risk_per_share <= 0:
        raise ValueError(
            "Non-positive risk from "
            "actual fill price."
        )

    return_values = {
        horizon:
            _mark_to_market_return(
                bars=bars,
                fill_index=(
                    fill_index
                ),
                horizon=(
                    horizon
                ),
                entry_price=(
                    fill_price
                ),
            )
        for horizon
        in RETURN_HORIZONS
    }

    held_bars = bars[
        fill_index:
        fill_index
        + horizon_days
    ]

    event_label: (
        OutcomeLabel | None
    ) = None

    exit_date: date | None = None
    exit_price: float | None = None

    target_hit = False
    stop_hit = False

    target_hit_date: (
        date | None
    ) = None

    stop_hit_date: (
        date | None
    ) = None

    sequence_ambiguous = False

    event_index: int | None = None

    for index, bar in enumerate(
        held_bars
    ):
        high = _float(
            bar["high"]
        )

        low = _float(
            bar["low"]
        )

        stop_touched = (
            low
            <= stop_price
        )

        target_touched = (
            high
            >= target_primary
        )

        if (
            stop_touched
            and target_touched
        ):
            sequence_ambiguous = True

            event_label = "STOP"

            stop_hit = True

            stop_hit_date = (
                bar[
                    "trading_date"
                ]
            )

            exit_date = (
                stop_hit_date
            )

            exit_price = (
                stop_price
            )

            event_index = index
            break

        if stop_touched:
            event_label = "STOP"

            stop_hit = True

            stop_hit_date = (
                bar[
                    "trading_date"
                ]
            )

            exit_date = (
                stop_hit_date
            )

            exit_price = (
                stop_price
            )

            event_index = index
            break

        if target_touched:
            event_label = "TARGET"

            target_hit = True

            target_hit_date = (
                bar[
                    "trading_date"
                ]
            )

            exit_date = (
                target_hit_date
            )

            exit_price = (
                target_primary
            )

            event_index = index
            break

    if event_index is not None:
        path_bars = held_bars[
            :event_index + 1
        ]

        bars_held = (
            event_index
            + 1
        )

        horizon_complete = True

    else:
        path_bars = held_bars

        bars_held = len(
            held_bars
        )

        if (
            len(held_bars)
            >= horizon_days
        ):
            event_label = (
                "EXPIRED"
            )

            horizon_complete = True

            exit_date = (
                held_bars[-1][
                    "trading_date"
                ]
            )

            exit_price = _float(
                held_bars[-1][
                    "close"
                ]
            )

        else:
            event_label = "OPEN"

            horizon_complete = False

    highs = [
        _float(
            row["high"]
        )
        for row in path_bars
    ]

    lows = [
        _float(
            row["low"]
        )
        for row in path_bars
    ]

    mfe = (
        max(highs)
        / fill_price
        - 1.0
    )

    mae = (
        min(lows)
        / fill_price
        - 1.0
    )

    mfe_r = (
        (
            max(highs)
            - fill_price
        )
        / risk_per_share
    )

    mae_r = (
        (
            min(lows)
            - fill_price
        )
        / risk_per_share
    )

    realized_return: (
        float | None
    ) = None

    realized_r: (
        float | None
    ) = None

    if (
        exit_price is not None
    ):
        realized_return = (
            exit_price
            / fill_price
            - 1.0
        )

        realized_r = (
            (
                exit_price
                - fill_price
            )
            / risk_per_share
        )

    return SignalOutcomeResult(
        evaluated_through=(
            evaluated_through
        ),
        return_t1=(
            return_values[1]
        ),
        return_t3=(
            return_values[3]
        ),
        return_t5=(
            return_values[5]
        ),
        return_t10=(
            return_values[10]
        ),
        return_t20=(
            return_values[20]
        ),
        mfe=_round(
            mfe
        ),
        mae=_round(
            mae
        ),
        target_hit=(
            target_hit
        ),
        stop_hit=(
            stop_hit
        ),
        entry_filled=True,
        entry_date=(
            entry_date
        ),
        entry_price=_round(
            fill_price,
            6,
        ),
        exit_date=(
            exit_date
        ),
        exit_price=_round(
            exit_price,
            6,
        ),
        outcome_label=(
            event_label
        ),
        realized_return=_round(
            realized_return
        ),
        realized_r=_round(
            realized_r
        ),
        mfe_r=_round(
            mfe_r
        ),
        mae_r=_round(
            mae_r
        ),
        bars_to_entry=(
            fill_index
            + 1
        ),
        bars_held=(
            bars_held
        ),
        target_hit_date=(
            target_hit_date
        ),
        stop_hit_date=(
            stop_hit_date
        ),
        horizon_complete=(
            horizon_complete
        ),
        available_bars=(
            available_bars
        ),
        sequence_ambiguous=(
            sequence_ambiguous
        ),
        fill_method=(
            fill_method
        ),
    )


def _max_timestamp(
    values: list[Any],
) -> Any:
    valid = [
        value
        for value in values
        if value is not None
    ]

    if not valid:
        return None

    return max(
        valid
    )


def prepare_signal_outcome_rows(
    *,
    inputs: list[dict[str, Any]],
    evaluation_model_version: str,
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        result = (
            evaluate_signal_outcome(
                entry_low=float(
                    item["entry_low"]
                ),
                entry_high=float(
                    item["entry_high"]
                ),
                stop_price=float(
                    item["stop_price"]
                ),
                target_primary=float(
                    item[
                        "target_primary"
                    ]
                ),
                horizon_days=int(
                    item[
                        "horizon_days"
                    ]
                ),
                bars=item["bars"],
            )
        )

        input_timestamps = [
            item[
                "signal_input_updated_at"
            ],
            item[
                "issued_at"
            ],
        ]

        input_timestamps.extend(
            bar[
                "ingested_at"
            ]
            for bar in item["bars"]
            if bar.get(
                "ingested_at"
            )
            is not None
        )

        input_updated_at = (
            _max_timestamp(
                input_timestamps
            )
        )

        warnings = [
            (
                "RESEARCH_BACKTEST_"
                "FOUNDATION_ONLY"
            ),
            (
                "YAHOO_EOD_IS_THIRD_PARTY_"
                "MARKET_DATA"
            ),
            (
                "DAILY_OHLC_HAS_NO_"
                "INTRADAY_SEQUENCE"
            ),
            (
                "SAME_BAR_TARGET_STOP_"
                "USES_STOP_FIRST"
            ),
            "NO_SLIPPAGE_MODEL",
            "NO_TRANSACTION_FEE_MODEL",
            (
                "CURRENT_UNIVERSE_HISTORY_"
                "IS_SURVIVORSHIP_BIASED"
            ),
            (
                "HISTORICAL_KSEI_AS_OF_DATE_"
                "IS_NOT_PUBLICATION_TIME_SAFE"
            ),
        ]

        if result.sequence_ambiguous:
            warnings.append(
                
                    "SAME_BAR_TARGET_STOP_"
                    "AMBIGUOUS"
                
            )

        evidence = {
            "scope":
                "signal_outcome_v1",

            "source_signal": {
                "signal_id":
                    str(
                        item[
                            "signal_id"
                        ]
                    ),
                "symbol":
                    item["symbol"],
                "sector_code":
                    item[
                        "sector_code"
                    ],
                "signal_date":
                    item[
                        "trading_date"
                    ].isoformat(),
                "trade_setup_model":
                    item[
                        "signal_model_version"
                    ],
            },

            "entry_model": {
                "window_trading_days":
                    ENTRY_WINDOW_DAYS,
                "entry_low":
                    float(
                        item[
                            "entry_low"
                        ]
                    ),
                "entry_high":
                    float(
                        item[
                            "entry_high"
                        ]
                    ),
                "fill_method":
                    result.fill_method,
                "bars_to_entry":
                    result.bars_to_entry,
            },

            "exit_model": {
                "stop_price":
                    float(
                        item[
                            "stop_price"
                        ]
                    ),
                "target_primary":
                    float(
                        item[
                            "target_primary"
                        ]
                    ),
                "horizon_days":
                    int(
                        item[
                            "horizon_days"
                        ]
                    ),
                "same_bar_rule":
                    "STOP_FIRST",
                "sequence_ambiguous":
                    result
                    .sequence_ambiguous,
            },

            "returns": {
                "semantics":
                    (
                        "mark_to_market_close_"
                        "return_n_sessions_"
                        "after_entry"
                    ),
                "realized_return":
                    result
                    .realized_return,
                "realized_r":
                    result.realized_r,
                "mfe":
                    result.mfe,
                "mae":
                    result.mae,
                "mfe_r":
                    result.mfe_r,
                "mae_r":
                    result.mae_r,
            },

            "warnings":
                warnings,
        }

        rows.append(
            {
                "signal_id":
                    item["signal_id"],

                "evaluated_through":
                    result
                    .evaluated_through,

                "return_t1":
                    result.return_t1,

                "return_t3":
                    result.return_t3,

                "return_t5":
                    result.return_t5,

                "return_t10":
                    result.return_t10,

                "return_t20":
                    result.return_t20,

                "mfe":
                    result.mfe,

                "mae":
                    result.mae,

                "target_hit":
                    result.target_hit,

                "stop_hit":
                    result.stop_hit,

                "target_hit_at":
                    None,

                "stop_hit_at":
                    None,

                "time_to_target_hours":
                    None,

                "entry_filled":
                    result.entry_filled,

                "entry_date":
                    result.entry_date,

                "entry_price":
                    result.entry_price,

                "exit_date":
                    result.exit_date,

                "exit_price":
                    result.exit_price,

                "outcome_label":
                    result.outcome_label,

                "realized_return":
                    result
                    .realized_return,

                "realized_r":
                    result.realized_r,

                "mfe_r":
                    result.mfe_r,

                "mae_r":
                    result.mae_r,

                "bars_to_entry":
                    result.bars_to_entry,

                "bars_held":
                    result.bars_held,

                "target_hit_date":
                    result
                    .target_hit_date,

                "stop_hit_date":
                    result.stop_hit_date,

                "horizon_complete":
                    result
                    .horizon_complete,

                "available_bars":
                    result.available_bars,

                "sequence_ambiguous":
                    result
                    .sequence_ambiguous,

                "evaluation_model_version":
                    evaluation_model_version,

                "input_updated_at":
                    input_updated_at,

                "evidence":
                    evidence,
            }
        )

    return rows


def resolve_signal_outcome_build_mode(
    *,
    force: bool,
    state_exists: bool,
    input_model_matches: bool,
    stored_rows: int,
    expected_rows: int,
    processed_through: date | None,
    latest_price_date: date,
    stored_input_updated_at: Any,
    current_input_updated_at: Any,
) -> OutcomeBuildMode:
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

    if processed_through > latest_price_date:
        raise RuntimeError(
            "Signal outcome build state is "
            "ahead of available EOD prices."
        )

    if (
        processed_through
        == latest_price_date
        and stored_input_updated_at
        == current_input_updated_at
    ):
        return "UP_TO_DATE"

    return "REFRESH"