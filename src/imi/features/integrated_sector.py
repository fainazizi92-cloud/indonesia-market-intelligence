import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

INTEGRATED_SECTOR_VERSION = (
    "integrated_sector_v1"
)

BASE_TECHNICAL_WEIGHT = 0.80
BASE_OWNERSHIP_WEIGHT = 0.20

OWNERSHIP_STALE_DAYS = 45


IntegratedSectorBuildMode = Literal[
    "FULL",
    "INCREMENTAL",
    "UP_TO_DATE",
]


CURRENT_UNIVERSE_PATTERN = re.compile(
    r"current_(?P<date>\d{8})"
)


@dataclass(frozen=True)
class IntegratedSectorMetrics:
    ownership_age_days: int
    ownership_stale_flag: bool

    technical_weight: float
    ownership_weight: float

    integrated_score: float
    integrated_label: str
    alignment_label: str


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


def extract_current_universe_date(
    model_version: str,
) -> date:
    match = CURRENT_UNIVERSE_PATTERN.search(
        model_version
    )

    if match is None:
        raise ValueError(
            "Model version does not "
            "contain a current-universe "
            f"date: {model_version}"
        )

    value = match.group(
        "date"
    )

    try:
        return date(
            int(value[0:4]),
            int(value[4:6]),
            int(value[6:8]),
        )

    except ValueError as exc:
        raise ValueError(
            "Invalid current-universe "
            f"date in model version: "
            f"{model_version}"
        ) from exc


def build_integrated_sector_model_version(
    universe_date: date,
) -> str:
    return (
        f"{INTEGRATED_SECTOR_VERSION}"
        f"_current_{universe_date:%Y%m%d}"
    )


def classify_integrated_score(
    score: float,
) -> str:
    if score >= 65.0:
        return "STRONG_BULLISH"

    if score >= 55.0:
        return "BULLISH"

    if score <= 35.0:
        return "STRONG_BEARISH"

    if score <= 45.0:
        return "BEARISH"

    return "NEUTRAL"


def score_direction(
    score: float,
) -> str:
    if score >= 55.0:
        return "BULLISH"

    if score <= 45.0:
        return "BEARISH"

    return "NEUTRAL"


def calculate_effective_weights(
    *,
    ownership_age_days: int,
) -> tuple[float, float, bool]:
    if ownership_age_days < 0:
        raise ValueError(
            "ownership_age_days "
            "cannot be negative."
        )

    stale = (
        ownership_age_days
        > OWNERSHIP_STALE_DAYS
    )

    if stale:
        return (
            1.0,
            0.0,
            True,
        )

    return (
        BASE_TECHNICAL_WEIGHT,
        BASE_OWNERSHIP_WEIGHT,
        False,
    )


def classify_alignment(
    *,
    technical_score: float,
    ownership_score: float,
    ownership_stale_flag: bool,
) -> str:
    if ownership_stale_flag:
        return "OWNERSHIP_STALE"

    technical_direction = (
        score_direction(
            technical_score
        )
    )

    ownership_direction = (
        score_direction(
            ownership_score
        )
    )

    if (
        technical_direction
        == "BULLISH"
        and ownership_direction
        == "BULLISH"
    ):
        return "CONFIRMED_BULLISH"

    if (
        technical_direction
        == "BEARISH"
        and ownership_direction
        == "BEARISH"
    ):
        return "CONFIRMED_BEARISH"

    if (
        technical_direction
        == "NEUTRAL"
        and ownership_direction
        == "NEUTRAL"
    ):
        return "NEUTRAL"

    if (
        technical_direction
        in {
            "BULLISH",
            "BEARISH",
        }
        and ownership_direction
        == "NEUTRAL"
    ):
        return "TECHNICAL_LEAD"

    if (
        technical_direction
        == "NEUTRAL"
        and ownership_direction
        in {
            "BULLISH",
            "BEARISH",
        }
    ):
        return "OWNERSHIP_LEAD"

    if (
        technical_direction
        != "NEUTRAL"
        and ownership_direction
        != "NEUTRAL"
        and technical_direction
        != ownership_direction
    ):
        return "DIVERGENCE"

    return "NEUTRAL"


