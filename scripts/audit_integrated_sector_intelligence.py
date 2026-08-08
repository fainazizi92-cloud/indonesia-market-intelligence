import math

from imi.db import engine
from imi.features.integrated_sector import (
    build_integrated_sector_model_version,
    extract_current_universe_date,
    prepare_integrated_sector_rows,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.integrated_sector import (
    get_duplicate_groups,
    get_expected_coverage,
    get_latest_input_state,
    get_latest_ownership_model_state,
    get_latest_technical_model_state,
    get_stored_coverage,
    load_all_stored,
    load_integrated_inputs,
    load_latest_ranking,
)

FLOAT_FIELDS = (
    "technical_score",
    "ownership_score",
    "technical_weight",
    "ownership_weight",
    "integrated_score",
)

INTEGER_FIELDS = (
    "ownership_age_days",
)

EXACT_FIELDS = (
    "technical_rotation_label",
    "ownership_as_of_date",
    "ownership_signal_label",
    "ownership_low_coverage_flag",
    "ownership_stale_flag",
    "integrated_label",
    "alignment_label",
    "technical_model_version",
    "ownership_model_version",
    "model_version",
)


def float_matches(
    left,
    right,
) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-9,
        abs_tol=1e-4,
    )


def main() -> None:
    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        technical_state = (
            get_latest_technical_model_state(
                connection
            )
        )

        ownership_state = (
            get_latest_ownership_model_state(
                connection,
                source_id=source_id,
            )
        )

    technical_model_version = str(
        technical_state[
            "model_version"
        ]
    )

    ownership_model_version = str(
        ownership_state[
            "model_version"
        ]
    )

    technical_universe_date = (
        extract_current_universe_date(
            technical_model_version
        )
    )

    ownership_universe_date = (
        extract_current_universe_date(
            ownership_model_version
        )
    )

    if (
        technical_universe_date
        != ownership_universe_date
    ):
        raise RuntimeError(
            "Input model universes "
            "do not match."
        )

    model_version = (
        build_integrated_sector_model_version(
            technical_universe_date
        )
    )

    with engine.connect() as connection:
        expected = (
            get_expected_coverage(
                connection,
                source_id=source_id,
                technical_model_version=(
                    technical_model_version
                ),
                ownership_model_version=(
                    ownership_model_version
                ),
            )
        )

        latest_input = (
            get_latest_input_state(
                connection,
                source_id=source_id,
                technical_model_version=(
                    technical_model_version
                ),
                ownership_model_version=(
                    ownership_model_version
                ),
            )
        )

        inputs = (
            load_integrated_inputs(
                connection,
                source_id=source_id,
                technical_model_version=(
                    technical_model_version
                ),
                ownership_model_version=(
                    ownership_model_version
                ),
            )
        )

        stored = (
            load_all_stored(
                connection,
                model_version=model_version,
            )
        )

        actual = (
            get_stored_coverage(
                connection,
                model_version=model_version,
            )
        )

        duplicates = (
            get_duplicate_groups(
                connection,
                model_version=model_version,
            )
        )

        ranking = (
            load_latest_ranking(
                connection,
                model_version=model_version,
                trading_date=(
                    latest_input[
                        "latest_input_date"
                    ]
                ),
            )
        )

    generated = (
        prepare_integrated_sector_rows(
            inputs=inputs,
            technical_model_version=(
                technical_model_version
            ),
            ownership_model_version=(
                ownership_model_version
            ),
            model_version=model_version,
        )
    )

    generated_by_key = {
        (
            row["trading_date"],
            row["sector_code"],
        ): row
        for row in generated
    }

    stored_by_key = {
        (
            row["trading_date"],
            row["sector_code"],
        ): row
        for row in stored
    }

    generated_keys = set(
        generated_by_key
    )

    stored_keys = set(
        stored_by_key
    )

    mismatches: list[str] = []

    if generated_keys != stored_keys:
        missing = (
            generated_keys
            - stored_keys
        )

        unexpected = (
            stored_keys
            - generated_keys
        )

        if missing:
            mismatches.append(
                "Missing stored keys: "
                f"{sorted(missing)[:20]}"
            )

        if unexpected:
            mismatches.append(
                "Unexpected stored keys: "
                f"{sorted(unexpected)[:20]}"
            )

    for key in sorted(
        generated_keys
        & stored_keys
    ):
        generated_row = (
            generated_by_key[key]
        )

        stored_row = (
            stored_by_key[key]
        )

        for field in FLOAT_FIELDS:
            if not float_matches(
                generated_row[field],
                stored_row[field],
            ):
                mismatches.append(
                    f"{key} {field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

        for field in INTEGER_FIELDS:
            if int(
                generated_row[field]
            ) != int(
                stored_row[field]
            ):
                mismatches.append(
                    f"{key} {field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

        for field in EXACT_FIELDS:
            if (
                generated_row[field]
                != stored_row[field]
            ):
                mismatches.append(
                    f"{key} {field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

    coverage_pass = (
        int(
            actual["rows"]
        )
        == int(
            expected["expected_rows"]
        )
        and int(
            actual["sectors"]
        )
        == int(
            expected["expected_sectors"]
        )
        and int(
            actual["dates"]
        )
        == int(
            expected["expected_dates"]
        )
        and actual["first_date"]
        == expected["expected_first"]
        and actual["last_date"]
        == expected["expected_last"]
    )

    quality_pass = (
        not mismatches
        and duplicates == 0
    )

    latest_pass = (
        bool(ranking)
        and ranking[0][
            "trading_date"
        ]
        == latest_input[
            "latest_input_date"
        ]
        and len(ranking)
        == int(
            latest_input[
                "latest_sector_count"
            ]
        )
    )

    print(
        "Integrated Sector Intelligence Audit"
    )
    print(
        "------------------------------------"
    )
    print(
        f"Technical model : "
        f"{technical_model_version}"
    )
    print(
        f"Ownership model : "
        f"{ownership_model_version}"
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
        f"{actual['rows']}"
    )
    print(
        f"Expected rows   : "
        f"{expected['expected_rows']}"
    )
    print(
        f"Sectors         : "
        f"{actual['sectors']}"
    )
    print(
        f"Expected sectors: "
        f"{expected['expected_sectors']}"
    )
    print(
        f"Dates           : "
        f"{actual['dates']}"
    )
    print(
        f"Expected dates  : "
        f"{expected['expected_dates']}"
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
    print(
        f"Mismatches      : "
        f"{len(mismatches)}"
    )
    print(
        f"Duplicate groups: "
        f"{duplicates}"
    )

    if mismatches:
        print()
        print(
            "Mismatch sample:"
        )

        for item in mismatches[:30]:
            print(
                item
            )

    print()
    print(
        "Latest ranking:"
    )

    for position, row in enumerate(
        ranking,
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['sector_code']:<12} "
            f"integrated="
            f"{float(row['integrated_score']):>7.2f} "
            f"technical="
            f"{float(row['technical_score']):>7.2f} "
            f"ownership="
            f"{float(row['ownership_score']):>7.2f} "
            f"age="
            f"{row['ownership_age_days']:>2}d "
            f"{row['integrated_label']:<14} "
            f"{row['alignment_label']}"
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
        "KSEI ownership is not daily "
        "foreign buy/sell flow."
    )
    print(
        "Historical joins use KSEI "
        "as_of_date. Strict trading "
        "backtests require publication/"
        "availability timestamps before "
        "these historical rows are used "
        "without look-ahead risk."
    )


if __name__ == "__main__":
    main()