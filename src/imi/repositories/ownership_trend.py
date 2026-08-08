from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

PAIR_CTE = """
WITH base AS (
    SELECT
        o.instrument_id,
        i.symbol,
        i.sector_code,
        o.as_of_date,

        CAST(
            o.foreign_ownership_pct
            AS DOUBLE PRECISION
        ) AS foreign_ownership_pct,

        (
            jsonb_extract_path_text(
                o.holder_details,
                'foreign',
                'total'
            )
        )::numeric
            AS foreign_shares,

        (
            jsonb_extract_path_text(
                o.holder_details,
                'security_number'
            )
        )::numeric
            AS security_number

    FROM ownership_snapshots o

    JOIN instruments i
      ON i.id =
         o.instrument_id

    WHERE o.source_id =
          :source_id
),

ordered AS (
    SELECT
        instrument_id,
        symbol,
        sector_code,
        as_of_date,
        foreign_ownership_pct,
        foreign_shares,
        security_number,

        LAG(
            as_of_date
        ) OVER (
            PARTITION BY instrument_id
            ORDER BY as_of_date
        ) AS previous_as_of_date,

        LAG(
            foreign_ownership_pct
        ) OVER (
            PARTITION BY instrument_id
            ORDER BY as_of_date
        ) AS previous_foreign_ownership_pct,

        LAG(
            foreign_shares
        ) OVER (
            PARTITION BY instrument_id
            ORDER BY as_of_date
        ) AS previous_foreign_shares,

        LAG(
            security_number
        ) OVER (
            PARTITION BY instrument_id
            ORDER BY as_of_date
        ) AS previous_security_number

    FROM base
)
"""


LOAD_ALL_PAIRS = text(
    PAIR_CTE
    + """
    SELECT
        instrument_id,
        symbol,
        sector_code,
        as_of_date,
        previous_as_of_date,

        foreign_ownership_pct,
        previous_foreign_ownership_pct,

        foreign_shares,
        previous_foreign_shares,

        security_number,
        previous_security_number

    FROM ordered

    WHERE previous_as_of_date
          IS NOT NULL

    ORDER BY
        instrument_id,
        as_of_date
    """
)


LOAD_INCREMENTAL_PAIRS = text(
    PAIR_CTE
    + """
    SELECT
        instrument_id,
        symbol,
        sector_code,
        as_of_date,
        previous_as_of_date,

        foreign_ownership_pct,
        previous_foreign_ownership_pct,

        foreign_shares,
        previous_foreign_shares,

        security_number,
        previous_security_number

    FROM ordered

    WHERE previous_as_of_date
          IS NOT NULL
      AND as_of_date >
          :after_date

    ORDER BY
        instrument_id,
        as_of_date
    """
)


EXPECTED_COVERAGE = text(
    PAIR_CTE
    + """
    SELECT
        COUNT(*) AS expected_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS expected_instruments,

        COUNT(
            DISTINCT as_of_date
        ) AS expected_snapshot_dates,

        MIN(as_of_date)
            AS expected_first,

        MAX(as_of_date)
            AS expected_last

    FROM ordered

    WHERE previous_as_of_date
          IS NOT NULL
    """
)


EXPECTED_COVERAGE_AFTER = text(
    PAIR_CTE
    + """
    SELECT
        COUNT(*) AS expected_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS expected_instruments,

        COUNT(
            DISTINCT as_of_date
        ) AS expected_snapshot_dates,

        MIN(as_of_date)
            AS expected_first,

        MAX(as_of_date)
            AS expected_last

    FROM ordered

    WHERE previous_as_of_date
          IS NOT NULL
      AND as_of_date >
          :after_date
    """
)


