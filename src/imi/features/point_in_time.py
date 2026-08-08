from dataclasses import dataclass
from datetime import (
    date,
    datetime,
)
from typing import Any, Literal

POINT_IN_TIME_VERSION = (
    "point_in_time_v1"
)


AvailabilityStatus = Literal[
    "KNOWN",
    "UNKNOWN",
    "ESTIMATED",
]


@dataclass(frozen=True)
class AvailabilityDecision:
    observation_date: date

    published_at: datetime | None
    available_at: datetime | None

    availability_status: AvailabilityStatus

    point_in_time_safe: bool

    reason: str


@dataclass(frozen=True)
class PointInTimeCoverage:
    total: int

    known: int
    unknown: int
    estimated: int

    safe: int

    coverage_ratio: float | None


def build_observation_key(
    *parts: Any,
) -> str:
    values = [
        str(part).strip()
        for part in parts
        if (
            part is not None
            and str(part).strip()
        )
    ]

    if not values:
        raise ValueError(
            "Observation key cannot "
            "be empty."
        )

    return "|".join(
        values
    )


def evaluate_availability(
    *,
    observation_date: date,
    published_at: datetime | None,
    available_at: datetime | None,
    status: AvailabilityStatus,
) -> AvailabilityDecision:
    if (
        published_at is not None
        and available_at is not None
        and available_at < published_at
    ):
        raise ValueError(
            "available_at cannot be "
            "before published_at."
        )

    if status == "UNKNOWN":
        return AvailabilityDecision(
            observation_date=(
                observation_date
            ),
            published_at=(
                published_at
            ),
            available_at=(
                available_at
            ),
            availability_status=(
                status
            ),
            point_in_time_safe=False,
            reason=(
                "AVAILABILITY_UNKNOWN"
            ),
        )

    if available_at is None:
        return AvailabilityDecision(
            observation_date=(
                observation_date
            ),
            published_at=(
                published_at
            ),
            available_at=None,
            availability_status=(
                status
            ),
            point_in_time_safe=False,
            reason=(
                "AVAILABLE_AT_MISSING"
            ),
        )

    if status == "ESTIMATED":
        return AvailabilityDecision(
            observation_date=(
                observation_date
            ),
            published_at=(
                published_at
            ),
            available_at=(
                available_at
            ),
            availability_status=(
                status
            ),
            point_in_time_safe=False,
            reason=(
                "AVAILABILITY_ESTIMATED"
            ),
        )

    return AvailabilityDecision(
        observation_date=(
            observation_date
        ),
        published_at=(
            published_at
        ),
        available_at=(
            available_at
        ),
        availability_status=(
            status
        ),
        point_in_time_safe=True,
        reason=(
            "KNOWN_AVAILABLE_AT"
        ),
    )


def information_available_on(
    *,
    signal_date: date,
    decision: AvailabilityDecision,
) -> bool:
    if not decision.point_in_time_safe:
        return False

    if decision.available_at is None:
        return False

    return (
        decision.available_at.date()
        <= signal_date
    )


def historical_membership_active(
    *,
    signal_date: date,
    valid_from: date,
    valid_to: date | None,
    membership_status: str,
    point_in_time_safe: bool,
) -> bool:
    if not point_in_time_safe:
        return False

    if membership_status != "ACTIVE":
        return False

    if signal_date < valid_from:
        return False

    return (
        valid_to is None
        or signal_date <= valid_to
    )


def calculate_pit_coverage(
    rows: list[dict[str, Any]],
) -> PointInTimeCoverage:
    total = len(
        rows
    )

    known = sum(
        row[
            "availability_status"
        ]
        == "KNOWN"
        for row in rows
    )

    unknown = sum(
        row[
            "availability_status"
        ]
        == "UNKNOWN"
        for row in rows
    )

    estimated = sum(
        row[
            "availability_status"
        ]
        == "ESTIMATED"
        for row in rows
    )

    safe = sum(
        bool(
            row[
                "point_in_time_safe"
            ]
        )
        for row in rows
    )

    coverage_ratio = (
        None
        if total == 0
        else round(
            safe / total,
            8,
        )
    )

    return PointInTimeCoverage(
        total=total,
        known=known,
        unknown=unknown,
        estimated=estimated,
        safe=safe,
        coverage_ratio=(
            coverage_ratio
        ),
    )


