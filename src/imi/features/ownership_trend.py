from dataclasses import dataclass
from datetime import date
from typing import Any, Literal
from uuid import UUID

OWNERSHIP_TREND_MODEL_VERSION = (
    "ownership_trend_v1_ksei_official"
)

ACCUMULATION_THRESHOLD_PP = 0.10
DISTRIBUTION_THRESHOLD_PP = -0.10

STRONG_MOVE_REFERENCE_PP = 0.50

CORPORATE_ACTION_THRESHOLD_PCT = 1.0
SNAPSHOT_GAP_THRESHOLD_DAYS = 45


OwnershipTrendBuildMode = Literal[
    "FULL",
    "INCREMENTAL",
    "UP_TO_DATE",
]


@dataclass(frozen=True)
class OwnershipTrendMetrics:
    delta_foreign_ownership_pp: float
    delta_foreign_shares: int
    delta_security_number_pct: float
    normalized_foreign_share_change_pct: float

    days_between_snapshots: int

    trend_label: str
    signal_strength: float

    corporate_action_risk: bool
    snapshot_gap_flag: bool


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


def classify_ownership_trend(
    delta_foreign_ownership_pp: float,
) -> str:
    if (
        delta_foreign_ownership_pp
        >= ACCUMULATION_THRESHOLD_PP
    ):
        return "ACCUMULATING"

    if (
        delta_foreign_ownership_pp
        <= DISTRIBUTION_THRESHOLD_PP
    ):
        return "DISTRIBUTING"

    return "STABLE"


def calculate_signal_strength(
    *,
    delta_foreign_ownership_pp: float,
    corporate_action_risk: bool,
    snapshot_gap_flag: bool,
) -> float:
    raw_strength = (
        abs(
            delta_foreign_ownership_pp
        )
        / STRONG_MOVE_REFERENCE_PP
        * 100.0
    )

    strength = _clamp(
        raw_strength
    )

    if corporate_action_risk:
        strength *= 0.50

    if snapshot_gap_flag:
        strength *= 0.75

    return round(
        _clamp(strength),
        4,
    )


def calculate_ownership_trend(
    *,
    as_of_date: date,
    previous_as_of_date: date,
    foreign_ownership_pct: float,
    previous_foreign_ownership_pct: float,
    foreign_shares: int,
    previous_foreign_shares: int,
    security_number: int,
    previous_security_number: int,
) -> OwnershipTrendMetrics:
    if as_of_date <= previous_as_of_date:
        raise ValueError(
            "as_of_date must be after "
            "previous_as_of_date."
        )

    if not (
        0.0
        <= foreign_ownership_pct
        <= 100.0
    ):
        raise ValueError(
            "foreign_ownership_pct "
            "must be between 0 and 100."
        )

    if not (
        0.0
        <= previous_foreign_ownership_pct
        <= 100.0
    ):
        raise ValueError(
            "previous_foreign_ownership_pct "
            "must be between 0 and 100."
        )

    if foreign_shares < 0:
        raise ValueError(
            "foreign_shares cannot "
            "be negative."
        )

    if previous_foreign_shares < 0:
        raise ValueError(
            "previous_foreign_shares "
            "cannot be negative."
        )

    if security_number <= 0:
        raise ValueError(
            "security_number must be "
            "greater than zero."
        )

    if previous_security_number <= 0:
        raise ValueError(
            "previous_security_number "
            "must be greater than zero."
        )

    delta_foreign_ownership_pp = (
        foreign_ownership_pct
        - previous_foreign_ownership_pct
    )

    delta_foreign_shares = (
        foreign_shares
        - previous_foreign_shares
    )

    delta_security_number = (
        security_number
        - previous_security_number
    )

    delta_security_number_pct = (
        delta_security_number
        / previous_security_number
        * 100.0
    )

    normalized_foreign_share_change_pct = (
        delta_foreign_shares
        / previous_security_number
        * 100.0
    )

    days_between_snapshots = (
        as_of_date
        - previous_as_of_date
    ).days

    corporate_action_risk = (
        abs(
            delta_security_number_pct
        )
        >= CORPORATE_ACTION_THRESHOLD_PCT
    )

    snapshot_gap_flag = (
        days_between_snapshots
        > SNAPSHOT_GAP_THRESHOLD_DAYS
    )

    trend_label = (
        classify_ownership_trend(
            delta_foreign_ownership_pp
        )
    )

    signal_strength = (
        calculate_signal_strength(
            delta_foreign_ownership_pp=(
                delta_foreign_ownership_pp
            ),
            corporate_action_risk=(
                corporate_action_risk
            ),
            snapshot_gap_flag=(
                snapshot_gap_flag
            ),
        )
    )

    return OwnershipTrendMetrics(
        delta_foreign_ownership_pp=round(
            delta_foreign_ownership_pp,
            8,
        ),
        delta_foreign_shares=(
            delta_foreign_shares
        ),
        delta_security_number_pct=round(
            delta_security_number_pct,
            8,
        ),
        normalized_foreign_share_change_pct=(
            round(
                normalized_foreign_share_change_pct,
                8,
            )
        ),
        days_between_snapshots=(
            days_between_snapshots
        ),
        trend_label=trend_label,
        signal_strength=signal_strength,
        corporate_action_risk=(
            corporate_action_risk
        ),
        snapshot_gap_flag=(
            snapshot_gap_flag
        ),
    )


