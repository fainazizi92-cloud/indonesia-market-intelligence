from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

LATEST_TECHNICAL_MODEL = text(
    """
    SELECT
        model_version,

        MAX(trading_date)
            AS latest_date,

        MAX(calculated_at)
            AS latest_calculated_at

    FROM sector_scores_daily

    WHERE model_version LIKE
          'sector_rotation_v1_current_%_yahoo_eod'

    GROUP BY model_version

    ORDER BY
        latest_date DESC,
        latest_calculated_at DESC

    LIMIT 1
    """
)


LATEST_OWNERSHIP_MODEL = text(
    """
    SELECT
        model_version,

        MAX(as_of_date)
            AS latest_date,

        MAX(calculated_at)
            AS latest_calculated_at

    FROM sector_ownership_signals

    WHERE source_id =
          :source_id
      AND model_version LIKE
          'sector_ownership_v1_current_%_ksei_official'

    GROUP BY model_version

    ORDER BY
        latest_date DESC,
        latest_calculated_at DESC

    LIMIT 1
    """
)


INPUT_CTE = """
WITH integrated_input AS (
    SELECT
        t.trading_date,
        t.sector_code,

        CAST(
            t.score
            AS DOUBLE PRECISION
        ) AS technical_score,

        t.rotation_label
            AS technical_rotation_label,

        o.as_of_date
            AS ownership_as_of_date,

        CAST(
            o.score
            AS DOUBLE PRECISION
        ) AS ownership_score,

        o.signal_label
            AS ownership_signal_label,

        o.low_coverage_flag
            AS ownership_low_coverage_flag

    FROM sector_scores_daily t

    JOIN LATERAL (
        SELECT
            s.as_of_date,
            s.score,
            s.signal_label,
            s.low_coverage_flag

        FROM sector_ownership_signals s

        WHERE s.source_id =
              :source_id
          AND s.model_version =
              :ownership_model_version
          AND s.sector_code =
              t.sector_code
          AND s.as_of_date
              <= t.trading_date

        ORDER BY
            s.as_of_date DESC

        LIMIT 1
    ) o
      ON TRUE

    WHERE t.model_version =
          :technical_model_version
      AND t.score IS NOT NULL
)
"""


LOAD_ALL_INPUTS = text(
    INPUT_CTE
    + """
    SELECT
        trading_date,
        sector_code,
        technical_score,
        technical_rotation_label,

        ownership_as_of_date,
        ownership_score,
        ownership_signal_label,
        ownership_low_coverage_flag

    FROM integrated_input

    ORDER BY
        sector_code,
        trading_date
    """
)


LOAD_INCREMENTAL_INPUTS = text(
    INPUT_CTE
    + """
    SELECT
        trading_date,
        sector_code,
        technical_score,
        technical_rotation_label,

        ownership_as_of_date,
        ownership_score,
        ownership_signal_label,
        ownership_low_coverage_flag

    FROM integrated_input

    WHERE trading_date >
          :after_date

    ORDER BY
        sector_code,
        trading_date
    """
)


