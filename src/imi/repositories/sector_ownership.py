from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from imi.features.sector_ownership import (
    EXTREME_MOVE_THRESHOLD_PP,
    STOCK_DELTA_CLIP_PP,
)

LATEST_UNIVERSE_SNAPSHOT_DATE = text(
    """
    SELECT MAX(snapshot_date)

    FROM instrument_universe_snapshots

    WHERE universe_code =
          'IDX_ALL_CURRENT'
    """
)


SECTOR_INPUT_CTE = """
WITH latest_universe AS (
    SELECT MAX(snapshot_date)
        AS snapshot_date

    FROM instrument_universe_snapshots

    WHERE universe_code =
          'IDX_ALL_CURRENT'
),

current_sector_counts AS (
    SELECT
        i.sector_code,

        COUNT(*)
            AS current_universe_count

    FROM instrument_universe_snapshots u

    CROSS JOIN latest_universe lu

    JOIN instruments i
      ON i.id =
         u.instrument_id

    WHERE u.universe_code =
          'IDX_ALL_CURRENT'
      AND u.snapshot_date =
          lu.snapshot_date
      AND u.is_member = TRUE
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND i.sector_code IS NOT NULL

    GROUP BY i.sector_code
),

sector_input AS (
    SELECT
        t.as_of_date,
        i.sector_code,

        COUNT(*)
            AS eligible_count,

        MAX(
            c.current_universe_count
        ) AS current_universe_count,

        COUNT(*) FILTER (
            WHERE
                NOT t.corporate_action_risk
                AND NOT t.snapshot_gap_flag
        ) AS clean_count,

        COUNT(*) FILTER (
            WHERE
                NOT t.corporate_action_risk
                AND NOT t.snapshot_gap_flag
                AND t.trend_label =
                    'ACCUMULATING'
        ) AS accumulating_count,

        COUNT(*) FILTER (
            WHERE
                NOT t.corporate_action_risk
                AND NOT t.snapshot_gap_flag
                AND t.trend_label =
                    'STABLE'
        ) AS stable_count,

        COUNT(*) FILTER (
            WHERE
                NOT t.corporate_action_risk
                AND NOT t.snapshot_gap_flag
                AND t.trend_label =
                    'DISTRIBUTING'
        ) AS distributing_count,

        COUNT(*) FILTER (
            WHERE
                t.corporate_action_risk
        ) AS corporate_action_risk_count,

        COUNT(*) FILTER (
            WHERE
                t.snapshot_gap_flag
        ) AS snapshot_gap_count,

        COUNT(*) FILTER (
            WHERE
                ABS(
                    t.delta_foreign_ownership_pp
                )
                >= :extreme_threshold_pp
        ) AS extreme_move_count,

        AVG(
            CAST(
                t.delta_foreign_ownership_pp
                AS DOUBLE PRECISION
            )
        ) AS avg_delta_foreign_ownership_pp,

        AVG(
            LEAST(
                :clip_pp,
                GREATEST(
                    -:clip_pp,
                    CAST(
                        t.delta_foreign_ownership_pp
                        AS DOUBLE PRECISION
                    )
                )
            )
        ) FILTER (
            WHERE
                NOT t.corporate_action_risk
                AND NOT t.snapshot_gap_flag
        ) AS avg_clean_clipped_delta_pp

    FROM ownership_trends t

    JOIN instruments i
      ON i.id =
         t.instrument_id

    JOIN current_sector_counts c
      ON c.sector_code =
         i.sector_code

    WHERE t.source_id =
          :source_id
      AND t.model_version =
          :input_model_version
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND i.sector_code IS NOT NULL

    GROUP BY
        t.as_of_date,
        i.sector_code
)
"""


LOAD_ALL_INPUTS = text(
    SECTOR_INPUT_CTE
    + """
    SELECT
        as_of_date,
        sector_code,
        eligible_count,
        current_universe_count,
        clean_count,
        accumulating_count,
        stable_count,
        distributing_count,
        corporate_action_risk_count,
        snapshot_gap_count,
        extreme_move_count,
        avg_delta_foreign_ownership_pp,
        avg_clean_clipped_delta_pp

    FROM sector_input

    ORDER BY
        sector_code,
        as_of_date
    """
)


