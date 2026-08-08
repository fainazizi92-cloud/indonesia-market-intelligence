import argparse
import math
from datetime import timedelta
from time import perf_counter
from typing import Any

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
    get_latest_ownership_model_state,
    get_latest_technical_model_state,
    get_recent_dates,
    load_integrated_inputs,
    load_stored_after,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify incremental integrated "
            "sector intelligence."
        )
    )

    parser.add_argument(
        "--dates",
        type=int,
        default=10,
    )

    return parser.parse_args()


def float_matches(
    left: Any,
    right: Any,
) -> bool:
    return math.isclose(
        float(left),
        float(right),
        rel_tol=1e-9,
        abs_tol=1e-4,
    )


def main() -> None:
    started = perf_counter()

    args = parse_args()

    if args.dates <= 0:
        raise ValueError(
            "dates must be greater "
            "than zero."
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
            "Input model universes "
            "do not match."
        )

    model_version = (
        build_integrated_sector_model_version(
            technical_universe_date
        )
    )

    with engine.connect() as connection:
        recent_dates = (
            get_recent_dates(
                connection,
                model_version=model_version,
                limit=args.dates,
            )
        )

    if len(recent_dates) < args.dates:
        raise RuntimeError(
            "Not enough integrated dates "
            "for verification."
        )

    expected_dates = set(
        recent_dates
    )

    earliest = min(
        expected_dates
    )

    after_date = (
        earliest
        - timedelta(
            days=1
        )
    )

    with engine.connect() as connection:
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

        stored = (
            load_stored_after(
                connection,
                model_version=model_version,
                after_date=after_date,
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

    generated = [
        row
        for row in generated
        if row["trading_date"]
        in expected_dates
    ]

    stored = [
        row
        for row in stored
        if row["trading_date"]
        in expected_dates
    ]

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
            stored_keys
            - generated_keys
        )

        unexpected = (
            generated_keys
            - stored_keys
        )

        if missing:
            mismatches.append(
                "Missing generated keys: "
                f"{sorted(missing)[:20]}"
            )

        if unexpected:
            mismatches.append(
                "Unexpected generated keys: "
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

    elapsed = (
        perf_counter()
        - started
    )

    print(
        "Integrated Sector Intelligence "
        "Incremental Verification"
    )
    print(
        "--------------------------------"
    )
    print(
        f"Dates           : "
        f"{args.dates}"
    )
    print(
        f"Generated rows  : "
        f"{len(generated)}"
    )
    print(
        f"Stored rows     : "
        f"{len(stored)}"
    )
    print(
        f"Mismatches      : "
        f"{len(mismatches)}"
    )
    print(
        f"Elapsed seconds : "
        f"{elapsed:.3f}"
    )

    if mismatches:
        print()
        print(
            "Mismatch sample:"
        )

        for mismatch in (
            mismatches[:30]
        ):
            print(
                mismatch
            )

    print()
    print(
        "Result          : "
        + (
            "PASS"
            if not mismatches
            else "FAIL"
        )
    )

    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()