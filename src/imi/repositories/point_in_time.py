import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

KSEI_DATASET_CODE = (
    "KSEI_OWNERSHIP_SNAPSHOT"
)

IDX_UNIVERSE_DATASET_CODE = (
    "IDX_CURRENT_UNIVERSE_SNAPSHOT"
)


KSEI_OBSERVATIONS = text(
    """
    SELECT
        os.as_of_date
            AS observation_date,

        COUNT(*)
            AS snapshot_rows,

        MIN(os.ingested_at)
            AS first_ingested_at,

        MAX(os.ingested_at)
            AS last_ingested_at,

        MIN(
            os.holder_details
            ->> 'archive_name'
        ) AS archive_name,

        COUNT(
            DISTINCT (
                os.holder_details
                ->> 'archive_name'
            )
        ) AS archive_count

    FROM ownership_snapshots os

    JOIN data_sources ds
      ON ds.id =
         os.source_id

    WHERE ds.code =
          'KSEI_OFFICIAL'

    GROUP BY
        os.as_of_date

    ORDER BY
        os.as_of_date
    """
)


LATEST_CURRENT_UNIVERSE = text(
    """
    WITH latest_snapshot AS (
        SELECT
            MAX(ius.snapshot_date)
                AS snapshot_date

        FROM instrument_universe_snapshots ius

        JOIN data_sources ds
          ON ds.id =
             ius.source_id

        WHERE ius.universe_code =
              'IDX_ALL_CURRENT'

          AND ius.is_member = TRUE

          AND ds.code =
              'IDX_OFFICIAL'
    )

    SELECT
        ius.instrument_id,

        i.symbol,
        i.listed_date,
        i.delisted_date,

        ius.snapshot_date,
        ius.ingested_at,

        ius.metadata

    FROM instrument_universe_snapshots ius

    JOIN latest_snapshot ls
      ON ls.snapshot_date =
         ius.snapshot_date

    JOIN data_sources ds
      ON ds.id =
         ius.source_id

    JOIN instruments i
      ON i.id =
         ius.instrument_id

    WHERE ius.universe_code =
          'IDX_ALL_CURRENT'

      AND ius.is_member = TRUE

      AND ds.code =
          'IDX_OFFICIAL'

      AND i.exchange =
          'IDX'

      AND i.asset_type =
          'EQUITY'

    ORDER BY
        i.symbol
    """
)


UPSERT_AVAILABILITY = text(
    """
    INSERT INTO data_publication_availability (
        dataset_code,
        observation_key,
        observation_date,

        published_at,
        available_at,

        availability_status,

        source_code,
        source_reference,

        point_in_time_safe,

        evidence,

        ingested_at
    )
    VALUES (
        :dataset_code,
        :observation_key,
        :observation_date,

        :published_at,
        :available_at,

        :availability_status,

        :source_code,
        :source_reference,

        :point_in_time_safe,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        dataset_code,
        observation_key,
        observation_date,
        source_code
    )
    DO UPDATE SET
        published_at =
            EXCLUDED.published_at,

        available_at =
            EXCLUDED.available_at,

        availability_status =
            EXCLUDED.availability_status,

        source_reference =
            EXCLUDED.source_reference,

        point_in_time_safe =
            EXCLUDED.point_in_time_safe,

        evidence =
            EXCLUDED.evidence,

        ingested_at =
            NOW()

    WHERE
        CASE
            WHEN EXCLUDED.availability_status =
                 'KNOWN'
                THEN 3

            WHEN EXCLUDED.availability_status =
                 'ESTIMATED'
                THEN 2

            ELSE 1
        END
        >
        CASE
            WHEN data_publication_availability
                 .availability_status =
                 'KNOWN'
                THEN 3

            WHEN data_publication_availability
                 .availability_status =
                 'ESTIMATED'
                THEN 2

            ELSE 1
        END
    """
)