def prepare_unknown_availability_row(
    *,
    dataset_code: str,
    observation_key: str,
    observation_date: date,
    source_code: str,
    source_reference: str | None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = evaluate_availability(
        observation_date=(
            observation_date
        ),
        published_at=None,
        available_at=None,
        status="UNKNOWN",
    )

    return {
        "dataset_code":
            dataset_code,

        "observation_key":
            observation_key,

        "observation_date":
            observation_date,

        "published_at":
            decision.published_at,

        "available_at":
            decision.available_at,

        "availability_status":
            decision
            .availability_status,

        "source_code":
            source_code,

        "source_reference":
            source_reference,

        "point_in_time_safe":
            decision
            .point_in_time_safe,

        "evidence": {
            "scope":
                POINT_IN_TIME_VERSION,

            "reason":
                decision.reason,

            "source":
                (
                    evidence
                    or {}
                ),

            "warning":
                (
                    "No publication timestamp "
                    "has been fabricated."
                ),
        },
    }


def prepare_known_availability_row(
    *,
    dataset_code: str,
    observation_key: str,
    observation_date: date,
    available_at: datetime,
    source_code: str,
    source_reference: str | None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = evaluate_availability(
        observation_date=(
            observation_date
        ),
        published_at=None,
        available_at=(
            available_at
        ),
        status="KNOWN",
    )

    return {
        "dataset_code":
            dataset_code,

        "observation_key":
            observation_key,

        "observation_date":
            observation_date,

        "published_at":
            None,

        "available_at":
            decision.available_at,

        "availability_status":
            decision
            .availability_status,

        "source_code":
            source_code,

        "source_reference":
            source_reference,

        "point_in_time_safe":
            decision
            .point_in_time_safe,

        "evidence": {
            "scope":
                POINT_IN_TIME_VERSION,

            "reason":
                "SYSTEM_OBSERVED_AT",

            "source":
                (
                    evidence
                    or {}
                ),

            "warning":
                (
                    "available_at is the "
                    "system observation time, "
                    "not a fabricated official "
                    "publication timestamp."
                ),
        },
    }


def prepare_current_universe_membership_rows(
    inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for item in inputs:
        ingested_at = item[
            "ingested_at"
        ]

        safe = (
            ingested_at
            is not None
        )

        rows.append(
            {
                "instrument_id":
                    item[
                        "instrument_id"
                    ],

                "universe_code":
                    "IDX_ALL_CURRENT",

                "valid_from":
                    item[
                        "snapshot_date"
                    ],

                "valid_to":
                    None,

                "membership_status":
                    "ACTIVE",

                "source_code":
                    "IDX_OFFICIAL",

                "available_at":
                    ingested_at,

                "availability_status":
                    (
                        "KNOWN"
                        if safe
                        else "UNKNOWN"
                    ),

                "point_in_time_safe":
                    safe,

                "evidence": {
                    "scope":
                        POINT_IN_TIME_VERSION,

                    "symbol":
                        item[
                            "symbol"
                        ],

                    "snapshot_date":
                        item[
                            "snapshot_date"
                        ].isoformat(),

                    "warning":
                        (
                            "Current-universe "
                            "observation only. "
                            "This does not "
                            "reconstruct historical "
                            "IDX membership."
                        ),
                },
            }
        )

    return rows


def prepare_current_lifecycle_rows(
    inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for item in inputs:
        snapshot_date = item[
            "snapshot_date"
        ]

        ingested_at = item[
            "ingested_at"
        ]

        delisted_date = item[
            "delisted_date"
        ]

        if (
            delisted_date is not None
            and delisted_date
            <= snapshot_date
        ):
            lifecycle_status = (
                "DELISTED"
            )
        else:
            lifecycle_status = (
                "LISTED"
            )

        rows.append(
            {
                "instrument_id":
                    item[
                        "instrument_id"
                    ],

                "effective_from":
                    snapshot_date,

                "effective_to":
                    None,

                "lifecycle_status":
                    lifecycle_status,

                "listing_date":
                    item[
                        "listed_date"
                    ],

                "delisting_date":
                    delisted_date,

                "source_code":
                    "IDX_OFFICIAL",

                "source_reference":
                    (
                        "IDX company profiles"
                    ),

                "available_at":
                    ingested_at,

                "availability_status":
                    (
                        "KNOWN"
                        if ingested_at
                        is not None
                        else "UNKNOWN"
                    ),

                "quality":
                    "VALID",

                "evidence": {
                    "scope":
                        POINT_IN_TIME_VERSION,

                    "symbol":
                        item[
                            "symbol"
                        ],

                    "warning":
                        (
                            "Lifecycle status is "
                            "observed from the "
                            "current IDX profile. "
                            "Historical lifecycle "
                            "has not yet been "
                            "reconstructed."
                        ),
                },
            }
        )

    return rows