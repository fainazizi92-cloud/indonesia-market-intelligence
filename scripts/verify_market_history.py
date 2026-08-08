from imi.db import engine
from imi.features.market_history import (
    market_rule_seed_rows,
    prepare_current_board_rows,
)
from imi.repositories.market_history import (
    load_board_history,
    load_latest_current_universe,
    load_market_rules,
)


def main() -> None:
    with engine.connect() as connection:
        universe = (
            load_latest_current_universe(
                connection
            )
        )

        stored_board = (
            load_board_history(
                connection
            )
        )

        stored_rules = (
            load_market_rules(
                connection
            )
        )

    expected_board = (
        prepare_current_board_rows(
            universe
        )
    )

    expected_rules = (
        market_rule_seed_rows()
    )

    snapshot_date = max(
        row[
            "snapshot_date"
        ]
        for row in universe
    )

    actual_board = [
        row
        for row in stored_board
        if (
            row[
                "effective_from"
            ]
            == snapshot_date
            and row[
                "source_code"
            ]
            == (
                "IDX_OFFICIAL_"
                "CURRENT_PROFILE"
            )
        )
    ]

    expected_ids = {
        row[
            "instrument_id"
        ]
        for row in expected_board
    }

    actual_ids = {
        row[
            "instrument_id"
        ]
        for row in actual_board
    }

    expected_rule_keys = {
        row[
            "rule_key"
        ]
        for row in expected_rules
    }

    actual_rule_keys = {
        row[
            "rule_key"
        ]
        for row in stored_rules
    }

    missing_board = (
        expected_ids
        - actual_ids
    )

    extra_board = (
        actual_ids
        - expected_ids
    )

    missing_rules = (
        expected_rule_keys
        - actual_rule_keys
    )

    passed = (
        not missing_board
        and not extra_board
        and not missing_rules
    )

    print(
        "Historical Market Verification"
    )

    print(
        "------------------------------"
    )

    print(
        f"Snapshot date          : "
        f"{snapshot_date}"
    )

    print(
        f"Expected board rows    : "
        f"{len(expected_ids)}"
    )

    print(
        f"Stored board rows      : "
        f"{len(actual_ids)}"
    )

    print(
        f"Missing board rows     : "
        f"{len(missing_board)}"
    )

    print(
        f"Extra board rows       : "
        f"{len(extra_board)}"
    )

    print(
        f"Expected market rules  : "
        f"{len(expected_rule_keys)}"
    )

    print(
        f"Missing market rules   : "
        f"{len(missing_rules)}"
    )

    print(
        "Result                : "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    if not passed:
        raise RuntimeError(
            "Historical market "
            "verification failed."
        )


if __name__ == "__main__":
    main()