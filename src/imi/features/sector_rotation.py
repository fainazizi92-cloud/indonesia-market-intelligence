from datetime import date
from typing import Any, Literal

SECTOR_ROTATION_VERSION = "sector_rotation_v1"

EXPECTED_SECTOR_CODES = (
    "IDXBASIC",
    "IDXCYCLIC",
    "IDXENERGY",
    "IDXFINANCE",
    "IDXHEALTH",
    "IDXINDUST",
    "IDXINFRA",
    "IDXNONCYC",
    "IDXPROPERT",
    "IDXTECHNO",
    "IDXTRANS",
)

RELATIVE_STRENGTH_WEIGHT = 0.45
BREADTH_WEIGHT = 0.35
VOLUME_WEIGHT = 0.20

RS_20D_WEIGHT = 0.65
RS_60D_WEIGHT = 0.35

BREADTH_TREND_WEIGHT = 0.70
BREADTH_DIRECTION_WEIGHT = 0.30

ROTATION_LOOKBACK = 20

SectorBuildMode = Literal[
    "FULL",
    "INCREMENTAL",
    "UP_TO_DATE",
]


def build_sector_model_version(
    snapshot_date: date,
) -> str:
    return (
        f"{SECTOR_ROTATION_VERSION}"
        f"_current_{snapshot_date:%Y%m%d}"
        "_yahoo_eod"
    )


def resolve_sector_build_mode(
    *,
    existing_last_date: date | None,
    existing_latest_sector_count: int,
    latest_input_date: date,
    latest_input_sector_count: int,
    force: bool,
) -> SectorBuildMode:
    if force:
        return "FULL"

    if existing_last_date is None:
        return "FULL"

    if existing_last_date > latest_input_date:
        raise RuntimeError(
            "Sector rotation data is ahead "
            "of sector input data: "
            f"stored={existing_last_date}, "
            f"input={latest_input_date}."
        )

    if (
        existing_latest_sector_count
        != latest_input_sector_count
    ):
        return "FULL"

    if existing_last_date == latest_input_date:
        return "UP_TO_DATE"

    return "INCREMENTAL"


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


def calculate_relative_strength_score(
    *,
    sector_return_20d: float,
    sector_return_60d: float,
    ihsg_return_20d: float,
    ihsg_return_60d: float,
) -> float:
    excess_20d = (
        sector_return_20d
        - ihsg_return_20d
    )

    excess_60d = (
        sector_return_60d
        - ihsg_return_60d
    )

    blended_excess = (
        RS_20D_WEIGHT
        * excess_20d
        + RS_60D_WEIGHT
        * excess_60d
    )

    score = (
        50.0
        + 200.0
        * blended_excess
    )

    return round(
        _clamp(score),
        4,
    )


def calculate_sector_breadth_score(
    *,
    advances: int,
    declines: int,
    unchanged: int,
    pct_above_ema20: float,
    pct_above_ema50: float,
    pct_above_ema200: float,
) -> float:
    total = (
        advances
        + declines
        + unchanged
    )

    if total <= 0:
        return 50.0

    trend_score = (
        pct_above_ema20
        + pct_above_ema50
        + pct_above_ema200
    ) / 3.0

    directional_balance = (
        advances
        - declines
    ) / total

    directional_score = (
        50.0
        + 50.0
        * directional_balance
    )

    score = (
        BREADTH_TREND_WEIGHT
        * trend_score
        + BREADTH_DIRECTION_WEIGHT
        * directional_score
    )

    return round(
        _clamp(score),
        4,
    )


def calculate_volume_score(
    *,
    up_volume: float,
    down_volume: float,
) -> float:
    total_volume = (
        up_volume
        + down_volume
    )

    if total_volume <= 0:
        return 50.0

    balance = (
        up_volume
        - down_volume
    ) / total_volume

    score = (
        50.0
        + 50.0
        * balance
    )

    return round(
        _clamp(score),
        4,
    )


def calculate_sector_composite_score(
    *,
    relative_strength_score: float,
    breadth_score: float,
    volume_score: float,
) -> float:
    score = (
        RELATIVE_STRENGTH_WEIGHT
        * relative_strength_score
        + BREADTH_WEIGHT
        * breadth_score
        + VOLUME_WEIGHT
        * volume_score
    )

    return round(
        _clamp(score),
        4,
    )


