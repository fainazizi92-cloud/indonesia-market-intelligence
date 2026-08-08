from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

LOAD_IDX_EQUITY_INSTRUMENTS = text(
    """
    SELECT
        id,
        symbol
    FROM instruments
    WHERE exchange = 'IDX'
      AND asset_type = 'EQUITY'
    """
)


UPSERT_OWNERSHIP = text(
    """
    INSERT INTO ownership_snapshots (
        instrument_id,
        as_of_date,
        free_float_pct,
        foreign_ownership_pct,
        hsc_flag,
        concentration_score,
        holder_details,
        source_id,
        ingested_at
    )
    VALUES (
        :instrument_id,
        :as_of_date,
        :free_float_pct,
        :foreign_ownership_pct,
        :hsc_flag,
        :concentration_score,
        CAST(
            :holder_details
            AS JSONB
        ),
        :source_id,
        NOW()
    )
    ON CONFLICT (
        instrument_id,
        as_of_date,
        source_id
    )
    DO UPDATE SET
        free_float_pct =
            EXCLUDED.free_float_pct,
        foreign_ownership_pct =
            EXCLUDED.foreign_ownership_pct,
        hsc_flag =
            EXCLUDED.hsc_flag,
        concentration_score =
            EXCLUDED.concentration_score,
        holder_details =
            EXCLUDED.holder_details,
        ingested_at =
            NOW()
    """
)


OWNERSHIP_COVERAGE = text(
    """
    SELECT
        COUNT(*) AS rows,
        COUNT(
            DISTINCT instrument_id
        ) AS instruments,
        COUNT(
            DISTINCT as_of_date
        ) AS snapshot_dates,
        MIN(as_of_date)
            AS first_date,
        MAX(as_of_date)
            AS last_date
    FROM ownership_snapshots
    WHERE source_id =
          :source_id
    """
)


def get_idx_equity_map(
    connection: Connection,
) -> dict[str, UUID]:
    rows = connection.execute(
        LOAD_IDX_EQUITY_INSTRUMENTS
    ).mappings()

    return {
        str(row["symbol"]).upper():
            row["id"]
        for row in rows
    }


def get_ownership_coverage(
    connection: Connection,
    *,
    source_id: UUID,
) -> dict[str, Any]:
    row = connection.execute(
        OWNERSHIP_COVERAGE,
        {
            "source_id":
                source_id
        },
    ).mappings().one()

    return dict(row)


def upsert_ownership_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
    batch_size: int = 1000,
) -> int:
    if not rows:
        return 0

    import json

    total = 0

    for start in range(
        0,
        len(rows),
        batch_size,
    ):
        batch = rows[
            start:
            start + batch_size
        ]

        serialized_batch = []

        for row in batch:
            serialized = dict(row)

            serialized[
                "holder_details"
            ] = json.dumps(
                row["holder_details"]
            )

            serialized_batch.append(
                serialized
            )

        connection.execute(
            UPSERT_OWNERSHIP,
            serialized_batch,
        )

        total += len(
            serialized_batch
        )

    return total