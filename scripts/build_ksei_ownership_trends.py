import argparse
from time import perf_counter

from sqlalchemy import text

from imi.db import engine
from imi.features.ownership_trend import (
    OWNERSHIP_TREND_MODEL_VERSION,
    prepare_ownership_trend_rows,
    resolve_ownership_trend_build_mode,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.ownership_trend import (
    get_expected_count_for_date,
    get_expected_coverage,
    get_latest_input_state,
    get_stored_latest_state,
    load_ownership_pairs,
    upsert_ownership_trends,
)

DEFAULT_BATCH_SIZE = 1000


LATEST_RANKING_SQL = text(
    """
    SELECT
        i.symbol,
        i.sector_code,

        t.foreign_ownership_pct,
        t.delta_foreign_ownership_pp,
        t.delta_foreign_shares,

        t.trend_label,
        t.signal_strength,

        t.corporate_action_risk,
        t.snapshot_gap_flag

    FROM ownership_trends t

    JOIN instruments i
      ON i.id =
         t.instrument_id

    WHERE t.source_id =
          :source_id
      AND t.model_version =
          :model_version
      AND t.as_of_date =
          :as_of_date

    ORDER BY
        t.delta_foreign_ownership_pp
        DESC
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build historical or "
            "incremental KSEI "
            "ownership trends."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force full historical "
            "rebuild."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def print_latest_ranking(
    *,
    source_id,
    latest_date,
) -> None:
    with engine.connect() as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                LATEST_RANKING_SQL,
                {
                    "source_id":
                        source_id,
                    "model_version":
                        OWNERSHIP_TREND_MODEL_VERSION,
                    "as_of_date":
                        latest_date,
                },
            ).mappings()
        ]

    if not rows:
        return

    print()
    print(
        "Top foreign ownership "
        "accumulation:"
    )

    for position, row in enumerate(
        rows[:15],
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
        "Top foreign ownership "
        "distribution:"
    )

    for position, row in enumerate(
        reversed(
            rows[-15:]
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


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.batch_size <= 0:
        raise ValueError(
            "batch-size must be "
            "greater than zero."
        )

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        latest_input = (
            get_latest_input_state(
                connection,
                source_id=source_id,
            )
        )

        stored = (
            get_stored_latest_state(
                connection,
                source_id=source_id,
                model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
            )
        )

    latest_input_date = (
        latest_input[
            "latest_input_date"
        ]
    )

    existing_last_date = (
        stored["latest_date"]
    )

    existing_latest_count = int(
        stored["latest_count"]
    )

    if existing_last_date is None:
        existing_expected_count = 0

    else:
        with engine.connect() as connection:
            existing_expected_count = (
                get_expected_count_for_date(
                    connection,
                    source_id=source_id,
                    as_of_date=(
                        existing_last_date
                    ),
                )
            )

    mode = (
        resolve_ownership_trend_build_mode(
            existing_last_date=(
                existing_last_date
            ),
            existing_latest_count=(
                existing_latest_count
            ),
            existing_expected_count=(
                existing_expected_count
            ),
            latest_input_date=(
                latest_input_date
            ),
            force=args.force,
        )
    )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "KSEI Ownership Trend Engine"
    )
    print(
        "---------------------------"
    )
    print(
        "Source          : "
        "KSEI_OFFICIAL"
    )
    print(
        f"Model version   : "
        f"{OWNERSHIP_TREND_MODEL_VERSION}"
    )
    print(
        f"Latest input    : "
        f"{latest_input_date}"
    )
    print(
        f"Ownership rows  : "
        f"{latest_input['latest_ownership_count']}"
    )
    print(
        f"Trend eligible  : "
        f"{latest_input['latest_trend_eligible_count']}"
    )
    print(
        f"Existing last   : "
        f"{existing_last_date}"
    )
    print(
        f"Stored latest   : "
        f"{existing_latest_count}"
    )
    print(
        f"Expected stored : "
        f"{existing_expected_count}"
    )
    print(
        f"Build mode      : "
        f"{mode}"
    )
    print()

    if mode == "UP_TO_DATE":
        elapsed = (
            perf_counter()
            - started
        )

        print(
            "Ownership trend dataset "
            "is already up-to-date."
        )
        print(
            "Rows written    : 0"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )

        print_latest_ranking(
            source_id=source_id,
            latest_date=(
                latest_input_date
            ),
        )

        return

    after_date = None

    if mode == "INCREMENTAL":
        if existing_last_date is None:
            raise RuntimeError(
                "Incremental mode requires "
                "existing trend data."
            )

        after_date = (
            existing_last_date
        )

    with engine.connect() as connection:
        expected = (
            get_expected_coverage(
                connection,
                source_id=source_id,
                after_date=after_date,
            )
        )

        inputs = (
            load_ownership_pairs(
                connection,
                source_id=source_id,
                after_date=after_date,
            )
        )

    rows = (
        prepare_ownership_trend_rows(
            inputs=inputs,
            source_id=source_id,
        )
    )

    expected_rows = int(
        expected["expected_rows"]
    )

    if len(rows) != expected_rows:
        raise RuntimeError(
            "Ownership trend generated "
            "row count does not match "
            "expected coverage: "
            f"generated={len(rows)}, "
            f"expected={expected_rows}."
        )

    if not rows:
        raise RuntimeError(
            "No ownership trend rows "
            "were generated."
        )

    generated_last_date = max(
        row["as_of_date"]
        for row in rows
    )

    if (
        generated_last_date
        != latest_input_date
    ):
        raise RuntimeError(
            "Ownership trend build did "
            "not reach latest input date: "
            f"generated="
            f"{generated_last_date}, "
            f"expected="
            f"{latest_input_date}."
        )

    with engine.begin() as connection:
        written = (
            upsert_ownership_trends(
                connection,
                rows=rows,
                batch_size=(
                    args.batch_size
                ),
            )
        )

    elapsed = (
        perf_counter()
        - started
    )

    print(
        f"Expected rows   : "
        f"{expected_rows}"
    )
    print(
        f"Generated rows  : "
        f"{len(rows)}"
    )
    print(
        f"Rows written    : "
        f"{written}"
    )
    print(
        f"Expected first  : "
        f"{expected['expected_first']}"
    )
    print(
        f"Expected last   : "
        f"{expected['expected_last']}"
    )
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    print_latest_ranking(
        source_id=source_id,
        latest_date=(
            latest_input_date
        ),
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "ACCUMULATING/DISTRIBUTING "
        "describes ownership change, "
        "not daily foreign buy/sell."
    )
    print(
        "Corporate-action risk is "
        "flagged when security count "
        "changes by at least 1%."
    )
    print(
        "Historical data remains "
        "current-universe biased."
    )


if __name__ == "__main__":
    main()