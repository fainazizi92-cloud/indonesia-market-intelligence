import argparse
from datetime import date

from sqlalchemy import text

from imi.db import engine
from imi.repositories.equity_eod import (
    get_source_id,
)

COVERAGE_SQL = text(
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


SNAPSHOT_SQL = text(
    """
    SELECT
        as_of_date,

        COUNT(*)
            AS rows,

        COUNT(
            DISTINCT instrument_id
        ) AS instruments

    FROM ownership_snapshots

    WHERE source_id =
          :source_id

    GROUP BY as_of_date

    ORDER BY as_of_date
    """
)


QUALITY_SQL = text(
    """
    SELECT
        COUNT(*) FILTER (
            WHERE foreign_ownership_pct
                  IS NULL
        ) AS null_foreign_pct,

        COUNT(*) FILTER (
            WHERE foreign_ownership_pct
                  IS NOT NULL
              AND NOT (
                  foreign_ownership_pct
                  BETWEEN 0 AND 100
              )
        ) AS invalid_foreign_pct,

        COUNT(*) FILTER (
            WHERE free_float_pct
                  IS NOT NULL
        ) AS free_float_non_null,

        COUNT(*) FILTER (
            WHERE hsc_flag
                  IS NOT NULL
        ) AS hsc_non_null,

        COUNT(*) FILTER (
            WHERE concentration_score
                  IS NOT NULL
        ) AS concentration_non_null,

        COUNT(*) FILTER (
            WHERE
                jsonb_extract_path_text(
                    holder_details,
                    'security_number'
                ) IS NULL
                OR
                jsonb_extract_path_text(
                    holder_details,
                    'local'
                ) IS NULL
                OR
                jsonb_extract_path_text(
                    holder_details,
                    'foreign'
                ) IS NULL
                OR
                jsonb_extract_path_text(
                    holder_details,
                    'scripless_total'
                ) IS NULL
                OR
                jsonb_extract_path_text(
                    holder_details,
                    'foreign_ownership_pct'
                ) IS NULL
                OR
                jsonb_extract_path_text(
                    holder_details,
                    'as_of_date'
                ) IS NULL
        ) AS incomplete_holder_details,

        COUNT(*) FILTER (
            WHERE
                jsonb_extract_path_text(
                    holder_details,
                    'as_of_date'
                )
                IS DISTINCT FROM
                as_of_date::text
        ) AS holder_date_mismatch,

        COUNT(*) FILTER (
            WHERE ABS(
                foreign_ownership_pct
                -
                (
                    (
                        jsonb_extract_path_text(
                            holder_details,
                            'foreign',
                            'total'
                        )
                    )::numeric
                    /
                    NULLIF(
                        (
                            jsonb_extract_path_text(
                                holder_details,
                                'security_number'
                            )
                        )::numeric,
                        0
                    )
                    * 100
                )
            ) > 0.0001
        ) AS foreign_pct_mismatch,

        COUNT(*) FILTER (
            WHERE
                (
                    (
                        jsonb_extract_path_text(
                            holder_details,
                            'local',
                            'total'
                        )
                    )::numeric
                    +
                    (
                        jsonb_extract_path_text(
                            holder_details,
                            'foreign',
                            'total'
                        )
                    )::numeric
                )
                >
                (
                    jsonb_extract_path_text(
                        holder_details,
                        'security_number'
                    )
                )::numeric
        ) AS scripless_exceeds_securities

    FROM ownership_snapshots

    WHERE source_id =
          :source_id
    """
)


DUPLICATE_SQL = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            instrument_id,
            as_of_date,
            source_id

        FROM ownership_snapshots

        WHERE source_id =
              :source_id

        GROUP BY
            instrument_id,
            as_of_date,
            source_id

        HAVING COUNT(*) != 1
    ) duplicate_groups
    """
)


LATEST_CURRENT_COVERAGE_SQL = text(
    """
    WITH latest_universe AS (
        SELECT
            MAX(snapshot_date)
                AS snapshot_date

        FROM instrument_universe_snapshots

        WHERE universe_code =
              'IDX_ALL_CURRENT'
    ),

    current_universe AS (
        SELECT DISTINCT
            u.instrument_id

        FROM instrument_universe_snapshots u

        CROSS JOIN latest_universe lu

        WHERE u.universe_code =
              'IDX_ALL_CURRENT'
          AND u.snapshot_date =
              lu.snapshot_date
          AND u.is_member = TRUE
    ),

    latest_ownership AS (
        SELECT
            MAX(as_of_date)
                AS as_of_date

        FROM ownership_snapshots

        WHERE source_id =
              :source_id
    )

    SELECT
        lo.as_of_date,

        COUNT(
            cu.instrument_id
        ) AS expected_current,

        COUNT(
            o.instrument_id
        ) AS stored_current,

        COUNT(
            cu.instrument_id
        )
        -
        COUNT(
            o.instrument_id
        ) AS missing_current

    FROM current_universe cu

    CROSS JOIN latest_ownership lo

    LEFT JOIN ownership_snapshots o
      ON o.instrument_id =
         cu.instrument_id
     AND o.as_of_date =
         lo.as_of_date
     AND o.source_id =
         :source_id

    GROUP BY lo.as_of_date
    """
)


def parse_date_argument(
    value: str,
) -> date:
    try:
        return date.fromisoformat(
            value
        )

    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected YYYY-MM-DD."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit historical KSEI "
            "ownership snapshots."
        )
    )

    parser.add_argument(
        "--expected-snapshots",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--expected-first",
        type=parse_date_argument,
        default=None,
    )

    parser.add_argument(
        "--expected-last",
        type=parse_date_argument,
        default=None,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        coverage = dict(
            connection.execute(
                COVERAGE_SQL,
                {
                    "source_id":
                        source_id,
                },
            ).mappings().one()
        )

        snapshots = [
            dict(row)
            for row
            in connection.execute(
                SNAPSHOT_SQL,
                {
                    "source_id":
                        source_id,
                },
            ).mappings()
        ]

        quality = dict(
            connection.execute(
                QUALITY_SQL,
                {
                    "source_id":
                        source_id,
                },
            ).mappings().one()
        )

        duplicate_groups = (
            connection.execute(
                DUPLICATE_SQL,
                {
                    "source_id":
                        source_id,
                },
            ).scalar_one()
        )

        latest = dict(
            connection.execute(
                LATEST_CURRENT_COVERAGE_SQL,
                {
                    "source_id":
                        source_id,
                },
            ).mappings().one()
        )

    print(
        "KSEI Ownership Historical Audit"
    )
    print(
        "-------------------------------"
    )

    print()
    print(
        "Coverage:"
    )
    print(
        f"Rows            : "
        f"{coverage['rows']}"
    )
    print(
        f"Instruments     : "
        f"{coverage['instruments']}"
    )
    print(
        f"Snapshot dates  : "
        f"{coverage['snapshot_dates']}"
    )
    print(
        f"First date      : "
        f"{coverage['first_date']}"
    )
    print(
        f"Last date       : "
        f"{coverage['last_date']}"
    )

    print()
    print(
        "Snapshots:"
    )

    for row in snapshots:
        print(
            f"{row['as_of_date']} | "
            f"rows="
            f"{row['rows']} | "
            f"instruments="
            f"{row['instruments']}"
        )

    print()
    print(
        "Quality:"
    )

    for key, value in (
        quality.items()
    ):
        print(
            f"{key:<28}: "
            f"{value}"
        )

    print(
        f"{'duplicate_groups':<28}: "
        f"{duplicate_groups}"
    )

    print()
    print(
        "Latest current-universe "
        "coverage:"
    )
    print(
        f"Latest ownership : "
        f"{latest['as_of_date']}"
    )
    print(
        f"Expected current : "
        f"{latest['expected_current']}"
    )
    print(
        f"Stored current   : "
        f"{latest['stored_current']}"
    )
    print(
        f"Missing current  : "
        f"{latest['missing_current']}"
    )

    coverage_pass = True

    if (
        args.expected_snapshots
        is not None
        and int(
            coverage["snapshot_dates"]
        )
        != args.expected_snapshots
    ):
        coverage_pass = False

    if (
        args.expected_first
        is not None
        and coverage["first_date"]
        != args.expected_first
    ):
        coverage_pass = False

    if (
        args.expected_last
        is not None
        and coverage["last_date"]
        != args.expected_last
    ):
        coverage_pass = False

    quality_pass = (
        all(
            int(value) == 0
            for value
            in quality.values()
        )
        and int(
            duplicate_groups
        ) == 0
    )

    latest_pass = (
        latest["as_of_date"]
        is not None
        and int(
            latest["missing_current"]
        ) == 0
    )

    print()
    print(
        "Result:"
    )
    print(
        "Coverage : "
        + (
            "PASS"
            if coverage_pass
            else "FAIL"
        )
    )
    print(
        "Quality  : "
        + (
            "PASS"
            if quality_pass
            else "FAIL"
        )
    )
    print(
        "Latest   : "
        + (
            "PASS"
            if latest_pass
            else "FAIL"
        )
    )

    if not (
        coverage_pass
        and quality_pass
        and latest_pass
    ):
        raise SystemExit(1)

    print()
    print(
        "WARNING:"
    )
    print(
        "Historical ownership currently "
        "uses the current IDX instrument "
        "master and is therefore "
        "survivorship-biased."
    )
    print(
        "KSEI ownership snapshots are "
        "not daily foreign buy/sell "
        "flow data."
    )


if __name__ == "__main__":
    main()