LOAD_INCREMENTAL_INPUTS = text(
    SECTOR_INPUT_CTE
    + """
    SELECT
        as_of_date,
        sector_code,
        eligible_count,
        current_universe_count,
        clean_count,
        accumulating_count,
        stable_count,
        distributing_count,
        corporate_action_risk_count,
        snapshot_gap_count,
        extreme_move_count,
        avg_delta_foreign_ownership_pp,
        avg_clean_clipped_delta_pp

    FROM sector_input

    WHERE as_of_date >
          :after_date

    ORDER BY
        sector_code,
        as_of_date
    """
)


EXPECTED_COVERAGE = text(
    SECTOR_INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT sector_code
        ) AS expected_sectors,

        COUNT(
            DISTINCT as_of_date
        ) AS expected_dates,

        MIN(as_of_date)
            AS expected_first,

        MAX(as_of_date)
            AS expected_last

    FROM sector_input
    """
)


EXPECTED_COVERAGE_AFTER = text(
    SECTOR_INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT sector_code
        ) AS expected_sectors,

        COUNT(
            DISTINCT as_of_date
        ) AS expected_dates,

        MIN(as_of_date)
            AS expected_first,

        MAX(as_of_date)
            AS expected_last

    FROM sector_input

    WHERE as_of_date >
          :after_date
    """
)


LATEST_INPUT_STATE = text(
    """
    WITH latest AS (
        SELECT MAX(as_of_date)
            AS as_of_date

        FROM ownership_trends

        WHERE source_id =
              :source_id
          AND model_version =
              :input_model_version
    )

    SELECT
        latest.as_of_date
            AS latest_input_date,

        COALESCE(
            (
                SELECT COUNT(*)

                FROM ownership_trends t

                JOIN instruments i
                  ON i.id =
                     t.instrument_id

                WHERE t.source_id =
                      :source_id
                  AND t.model_version =
                      :input_model_version
                  AND t.as_of_date =
                      latest.as_of_date
                  AND i.exchange = 'IDX'
                  AND i.asset_type =
                      'EQUITY'
                  AND i.sector_code
                      IS NOT NULL
            ),
            0
        ) AS latest_input_rows,

        COALESCE(
            (
                SELECT COUNT(
                    DISTINCT i.sector_code
                )

                FROM ownership_trends t

                JOIN instruments i
                  ON i.id =
                     t.instrument_id

                WHERE t.source_id =
                      :source_id
                  AND t.model_version =
                      :input_model_version
                  AND t.as_of_date =
                      latest.as_of_date
                  AND i.exchange = 'IDX'
                  AND i.asset_type =
                      'EQUITY'
                  AND i.sector_code
                      IS NOT NULL
            ),
            0
        ) AS latest_sector_count

    FROM latest
    """
)


EXPECTED_SECTOR_COUNT_FOR_DATE = text(
    """
    SELECT COUNT(
        DISTINCT i.sector_code
    )

    FROM ownership_trends t

    JOIN instruments i
      ON i.id =
         t.instrument_id

    WHERE t.source_id =
          :source_id
      AND t.model_version =
          :input_model_version
      AND t.as_of_date =
          :as_of_date
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
      AND i.sector_code IS NOT NULL
    """
)


STORED_LATEST_STATE = text(
    """
    WITH latest AS (
        SELECT MAX(as_of_date)
            AS as_of_date

        FROM sector_ownership_signals

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

                FROM sector_ownership_signals s

                WHERE s.source_id =
                      :source_id
                  AND s.model_version =
                      :model_version
                  AND s.as_of_date =
                      latest.as_of_date
            ),
            0
        ) AS latest_sector_count

    FROM latest
    """
)


