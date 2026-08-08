from collections import Counter

from imi.db import engine
from imi.features.market_history import (
    BOARD_UNKNOWN,
    market_rule_seed_rows,
    prepare_current_board_rows,
)
from imi.repositories.market_history import (
    get_board_coverage,
    get_corporate_action_coverage,
    get_universe_coverage,
    load_latest_current_universe,
    upsert_board_rows,
    upsert_coverage_state,
    upsert_market_rules,
)


def main() -> None:
    with engine.connect() as connection:
        universe = (
            load_latest_current_universe(
                connection
            )
        )

    if not universe:
        raise RuntimeError(
            "No current IDX universe "
            "snapshot found."
        )

    snapshot_dates = {
        row[
            "snapshot_date"
        ]
        for row in universe
    }

    if len(
        snapshot_dates
    ) != 1:
        raise RuntimeError(
            "Expected exactly one "
            "latest universe date."
        )

    snapshot_date = next(
        iter(
            snapshot_dates
        )
    )

    board_rows = (
        prepare_current_board_rows(
            universe
        )
    )

    market_rules = (
        market_rule_seed_rows()
    )

    with engine.begin() as connection:
        board_written = (
            upsert_board_rows(
                connection,
                rows=board_rows,
            )
        )

        rules_written = (
            upsert_market_rules(
                connection,
                rows=market_rules,
            )
        )

        board_coverage = (
            get_board_coverage(
                connection
            )
        )

        universe_coverage = (
            get_universe_coverage(
                connection
            )
        )

        corporate_coverage = (
            get_corporate_action_coverage(
                connection
            )
        )

        upsert_coverage_state(
            connection,
            dataset_code=(
                "IDX_BOARD_HISTORY"
            ),
            observed_rows=int(
                board_coverage[
                    "observed_rows"
                ]
                or 0
            ),
            distinct_instruments=int(
                board_coverage[
                    "distinct_instruments"
                ]
                or 0
            ),
            point_in_time_safe_rows=int(
                board_coverage[
                    "point_in_time_safe_rows"
                ]
                or 0
            ),
            first_observation_date=(
                board_coverage[
                    "first_date"
                ]
            ),
            last_observation_date=(
                board_coverage[
                    "last_date"
                ]
            ),
            complete_history=False,
            blocking_reason=(
                "ONLY_CURRENT_IDX_BOARD_"
                "SNAPSHOT_AVAILABLE"
            ),
            evidence={
                "snapshot_date":
                    snapshot_date
                    .isoformat(),

                "warning":
                    (
                        "Current board "
                        "classification cannot "
                        "be applied to signals "
                        "before its observation "
                        "date."
                    ),
            },
        )

        upsert_coverage_state(
            connection,
            dataset_code=(
                "IDX_HISTORICAL_UNIVERSE"
            ),
            observed_rows=int(
                universe_coverage[
                    "observed_rows"
                ]
                or 0
            ),
            distinct_instruments=int(
                universe_coverage[
                    "distinct_instruments"
                ]
                or 0
            ),
            point_in_time_safe_rows=int(
                universe_coverage[
                    "point_in_time_safe_rows"
                ]
                or 0
            ),
            first_observation_date=(
                universe_coverage[
                    "first_date"
                ]
            ),
            last_observation_date=(
                universe_coverage[
                    "last_date"
                ]
            ),
            complete_history=False,
            blocking_reason=(
                "HISTORICAL_LISTED_AND_"
                "DELISTED_UNIVERSE_NOT_"
                "RECONSTRUCTED"
            ),
            evidence={
                "warning":
                    (
                        "Current universe "
                        "remains insufficient "
                        "for strict historical "
                        "survivorship control."
                    ),
            },
        )

        upsert_coverage_state(
            connection,
            dataset_code=(
                "IDX_CORPORATE_ACTIONS"
            ),
            observed_rows=int(
                corporate_coverage[
                    "observed_rows"
                ]
                or 0
            ),
            distinct_instruments=int(
                corporate_coverage[
                    "distinct_instruments"
                ]
                or 0
            ),
            point_in_time_safe_rows=0,
            first_observation_date=(
                corporate_coverage[
                    "first_date"
                ]
            ),
            last_observation_date=(
                corporate_coverage[
                    "last_date"
                ]
            ),
            complete_history=False,
            blocking_reason=(
                "CORPORATE_ACTION_MASTER_"
                "COMPLETENESS_NOT_"
                "ESTABLISHED"
            ),
            evidence={
                "warning":
                    (
                        "Existing corporate "
                        "action rows, if any, "
                        "are not treated as a "
                        "complete historical "
                        "master."
                    ),
            },
        )

    board_counts = Counter(
        row[
            "board_code"
        ]
        for row in board_rows
    )

    unknown_raw = sorted(
        {
            str(
                row[
                    "raw_board_name"
                ]
            )
            for row in board_rows
            if row[
                "board_code"
            ]
            == BOARD_UNKNOWN
        }
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Historical Market Foundation V1"
    )

    print(
        "-------------------------------"
    )

    print(
        f"Universe snapshot     : "
        f"{snapshot_date}"
    )

    print(
        f"Universe instruments  : "
        f"{len(universe)}"
    )

    print(
        f"Board rows written    : "
        f"{board_written}"
    )

    print(
        f"Market rules written  : "
        f"{rules_written}"
    )

    print()

    print(
        "Current board distribution:"
    )

    for (
        board,
        count,
    ) in sorted(
        board_counts.items()
    ):
        print(
            f"{board:<15} : "
            f"{count}"
        )

    if unknown_raw:
        print()

        print(
            "Unknown raw board values:"
        )

        for value in (
            unknown_raw[:20]
        ):
            print(
                f"- {value}"
            )

    print()

    print(
        "Historical coverage:"
    )

    print(
        "Board history       : "
        "NOT COMPLETE"
    )

    print(
        "Historical universe : "
        "NOT COMPLETE"
    )

    print(
        "Corporate actions   : "
        "NOT COMPLETE"
    )

    print()

    print(
        "STRICT HISTORICAL READINESS:"
    )

    print(
        "READY : NO"
    )

    print(
        "- Current board snapshot "
        "cannot be backdated."
    )

    print(
        "- Delisted/historical universe "
        "is not reconstructed."
    )

    print(
        "- Corporate-action master "
        "completeness is not established."
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "The current board snapshot "
        "starts on its actual observation "
        "date only."
    )

    print(
        "No historical board membership "
        "has been fabricated."
    )


if __name__ == "__main__":
    main()