def classify_rotation(
    *,
    score: float,
    score_change_20d: float | None,
) -> str:
    if score_change_20d is None:
        if score >= 60.0:
            return "LEADING"

        if score <= 40.0:
            return "LAGGING"

        return "NEUTRAL"

    if (
        score >= 60.0
        and score_change_20d >= 0.0
    ):
        return "LEADING"

    if (
        score <= 40.0
        and score_change_20d <= 0.0
    ):
        return "LAGGING"

    if score_change_20d >= 5.0:
        return "IMPROVING"

    if score_change_20d <= -5.0:
        return "WEAKENING"

    return "NEUTRAL"


def prepare_sector_score_rows(
    *,
    inputs: list[dict[str, Any]],
    model_version: str,
    prior_score_history: (
        dict[str, list[float]]
        | None
    ) = None,
) -> list[dict[str, Any]]:
    histories: dict[
        str,
        list[float],
    ] = {}

    if prior_score_history:
        histories = {
            sector_code: list(scores)
            for sector_code, scores
            in prior_score_history.items()
        }

    output: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        sector_code = str(
            item["sector_code"]
        )

        eligible_count = int(
            item["eligible_count"]
        )

        advances = int(
            item["advances"]
        )

        declines = int(
            item["declines"]
        )

        unchanged = int(
            item["unchanged"]
        )

        directional_total = (
            advances
            + declines
            + unchanged
        )

        if directional_total != eligible_count:
            raise RuntimeError(
                "Sector population mismatch "
                f"for {sector_code} on "
                f"{item['trading_date']}: "
                f"eligible={eligible_count}, "
                f"A+D+U={directional_total}"
            )

        relative_strength_score = (
            calculate_relative_strength_score(
                sector_return_20d=float(
                    item[
                        "sector_return_20d"
                    ]
                ),
                sector_return_60d=float(
                    item[
                        "sector_return_60d"
                    ]
                ),
                ihsg_return_20d=float(
                    item[
                        "ihsg_return_20d"
                    ]
                ),
                ihsg_return_60d=float(
                    item[
                        "ihsg_return_60d"
                    ]
                ),
            )
        )

        breadth_score = (
            calculate_sector_breadth_score(
                advances=advances,
                declines=declines,
                unchanged=unchanged,
                pct_above_ema20=float(
                    item[
                        "pct_above_ema20"
                    ]
                ),
                pct_above_ema50=float(
                    item[
                        "pct_above_ema50"
                    ]
                ),
                pct_above_ema200=float(
                    item[
                        "pct_above_ema200"
                    ]
                ),
            )
        )

        volume_score = (
            calculate_volume_score(
                up_volume=float(
                    item["up_volume"]
                ),
                down_volume=float(
                    item["down_volume"]
                ),
            )
        )

        score = (
            calculate_sector_composite_score(
                relative_strength_score=(
                    relative_strength_score
                ),
                breadth_score=(
                    breadth_score
                ),
                volume_score=(
                    volume_score
                ),
            )
        )

        history = histories.setdefault(
            sector_code,
            [],
        )

        score_change_20d = None

        if len(history) >= ROTATION_LOOKBACK:
            score_change_20d = (
                score
                - history[
                    -ROTATION_LOOKBACK
                ]
            )

        rotation_label = (
            classify_rotation(
                score=score,
                score_change_20d=(
                    score_change_20d
                ),
            )
        )

        history.append(score)

        if len(history) > ROTATION_LOOKBACK:
            del history[
                :-ROTATION_LOOKBACK
            ]

        output.append(
            {
                "trading_date":
                    item["trading_date"],
                "sector_code":
                    sector_code,
                "rotation_label":
                    rotation_label,
                "score":
                    score,
                "relative_strength_score":
                    relative_strength_score,
                "breadth_score":
                    breadth_score,
                "flow_score":
                    None,
                "volume_score":
                    volume_score,
                "catalyst_score":
                    None,
                "model_version":
                    model_version,
            }
        )

    return output