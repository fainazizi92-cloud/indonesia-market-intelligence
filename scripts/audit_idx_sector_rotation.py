from sqlalchemy import text

from imi.db import engine
from imi.features.sector_rotation import (
    EXPECTED_SECTOR_CODES,
    build_sector_model_version,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.sector_rotation import (
    get_expected_sector_coverage,
    get_latest_snapshot_date,
)

SUMMARY = text(
    """
    SELECT
        COUNT(*) AS rows,
        COUNT(
            DISTINCT sector_code
        ) AS sectors,
        MIN(trading_date)
            AS first_date,
        MAX(trading_date)
            AS last_date
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
    """
)


NULL_CORE = text(
    """
    SELECT COUNT(*)
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND (
          rotation_label IS NULL
          OR score IS NULL
          OR relative_strength_score
             IS NULL
          OR breadth_score IS NULL
          OR volume_score IS NULL
      )
    """
)


INVALID_SCORES = text(
    """
    SELECT COUNT(*)
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND (
          score < 0
          OR score > 100
          OR relative_strength_score < 0
          OR relative_strength_score > 100
          OR breadth_score < 0
          OR breadth_score > 100
          OR volume_score < 0
          OR volume_score > 100
      )
    """
)


INVALID_LABELS = text(
    """
    SELECT COUNT(*)
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND rotation_label NOT IN (
          'LEADING',
          'IMPROVING',
          'NEUTRAL',
          'WEAKENING',
          'LAGGING'
      )
    """
)


FLOW_NON_NULL = text(
    """
    SELECT COUNT(*)
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND flow_score IS NOT NULL
    """
)


CATALYST_NON_NULL = text(
    """
    SELECT COUNT(*)
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND catalyst_score IS NOT NULL
    """
)


DUPLICATE_GROUPS = text(
    """
    SELECT COUNT(*)
    FROM (
        SELECT
            trading_date,
            sector_code,
            model_version,
            COUNT(*) AS row_count
        FROM sector_scores_daily
        WHERE model_version =
              :model_version
        GROUP BY
            trading_date,
            sector_code,
            model_version
        HAVING COUNT(*) != 1
    ) AS duplicate_groups
    """
)


LATEST_ROWS = text(
    """
    SELECT
        trading_date,
        sector_code,
        rotation_label,
        score,
        relative_strength_score,
        breadth_score,
        flow_score,
        volume_score,
        catalyst_score
    FROM sector_scores_daily
    WHERE model_version =
          :model_version
      AND trading_date = (
          SELECT MAX(trading_date)
          FROM sector_scores_daily
          WHERE model_version =
                :model_version
      )
    ORDER BY score DESC
    """
)


def main() -> None:
    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        snapshot_date = (
            get_latest_snapshot_date(
                connection
            )
        )

        expected = (
            get_expected_sector_coverage(
                connection,
                snapshot_date=(
                    snapshot_date
                ),
                source_id=(
                    source_id
                ),
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

    model_version = (
        build_sector_model_version(
            snapshot_date
        )
    )

    parameters = {
        "model_version":
            model_version
    }

    with engine.connect() as connection:
        summary = (
            connection.execute(
                SUMMARY,
                parameters,
            ).mappings().one()
        )

        null_core = (
            connection.execute(
                NULL_CORE,
                parameters,
            ).scalar_one()
        )

        invalid_scores = (
            connection.execute(
                INVALID_SCORES,
                parameters,
            ).scalar_one()
        )

        invalid_labels = (
            connection.execute(
                INVALID_LABELS,
                parameters,
            ).scalar_one()
        )

        flow_non_null = (
            connection.execute(
                FLOW_NON_NULL,
                parameters,
            ).scalar_one()
        )

        catalyst_non_null = (
            connection.execute(
                CATALYST_NON_NULL,
                parameters,
            ).scalar_one()
        )

        duplicate_groups = (
            connection.execute(
                DUPLICATE_GROUPS,
                parameters,
            ).scalar_one()
        )

        latest_rows = list(
            connection.execute(
                LATEST_ROWS,
                parameters,
            ).mappings()
        )

    latest_sector_codes = {
        row["sector_code"]
        for row in latest_rows
    }

    expected_sector_codes = set(
        EXPECTED_SECTOR_CODES
    )

    missing_latest = (
        expected_sector_codes
        - latest_sector_codes
    )

    unexpected_latest = (
        latest_sector_codes
        - expected_sector_codes
    )

    coverage_pass = (
        int(summary["rows"])
        == int(
            expected["expected_rows"]
        )
        and int(summary["sectors"])
        == int(
            expected[
                "expected_sectors"
            ]
        )
        and summary["first_date"]
        == expected[
            "expected_first"
        ]
        and summary["last_date"]
        == expected[
            "expected_last"
        ]
    )

    quality_pass = all(
        value == 0
        for value in (
            null_core,
            invalid_scores,
            invalid_labels,
            flow_non_null,
            catalyst_non_null,
            duplicate_groups,
        )
    )

    latest_pass = (
        not missing_latest
        and not unexpected_latest
        and len(latest_rows) == len(
            EXPECTED_SECTOR_CODES
        )
    )

    print(
        "IDX Sector Rotation Audit"
    )
    print(
        "-------------------------"
    )

    print()
    print(
        f"Snapshot date   : "
        f"{snapshot_date}"
    )
    print(
        f"Model version   : "
        f"{model_version}"
    )

    print()
    print(
        "Coverage:"
    )
    print(
        f"Rows            : "
        f"{summary['rows']}"
    )
    print(
        f"Expected rows   : "
        f"{expected['expected_rows']}"
    )
    print(
        f"Sectors         : "
        f"{summary['sectors']}"
    )
    print(
        f"Expected sectors: "
        f"{expected['expected_sectors']}"
    )
    print(
        f"First date      : "
        f"{summary['first_date']}"
    )
    print(
        f"Expected first  : "
        f"{expected['expected_first']}"
    )
    print(
        f"Last date       : "
        f"{summary['last_date']}"
    )
    print(
        f"Expected last   : "
        f"{expected['expected_last']}"
    )

    print()
    print(
        "Quality:"
    )
    print(
        f"Null core scores    : "
        f"{null_core}"
    )
    print(
        f"Invalid scores      : "
        f"{invalid_scores}"
    )
    print(
        f"Invalid labels      : "
        f"{invalid_labels}"
    )
    print(
        f"Flow non-null       : "
        f"{flow_non_null}"
    )
    print(
        f"Catalyst non-null   : "
        f"{catalyst_non_null}"
    )
    print(
        f"Duplicate groups    : "
        f"{duplicate_groups}"
    )

    print()
    print(
        "Latest sector universe:"
    )
    print(
        f"Latest sectors      : "
        f"{len(latest_rows)}"
    )
    print(
        f"Missing sectors     : "
        f"{sorted(missing_latest)}"
    )
    print(
        f"Unexpected sectors  : "
        f"{sorted(unexpected_latest)}"
    )

    print()
    print(
        "Latest ranking:"
    )

    for position, row in enumerate(
        latest_rows,
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['sector_code']:<12} "
            f"score="
            f"{float(row['score']):>7.4f} "
            f"RS="
            f"{float(row['relative_strength_score']):>7.4f} "
            f"breadth="
            f"{float(row['breadth_score']):>7.4f} "
            f"volume="
            f"{float(row['volume_score']):>7.4f} "
            f"{row['rotation_label']}"
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

    print()
    print(
        "WARNING:"
    )
    print(
        "Sector Rotation V1 uses "
        "current-universe historical "
        "backfill and Yahoo EOD inputs."
    )
    print(
        "Do not treat historical results "
        "as survivorship-bias-free."
    )


if __name__ == "__main__":
    main()