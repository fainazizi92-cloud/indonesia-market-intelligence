import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

UPSERT_SOURCE = text(
    """
    INSERT INTO historical_source_catalog (
        source_key,
        source_id,

        dataset_family,
        source_kind,
        authority_class,

        base_url,
        probe_url,

        historical_access,
        access_mode,

        supports_download,
        supports_date_filter,

        point_in_time_potential,

        automation_status,

        priority,

        probe_config,
        evidence,

        updated_at
    )
    VALUES (
        :source_key,
        :source_id,

        :dataset_family,
        :source_kind,
        :authority_class,

        :base_url,
        :probe_url,

        :historical_access,
        :access_mode,

        :supports_download,
        :supports_date_filter,

        :point_in_time_potential,

        :automation_status,

        :priority,

        CAST(
            :probe_config
            AS JSONB
        ),

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        source_key
    )
    DO UPDATE SET
        source_id =
            EXCLUDED.source_id,

        dataset_family =
            EXCLUDED.dataset_family,

        source_kind =
            EXCLUDED.source_kind,

        authority_class =
            EXCLUDED.authority_class,

        base_url =
            EXCLUDED.base_url,

        probe_url =
            EXCLUDED.probe_url,

        historical_access =
            EXCLUDED.historical_access,

        access_mode =
            EXCLUDED.access_mode,

        supports_download =
            EXCLUDED.supports_download,

        supports_date_filter =
            EXCLUDED.supports_date_filter,

        point_in_time_potential =
            EXCLUDED.point_in_time_potential,

        automation_status =
            EXCLUDED.automation_status,

        priority =
            EXCLUDED.priority,

        probe_config =
            EXCLUDED.probe_config,

        evidence =
            EXCLUDED.evidence,

        updated_at =
            NOW()
    """
)


INSERT_PROBE_RUN = text(
    """
    INSERT INTO historical_source_probe_runs (
        source_key,

        success,

        http_status,

        final_url,

        content_type,
        content_length,

        marker_hits,
        marker_total,

        elapsed_ms,

        error_type,
        error_message,

        marker_details,
        evidence
    )
    VALUES (
        :source_key,

        :success,

        :http_status,

        :final_url,

        :content_type,
        :content_length,

        :marker_hits,
        :marker_total,

        :elapsed_ms,

        :error_type,
        :error_message,

        CAST(
            :marker_details
            AS JSONB
        ),

        CAST(
            :evidence
            AS JSONB
        )
    )
    """
)


LOAD_CATALOG = text(
    """
    SELECT
        source_key,
        source_id,

        dataset_family,
        source_kind,
        authority_class,

        base_url,
        probe_url,

        historical_access,
        access_mode,

        supports_download,
        supports_date_filter,

        point_in_time_potential,

        automation_status,

        priority,

        probe_config,
        evidence,

        updated_at

    FROM historical_source_catalog

    ORDER BY
        priority,
        dataset_family,
        source_key
    """
)


LOAD_LATEST_PROBES = text(
    """
    SELECT DISTINCT ON (
        source_key
    )
        source_key,

        id,
        checked_at,

        success,

        http_status,

        final_url,

        content_type,
        content_length,

        marker_hits,
        marker_total,

        elapsed_ms,

        error_type,
        error_message,

        marker_details,
        evidence

    FROM historical_source_probe_runs

    ORDER BY
        source_key,
        checked_at DESC,
        id DESC
    """
)


PROBE_COUNTS = text(
    """
    SELECT
        COUNT(*)
            AS total_runs,

        COUNT(
            DISTINCT source_key
        ) AS distinct_sources,

        COUNT(*) FILTER (
            WHERE success
        ) AS successful_runs,

        MAX(checked_at)
            AS latest_checked_at

    FROM historical_source_probe_runs
    """
)


def upsert_source_catalog(
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
            "probe_config"
        ] = json.dumps(
            row[
                "probe_config"
            ],
            sort_keys=True,
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
        UPSERT_SOURCE,
        serialized,
    )

    return len(
        serialized
    )


def insert_probe_runs(
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
            "marker_details"
        ] = json.dumps(
            row[
                "marker_details"
            ],
            sort_keys=True,
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
        INSERT_PROBE_RUN,
        serialized,
    )

    return len(
        serialized
    )


def load_source_catalog(
    connection: Connection,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row
        in connection.execute(
            LOAD_CATALOG
        ).mappings().all()
    ]


def load_latest_probes(
    connection: Connection,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row
        in connection.execute(
            LOAD_LATEST_PROBES
        ).mappings().all()
    ]


def get_probe_counts(
    connection: Connection,
) -> dict[str, Any]:
    return dict(
        connection.execute(
            PROBE_COUNTS
        ).mappings().one()
    )