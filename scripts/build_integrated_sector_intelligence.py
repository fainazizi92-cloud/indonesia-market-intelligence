import argparse
from time import perf_counter

from imi.db import engine
from imi.features.integrated_sector import (
    build_integrated_sector_model_version,
    extract_current_universe_date,
    prepare_integrated_sector_rows,
    resolve_integrated_sector_build_mode,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.integrated_sector import (
    delete_integrated_model,
    get_expected_coverage,
    get_input_state_for_date,
    get_latest_input_state,
    get_latest_ownership_model_state,
    get_latest_technical_model_state,
    get_stored_latest_state,
    load_integrated_inputs,
    load_latest_ranking,
    upsert_integrated_rows,
)

DEFAULT_BATCH_SIZE = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build integrated sector "
            "intelligence from technical "
            "rotation and KSEI ownership."
        )
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Force a full rebuild."
        ),
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
    )

    return parser.parse_args()


def print_ranking(
    *,
    model_version: str,
    trading_date,
) -> None:
    with engine.connect() as connection:
        rows = load_latest_ranking(
            connection,
            model_version=model_version,
            trading_date=trading_date,
        )

    if not rows:
        return

    print()
    print(
        "Latest integrated sector ranking:"
    )

    for position, row in enumerate(
        rows,
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
            f"own_date="
            f"{row['ownership_as_of_date']} "
            f"age="
            f"{row['ownership_age_days']:>2}d "
            f"{row['integrated_label']:<14} "
            f"{row['alignment_label']}"
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
            "Technical and ownership "
            "models use different current "
            "universes: "
            f"technical="
            f"{technical_universe_date}, "
            f"ownership="
            f"{ownership_universe_date}."
        )

    model_version = (
        build_integrated_sector_model_version(
            technical_universe_date
        )
    )

    with engine.connect() as connection:
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

        stored = (
            get_stored_latest_state(
                connection,
                model_version=model_version,
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

    existing_latest_sector_count = int(
        stored[
            "latest_sector_count"
        ]
        or 0
    )

    existing_ownership_signature = (
        stored[
            "ownership_signature"
        ]
    )

    if existing_last_date is None:
        existing_expected_sector_count = 0
        expected_existing_signature = None

    else:
        with engine.connect() as connection:
            expected_existing = (
                get_input_state_for_date(
                    connection,
                    source_id=source_id,
                    technical_model_version=(
                        technical_model_version
                    ),
                    ownership_model_version=(
                        ownership_model_version
                    ),
                    as_of_date=(
                        existing_last_date
                    ),
                )
            )

        existing_expected_sector_count = int(
            expected_existing[
                "sector_count"
            ]
            or 0
        )

        expected_existing_signature = (
            expected_existing[
                "ownership_signature"
            ]
        )

    mode = (
        resolve_integrated_sector_build_mode(
            existing_last_date=(
                existing_last_date
            ),
            existing_latest_sector_count=(
                existing_latest_sector_count
            ),
            existing_expected_sector_count=(
                existing_expected_sector_count
            ),
            existing_ownership_signature=(
                existing_ownership_signature
            ),
            expected_ownership_signature=(
                expected_existing_signature
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
        "Integrated Sector Intelligence"
    )
    print(
        "------------------------------"
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
        f"Universe        : "
        f"{technical_universe_date}"
    )
    print(
        f"Model version   : "
        f"{model_version}"
    )
    print(
        f"Latest input    : "
        f"{latest_input_date}"
    )
    print(
        f"Input sectors   : "
        f"{latest_input['latest_sector_count']}"
    )
    print(
        f"Ownership state : "
        f"{latest_input['ownership_signature']}"
    )
    print(
        f"Existing last   : "
        f"{existing_last_date}"
    )
    print(
        f"Stored sectors  : "
        f"{existing_latest_sector_count}"
    )
    print(
        f"Expected stored : "
        f"{existing_expected_sector_count}"
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
            "Integrated sector dataset "
            "is already up-to-date."
        )
        print(
            "Rows written    : 0"
        )
        print(
            f"Elapsed seconds : "
            f"{elapsed:.3f}"
        )

        print_ranking(
            model_version=model_version,
            trading_date=latest_input_date,
        )

        return

    after_date = None

    if mode == "INCREMENTAL":
        if existing_last_date is None:
            raise RuntimeError(
                "Incremental mode requires "
                "existing integrated data."
            )

        after_date = (
            existing_last_date
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
                after_date=after_date,
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
                after_date=after_date,
            )
        )

    rows = (
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

    expected_rows = int(
        expected["expected_rows"]
    )

    if len(rows) != expected_rows:
        raise RuntimeError(
            "Generated integrated rows "
            "do not match expected "
            "coverage: "
            f"generated={len(rows)}, "
            f"expected={expected_rows}."
        )

    if not rows:
        raise RuntimeError(
            "No integrated sector rows "
            "were generated."
        )

    generated_last_date = max(
        row["trading_date"]
        for row in rows
    )

    if (
        generated_last_date
        != latest_input_date
    ):
        raise RuntimeError(
            "Integrated build did not "
            "reach latest technical date: "
            f"generated="
            f"{generated_last_date}, "
            f"expected="
            f"{latest_input_date}."
        )

    with engine.begin() as connection:
        deleted = 0

        if mode == "FULL":
            deleted = (
                delete_integrated_model(
                    connection,
                    model_version=(
                        model_version
                    ),
                )
            )

        written = (
            upsert_integrated_rows(
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
        f"Rows deleted    : "
        f"{deleted}"
    )
    print(
        f"Rows written    : "
        f"{written}"
    )
    print(
        f"Expected sectors: "
        f"{expected['expected_sectors']}"
    )
    print(
        f"Expected dates  : "
        f"{expected['expected_dates']}"
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

    print_ranking(
        model_version=model_version,
        trading_date=latest_input_date,
    )

    print()
    print(
        "IMPORTANT:"
    )
    print(
        "Ownership is an independent "
        "monthly KSEI signal and is "
        "not treated as daily foreign "
        "buy/sell flow."
    )
    print(
        "Ownership older than 45 days "
        "receives zero effective weight."
    )
    print(
        "Historical integration uses "
        "ownership as_of_date and is "
        "not yet publication-time-safe "
        "for strict backtesting."
    )


if __name__ == "__main__":
    main()