LATEST_INPUT_STATE = text(
    PAIR_CTE
    + """
    ,
    latest AS (
        SELECT MAX(as_of_date)
            AS as_of_date
        FROM base
    )

    SELECT
        latest.as_of_date
            AS latest_input_date,

        COUNT(*) FILTER (
            WHERE ordered.as_of_date =
                  latest.as_of_date
        ) AS latest_ownership_count,

        COUNT(*) FILTER (
            WHERE ordered.as_of_date =
                  latest.as_of_date
              AND ordered.previous_as_of_date
                  IS NOT NULL
        ) AS latest_trend_eligible_count

    FROM latest

    LEFT JOIN ordered
      ON ordered.as_of_date =
         latest.as_of_date

    GROUP BY latest.as_of_date
    """
)


EXPECTED_COUNT_FOR_DATE = text(
    PAIR_CTE
    + """
    SELECT COUNT(*)

    FROM ordered

    WHERE as_of_date =
          :as_of_date
      AND previous_as_of_date
          IS NOT NULL
    """
)


STORED_LATEST_STATE = text(
    """
    WITH latest AS (
        SELECT MAX(as_of_date)
            AS as_of_date

        FROM ownership_trends

        WHERE source_id =
              :source_id
          AND model_version =
              :model_version
    )

    SELECT
        latest.as_of_date
            AS latest_date,

        COALESCE(
            (
                SELECT COUNT(*)

                FROM ownership_trends t

                WHERE t.source_id =
                      :source_id
                  AND t.model_version =
                      :model_version
                  AND t.as_of_date =
                      latest.as_of_date
            ),
            0
        ) AS latest_count

    FROM latest
    """
)


UPSERT_TREND = text(
    """
    INSERT INTO ownership_trends (
        instrument_id,
        as_of_date,
        previous_as_of_date,

        foreign_ownership_pct,
        previous_foreign_ownership_pct,
        delta_foreign_ownership_pp,

        foreign_shares,
        previous_foreign_shares,
        delta_foreign_shares,

        security_number,
        previous_security_number,
        delta_security_number_pct,

        normalized_foreign_share_change_pct,

        days_between_snapshots,

        trend_label,
        signal_strength,

        corporate_action_risk,
        snapshot_gap_flag,

        source_id,
        model_version,
        calculated_at
    )
    VALUES (
        :instrument_id,
        :as_of_date,
        :previous_as_of_date,

        :foreign_ownership_pct,
        :previous_foreign_ownership_pct,
        :delta_foreign_ownership_pp,

        :foreign_shares,
        :previous_foreign_shares,
        :delta_foreign_shares,

        :security_number,
        :previous_security_number,
        :delta_security_number_pct,

        :normalized_foreign_share_change_pct,

        :days_between_snapshots,

        :trend_label,
        :signal_strength,

        :corporate_action_risk,
        :snapshot_gap_flag,

        :source_id,
        :model_version,
        NOW()
    )

    ON CONFLICT (
        instrument_id,
        as_of_date,
        source_id,
        model_version
    )
    DO UPDATE SET
        previous_as_of_date =
            EXCLUDED.previous_as_of_date,

        foreign_ownership_pct =
            EXCLUDED.foreign_ownership_pct,

        previous_foreign_ownership_pct =
            EXCLUDED.previous_foreign_ownership_pct,

        delta_foreign_ownership_pp =
            EXCLUDED.delta_foreign_ownership_pp,

        foreign_shares =
            EXCLUDED.foreign_shares,

        previous_foreign_shares =
            EXCLUDED.previous_foreign_shares,

        delta_foreign_shares =
            EXCLUDED.delta_foreign_shares,

        security_number =
            EXCLUDED.security_number,

        previous_security_number =
            EXCLUDED.previous_security_number,

        delta_security_number_pct =
            EXCLUDED.delta_security_number_pct,

        normalized_foreign_share_change_pct =
            EXCLUDED.normalized_foreign_share_change_pct,

        days_between_snapshots =
            EXCLUDED.days_between_snapshots,

        trend_label =
            EXCLUDED.trend_label,

        signal_strength =
            EXCLUDED.signal_strength,

        corporate_action_risk =
            EXCLUDED.corporate_action_risk,

        snapshot_gap_flag =
            EXCLUDED.snapshot_gap_flag,

        calculated_at =
            NOW()
    """
)