UPSERT_UNIVERSE_MEMBERSHIP = text(
    """
    INSERT INTO historical_universe_membership (
        instrument_id,
        universe_code,

        valid_from,
        valid_to,

        membership_status,

        source_code,

        available_at,
        availability_status,

        point_in_time_safe,

        evidence,

        calculated_at
    )
    VALUES (
        :instrument_id,
        :universe_code,

        :valid_from,
        :valid_to,

        :membership_status,

        :source_code,

        :available_at,
        :availability_status,

        :point_in_time_safe,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        instrument_id,
        universe_code,
        valid_from,
        source_code
    )
    DO UPDATE SET
        valid_to =
            EXCLUDED.valid_to,

        membership_status =
            EXCLUDED.membership_status,

        available_at =
            EXCLUDED.available_at,

        availability_status =
            EXCLUDED.availability_status,

        point_in_time_safe =
            EXCLUDED.point_in_time_safe,

        evidence =
            EXCLUDED.evidence,

        calculated_at =
            NOW()
    """
)


UPSERT_LIFECYCLE = text(
    """
    INSERT INTO instrument_lifecycle_history (
        instrument_id,

        effective_from,
        effective_to,

        lifecycle_status,

        listing_date,
        delisting_date,

        source_code,
        source_reference,

        available_at,
        availability_status,

        quality,

        evidence,

        ingested_at
    )
    VALUES (
        :instrument_id,

        :effective_from,
        :effective_to,

        :lifecycle_status,

        :listing_date,
        :delisting_date,

        :source_code,
        :source_reference,

        :available_at,
        :availability_status,

        CAST(
            :quality
            AS quality_status
        ),

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        instrument_id,
        effective_from,
        source_code
    )
    DO UPDATE SET
        effective_to =
            EXCLUDED.effective_to,

        lifecycle_status =
            EXCLUDED.lifecycle_status,

        listing_date =
            EXCLUDED.listing_date,

        delisting_date =
            EXCLUDED.delisting_date,

        source_reference =
            EXCLUDED.source_reference,

        available_at =
            EXCLUDED.available_at,

        availability_status =
            EXCLUDED.availability_status,

        quality =
            EXCLUDED.quality,

        evidence =
            EXCLUDED.evidence,

        ingested_at =
            NOW()
    """
)


LOAD_DATASET_AVAILABILITY = text(
    """
    SELECT
        dataset_code,
        observation_key,
        observation_date,

        published_at,
        available_at,

        availability_status,

        source_code,
        source_reference,

        point_in_time_safe,

        evidence

    FROM data_publication_availability

    WHERE dataset_code =
          :dataset_code

    ORDER BY
        observation_date,
        observation_key
    """
)


LOAD_UNIVERSE_MEMBERSHIP = text(
    """
    SELECT
        instrument_id,
        universe_code,

        valid_from,
        valid_to,

        membership_status,

        source_code,

        available_at,
        availability_status,

        point_in_time_safe,

        evidence

    FROM historical_universe_membership

    WHERE universe_code =
          'IDX_ALL_CURRENT'

    ORDER BY
        valid_from,
        instrument_id
    """
)


LOAD_LIFECYCLE = text(
    """
    SELECT
        instrument_id,

        effective_from,
        effective_to,

        lifecycle_status,

        listing_date,
        delisting_date,

        source_code,
        source_reference,

        available_at,
        availability_status,

        quality,

        evidence

    FROM instrument_lifecycle_history

    WHERE source_code =
          'IDX_OFFICIAL'

    ORDER BY
        effective_from,
        instrument_id
    """
)


