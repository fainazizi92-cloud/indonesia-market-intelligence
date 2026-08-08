from imi.db import engine
from imi.features.point_in_time import (
    build_observation_key,
    calculate_pit_coverage,
    prepare_current_lifecycle_rows,
    prepare_current_universe_membership_rows,
    prepare_known_availability_row,
    prepare_unknown_availability_row,
)
from imi.repositories.point_in_time import (
    IDX_UNIVERSE_DATASET_CODE,
    KSEI_DATASET_CODE,
    load_dataset_availability,
    load_ksei_observations,
    load_latest_current_universe,
    upsert_audit_state,
    upsert_availability_rows,
    upsert_lifecycle_rows,
    upsert_universe_membership_rows,
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

    if not ksei_inputs:
        raise RuntimeError(
            "No KSEI ownership snapshots "
            "were found."
        )

    if not universe_inputs:
        raise RuntimeError(
            "No IDX current-universe "
            "snapshot was found."
        )

    snapshot_dates = {
        row[
            "snapshot_date"
        ]
        for row in universe_inputs
    }

    if len(snapshot_dates) != 1:
        raise RuntimeError(
            "Expected exactly one latest "
            "IDX universe snapshot date."
        )

    universe_snapshot_date = next(
        iter(
            snapshot_dates
        )
    )

    ksei_rows = []

    for item in ksei_inputs:
        archive_name = (
            item[
                "archive_name"
            ]
        )

        observation_date = (
            item[
                "observation_date"
            ]
        )

        observation_key = (
            build_observation_key(
                "KSEI_OFFICIAL",
                (
                    archive_name
                    or observation_date
                ),
            )
        )

        ksei_rows.append(
            prepare_unknown_availability_row(
                dataset_code=(
                    KSEI_DATASET_CODE
                ),
                observation_key=(
                    observation_key
                ),
                observation_date=(
                    observation_date
                ),
                source_code=(
                    "KSEI_OFFICIAL"
                ),
                source_reference=(
                    archive_name
                ),
                evidence={
                    "snapshot_rows":
                        int(
                            item[
                                "snapshot_rows"
                            ]
                        ),

                    "archive_count":
                        int(
                            item[
                                "archive_count"
                            ]
                        ),

                    "first_local_ingest":
                        (
                            None
                            if item[
                                "first_ingested_at"
                            ]
                            is None
                            else item[
                                "first_ingested_at"
                            ].isoformat()
                        ),

                    "last_local_ingest":
                        (
                            None
                            if item[
                                "last_ingested_at"
                            ]
                            is None
                            else item[
                                "last_ingested_at"
                            ].isoformat()
                        ),

                    "note":
                        (
                            "Local ingestion time "
                            "is not treated as "
                            "historical KSEI "
                            "publication time."
                        ),
                },
            )
        )

    universe_available_at = max(
        row[
            "ingested_at"
        ]
        for row in universe_inputs
        if row[
            "ingested_at"
        ]
        is not None
    )

    universe_availability = [
        prepare_known_availability_row(
            dataset_code=(
                IDX_UNIVERSE_DATASET_CODE
            ),
            observation_key=(
                build_observation_key(
                    "IDX_ALL_CURRENT",
                    universe_snapshot_date,
                )
            ),
            observation_date=(
                universe_snapshot_date
            ),
            available_at=(
                universe_available_at
            ),
            source_code=(
                "IDX_OFFICIAL"
            ),
            source_reference=(
                "IDX company profiles"
            ),
            evidence={
                "members":
                    len(
                        universe_inputs
                    ),

                "note":
                    (
                        "Known from local "
                        "system observation "
                        "time. This does not "
                        "create historical "
                        "membership before "
                        "the snapshot."
                    ),
            },
        )
    ]

    membership_rows = (
        prepare_current_universe_membership_rows(
            universe_inputs
        )
    )

    lifecycle_rows = (
        prepare_current_lifecycle_rows(
            universe_inputs
        )
    )

    with engine.begin() as connection:
        ksei_prepared = (
            upsert_availability_rows(
                connection,
                rows=ksei_rows,
            )
        )

        universe_prepared = (
            upsert_availability_rows(
                connection,
                rows=(
                    universe_availability
                ),
            )
        )

        membership_prepared = (
            upsert_universe_membership_rows(
                connection,
                rows=(
                    membership_rows
                ),
            )
        )

        lifecycle_prepared = (
            upsert_lifecycle_rows(
                connection,
                rows=(
                    lifecycle_rows
                ),
            )
        )

        stored_ksei = (
            load_dataset_availability(
                connection,
                dataset_code=(
                    KSEI_DATASET_CODE
                ),
            )
        )

        stored_universe = (
            load_dataset_availability(
                connection,
                dataset_code=(
                    IDX_UNIVERSE_DATASET_CODE
                ),
            )
        )

        ksei_coverage = (
            calculate_pit_coverage(
                stored_ksei
            )
        )

        universe_coverage = (
            calculate_pit_coverage(
                stored_universe
            )
        )

        ksei_dates = [
            row[
                "observation_date"
            ]
            for row in stored_ksei
        ]

        universe_dates = [
            row[
                "observation_date"
            ]
            for row in stored_universe
        ]

        upsert_audit_state(
            connection,
            dataset_code=(
                KSEI_DATASET_CODE
            ),
            total_observations=(
                ksei_coverage.total
            ),
            known_availability=(
                ksei_coverage.known
            ),
            unknown_availability=(
                ksei_coverage.unknown
            ),
            estimated_availability=(
                ksei_coverage.estimated
            ),
            pit_safe_observations=(
                ksei_coverage.safe
            ),
            first_observation_date=(
                min(ksei_dates)
                if ksei_dates
                else None
            ),
            last_observation_date=(
                max(ksei_dates)
                if ksei_dates
                else None
            ),
            evidence={
                "scope":
                    "point_in_time_v1",

                "strict_ready":
                    (
                        ksei_coverage.total > 0
                        and
                        ksei_coverage.safe
                        == ksei_coverage.total
                    ),

                "warning":
                    (
                        "Unknown KSEI "
                        "publication timing "
                        "remains a blocker."
                    ),
            },
        )

        upsert_audit_state(
            connection,
            dataset_code=(
                IDX_UNIVERSE_DATASET_CODE
            ),
            total_observations=(
                universe_coverage.total
            ),
            known_availability=(
                universe_coverage.known
            ),
            unknown_availability=(
                universe_coverage.unknown
            ),
            estimated_availability=(
                universe_coverage.estimated
            ),
            pit_safe_observations=(
                universe_coverage.safe
            ),
            first_observation_date=(
                min(universe_dates)
                if universe_dates
                else None
            ),
            last_observation_date=(
                max(universe_dates)
                if universe_dates
                else None
            ),
            evidence={
                "scope":
                    "point_in_time_v1",

                "strict_ready":
                    False,

                "warning":
                    (
                        "Current snapshot is "
                        "safe prospectively "
                        "but historical universe "
                        "has not been "
                        "reconstructed."
                    ),
            },
        )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Point-in-Time Infrastructure V1"
    )

    print(
        "-------------------------------"
    )

    print(
        f"KSEI observations       : "
        f"{len(ksei_inputs)}"
    )

    print(
        f"KSEI rows prepared      : "
        f"{ksei_prepared}"
    )

    print(
        f"KSEI known availability : "
        f"{ksei_coverage.known}"
    )

    print(
        f"KSEI unknown            : "
        f"{ksei_coverage.unknown}"
    )

    print(
        f"KSEI PIT safe           : "
        f"{ksei_coverage.safe}"
    )

    print()

    print(
        f"Universe snapshot       : "
        f"{universe_snapshot_date}"
    )

    print(
        f"Universe instruments    : "
        f"{len(universe_inputs)}"
    )

    print(
        f"Universe availability   : "
        f"{universe_prepared}"
    )

    print(
        f"Membership rows         : "
        f"{membership_prepared}"
    )

    print(
        f"Lifecycle rows          : "
        f"{lifecycle_prepared}"
    )

    print()

    print(
        "STRICT HISTORICAL READINESS:"
    )

    print(
        "READY : NO"
    )

    print(
        "- KSEI publication timestamps "
        "are not yet established."
    )

    print(
        "- Historical IDX universe "
        "membership is not yet "
        "reconstructed."
    )

    print(
        "- Current snapshot is only "
        "safe prospectively."
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "No KSEI availability date "
        "has been fabricated."
    )

    print(
        "Current-universe membership "
        "is never backdated to the "
        "instrument listing date."
    )


if __name__ == "__main__":
    main()