import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

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

        i.metadata
            ->> 'listing_board'
            AS listing_board,

        ius.snapshot_date,
        ius.ingested_at

    FROM instrument_universe_snapshots ius

    JOIN latest_snapshot ls
      ON ls.snapshot_date =
         ius.snapshot_date

    JOIN instruments i
      ON i.id =
         ius.instrument_id

    JOIN data_sources ds
      ON ds.id =
         ius.source_id

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


UPSERT_BOARD_HISTORY = text(
    """
    INSERT INTO instrument_board_history (
        instrument_id,

        effective_from,
        effective_to,

        board_code,
        raw_board_name,

        source_code,

        available_at,
        availability_status,

        point_in_time_safe,

        evidence,

        calculated_at
    )
    VALUES (
        :instrument_id,

        :effective_from,
        :effective_to,

        :board_code,
        :raw_board_name,

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
        effective_from,
        source_code
    )
    DO UPDATE SET
        effective_to =
            EXCLUDED.effective_to,

        board_code =
            EXCLUDED.board_code,

        raw_board_name =
            EXCLUDED.raw_board_name,

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


UPSERT_MARKET_RULE = text(
    """
    INSERT INTO idx_market_rule_history (
        rule_key,

        rule_type,
        market,
        board_group,

        effective_from,
        effective_to,

        price_min,
        price_min_inclusive,

        price_max,
        price_max_inclusive,

        lot_size,
        tick_size,

        ara_pct,
        arb_pct,

        ara_absolute,
        arb_absolute,

        source_reference,
        verification_status,

        evidence,

        created_at
    )
    VALUES (
        :rule_key,

        :rule_type,
        :market,
        :board_group,

        :effective_from,
        :effective_to,

        :price_min,
        :price_min_inclusive,

        :price_max,
        :price_max_inclusive,

        :lot_size,
        :tick_size,

        :ara_pct,
        :arb_pct,

        :ara_absolute,
        :arb_absolute,

        :source_reference,
        :verification_status,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        rule_key
    )
    DO UPDATE SET
        rule_type =
            EXCLUDED.rule_type,

        market =
            EXCLUDED.market,

        board_group =
            EXCLUDED.board_group,

        effective_from =
            EXCLUDED.effective_from,

        effective_to =
            EXCLUDED.effective_to,

        price_min =
            EXCLUDED.price_min,

        price_min_inclusive =
            EXCLUDED.price_min_inclusive,

        price_max =
            EXCLUDED.price_max,

        price_max_inclusive =
            EXCLUDED.price_max_inclusive,

        lot_size =
            EXCLUDED.lot_size,

        tick_size =
            EXCLUDED.tick_size,

        ara_pct =
            EXCLUDED.ara_pct,

        arb_pct =
            EXCLUDED.arb_pct,

        ara_absolute =
            EXCLUDED.ara_absolute,

        arb_absolute =
            EXCLUDED.arb_absolute,

        source_reference =
            EXCLUDED.source_reference,

        verification_status =
            EXCLUDED.verification_status,

        evidence =
            EXCLUDED.evidence
    """
)


LOAD_BOARD_HISTORY = text(
    """
    SELECT
        instrument_id,

        effective_from,
        effective_to,

        board_code,
        raw_board_name,

        source_code,

        available_at,
        availability_status,

        point_in_time_safe,

        evidence

    FROM instrument_board_history

    ORDER BY
        effective_from,
        instrument_id
    """
)


LOAD_MARKET_RULES = text(
    """
    SELECT
        rule_key,

        rule_type,
        market,
        board_group,

        effective_from,
        effective_to,

        price_min,
        price_min_inclusive,

        price_max,
        price_max_inclusive,

        lot_size,
        tick_size,

        ara_pct,
        arb_pct,

        ara_absolute,
        arb_absolute,

        source_reference,
        verification_status,

        evidence

    FROM idx_market_rule_history

    ORDER BY
        rule_type,
        effective_from,
        rule_key
    """
)


CORPORATE_ACTION_COVERAGE = text(
    """
    SELECT
        COUNT(*)
            AS observed_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS distinct_instruments,

        MIN(
            COALESCE(
                ex_date,
                cum_date,
                record_date,
                announcement_at::date
            )
        ) AS first_date,

        MAX(
            COALESCE(
                ex_date,
                cum_date,
                record_date,
                announcement_at::date
            )
        ) AS last_date

    FROM corporate_actions
    """
)


UNIVERSE_COVERAGE = text(
    """
    SELECT
        COUNT(*)
            AS observed_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS distinct_instruments,

        COUNT(*) FILTER (
            WHERE point_in_time_safe
        ) AS point_in_time_safe_rows,

        MIN(valid_from)
            AS first_date,

        MAX(valid_from)
            AS last_date

    FROM historical_universe_membership
    """
)


BOARD_COVERAGE = text(
    """
    SELECT
        COUNT(*)
            AS observed_rows,

        COUNT(
            DISTINCT instrument_id
        ) AS distinct_instruments,

        COUNT(*) FILTER (
            WHERE point_in_time_safe
        ) AS point_in_time_safe_rows,

        MIN(effective_from)
            AS first_date,

        MAX(effective_from)
            AS last_date

    FROM instrument_board_history
    """
)


UPSERT_COVERAGE_STATE = text(
    """
    INSERT INTO historical_data_coverage_state (
        dataset_code,

        observed_rows,
        distinct_instruments,
        point_in_time_safe_rows,

        first_observation_date,
        last_observation_date,

        complete_history,

        blocking_reason,

        evidence,

        calculated_at
    )
    VALUES (
        :dataset_code,

        :observed_rows,
        :distinct_instruments,
        :point_in_time_safe_rows,

        :first_observation_date,
        :last_observation_date,

        :complete_history,

        :blocking_reason,

        CAST(
            :evidence
            AS JSONB
        ),

        NOW()
    )

    ON CONFLICT (
        dataset_code
    )
    DO UPDATE SET
        observed_rows =
            EXCLUDED.observed_rows,

        distinct_instruments =
            EXCLUDED.distinct_instruments,

        point_in_time_safe_rows =
            EXCLUDED.point_in_time_safe_rows,

        first_observation_date =
            EXCLUDED.first_observation_date,

        last_observation_date =
            EXCLUDED.last_observation_date,

        complete_history =
            EXCLUDED.complete_history,

        blocking_reason =
            EXCLUDED.blocking_reason,

        evidence =
            EXCLUDED.evidence,

        calculated_at =
            NOW()
    """
)


LOAD_COVERAGE_STATES = text(
    """
    SELECT
        dataset_code,

        observed_rows,
        distinct_instruments,
        point_in_time_safe_rows,

        first_observation_date,
        last_observation_date,

        complete_history,

        blocking_reason,

        evidence

    FROM historical_data_coverage_state

    ORDER BY
        dataset_code
    """
)


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


def upsert_board_rows(
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
        UPSERT_BOARD_HISTORY,
        serialized,
    )

    return len(
        serialized
    )


def upsert_market_rules(
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
        UPSERT_MARKET_RULE,
        serialized,
    )

    return len(
        serialized
    )


def load_board_history(
    connection: Connection,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row
        in connection.execute(
            LOAD_BOARD_HISTORY
        ).mappings().all()
    ]


def load_market_rules(
    connection: Connection,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row
        in connection.execute(
            LOAD_MARKET_RULES
        ).mappings().all()
    ]


def get_corporate_action_coverage(
    connection: Connection,
) -> dict[str, Any]:
    return dict(
        connection.execute(
            CORPORATE_ACTION_COVERAGE
        ).mappings().one()
    )


def get_universe_coverage(
    connection: Connection,
) -> dict[str, Any]:
    return dict(
        connection.execute(
            UNIVERSE_COVERAGE
        ).mappings().one()
    )


def get_board_coverage(
    connection: Connection,
) -> dict[str, Any]:
    return dict(
        connection.execute(
            BOARD_COVERAGE
        ).mappings().one()
    )


def upsert_coverage_state(
    connection: Connection,
    *,
    dataset_code: str,
    observed_rows: int,
    distinct_instruments: int,
    point_in_time_safe_rows: int,
    first_observation_date,
    last_observation_date,
    complete_history: bool,
    blocking_reason: str,
    evidence: dict[str, Any],
) -> None:
    connection.execute(
        UPSERT_COVERAGE_STATE,
        {
            "dataset_code":
                dataset_code,

            "observed_rows":
                observed_rows,

            "distinct_instruments":
                distinct_instruments,

            "point_in_time_safe_rows":
                point_in_time_safe_rows,

            "first_observation_date":
                first_observation_date,

            "last_observation_date":
                last_observation_date,

            "complete_history":
                complete_history,

            "blocking_reason":
                blocking_reason,

            "evidence":
                json.dumps(
                    evidence,
                    sort_keys=True,
                ),
        },
    )


def load_coverage_states(
    connection: Connection,
) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row
        in connection.execute(
            LOAD_COVERAGE_STATES
        ).mappings().all()
    ]