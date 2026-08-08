from sqlalchemy import text

from imi.db import engine
from imi.features.ownership_trend import (
    CORPORATE_ACTION_THRESHOLD_PCT,
    OWNERSHIP_TREND_MODEL_VERSION,
    SNAPSHOT_GAP_THRESHOLD_DAYS,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.ownership_trend import (
    get_expected_coverage,
    get_latest_input_state,
)

ACTUAL_COVERAGE_SQL = text(
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

    FROM ownership_trends

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version
    """
)


QUALITY_SQL = text(
    """
    SELECT
        COUNT(*) FILTER (
            WHERE trend_label
                  NOT IN (
                      'ACCUMULATING',
                      'STABLE',
                      'DISTRIBUTING'
                  )
        ) AS invalid_labels,

        COUNT(*) FILTER (
            WHERE signal_strength
                  NOT BETWEEN 0 AND 100
        ) AS invalid_strength,

        COUNT(*) FILTER (
            WHERE previous_as_of_date
                  >= as_of_date
        ) AS invalid_dates,

        COUNT(*) FILTER (
            WHERE days_between_snapshots
                  <= 0
        ) AS invalid_days,

        COUNT(*) FILTER (
            WHERE ABS(
                delta_foreign_ownership_pp
                -
                (
                    foreign_ownership_pct
                    -
                    previous_foreign_ownership_pct
                )
            ) > 0.0001
        ) AS delta_pct_mismatch,

        COUNT(*) FILTER (
            WHERE delta_foreign_shares
                  != (
                      foreign_shares
                      -
                      previous_foreign_shares
                  )
        ) AS delta_shares_mismatch,

        COUNT(*) FILTER (
            WHERE ABS(
                delta_security_number_pct
                -
                (
                    (
                        security_number
                        -
                        previous_security_number
                    )
                    /
                    previous_security_number
                    * 100
                )
            ) > 0.0001
        ) AS security_delta_mismatch,

        COUNT(*) FILTER (
            WHERE ABS(
                normalized_foreign_share_change_pct
                -
                (
                    delta_foreign_shares
                    /
                    previous_security_number
                    * 100
                )
            ) > 0.0001
        ) AS normalized_change_mismatch,

        COUNT(*) FILTER (
            WHERE corporate_action_risk
                  IS DISTINCT FROM
                  (
                      ABS(
                          delta_security_number_pct
                      )
                      >= :corporate_threshold
                  )
        ) AS corporate_flag_mismatch,

        COUNT(*) FILTER (
            WHERE snapshot_gap_flag
                  IS DISTINCT FROM
                  (
                      days_between_snapshots
                      > :gap_threshold
                  )
        ) AS gap_flag_mismatch

    FROM ownership_trends

    WHERE source_id =
          :source_id
      AND model_version =
          :model_version
    """
)


DUPLICATE_SQL = text(
    """
    SELECT COUNT(*)

    FROM (
        SELECT
            instrument_id,
            as_of_date,
            source_id,
            model_version

        FROM ownership_trends

        WHERE source_id =
              :source_id
          AND model_version =
              :model_version

        GROUP BY
            instrument_id,
            as_of_date,
            source_id,
            model_version

        HAVING COUNT(*) != 1
    ) duplicate_groups
    """
)


LATEST_SQL = text(
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
        latest.as_of_date,

        COUNT(t.instrument_id)
            AS stored

    FROM latest

    LEFT JOIN ownership_trends t
      ON t.as_of_date =
         latest.as_of_date
     AND t.source_id =
         :source_id
     AND t.model_version =
         :model_version

    GROUP BY latest.as_of_date
    """
)


RANKING_SQL = text(
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
        i.symbol,
        i.sector_code,

        t.delta_foreign_ownership_pp,
        t.foreign_ownership_pct,
        t.delta_foreign_shares,

        t.trend_label,
        t.signal_strength,

        t.corporate_action_risk,
        t.snapshot_gap_flag

    FROM ownership_trends t

    JOIN instruments i
      ON i.id =
         t.instrument_id

    CROSS JOIN latest

    WHERE t.source_id =
          :source_id
      AND t.model_version =
          :model_version
      AND t.as_of_date =
          latest.as_of_date

    ORDER BY
        t.delta_foreign_ownership_pp
        DESC
    """
)


def main() -> None:
    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        expected = (
            get_expected_coverage(
                connection,
                source_id=source_id,
            )
        )

        latest_input = (
            get_latest_input_state(
                connection,
                source_id=source_id,
            )
        )

        actual = dict(
            connection.execute(
                ACTUAL_COVERAGE_SQL,
                {
                    "source_id":
                        source_id,
                    "model_version":
                        OWNERSHIP_TREND_MODEL_VERSION,
                },
            ).mappings().one()
        )

        quality = dict(
            connection.execute(
                QUALITY_SQL,
                {
                    "source_id":
                        source_id,
                    "model_version":
                        OWNERSHIP_TREND_MODEL_VERSION,
                    "corporate_threshold":
                        CORPORATE_ACTION_THRESHOLD_PCT,
                    "gap_threshold":
                        SNAPSHOT_GAP_THRESHOLD_DAYS,
                },
            ).mappings().one()
        )

        duplicates = int(
            connection.execute(
                DUPLICATE_SQL,
                {
                    "source_id":
                        source_id,
                    "model_version":
                        OWNERSHIP_TREND_MODEL_VERSION,
                },
            ).scalar_one()
        )

        latest = dict(
            connection.execute(
                LATEST_SQL,
                {
                    "source_id":
                        source_id,
                    "model_version":
                        OWNERSHIP_TREND_MODEL_VERSION,
                },
            ).mappings().one()
        )

        ranking = [
            dict(row)
            for row in connection.execute(
                RANKING_SQL,
                {
                    "source_id":
                        source_id,
                    "model_version":
                        OWNERSHIP_TREND_MODEL_VERSION,
                },
            ).mappings()
        ]

    expected_latest_count = int(
        latest_input[
            "latest_trend_eligible_count"
        ]
    )

    print(
        "KSEI Ownership Trend Audit"
    )
    print(
        "--------------------------"
    )
    print(
        f"Model version   : "
        f"{OWNERSHIP_TREND_MODEL_VERSION}"
    )

    print()
    print(
        "Coverage:"
    )
    print(
        f"Rows            : "
        f"{actual['rows']}"
    )
    print(
        f"Expected rows   : "
        f"{expected['expected_rows']}"
    )
    print(
        f"Instruments     : "
        f"{actual['instruments']}"
    )
    print(
        f"Expected inst.  : "
        f"{expected['expected_instruments']}"
    )
    print(
        f"Snapshot dates  : "
        f"{actual['snapshot_dates']}"
    )
    print(
        f"Expected dates  : "
        f"{expected['expected_snapshot_dates']}"
    )
    print(
        f"First date      : "
        f"{actual['first_date']}"
    )
    print(
        f"Expected first  : "
        f"{expected['expected_first']}"
    )
    print(
        f"Last date       : "
        f"{actual['last_date']}"
    )
    print(
        f"Expected last   : "
        f"{expected['expected_last']}"
    )

    print()
    print(
        "Quality:"
    )

    for key, value in quality.items():
        print(
            f"{key:<28}: "
            f"{value}"
        )

    print(
        f"{'duplicate_groups':<28}: "
        f"{duplicates}"
    )

    print()
    print(
        "Latest:"
    )
    print(
        f"Input date      : "
        f"{latest_input['latest_input_date']}"
    )
    print(
        f"Trend date      : "
        f"{latest['as_of_date']}"
    )
    print(
        f"Expected rows   : "
        f"{expected_latest_count}"
    )
    print(
        f"Stored rows     : "
        f"{latest['stored']}"
    )

    coverage_pass = (
        int(
            actual["rows"]
        )
        == int(
            expected["expected_rows"]
        )
        and int(
            actual["instruments"]
        )
        == int(
            expected[
                "expected_instruments"
            ]
        )
        and int(
            actual["snapshot_dates"]
        )
        == int(
            expected[
                "expected_snapshot_dates"
            ]
        )
        and actual["first_date"]
        == expected["expected_first"]
        and actual["last_date"]
        == expected["expected_last"]
    )

    quality_pass = (
        all(
            int(value) == 0
            for value
            in quality.values()
        )
        and duplicates == 0
    )

    latest_pass = (
        latest["as_of_date"]
        == latest_input[
            "latest_input_date"
        ]
        and int(
            latest["stored"]
        )
        == expected_latest_count
    )

    print()
    print(
        "Latest accumulation ranking:"
    )

    for position, row in enumerate(
        ranking[:15],
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['symbol']:<6} "
            f"delta_pp="
            f"{float(row['delta_foreign_ownership_pp']):>9.4f} "
            f"foreign_pct="
            f"{float(row['foreign_ownership_pct']):>9.4f} "
            f"strength="
            f"{float(row['signal_strength']):>7.2f} "
            f"{row['trend_label']:<12} "
            f"CA_RISK="
            f"{row['corporate_action_risk']}"
        )

    print()
    print(
        "Latest distribution ranking:"
    )

    for position, row in enumerate(
        reversed(
            ranking[-15:]
        ),
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['symbol']:<6} "
            f"delta_pp="
            f"{float(row['delta_foreign_ownership_pp']):>9.4f} "
            f"foreign_pct="
            f"{float(row['foreign_ownership_pct']):>9.4f} "
            f"strength="
            f"{float(row['signal_strength']):>7.2f} "
            f"{row['trend_label']:<12} "
            f"CA_RISK="
            f"{row['corporate_action_risk']}"
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
        "Ownership trend is based on "
        "KSEI ownership snapshots, "
        "not daily foreign trading flow."
    )
    print(
        "Historical results remain "
        "current-universe biased."
    )


if __name__ == "__main__":
    main()