UPSERT_SIGNAL = text(
    """
    INSERT INTO sector_ownership_signals (
        as_of_date,
        sector_code,

        eligible_count,
        current_universe_count,
        coverage_pct,

        clean_count,

        accumulating_count,
        stable_count,
        distributing_count,

        corporate_action_risk_count,
        snapshot_gap_count,
        extreme_move_count,

        avg_delta_foreign_ownership_pp,
        avg_clean_clipped_delta_pp,

        breadth_score,
        intensity_score,
        score,

        signal_label,
        low_coverage_flag,

        source_id,
        input_model_version,
        model_version,

        calculated_at
    )
    VALUES (
        :as_of_date,
        :sector_code,

        :eligible_count,
        :current_universe_count,
        :coverage_pct,

        :clean_count,

        :accumulating_count,
        :stable_count,
        :distributing_count,

        :corporate_action_risk_count,
        :snapshot_gap_count,
        :extreme_move_count,

        :avg_delta_foreign_ownership_pp,
        :avg_clean_clipped_delta_pp,

        :breadth_score,
        :intensity_score,
        :score,

        :signal_label,
        :low_coverage_flag,

        :source_id,
        :input_model_version,
        :model_version,

        NOW()
    )

    ON CONFLICT (
        as_of_date,
        sector_code,
        source_id,
        model_version
    )
    DO UPDATE SET
        eligible_count =
            EXCLUDED.eligible_count,

        current_universe_count =
            EXCLUDED.current_universe_count,

        coverage_pct =
            EXCLUDED.coverage_pct,

        clean_count =
            EXCLUDED.clean_count,

        accumulating_count =
            EXCLUDED.accumulating_count,

        stable_count =
            EXCLUDED.stable_count,

        distributing_count =
            EXCLUDED.distributing_count,

        corporate_action_risk_count =
            EXCLUDED.corporate_action_risk_count,

        snapshot_gap_count =
            EXCLUDED.snapshot_gap_count,

        extreme_move_count =
            EXCLUDED.extreme_move_count,

        avg_delta_foreign_ownership_pp =
            EXCLUDED.avg_delta_foreign_ownership_pp,

        avg_clean_clipped_delta_pp =
            EXCLUDED.avg_clean_clipped_delta_pp,

        breadth_score =
            EXCLUDED.breadth_score,

        intensity_score =
            EXCLUDED.intensity_score,

        score =
            EXCLUDED.score,

        signal_label =
            EXCLUDED.signal_label,

        low_coverage_flag =
            EXCLUDED.low_coverage_flag,

        input_model_version =
            EXCLUDED.input_model_version,

        calculated_at =
            NOW()
    """
)


STORED_COVERAGE = text(
    """
    SELECT
        COUNT(*) AS rows,

        COUNT(
            DISTINCT sector_code
        ) AS sectors,

        COUNT(
            DISTINCT as_of_date
        ) AS dates,

        MIN(as_of_date)
            AS first_date,

        MAX(as_of_date)
            AS last_date

    FROM sector_ownership_signals

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version
    """
)


RECENT_DATES = text(
    """
    SELECT DISTINCT
        as_of_date

    FROM sector_ownership_signals

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
        as_of_date,
        sector_code,

        eligible_count,
        current_universe_count,
        coverage_pct,

        clean_count,

        accumulating_count,
        stable_count,
        distributing_count,

        corporate_action_risk_count,
        snapshot_gap_count,
        extreme_move_count,

        avg_delta_foreign_ownership_pp,
        avg_clean_clipped_delta_pp,

        breadth_score,
        intensity_score,
        score,

        signal_label,
        low_coverage_flag,

        source_id,
        input_model_version,
        model_version

    FROM sector_ownership_signals

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version
      AND as_of_date >
          :after_date

    ORDER BY
        sector_code,
        as_of_date
    """
)


LOAD_ALL_STORED = text(
    """
    SELECT
        as_of_date,
        sector_code,

        eligible_count,
        current_universe_count,
        coverage_pct,

        clean_count,

        accumulating_count,
        stable_count,
        distributing_count,

        corporate_action_risk_count,
        snapshot_gap_count,
        extreme_move_count,

        avg_delta_foreign_ownership_pp,
        avg_clean_clipped_delta_pp,

        breadth_score,
        intensity_score,
        score,

        signal_label,
        low_coverage_flag,

        source_id,
        input_model_version,
        model_version

    FROM sector_ownership_signals

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version

    ORDER BY
        sector_code,
        as_of_date
    """
)


LATEST_RANKING = text(
    """
    SELECT
        as_of_date,
        sector_code,

        eligible_count,
        current_universe_count,
        coverage_pct,

        clean_count,

        accumulating_count,
        stable_count,
        distributing_count,

        corporate_action_risk_count,
        snapshot_gap_count,
        extreme_move_count,

        avg_delta_foreign_ownership_pp,
        avg_clean_clipped_delta_pp,

        breadth_score,
        intensity_score,
        score,

        signal_label,
        low_coverage_flag

    FROM sector_ownership_signals

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version
      AND as_of_date =
          :as_of_date

    ORDER BY score DESC
    """
)


