from sqlalchemy import text

from imi.db import engine
from imi.features.market_breadth import (
    build_universe_code,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.market_breadth import (
    get_latest_snapshot_date,
)

SUMMARY = text(
    """
    SELECT
        COUNT(*) AS rows,
        MIN(trading_date)
            AS first_date,
        MAX(trading_date)
            AS last_date
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
    """
)


EXPECTED_DATES = text(
    """
    WITH current_universe AS (
        SELECT instrument_id
        FROM instrument_universe_snapshots
        WHERE universe_code =
              'IDX_ALL_CURRENT'
          AND snapshot_date =
              :snapshot_date
          AND is_member = TRUE
    )
    SELECT
        COUNT(
            DISTINCT tf.trading_date
        ) AS expected_rows,
        MIN(tf.trading_date)
            AS expected_first,
        MAX(tf.trading_date)
            AS expected_last
    FROM technical_features_daily tf
    JOIN current_universe u
      ON u.instrument_id =
         tf.instrument_id
    WHERE tf.feature_version =
          :feature_version
      AND tf.ema200 IS NOT NULL
    """
)


NULL_METRICS = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
      AND (
          advances IS NULL
          OR declines IS NULL
          OR unchanged IS NULL
          OR new_high_20d IS NULL
          OR new_low_20d IS NULL
          OR new_high_52w IS NULL
          OR new_low_52w IS NULL
          OR pct_above_ema20
             IS NULL
          OR pct_above_ema50
             IS NULL
          OR pct_above_ema200
             IS NULL
          OR up_volume IS NULL
          OR down_volume IS NULL
          OR breadth_score IS NULL
          OR source_id IS NULL
      )
    """
)


NEGATIVE_COUNTS = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
      AND (
          advances < 0
          OR declines < 0
          OR unchanged < 0
          OR new_high_20d < 0
          OR new_low_20d < 0
          OR new_high_52w < 0
          OR new_low_52w < 0
      )
    """
)


INVALID_PERCENTAGES = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
      AND (
          pct_above_ema20 < 0
          OR pct_above_ema20 > 100
          OR pct_above_ema50 < 0
          OR pct_above_ema50 > 100
          OR pct_above_ema200 < 0
          OR pct_above_ema200 > 100
      )
    """
)


INVALID_SCORE = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
      AND (
          breadth_score < 0
          OR breadth_score > 100
      )
    """
)


INVALID_VOLUME = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
      AND (
          up_volume < 0
          OR down_volume < 0
      )
    """
)


INVALID_POPULATION = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
      AND (
          advances
          + declines
          + unchanged
      ) <= 0
    """
)


SOURCE_MISMATCH = text(
    """
    SELECT COUNT(*)
    FROM market_breadth_daily b
    LEFT JOIN data_sources d
      ON d.id = b.source_id
    WHERE b.universe_code =
          :universe_code
      AND (
          d.code IS NULL
          OR d.code
             <> 'YAHOO_FINANCE'
      )
    """
)


LATEST_ROW = text(
    """
    SELECT
        trading_date,
        advances,
        declines,
        unchanged,
        new_high_20d,
        new_low_20d,
        new_high_52w,
        new_low_52w,
        pct_above_ema20,
        pct_above_ema50,
        pct_above_ema200,
        up_volume,
        down_volume,
        breadth_score
    FROM market_breadth_daily
    WHERE universe_code =
          :universe_code
    ORDER BY trading_date DESC
    LIMIT 1
    """
)