def calculate_integrated_sector_metrics(
    *,
    trading_date: date,
    ownership_as_of_date: date,
    technical_score: float,
    ownership_score: float,
) -> IntegratedSectorMetrics:
    if (
        ownership_as_of_date
        > trading_date
    ):
        raise ValueError(
            "Ownership snapshot cannot "
            "be after trading_date."
        )

    if not (
        0.0
        <= technical_score
        <= 100.0
    ):
        raise ValueError(
            "technical_score must be "
            "between 0 and 100."
        )

    if not (
        0.0
        <= ownership_score
        <= 100.0
    ):
        raise ValueError(
            "ownership_score must be "
            "between 0 and 100."
        )

    ownership_age_days = (
        trading_date
        - ownership_as_of_date
    ).days

    (
        technical_weight,
        ownership_weight,
        ownership_stale_flag,
    ) = calculate_effective_weights(
        ownership_age_days=(
            ownership_age_days
        )
    )

    integrated_score = (
        technical_score
        * technical_weight
        + ownership_score
        * ownership_weight
    )

    integrated_score = round(
        _clamp(
            integrated_score
        ),
        6,
    )

    integrated_label = (
        classify_integrated_score(
            integrated_score
        )
    )

    alignment_label = (
        classify_alignment(
            technical_score=(
                technical_score
            ),
            ownership_score=(
                ownership_score
            ),
            ownership_stale_flag=(
                ownership_stale_flag
            ),
        )
    )

    return IntegratedSectorMetrics(
        ownership_age_days=(
            ownership_age_days
        ),
        ownership_stale_flag=(
            ownership_stale_flag
        ),
        technical_weight=round(
            technical_weight,
            6,
        ),
        ownership_weight=round(
            ownership_weight,
            6,
        ),
        integrated_score=(
            integrated_score
        ),
        integrated_label=(
            integrated_label
        ),
        alignment_label=(
            alignment_label
        ),
    )


def resolve_integrated_sector_build_mode(
    *,
    existing_last_date: date | None,
    existing_latest_sector_count: int,
    existing_expected_sector_count: int,
    existing_ownership_signature: str | None,
    expected_ownership_signature: str | None,
    latest_input_date: date,
    force: bool,
) -> IntegratedSectorBuildMode:
    if force:
        return "FULL"

    if existing_last_date is None:
        return "FULL"

    if (
        existing_last_date
        > latest_input_date
    ):
        raise RuntimeError(
            "Integrated sector dataset "
            "is ahead of technical input: "
            f"stored={existing_last_date}, "
            f"input={latest_input_date}."
        )

    if (
        existing_latest_sector_count
        != existing_expected_sector_count
    ):
        return "FULL"

    if (
        existing_ownership_signature
        != expected_ownership_signature
    ):
        return "FULL"

    if (
        existing_last_date
        == latest_input_date
    ):
        return "UP_TO_DATE"

    return "INCREMENTAL"


def prepare_integrated_sector_rows(
    *,
    inputs: list[dict[str, Any]],
    technical_model_version: str,
    ownership_model_version: str,
    model_version: str,
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        technical_score = float(
            item["technical_score"]
        )

        ownership_score = float(
            item["ownership_score"]
        )

        metrics = (
            calculate_integrated_sector_metrics(
                trading_date=(
                    item["trading_date"]
                ),
                ownership_as_of_date=(
                    item[
                        "ownership_as_of_date"
                    ]
                ),
                technical_score=(
                    technical_score
                ),
                ownership_score=(
                    ownership_score
                ),
            )
        )

        rows.append(
            {
                "trading_date":
                    item["trading_date"],

                "sector_code":
                    str(
                        item[
                            "sector_code"
                        ]
                    ),

                "technical_score":
                    round(
                        technical_score,
                        6,
                    ),

                "technical_rotation_label":
                    str(
                        item[
                            "technical_rotation_label"
                        ]
                    ),

                "ownership_as_of_date":
                    item[
                        "ownership_as_of_date"
                    ],

                "ownership_score":
                    round(
                        ownership_score,
                        6,
                    ),

                "ownership_signal_label":
                    str(
                        item[
                            "ownership_signal_label"
                        ]
                    ),

                "ownership_age_days":
                    metrics
                    .ownership_age_days,

                "ownership_low_coverage_flag":
                    bool(
                        item[
                            "ownership_low_coverage_flag"
                        ]
                    ),

                "ownership_stale_flag":
                    metrics
                    .ownership_stale_flag,

                "technical_weight":
                    metrics
                    .technical_weight,

                "ownership_weight":
                    metrics
                    .ownership_weight,

                "integrated_score":
                    metrics
                    .integrated_score,

                "integrated_label":
                    metrics
                    .integrated_label,

                "alignment_label":
                    metrics
                    .alignment_label,

                "technical_model_version":
                    technical_model_version,

                "ownership_model_version":
                    ownership_model_version,

                "model_version":
                    model_version,
            }
        )

    return rows