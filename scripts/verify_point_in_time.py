from imi.db import engine
from imi.features.point_in_time import (
    prepare_current_lifecycle_rows,
    prepare_current_universe_membership_rows,
)
from imi.repositories.point_in_time import (
    load_latest_current_universe,
    load_lifecycle_rows,
    load_universe_membership,
)


def main() -> None:
    with engine.connect() as connection:
        inputs = (
            load_latest_current_universe(
                connection
            )
        )

        stored_membership = (
            load_universe_membership(
                connection
            )
        )

        stored_lifecycle = (
            load_lifecycle_rows(
                connection
            )
        )

    if not inputs:
        raise RuntimeError(
            "Current universe input "
            "is empty."
        )

    expected_membership = (
        prepare_current_universe_membership_rows(
            inputs
        )
    )

    expected_lifecycle = (
        prepare_current_lifecycle_rows(
            inputs
        )
    )

    snapshot_date = max(
        row[
            "snapshot_date"
        ]
        for row in inputs
    )

    stored_membership = [
        row
        for row in stored_membership
        if row[
            "valid_from"
        ]
        == snapshot_date
    ]

    stored_lifecycle = [
        row
        for row in stored_lifecycle
        if row[
            "effective_from"
        ]
        == snapshot_date
    ]

    expected_membership_map = {
        row[
            "instrument_id"
        ]:
            row
        for row in expected_membership
    }

    stored_membership_map = {
        row[
            "instrument_id"
        ]:
            row
        for row in stored_membership
    }

    expected_lifecycle_map = {
        row[
            "instrument_id"
        ]:
            row
        for row in expected_lifecycle
    }

    stored_lifecycle_map = {
        row[
            "instrument_id"
        ]:
            row
        for row in stored_lifecycle
    }

    membership_mismatch = 0

    for instrument_id, expected in (
        expected_membership_map.items()
    ):
        actual = (
            stored_membership_map.get(
                instrument_id
            )
        )

        if actual is None:
            membership_mismatch += 1
            continue

        fields = (
            "universe_code",
            "valid_from",
            "valid_to",
            "membership_status",
            "source_code",
            "available_at",
            "availability_status",
            "point_in_time_safe",
            "evidence",
        )

        if any(
            expected[field]
            != actual[field]
            for field in fields
        ):
            membership_mismatch += 1

    lifecycle_mismatch = 0

    for instrument_id, expected in (
        expected_lifecycle_map.items()
    ):
        actual = (
            stored_lifecycle_map.get(
                instrument_id
            )
        )

        if actual is None:
            lifecycle_mismatch += 1
            continue

        fields = (
            "effective_from",
            "effective_to",
            "lifecycle_status",
            "listing_date",
            "delisting_date",
            "source_code",
            "source_reference",
            "available_at",
            "availability_status",
            "evidence",
        )

        if any(
            expected[field]
            != actual[field]
            for field in fields
        ):
            lifecycle_mismatch += 1

    passed = (
        len(
            expected_membership
        )
        == len(
            stored_membership
        )
        and len(
            expected_lifecycle
        )
        == len(
            stored_lifecycle
        )
        and membership_mismatch == 0
        and lifecycle_mismatch == 0
    )

    print(
        "Point-in-Time Verification"
    )

    print(
        "--------------------------"
    )

    print(
        f"Snapshot date          : "
        f"{snapshot_date}"
    )

    print(
        f"Expected memberships   : "
        f"{len(expected_membership)}"
    )

    print(
        f"Stored memberships     : "
        f"{len(stored_membership)}"
    )

    print(
        f"Membership mismatches  : "
        f"{membership_mismatch}"
    )

    print(
        f"Expected lifecycle     : "
        f"{len(expected_lifecycle)}"
    )

    print(
        f"Stored lifecycle       : "
        f"{len(stored_lifecycle)}"
    )

    print(
        f"Lifecycle mismatches   : "
        f"{lifecycle_mismatch}"
    )

    print(
        "Result                 : "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    if not passed:
        raise RuntimeError(
            "Point-in-time verification "
            "failed."
        )


if __name__ == "__main__":
    main()