RECENT_TREND_DATES = text(
    """
    SELECT DISTINCT
        as_of_date

    FROM ownership_trends

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version

    ORDER BY as_of_date DESC

    LIMIT :limit
    """
)


LOAD_STORED_AFTER = text(
    """
    SELECT
        instrument_id,
        as_of_date,
        previous_as_of_date,

        foreign_ownership_pct,
        previous_foreign_ownership_pct,
        delta_foreign_ownership_pp,

        foreign_shares,
        previous_foreign_shares,
        delta_foreign_shares,

        security_number,
        previous_security_number,
        delta_security_number_pct,

        normalized_foreign_share_change_pct,

        days_between_snapshots,

        trend_label,
        signal_strength,

        corporate_action_risk,
        snapshot_gap_flag,

        source_id,
        model_version

    FROM ownership_trends

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version
      AND as_of_date >
          :after_date

    ORDER BY
        instrument_id,
        as_of_date
    """
)


def get_latest_input_state(
    connection: Connection,
    *,
    source_id: UUID,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_INPUT_STATE,
        {
            "source_id":
                source_id,
        },
    ).mappings().one()

    result = dict(
        row
    )

    if (
        result["latest_input_date"]
        is None
    ):
        raise RuntimeError(
            "No KSEI ownership "
            "snapshots are available."
        )

    return result


def get_stored_latest_state(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_LATEST_STATE,
        {
            "source_id":
                source_id,
            "model_version":
                model_version,
        },
    ).mappings().one()

    return dict(
        row
    )


def get_expected_count_for_date(
    connection: Connection,
    *,
    source_id: UUID,
    as_of_date: date,
) -> int:
    return int(
        connection.execute(
            EXPECTED_COUNT_FOR_DATE,
            {
                "source_id":
                    source_id,
                "as_of_date":
                    as_of_date,
            },
        ).scalar_one()
    )


def get_expected_coverage(
    connection: Connection,
    *,
    source_id: UUID,
    after_date: date | None = None,
) -> dict[str, Any]:
    if after_date is None:
        row = connection.execute(
            EXPECTED_COVERAGE,
            {
                "source_id":
                    source_id,
            },
        ).mappings().one()

    else:
        row = connection.execute(
            EXPECTED_COVERAGE_AFTER,
            {
                "source_id":
                    source_id,
                "after_date":
                    after_date,
            },
        ).mappings().one()

    return dict(
        row
    )


def load_ownership_pairs(
    connection: Connection,
    *,
    source_id: UUID,
    after_date: date | None = None,
) -> list[dict[str, Any]]:
    if after_date is None:
        rows = connection.execute(
            LOAD_ALL_PAIRS,
            {
                "source_id":
                    source_id,
            },
        ).mappings().all()

    else:
        rows = connection.execute(
            LOAD_INCREMENTAL_PAIRS,
            {
                "source_id":
                    source_id,
                "after_date":
                    after_date,
            },
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def upsert_ownership_trends(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
    batch_size: int = 1000,
) -> int:
    if not rows:
        return 0

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be "
            "greater than zero."
        )

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

        connection.execute(
            UPSERT_TREND,
            batch,
        )

        total += len(
            batch
        )

    return total


def get_recent_trend_dates(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
    limit: int,
) -> list[date]:
    rows = connection.execute(
        RECENT_TREND_DATES,
        {
            "source_id":
                source_id,
            "model_version":
                model_version,
            "limit":
                limit,
        },
    )

    return [
        row.as_of_date
        for row in rows
    ]


def load_stored_trends_after(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
    after_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED_AFTER,
        {
            "source_id":
                source_id,
            "model_version":
                model_version,
            "after_date":
                after_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]