EXPECTED_COVERAGE = text(
    INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT sector_code
        ) AS expected_sectors,

        COUNT(
            DISTINCT trading_date
        ) AS expected_dates,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM integrated_input
    """
)


EXPECTED_COVERAGE_AFTER = text(
    INPUT_CTE
    + """
    SELECT
        COUNT(*)
            AS expected_rows,

        COUNT(
            DISTINCT sector_code
        ) AS expected_sectors,

        COUNT(
            DISTINCT trading_date
        ) AS expected_dates,

        MIN(trading_date)
            AS expected_first,

        MAX(trading_date)
            AS expected_last

    FROM integrated_input

    WHERE trading_date >
          :after_date
    """
)


LATEST_INPUT_STATE = text(
    INPUT_CTE
    + """
    ,
    latest AS (
        SELECT MAX(trading_date)
            AS trading_date

        FROM integrated_input
    )

    SELECT
        latest.trading_date
            AS latest_input_date,

        COUNT(
            i.sector_code
        ) AS latest_sector_count,

        STRING_AGG(
            i.sector_code
            || ':'
            || i.ownership_as_of_date::text,
            ','
            ORDER BY i.sector_code
        ) AS ownership_signature

    FROM latest

    LEFT JOIN integrated_input i
      ON i.trading_date =
         latest.trading_date

    GROUP BY
        latest.trading_date
    """
)


INPUT_STATE_FOR_DATE = text(
    INPUT_CTE
    + """
    SELECT
        CAST(
            :as_of_date
            AS DATE
        ) AS trading_date,

        COUNT(
            sector_code
        ) AS sector_count,

        STRING_AGG(
            sector_code
            || ':'
            || ownership_as_of_date::text,
            ','
            ORDER BY sector_code
        ) AS ownership_signature

    FROM integrated_input

    WHERE trading_date =
          :as_of_date
    """
)


STORED_LATEST_STATE = text(
    """
    WITH latest AS (
        SELECT MAX(trading_date)
            AS trading_date

        FROM integrated_sector_intelligence

        WHERE model_version =
              :model_version
    )

    SELECT
        latest.trading_date
            AS latest_date,

        COUNT(
            i.sector_code
        ) AS latest_sector_count,

        STRING_AGG(
            i.sector_code
            || ':'
            || i.ownership_as_of_date::text,
            ','
            ORDER BY i.sector_code
        ) AS ownership_signature

    FROM latest

    LEFT JOIN integrated_sector_intelligence i
      ON i.trading_date =
         latest.trading_date
     AND i.model_version =
         :model_version

    GROUP BY
        latest.trading_date
    """
)


UPSERT_ROW = text(
    """
    INSERT INTO integrated_sector_intelligence (
        trading_date,
        sector_code,

        technical_score,
        technical_rotation_label,

        ownership_as_of_date,
        ownership_score,
        ownership_signal_label,

        ownership_age_days,
        ownership_low_coverage_flag,
        ownership_stale_flag,

        technical_weight,
        ownership_weight,

        integrated_score,
        integrated_label,
        alignment_label,

        technical_model_version,
        ownership_model_version,
        model_version,

        calculated_at
    )
    VALUES (
        :trading_date,
        :sector_code,

        :technical_score,
        :technical_rotation_label,

        :ownership_as_of_date,
        :ownership_score,
        :ownership_signal_label,

        :ownership_age_days,
        :ownership_low_coverage_flag,
        :ownership_stale_flag,

        :technical_weight,
        :ownership_weight,

        :integrated_score,
        :integrated_label,
        :alignment_label,

        :technical_model_version,
        :ownership_model_version,
        :model_version,

        NOW()
    )

    ON CONFLICT (
        trading_date,
        sector_code,
        model_version
    )
    DO UPDATE SET
        technical_score =
            EXCLUDED.technical_score,

        technical_rotation_label =
            EXCLUDED.technical_rotation_label,

        ownership_as_of_date =
            EXCLUDED.ownership_as_of_date,

        ownership_score =
            EXCLUDED.ownership_score,

        ownership_signal_label =
            EXCLUDED.ownership_signal_label,

        ownership_age_days =
            EXCLUDED.ownership_age_days,

        ownership_low_coverage_flag =
            EXCLUDED.ownership_low_coverage_flag,

        ownership_stale_flag =
            EXCLUDED.ownership_stale_flag,

        technical_weight =
            EXCLUDED.technical_weight,

        ownership_weight =
            EXCLUDED.ownership_weight,

        integrated_score =
            EXCLUDED.integrated_score,

        integrated_label =
            EXCLUDED.integrated_label,

        alignment_label =
            EXCLUDED.alignment_label,

        technical_model_version =
            EXCLUDED.technical_model_version,

        ownership_model_version =
            EXCLUDED.ownership_model_version,

        calculated_at =
            NOW()
    """
)


DELETE_MODEL = text(
    """
    DELETE FROM integrated_sector_intelligence

    WHERE model_version =
          :model_version
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
            DISTINCT trading_date
        ) AS dates,

        MIN(trading_date)
            AS first_date,

        MAX(trading_date)
            AS last_date

    FROM integrated_sector_intelligence

    WHERE model_version =
          :model_version
    """
)


LATEST_RANKING = text(
    """
    SELECT
        trading_date,
        sector_code,

        technical_score,
        technical_rotation_label,

        ownership_as_of_date,
        ownership_score,
        ownership_signal_label,

        ownership_age_days,
        ownership_low_coverage_flag,
        ownership_stale_flag,

        technical_weight,
        ownership_weight,

        integrated_score,
        integrated_label,
        alignment_label,

        technical_model_version,
        ownership_model_version,
        model_version

    FROM integrated_sector_intelligence

    WHERE model_version =
          :model_version
      AND trading_date =
          :trading_date

    ORDER BY
        integrated_score DESC
    """
)


LOAD_ALL_STORED = text(
    """
    SELECT
        trading_date,
        sector_code,

        technical_score,
        technical_rotation_label,

        ownership_as_of_date,
        ownership_score,
        ownership_signal_label,

        ownership_age_days,
        ownership_low_coverage_flag,
        ownership_stale_flag,

        technical_weight,
        ownership_weight,

        integrated_score,
        integrated_label,
        alignment_label,

        technical_model_version,
        ownership_model_version,
        model_version

    FROM integrated_sector_intelligence

    WHERE model_version =
          :model_version

    ORDER BY
        sector_code,
        trading_date
    """
)


LOAD_STORED_AFTER = text(
    """
    SELECT
        trading_date,
        sector_code,

        technical_score,
        technical_rotation_label,

        ownership_as_of_date,
        ownership_score,
        ownership_signal_label,

        ownership_age_days,
        ownership_low_coverage_flag,
        ownership_stale_flag,

        technical_weight,
        ownership_weight,

        integrated_score,
        integrated_label,
        alignment_label,

        technical_model_version,
        ownership_model_version,
        model_version

    FROM integrated_sector_intelligence

    WHERE model_version =
          :model_version
      AND trading_date >
          :after_date

    ORDER BY
        sector_code,
        trading_date
    """
)


RECENT_DATES = text(
    """
    SELECT DISTINCT
        trading_date

    FROM integrated_sector_intelligence

    WHERE model_version =
          :model_version

    ORDER BY trading_date DESC

    LIMIT :limit
    """
)


DUPLICATE_GROUPS = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            trading_date,
            sector_code,
            model_version

        FROM integrated_sector_intelligence

        WHERE model_version =
              :model_version

        GROUP BY
            trading_date,
            sector_code,
            model_version

        HAVING COUNT(*) != 1
    ) duplicates
    """
)