def main() -> None:
    with engine.connect() as connection:
        snapshot_date = (
            get_latest_snapshot_date(
                connection
            )
        )

    universe_code = (
        build_universe_code(
            snapshot_date
        )
    )

    parameters = {
        "universe_code":
            universe_code,
        "snapshot_date":
            snapshot_date,
        "feature_version":
            FEATURE_VERSION,
    }

    with engine.connect() as connection:
        summary = (
            connection.execute(
                SUMMARY,
                parameters,
            ).mappings().one()
        )

        expected = (
            connection.execute(
                EXPECTED_DATES,
                parameters,
            ).mappings().one()
        )

        null_metrics = (
            connection.execute(
                NULL_METRICS,
                parameters,
            ).scalar_one()
        )

        negative_counts = (
            connection.execute(
                NEGATIVE_COUNTS,
                parameters,
            ).scalar_one()
        )

        invalid_percentages = (
            connection.execute(
                INVALID_PERCENTAGES,
                parameters,
            ).scalar_one()
        )

        invalid_score = (
            connection.execute(
                INVALID_SCORE,
                parameters,
            ).scalar_one()
        )

        invalid_volume = (
            connection.execute(
                INVALID_VOLUME,
                parameters,
            ).scalar_one()
        )

        invalid_population = (
            connection.execute(
                INVALID_POPULATION,
                parameters,
            ).scalar_one()
        )

        source_mismatch = (
            connection.execute(
                SOURCE_MISMATCH,
                parameters,
            ).scalar_one()
        )

        latest = (
            connection.execute(
                LATEST_ROW,
                parameters,
            ).mappings().first()
        )

    print(
        "IDX Market Breadth Audit"
    )
    print(
        "------------------------"
    )

    print()
    print(
        f"Snapshot date   : "
        f"{snapshot_date}"
    )
    print(
        f"Universe code   : "
        f"{universe_code}"
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
        f"Null metrics        : "
        f"{null_metrics}"
    )
    print(
        f"Negative counts     : "
        f"{negative_counts}"
    )
    print(
        f"Invalid percentages : "
        f"{invalid_percentages}"
    )
    print(
        f"Invalid score       : "
        f"{invalid_score}"
    )
    print(
        f"Invalid volume      : "
        f"{invalid_volume}"
    )
    print(
        f"Invalid population  : "
        f"{invalid_population}"
    )
    print(
        f"Source mismatch     : "
        f"{source_mismatch}"
    )

    if latest is not None:
        total = (
            latest["advances"]
            + latest["declines"]
            + latest["unchanged"]
        )

        print()
        print(
            "Latest breadth:"
        )
        print(
            f"Date             : "
            f"{latest['trading_date']}"
        )
        print(
            f"Eligible stocks  : "
            f"{total}"
        )
        print(
            f"Advances         : "
            f"{latest['advances']}"
        )
        print(
            f"Declines         : "
            f"{latest['declines']}"
        )
        print(
            f"Unchanged        : "
            f"{latest['unchanged']}"
        )
        print(
            f"% > EMA20        : "
            f"{latest['pct_above_ema20']}"
        )
        print(
            f"% > EMA50        : "
            f"{latest['pct_above_ema50']}"
        )
        print(
            f"% > EMA200       : "
            f"{latest['pct_above_ema200']}"
        )
        print(
            f"New High 20D     : "
            f"{latest['new_high_20d']}"
        )
        print(
            f"New Low 20D      : "
            f"{latest['new_low_20d']}"
        )
        print(
            f"New High 52W     : "
            f"{latest['new_high_52w']}"
        )
        print(
            f"New Low 52W      : "
            f"{latest['new_low_52w']}"
        )
        print(
            f"Breadth score    : "
            f"{latest['breadth_score']}"
        )

    coverage_pass = (
        summary["rows"]
        == expected["expected_rows"]
        and summary["first_date"]
        == expected["expected_first"]
        and summary["last_date"]
        == expected["expected_last"]
    )

    quality_pass = all(
        value == 0
        for value in (
            null_metrics,
            negative_counts,
            invalid_percentages,
            invalid_score,
            invalid_volume,
            invalid_population,
            source_mismatch,
        )
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

    print()
    print(
        "WARNING:"
    )
    print(
        "This is a current-universe "
        "historical backfill."
    )
    print(
        "Do not use it as a "
        "survivorship-bias-free "
        "historical universe."
    )


if __name__ == "__main__":
    main()