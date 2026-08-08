import argparse
import math
from datetime import timedelta
from time import perf_counter
from typing import Any

from imi.db import engine
from imi.features.ownership_trend import (
    OWNERSHIP_TREND_MODEL_VERSION,
    prepare_ownership_trend_rows,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.ownership_trend import (
    get_recent_trend_dates,
    load_ownership_pairs,
    load_stored_trends_after,
)

FLOAT_FIELDS = (
    "foreign_ownership_pct",
    "previous_foreign_ownership_pct",
    "delta_foreign_ownership_pp",
    "delta_security_number_pct",
    "normalized_foreign_share_change_pct",
    "signal_strength",
)

INTEGER_FIELDS = (
    "foreign_shares",
    "previous_foreign_shares",
    "delta_foreign_shares",
    "security_number",
    "previous_security_number",
    "days_between_snapshots",
)

EXACT_FIELDS = (
    "previous_as_of_date",
    "trend_label",
    "corporate_action_risk",
    "snapshot_gap_flag",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--snapshots",
        type=int,
        default=3,
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

    if args.snapshots <= 0:
        raise ValueError(
            "snapshots must be "
            "greater than zero."
        )

    with engine.connect() as connection:
        source_id = get_source_id(
            connection,
            code="KSEI_OFFICIAL",
        )

        recent_dates = (
            get_recent_trend_dates(
                connection,
                source_id=source_id,
                model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
                limit=args.snapshots,
            )
        )

    if len(recent_dates) < args.snapshots:
        raise RuntimeError(
            "Not enough stored trend "
            "dates for verification."
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
        inputs = load_ownership_pairs(
            connection,
            source_id=source_id,
            after_date=after_date,
        )

        stored = (
            load_stored_trends_after(
                connection,
                source_id=source_id,
                model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
                after_date=after_date,
            )
        )

    generated = (
        prepare_ownership_trend_rows(
            inputs=inputs,
            source_id=source_id,
        )
    )

    generated = [
        row
        for row in generated
        if row["as_of_date"]
        in expected_dates
    ]

    stored = [
        row
        for row in stored
        if row["as_of_date"]
        in expected_dates
    ]

    generated_by_key = {
        (
            row["instrument_id"],
            row["as_of_date"],
        ): row
        for row in generated
    }

    stored_by_key = {
        (
            row["instrument_id"],
            row["as_of_date"],
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
                f"{list(missing)[:20]}"
            )

        if unexpected:
            mismatches.append(
                "Unexpected generated keys: "
                f"{list(unexpected)[:20]}"
            )

    for key in stored_keys:
        generated_row = (
            generated_by_key.get(
                key
            )
        )

        stored_row = (
            stored_by_key.get(
                key
            )
        )

        if (
            generated_row is None
            or stored_row is None
        ):
            continue

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
        "KSEI Ownership Trend "
        "Incremental Verification"
    )
    print(
        "--------------------------------"
    )
    print(
        f"Snapshots       : "
        f"{args.snapshots}"
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