def _input_params(
    *,
    source_id,
    technical_model_version: str,
    ownership_model_version: str,
) -> dict[str, Any]:
    return {
        "source_id":
            source_id,

        "technical_model_version":
            technical_model_version,

        "ownership_model_version":
            ownership_model_version,
    }


def get_latest_technical_model_state(
    connection: Connection,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_TECHNICAL_MODEL
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "Sector rotation technical "
            "model is unavailable."
        )

    return dict(
        row
    )


def get_latest_ownership_model_state(
    connection: Connection,
    *,
    source_id,
) -> dict[str, Any]:
    row = connection.execute(
        LATEST_OWNERSHIP_MODEL,
        {
            "source_id":
                source_id,
        },
    ).mappings().first()

    if row is None:
        raise RuntimeError(
            "Sector ownership model "
            "is unavailable."
        )

    return dict(
        row
    )


def get_latest_input_state(
    connection: Connection,
    *,
    source_id,
    technical_model_version: str,
    ownership_model_version: str,
) -> dict[str, Any]:
    params = _input_params(
        source_id=source_id,
        technical_model_version=(
            technical_model_version
        ),
        ownership_model_version=(
            ownership_model_version
        ),
    )

    row = connection.execute(
        LATEST_INPUT_STATE,
        params,
    ).mappings().one()

    result = dict(
        row
    )

    if (
        result["latest_input_date"]
        is None
    ):
        raise RuntimeError(
            "No integrated sector input "
            "rows are available."
        )

    return result


def get_input_state_for_date(
    connection: Connection,
    *,
    source_id,
    technical_model_version: str,
    ownership_model_version: str,
    as_of_date: date,
) -> dict[str, Any]:
    params = _input_params(
        source_id=source_id,
        technical_model_version=(
            technical_model_version
        ),
        ownership_model_version=(
            ownership_model_version
        ),
    )

    params[
        "as_of_date"
    ] = as_of_date

    row = connection.execute(
        INPUT_STATE_FOR_DATE,
        params,
    ).mappings().one()

    return dict(
        row
    )


def get_stored_latest_state(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_LATEST_STATE,
        {
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
    source_id,
    technical_model_version: str,
    ownership_model_version: str,
    after_date: date | None = None,
) -> dict[str, Any]:
    params = _input_params(
        source_id=source_id,
        technical_model_version=(
            technical_model_version
        ),
        ownership_model_version=(
            ownership_model_version
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


def load_integrated_inputs(
    connection: Connection,
    *,
    source_id,
    technical_model_version: str,
    ownership_model_version: str,
    after_date: date | None = None,
) -> list[dict[str, Any]]:
    params = _input_params(
        source_id=source_id,
        technical_model_version=(
            technical_model_version
        ),
        ownership_model_version=(
            ownership_model_version
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


def delete_integrated_model(
    connection: Connection,
    *,
    model_version: str,
) -> int:
    result = connection.execute(
        DELETE_MODEL,
        {
            "model_version":
                model_version,
        },
    )

    return int(
        result.rowcount or 0
    )


def upsert_integrated_rows(
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
            UPSERT_ROW,
            batch,
        )

        total += len(
            batch
        )

    return total


def get_stored_coverage(
    connection: Connection,
    *,
    model_version: str,
) -> dict[str, Any]:
    row = connection.execute(
        STORED_COVERAGE,
        {
            "model_version":
                model_version,
        },
    ).mappings().one()

    return dict(
        row
    )


def load_latest_ranking(
    connection: Connection,
    *,
    model_version: str,
    trading_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LATEST_RANKING,
        {
            "model_version":
                model_version,
            "trading_date":
                trading_date,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_all_stored(
    connection: Connection,
    *,
    model_version: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_ALL_STORED,
        {
            "model_version":
                model_version,
        },
    ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def load_stored_after(
    connection: Connection,
    *,
    model_version: str,
    after_date: date,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        LOAD_STORED_AFTER,
        {
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


def get_recent_dates(
    connection: Connection,
    *,
    model_version: str,
    limit: int,
) -> list[date]:
    rows = connection.execute(
        RECENT_DATES,
        {
            "model_version":
                model_version,
            "limit":
                limit,
        },
    )

    return [
        row.trading_date
        for row in rows
    ]


def get_duplicate_groups(
    connection: Connection,
    *,
    model_version: str,
) -> int:
    return int(
        connection.execute(
            DUPLICATE_GROUPS,
            {
                "model_version":
                    model_version,
            },
        ).scalar_one()
    )