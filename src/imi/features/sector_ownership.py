from datetime import date
from typing import Any, Literal
from uuid import UUID

SECTOR_OWNERSHIP_VERSION = (
    "sector_ownership_v1"
)

BREADTH_WEIGHT = 0.65
INTENSITY_WEIGHT = 0.35

STOCK_DELTA_CLIP_PP = 0.50

INTENSITY_REFERENCE_PP = 0.25

EXTREME_MOVE_THRESHOLD_PP = 5.0

LOW_COVERAGE_THRESHOLD_PCT = 80.0
LOW_COVERAGE_PENALTY = 0.50


SectorOwnershipBuildMode = Literal[
    "FULL",
    "INCREMENTAL",
    "UP_TO_DATE",
]


def build_sector_ownership_model_version(
    snapshot_date: date,
) -> str:
    return (
        f"{SECTOR_OWNERSHIP_VERSION}"
        f"_current_{snapshot_date:%Y%m%d}"
        "_ksei_official"
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


def calculate_coverage_pct(
    *,
    eligible_count: int,
    current_universe_count: int,
) -> float:
    if current_universe_count <= 0:
        raise ValueError(
            "current_universe_count "
            "must be greater than zero."
        )

    if eligible_count < 0:
        raise ValueError(
            "eligible_count cannot "
            "be negative."
        )

    coverage = (
        eligible_count
        / current_universe_count
        * 100.0
    )

    return round(
        _clamp(
            coverage
        ),
        6,
    )


def calculate_ownership_breadth_score(
    *,
    clean_count: int,
    accumulating_count: int,
    distributing_count: int,
) -> float:
    if clean_count < 0:
        raise ValueError(
            "clean_count cannot "
            "be negative."
        )

    if accumulating_count < 0:
        raise ValueError(
            "accumulating_count cannot "
            "be negative."
        )

    if distributing_count < 0:
        raise ValueError(
            "distributing_count cannot "
            "be negative."
        )

    if clean_count == 0:
        return 50.0

    directional_balance = (
        accumulating_count
        - distributing_count
    ) / clean_count

    score = (
        50.0
        + 50.0
        * directional_balance
    )

    return round(
        _clamp(
            score
        ),
        6,
    )


def calculate_ownership_intensity_score(
    *,
    avg_clean_clipped_delta_pp: float,
) -> float:
    score = (
        50.0
        + (
            avg_clean_clipped_delta_pp
            / INTENSITY_REFERENCE_PP
            * 50.0
        )
    )

    return round(
        _clamp(
            score
        ),
        6,
    )


def calculate_sector_ownership_score(
    *,
    breadth_score: float,
    intensity_score: float,
    coverage_pct: float,
) -> float:
    raw_score = (
        BREADTH_WEIGHT
        * breadth_score
        + INTENSITY_WEIGHT
        * intensity_score
    )

    if (
        coverage_pct
        < LOW_COVERAGE_THRESHOLD_PCT
    ):
        raw_score = (
            50.0
            + (
                raw_score
                - 50.0
            )
            * LOW_COVERAGE_PENALTY
        )

    return round(
        _clamp(
            raw_score
        ),
        6,
    )


def classify_sector_ownership_signal(
    score: float,
) -> str:
    if score >= 65.0:
        return "STRONG_ACCUMULATION"

    if score >= 55.0:
        return "ACCUMULATION"

    if score <= 35.0:
        return "STRONG_DISTRIBUTION"

    if score <= 45.0:
        return "DISTRIBUTION"

    return "NEUTRAL"


def resolve_sector_ownership_build_mode(
    *,
    existing_last_date: date | None,
    existing_latest_sector_count: int,
    existing_expected_sector_count: int,
    latest_input_date: date,
    force: bool,
) -> SectorOwnershipBuildMode:
    if force:
        return "FULL"

    if existing_last_date is None:
        return "FULL"

    if existing_last_date > latest_input_date:
        raise RuntimeError(
            "Sector ownership data is "
            "ahead of ownership trend "
            "input: "
            f"stored={existing_last_date}, "
            f"input={latest_input_date}."
        )

    if (
        existing_latest_sector_count
        != existing_expected_sector_count
    ):
        return "FULL"

    if (
        existing_last_date
        == latest_input_date
    ):
        return "UP_TO_DATE"

    return "INCREMENTAL"


def prepare_sector_ownership_rows(
    *,
    inputs: list[dict[str, Any]],
    source_id: UUID,
    input_model_version: str,
    model_version: str,
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        eligible_count = int(
            item["eligible_count"]
        )

        current_universe_count = int(
            item[
                "current_universe_count"
            ]
        )

        clean_count = int(
            item["clean_count"]
        )

        accumulating_count = int(
            item[
                "accumulating_count"
            ]
        )

        stable_count = int(
            item["stable_count"]
        )

        distributing_count = int(
            item[
                "distributing_count"
            ]
        )

        corporate_action_risk_count = int(
            item[
                "corporate_action_risk_count"
            ]
        )

        snapshot_gap_count = int(
            item[
                "snapshot_gap_count"
            ]
        )

        extreme_move_count = int(
            item[
                "extreme_move_count"
            ]
        )

        if eligible_count <= 0:
            raise ValueError(
                "eligible_count must be "
                "greater than zero."
            )

        if current_universe_count <= 0:
            raise ValueError(
                "current_universe_count "
                "must be greater than zero."
            )

        if clean_count < 0:
            raise ValueError(
                "clean_count cannot "
                "be negative."
            )

        if clean_count > eligible_count:
            raise ValueError(
                "clean_count cannot exceed "
                "eligible_count."
            )

        classified_count = (
            accumulating_count
            + stable_count
            + distributing_count
        )

        if (
            classified_count
            != clean_count
        ):
            raise ValueError(
                "Clean population mismatch "
                f"for {item['sector_code']} "
                f"on {item['as_of_date']}: "
                f"clean={clean_count}, "
                f"classified="
                f"{classified_count}."
            )

        for (
            label,
            count,
        ) in (
            (
                "corporate_action_risk_count",
                corporate_action_risk_count,
            ),
            (
                "snapshot_gap_count",
                snapshot_gap_count,
            ),
            (
                "extreme_move_count",
                extreme_move_count,
            ),
        ):
            if (
                count < 0
                or count > eligible_count
            ):
                raise ValueError(
                    f"{label} outside "
                    "valid population."
                )

        avg_delta = float(
            item[
                "avg_delta_foreign_ownership_pp"
            ]
        )

        raw_clean_delta = item[
            "avg_clean_clipped_delta_pp"
        ]

        if raw_clean_delta is None:
            if clean_count != 0:
                raise ValueError(
                    "avg_clean_clipped_delta_pp "
                    "is NULL despite non-zero "
                    "clean population."
                )

            avg_clean_clipped_delta_pp = 0.0

        else:
            avg_clean_clipped_delta_pp = (
                float(
                    raw_clean_delta
                )
            )

        coverage_pct = (
            calculate_coverage_pct(
                eligible_count=(
                    eligible_count
                ),
                current_universe_count=(
                    current_universe_count
                ),
            )
        )

        breadth_score = (
            calculate_ownership_breadth_score(
                clean_count=clean_count,
                accumulating_count=(
                    accumulating_count
                ),
                distributing_count=(
                    distributing_count
                ),
            )
        )

        intensity_score = (
            calculate_ownership_intensity_score(
                avg_clean_clipped_delta_pp=(
                    avg_clean_clipped_delta_pp
                ),
            )
        )

        score = (
            calculate_sector_ownership_score(
                breadth_score=(
                    breadth_score
                ),
                intensity_score=(
                    intensity_score
                ),
                coverage_pct=(
                    coverage_pct
                ),
            )
        )

        signal_label = (
            classify_sector_ownership_signal(
                score
            )
        )

        low_coverage_flag = (
            coverage_pct
            < LOW_COVERAGE_THRESHOLD_PCT
        )

        rows.append(
            {
                "as_of_date":
                    item["as_of_date"],

                "sector_code":
                    str(
                        item[
                            "sector_code"
                        ]
                    ),

                "eligible_count":
                    eligible_count,

                "current_universe_count":
                    current_universe_count,

                "coverage_pct":
                    coverage_pct,

                "clean_count":
                    clean_count,

                "accumulating_count":
                    accumulating_count,

                "stable_count":
                    stable_count,

                "distributing_count":
                    distributing_count,

                "corporate_action_risk_count":
                    corporate_action_risk_count,

                "snapshot_gap_count":
                    snapshot_gap_count,

                "extreme_move_count":
                    extreme_move_count,

                "avg_delta_foreign_ownership_pp":
                    round(
                        avg_delta,
                        8,
                    ),

                "avg_clean_clipped_delta_pp":
                    round(
                        avg_clean_clipped_delta_pp,
                        8,
                    ),

                "breadth_score":
                    breadth_score,

                "intensity_score":
                    intensity_score,

                "score":
                    score,

                "signal_label":
                    signal_label,

                "low_coverage_flag":
                    low_coverage_flag,

                "source_id":
                    source_id,

                "input_model_version":
                    input_model_version,

                "model_version":
                    model_version,
            }
        )

    return rows