import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

INSERT_CONTRACT = text(
    """
    INSERT INTO historical_source_contract_snapshots (
        source_key,

        requested_url,
        final_url,

        http_status,
        content_type,

        body_sha256,
        body_length,

        anchor_count,
        script_count,
        form_count,

        candidate_url_count,

        candidate_urls,
        endpoint_hints,

        parser_ready,
        parser_status,

        error_type,
        error_message,

        evidence
    )
    VALUES (
        :source_key,

        :requested_url,
        :final_url,

        :http_status,
        :content_type,

        :body_sha256,
        :body_length,

        :anchor_count,
        :script_count,
        :form_count,

        :candidate_url_count,

        CAST(
            :candidate_urls
            AS JSONB
        ),

        CAST(
            :endpoint_hints
            AS JSONB
        ),

        :parser_ready,
        :parser_status,

        :error_type,
        :error_message,

        CAST(
            :evidence
            AS JSONB
        )
    )
    """
)


LOAD_LATEST = text(
    """
    SELECT DISTINCT ON (
        source_key
    )
        id,

        source_key,
        inspected_at,

        requested_url,
        final_url,

        http_status,
        content_type,

        body_sha256,
        body_length,

        anchor_count,
        script_count,
        form_count,

        candidate_url_count,

        candidate_urls,
        endpoint_hints,

        parser_ready,
        parser_status,

        error_type,
        error_message,

        evidence

    FROM historical_source_contract_snapshots

    ORDER BY
        source_key,
        inspected_at DESC,
        id DESC
    """
)


LOAD_COUNTS = text(
    """
    SELECT
        COUNT(*)
            AS total_snapshots,

        COUNT(
            DISTINCT source_key
        ) AS distinct_sources,

        COUNT(*) FILTER (
            WHERE http_status
                  BETWEEN 200 AND 299
        ) AS successful_snapshots,

        COUNT(*) FILTER (
            WHERE candidate_url_count > 0
        ) AS candidate_snapshots,

        MAX(inspected_at)
            AS latest_inspected_at

    FROM historical_source_contract_snapshots
    """
)


def insert_contract_snapshots(
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
            "candidate_urls"
        ] = json.dumps(
            row[
                "candidate_urls"
            ],
            sort_keys=True,
        )

        item[
            "endpoint_hints"
        ] = json.dumps(
            row[
                "endpoint_hints"
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
        INSERT_CONTRACT,
        serialized,
    )

    return len(
        serialized
    )


def load_latest_contract_snapshots(
    connection: Connection,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row
        in connection.execute(
            LOAD_LATEST
        ).mappings().all()
    ]


def get_contract_counts(
    connection: Connection,
) -> dict[str, Any]:
    return dict(
        connection.execute(
            LOAD_COUNTS
        ).mappings().one()
    )