from imi.db import engine
from imi.features.market_history import (
    BOARD_UNKNOWN,
    market_rule_seed_rows,
    prepare_current_board_rows,
)
from imi.repositories.market_history import (
    load_board_history,
    load_coverage_states,
    load_latest_current_universe,
    load_market_rules,
)


def comparable_rule(
    row,
):
    fields = (
        "rule_key",
        "rule_type",
        "market",
        "board_group",
        "effective_from",
        "effective_to",
        "price_min",
        "price_min_inclusive",
        "price_max",
        "price_max_inclusive",
        "lot_size",
        "tick_size",
        "ara_pct",
        "arb_pct",
        "ara_absolute",
        "arb_absolute",
        "source_reference",
        "verification_status",
    )

    return {
        field:
            (
                None
                if row[field]
                is None
                else (
                    float(row[field])
                    if field in {
                        "price_min",
                        "price_max",
                        "tick_size",
                        "ara_pct",
                        "arb_pct",
                        "ara_absolute",
                        "arb_absolute",
                    }
                    else row[field]
                )
            )
        for field in fields
    }


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

        coverage = (
            load_coverage_states(
                connection
            )
        )

    if not universe:
        raise RuntimeError(
            "Current universe missing."
        )

    snapshot_date = max(
        row[
            "snapshot_date"
        ]
        for row in universe
    )

    expected_board = (
        prepare_current_board_rows(
            universe
        )
    )

    current_stored_board = [
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

    expected_board_map = {
        row[
            "instrument_id"
        ]:
            row
        for row in expected_board
    }

    stored_board_map = {
        row[
            "instrument_id"
        ]:
            row
        for row in current_stored_board
    }

    board_mismatches = 0

    for (
        instrument_id,
        expected,
    ) in expected_board_map.items():
        actual = stored_board_map.get(
            instrument_id
        )

        if actual is None:
            board_mismatches += 1
            continue

        fields = (
            "effective_from",
            "effective_to",
            "board_code",
            "raw_board_name",
            "source_code",
            "available_at",
            "availability_status",
            "point_in_time_safe",
            "evidence",
        )

        if any(
            expected[field]
            != actual[field]
            for field in fields
        ):
            board_mismatches += 1

    unknown_safe = sum(
        row[
            "board_code"
        ]
        == BOARD_UNKNOWN
        and bool(
            row[
                "point_in_time_safe"
            ]
        )
        for row in current_stored_board
    )

    expected_rules = {
        row[
            "rule_key"
        ]:
            comparable_rule(
                row
            )
        for row in (
            market_rule_seed_rows()
        )
    }

    stored_rules_map = {
        row[
            "rule_key"
        ]:
            comparable_rule(
                row
            )
        for row in stored_rules
    }

    rule_mismatches = 0

    for (
        key,
        expected,
    ) in expected_rules.items():
        if (
            stored_rules_map.get(
                key
            )
            != expected
        ):
            rule_mismatches += 1

    coverage_map = {
        row[
            "dataset_code"
        ]:
            row
        for row in coverage
    }

    required_coverage = {
        "IDX_BOARD_HISTORY",
        "IDX_HISTORICAL_UNIVERSE",
        "IDX_CORPORATE_ACTIONS",
    }

    coverage_missing = len(
        required_coverage
        - set(
            coverage_map
        )
    )

    incorrectly_complete = sum(
        bool(
            coverage_map[
                code
            ][
                "complete_history"
            ]
        )
        for code in required_coverage
        if code in coverage_map
    )

    coverage_pass = (
        len(
            expected_board
        )
        == len(
            current_stored_board
        )
        and len(
            expected_rules
        )
        <= len(
            stored_rules
        )
        and coverage_missing == 0
    )

    quality_pass = (
        board_mismatches == 0
        and unknown_safe == 0
        and rule_mismatches == 0
        and incorrectly_complete == 0
    )

    print(
        "Historical Market Foundation Audit"
    )

    print(
        "----------------------------------"
    )

    print(
        f"Universe snapshot      : "
        f"{snapshot_date}"
    )

    print(
        f"Expected board rows    : "
        f"{len(expected_board)}"
    )

    print(
        f"Stored board rows      : "
        f"{len(current_stored_board)}"
    )

    print(
        f"Board mismatches       : "
        f"{board_mismatches}"
    )

    print(
        f"Unsafe UNKNOWN boards  : "
        f"{unknown_safe}"
    )

    print()

    print(
        f"Expected seeded rules  : "
        f"{len(expected_rules)}"
    )

    print(
        f"Stored rules           : "
        f"{len(stored_rules)}"
    )

    print(
        f"Rule mismatches        : "
        f"{rule_mismatches}"
    )

    print()

    print(
        f"Coverage states missing: "
        f"{coverage_missing}"
    )

    print(
        f"Incorrectly complete   : "
        f"{incorrectly_complete}"
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
        "Strict historical readiness:"
    )

    print(
        "READY : NO"
    )

    if not (
        coverage_pass
        and quality_pass
    ):
        raise RuntimeError(
            "Historical market "
            "foundation audit failed."
        )


if __name__ == "__main__":
    main()