def resolve_ownership_trend_build_mode(
    *,
    existing_last_date: date | None,
    existing_latest_count: int,
    existing_expected_count: int,
    latest_input_date: date,
    force: bool,
) -> OwnershipTrendBuildMode:
    if force:
        return "FULL"

    if existing_last_date is None:
        return "FULL"

    if existing_last_date > latest_input_date:
        raise RuntimeError(
            "Ownership trend data is "
            "ahead of ownership input: "
            f"stored={existing_last_date}, "
            f"input={latest_input_date}."
        )

    if (
        existing_latest_count
        != existing_expected_count
    ):
        return "FULL"

    if (
        existing_last_date
        == latest_input_date
    ):
        return "UP_TO_DATE"

    return "INCREMENTAL"


def prepare_ownership_trend_rows(
    *,
    inputs: list[dict[str, Any]],
    source_id: UUID,
    model_version: str = (
        OWNERSHIP_TREND_MODEL_VERSION
    ),
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for item in inputs:
        metrics = calculate_ownership_trend(
            as_of_date=(
                item["as_of_date"]
            ),
            previous_as_of_date=(
                item[
                    "previous_as_of_date"
                ]
            ),
            foreign_ownership_pct=float(
                item[
                    "foreign_ownership_pct"
                ]
            ),
            previous_foreign_ownership_pct=(
                float(
                    item[
                        "previous_foreign_ownership_pct"
                    ]
                )
            ),
            foreign_shares=int(
                item["foreign_shares"]
            ),
            previous_foreign_shares=int(
                item[
                    "previous_foreign_shares"
                ]
            ),
            security_number=int(
                item["security_number"]
            ),
            previous_security_number=int(
                item[
                    "previous_security_number"
                ]
            ),
        )

        rows.append(
            {
                "instrument_id":
                    item["instrument_id"],

                "as_of_date":
                    item["as_of_date"],

                "previous_as_of_date":
                    item[
                        "previous_as_of_date"
                    ],

                "foreign_ownership_pct":
                    round(
                        float(
                            item[
                                "foreign_ownership_pct"
                            ]
                        ),
                        8,
                    ),

                "previous_foreign_ownership_pct":
                    round(
                        float(
                            item[
                                "previous_foreign_ownership_pct"
                            ]
                        ),
                        8,
                    ),

                "delta_foreign_ownership_pp":
                    metrics
                    .delta_foreign_ownership_pp,

                "foreign_shares":
                    int(
                        item[
                            "foreign_shares"
                        ]
                    ),

                "previous_foreign_shares":
                    int(
                        item[
                            "previous_foreign_shares"
                        ]
                    ),

                "delta_foreign_shares":
                    metrics
                    .delta_foreign_shares,

                "security_number":
                    int(
                        item[
                            "security_number"
                        ]
                    ),

                "previous_security_number":
                    int(
                        item[
                            "previous_security_number"
                        ]
                    ),

                "delta_security_number_pct":
                    metrics
                    .delta_security_number_pct,

                "normalized_foreign_share_change_pct":
                    metrics
                    .normalized_foreign_share_change_pct,

                "days_between_snapshots":
                    metrics
                    .days_between_snapshots,

                "trend_label":
                    metrics.trend_label,

                "signal_strength":
                    metrics.signal_strength,

                "corporate_action_risk":
                    metrics
                    .corporate_action_risk,

                "snapshot_gap_flag":
                    metrics
                    .snapshot_gap_flag,

                "source_id":
                    source_id,

                "model_version":
                    model_version,
            }
        )

    return rows