from imi.db import engine
from imi.features.point_in_time import (
    calculate_pit_coverage,
)
from imi.repositories.point_in_time import (
    IDX_UNIVERSE_DATASET_CODE,
    KSEI_DATASET_CODE,
    load_audit_state,
    load_dataset_availability,
    load_ksei_observations,
    load_latest_current_universe,
    load_lifecycle_rows,
    load_universe_membership,
)


def main() -> None:
    with engine.connect() as connection:
        ksei_inputs = (
            load_ksei_observations(
                connection
            )
        )

        universe_inputs = (
            load_latest_current_universe(
                connection
            )
        )

        ksei_availability = (
            load_dataset_availability(
                connection,
                dataset_code=(
                    KSEI_DATASET_CODE
                ),
            )
        )

        universe_availability = (
            load_dataset_availability(
                connection,
                dataset_code=(
                    IDX_UNIVERSE_DATASET_CODE
                ),
            )
        )

        memberships = (
            load_universe_membership(
                connection
            )
        )

        lifecycle = (
            load_lifecycle_rows(
                connection
            )
        )

        ksei_state = (
            load_audit_state(
                connection,
                dataset_code=(
                    KSEI_DATASET_CODE
                ),
            )
        )

        universe_state = (
            load_audit_state(
                connection,
                dataset_code=(
                    IDX_UNIVERSE_DATASET_CODE
                ),
            )
        )

    if not universe_inputs:
        raise RuntimeError(
            "Current universe input "
            "is missing."
        )

    latest_snapshot = max(
        row[
            "snapshot_date"
        ]
        for row in universe_inputs
    )

    latest_memberships = [
        row
        for row in memberships
        if row[
            "valid_from"
        ]
        == latest_snapshot
    ]

    latest_lifecycle = [
        row
        for row in lifecycle
        if row[
            "effective_from"
        ]
        == latest_snapshot
    ]

    ksei_coverage = (
        calculate_pit_coverage(
            ksei_availability
        )
    )

    universe_coverage = (
        calculate_pit_coverage(
            universe_availability
        )
    )

    invalid_ksei_safe = sum(
        bool(
            row[
                "point_in_time_safe"
            ]
        )
        and (
            row[
                "availability_status"
            ]
            != "KNOWN"
            or row[
                "available_at"
            ]
            is None
        )
        for row in ksei_availability
    )

    invalid_membership = sum(
        (
            not bool(
                row[
                    "point_in_time_safe"
                ]
            )
            or row[
                "available_at"
            ]
            is None
            or row[
                "membership_status"
            ]
            != "ACTIVE"
        )
        for row in latest_memberships
    )

    retroactive_membership = sum(
        row[
            "valid_from"
        ]
        < latest_snapshot
        for row in latest_memberships
    )

    invalid_lifecycle = sum(
        (
            row[
                "available_at"
            ]
            is None
            or row[
                "availability_status"
            ]
            != "KNOWN"
        )
        for row in latest_lifecycle
    )

    coverage_pass = (
        len(
            ksei_inputs
        )
        == len(
            ksei_availability
        )
        and len(
            universe_inputs
        )
        == len(
            latest_memberships
        )
        == len(
            latest_lifecycle
        )
    )

    quality_pass = (
        invalid_ksei_safe == 0
        and invalid_membership == 0
        and retroactive_membership == 0
        and invalid_lifecycle == 0
    )

    state_pass = (
        ksei_state is not None
        and universe_state is not None
        and int(
            ksei_state[
                "total_observations"
            ]
        )
        == ksei_coverage.total
        and int(
            universe_state[
                "total_observations"
            ]
        )
        == universe_coverage.total
    )

    print(
        "Point-in-Time Infrastructure Audit"
    )

    print(
        "----------------------------------"
    )

    print()

    print(
        "KSEI:"
    )

    print(
        f"Source observations : "
        f"{len(ksei_inputs)}"
    )

    print(
        f"Availability rows   : "
        f"{len(ksei_availability)}"
    )

    print(
        f"Known               : "
        f"{ksei_coverage.known}"
    )

    print(
        f"Unknown             : "
        f"{ksei_coverage.unknown}"
    )

    print(
        f"Estimated           : "
        f"{ksei_coverage.estimated}"
    )

    print(
        f"PIT safe            : "
        f"{ksei_coverage.safe}"
    )

    print()

    print(
        "Current IDX universe:"
    )

    print(
        f"Snapshot date       : "
        f"{latest_snapshot}"
    )

    print(
        f"Source members      : "
        f"{len(universe_inputs)}"
    )

    print(
        f"PIT memberships     : "
        f"{len(latest_memberships)}"
    )

    print(
        f"Lifecycle rows      : "
        f"{len(latest_lifecycle)}"
    )

    print(
        f"Invalid membership  : "
        f"{invalid_membership}"
    )

    print(
        f"Retroactive rows    : "
        f"{retroactive_membership}"
    )

    print(
        f"Invalid lifecycle   : "
        f"{invalid_lifecycle}"
    )

    print()

    print(
        "Quality:"
    )

    print(
        f"Invalid KSEI safe   : "
        f"{invalid_ksei_safe}"
    )

    print()

    print(
        "Result:"
    )

    print(
        "Coverage : "
        + (
            "PASS"
            if coverage_pass
            else "FAIL"
        )
    )

    print(
        "Quality  : "
        + (
            "PASS"
            if quality_pass
            else "FAIL"
        )
    )

    print(
        "State    : "
        + (
            "PASS"
            if state_pass
            else "FAIL"
        )
    )

    print()

    print(
        "Strict historical readiness:"
    )

    if (
        ksei_coverage.total > 0
        and ksei_coverage.safe
        == ksei_coverage.total
    ):
        print(
            "KSEI publication timing: "
            "READY"
        )
    else:
        print(
            "KSEI publication timing: "
            "NOT READY"
        )

    print(
        "Historical universe: "
        "NOT READY"
    )

    if not (
        coverage_pass
        and quality_pass
        and state_pass
    ):
        raise RuntimeError(
            "Point-in-time audit failed."
        )


if __name__ == "__main__":
    main()