DUPLICATE_GROUPS = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            as_of_date,
            sector_code,
            source_id,
            model_version

        FROM sector_ownership_signals

        WHERE source_id =
              :source_id
          AND model_version =
              :model_version

        GROUP BY
            as_of_date,
            sector_code,
            source_id,
            model_version

        HAVING COUNT(*) != 1
    ) duplicates
    """
)


def _aggregate_parameters(
    *,
    source_id: UUID,
    input_model_version: str,
) -> dict[str, Any]:
    return {
        "source_id":
            source_id,

        "input_model_version":
            input_model_version,

        "clip_pp":
            STOCK_DELTA_CLIP_PP,

        "extreme_threshold_pp":
            EXTREME_MOVE_THRESHOLD_PP,
    }


def get_latest_universe_snapshot_date(
    connection: Connection,
) -> date:
    value = connection.execute(
        LATEST_UNIVERSE_SNAPSHOT_DATE
    ).scalar_one()

    if value is None:
        raise RuntimeError(
            "IDX current-universe "
            "snapshot is unavailable."
        )

    return value


def get_latest_input_state(
    connection: Connection,
    *,
    source_id: UUID,
    input_model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_INPUT_STATE,
        {
            "source_id":
                source_id,
            "input_model_version":
                input_model_version,
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
            "Ownership trend input "
            "is unavailable."
        )

    return result


def get_expected_sector_count_for_date(
    connection: Connection,
    *,
    source_id: UUID,
    input_model_version: str,
    as_of_date: date,
) -> int:
    return int(
        connection.execute(
            EXPECTED_SECTOR_COUNT_FOR_DATE,
            {
                "source_id":
                    source_id,
                "input_model_version":
                    input_model_version,
                "as_of_date":
                    as_of_date,
            },
        ).scalar_one()
    )


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


def get_expected_coverage(
    connection: Connection,
    *,
    source_id: UUID,
    input_model_version: str,
    after_date: date | None = None,
) -> dict[str, Any]:
    params = _aggregate_parameters(
        source_id=source_id,
        input_model_version=(
            input_model_version
        ),
    )

    if after_date is None:
        row = connection.execute(
            EXPECTED_COVERAGE,
            params,
        ).mappings().one()

    else:
        params[
            "after_date"
        ] = after_date

        row = connection.execute(
            EXPECTED_COVERAGE_AFTER,
            params,
        ).mappings().one()

    return dict(
        row
    )


def load_sector_inputs(
    connection: Connection,
    *,
    source_id: UUID,
    input_model_version: str,
    after_date: date | None = None,
) -> list[dict[str, Any]]:
    params = _aggregate_parameters(
        source_id=source_id,
        input_model_version=(
            input_model_version
        ),
    )

    if after_date is None:
        rows = connection.execute(
            LOAD_ALL_INPUTS,
            params,
        ).mappings().all()

    else:
        params[
            "after_date"
        ] = after_date

        rows = connection.execute(
            LOAD_INCREMENTAL_INPUTS,
            params,
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def upsert_sector_ownership_rows(
    connection: Connection,
    *,
    rows: list[dict[str, Any]],
    batch_size: int = 500,
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
            UPSERT_SIGNAL,
            batch,
        )

        total += len(
            batch
        )

    return total


def get_stored_coverage(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_COVERAGE,
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


def get_recent_dates(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
    limit: int,
) -> list[date]:
    rows = connection.execute(
        RECENT_DATES,
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


def load_stored_after(
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


def load_all_stored(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_ALL_STORED,
        {
            "source_id":
                source_id,
            "model_version":
                model_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_latest_ranking(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
    as_of_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LATEST_RANKING,
        {
            "source_id":
                source_id,
            "model_version":
                model_version,
            "as_of_date":
                as_of_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def get_duplicate_groups(
    connection: Connection,
    *,
    source_id: UUID,
    model_version: str,
) -> int:
    return int(
        connection.execute(
            DUPLICATE_GROUPS,
            {
                "source_id":
                    source_id,
                "model_version":
                    model_version,
            },
        ).scalar_one()
    )