UPSERT_AUDIT_STATE = text(
    """
    INSERT INTO point_in_time_audit_state (
        dataset_code,

        total_observations,

        known_availability,
        unknown_availability,
        estimated_availability,

        pit_safe_observations,

        first_observation_date,
        last_observation_date,

        calculated_at,

        evidence
    )
    VALUES (
        :dataset_code,

        :total_observations,

        :known_availability,
        :unknown_availability,
        :estimated_availability,

        :pit_safe_observations,

        :first_observation_date,
        :last_observation_date,

        NOW(),

        CAST(
            :evidence
            AS JSONB
        )
    )

    ON CONFLICT (
        dataset_code
    )
    DO UPDATE SET
        total_observations =
            EXCLUDED.total_observations,

        known_availability =
            EXCLUDED.known_availability,

        unknown_availability =
            EXCLUDED.unknown_availability,

        estimated_availability =
            EXCLUDED.estimated_availability,

        pit_safe_observations =
            EXCLUDED.pit_safe_observations,

        first_observation_date =
            EXCLUDED.first_observation_date,

        last_observation_date =
            EXCLUDED.last_observation_date,

        calculated_at =
            NOW(),

        evidence =
            EXCLUDED.evidence
    """
)


LOAD_AUDIT_STATE = text(
    """
    SELECT
        dataset_code,

        total_observations,

        known_availability,
        unknown_availability,
        estimated_availability,

        pit_safe_observations,

        first_observation_date,
        last_observation_date,

        evidence

    FROM point_in_time_audit_state

    WHERE dataset_code =
          :dataset_code
    """
)


def load_ksei_observations(
    connection: Connection,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        KSEI_OBSERVATIONS
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_latest_current_universe(
    connection: Connection,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LATEST_CURRENT_UNIVERSE
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def upsert_availability_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0

    serialized = []

    for row in rows:
        item = dict(
            row
        )

        item[
            "evidence"
        ] = json.dumps(
            row[
                "evidence"
            ],
            sort_keys=True,
        )

        serialized.append(
            item
        )

    connection.execute(
        UPSERT_AVAILABILITY,
        serialized,
    )

    return len(
        serialized
    )


def upsert_universe_membership_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0

    serialized = []

    for row in rows:
        item = dict(
            row
        )

        item[
            "evidence"
        ] = json.dumps(
            row[
                "evidence"
            ],
            sort_keys=True,
        )

        serialized.append(
            item
        )

    connection.execute(
        UPSERT_UNIVERSE_MEMBERSHIP,
        serialized,
    )

    return len(
        serialized
    )


def upsert_lifecycle_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
) -> int:
    if not rows:
        return 0

    serialized = []

    for row in rows:
        item = dict(
            row
        )

        item[
            "evidence"
        ] = json.dumps(
            row[
                "evidence"
            ],
            sort_keys=True,
        )

        serialized.append(
            item
        )

    connection.execute(
        UPSERT_LIFECYCLE,
        serialized,
    )

    return len(
        serialized
    )


def load_dataset_availability(
    connection: Connection,
    *,
    dataset_code: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_DATASET_AVAILABILITY,
        {
            "dataset_code":
                dataset_code,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_universe_membership(
    connection: Connection,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_UNIVERSE_MEMBERSHIP
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_lifecycle_rows(
    connection: Connection,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_LIFECYCLE
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def upsert_audit_state(
    connection: Connection,
    *,
    dataset_code: str,
    total_observations: int,
    known_availability: int,
    unknown_availability: int,
    estimated_availability: int,
    pit_safe_observations: int,
    first_observation_date,
    last_observation_date,
    evidence: dict[str, Any],
) -> None:
    connection.execute(
        UPSERT_AUDIT_STATE,
        {
            "dataset_code":
                dataset_code,

            "total_observations":
                total_observations,

            "known_availability":
                known_availability,

            "unknown_availability":
                unknown_availability,

            "estimated_availability":
                estimated_availability,

            "pit_safe_observations":
                pit_safe_observations,

            "first_observation_date":
                first_observation_date,

            "last_observation_date":
                last_observation_date,

            "evidence":
                json.dumps(
                    evidence,
                    sort_keys=True,
                ),
        },
    )


def load_audit_state(
    connection: Connection,
    *,
    dataset_code: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        LOAD_AUDIT_STATE,
        {
            "dataset_code":
                dataset_code,
        },
    ).mappings().first()

    if row is None:
        return None

    return dict(
        row
    )