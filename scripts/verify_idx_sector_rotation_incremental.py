import argparse
import math
from time import perf_counter
from typing import Any

from imi.db import engine
from imi.features.sector_rotation import (
    ROTATION_LOOKBACK,
    build_sector_model_version,
    prepare_sector_score_rows,
)
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.sector_rotation import (
    get_latest_snapshot_date,
    get_recent_sector_dates,
    load_incremental_sector_inputs,
    load_prior_score_history,
    load_stored_sector_rows_after,
)

FLOAT_FIELDS = (
    "score",
    "relative_strength_score",
    "breadth_score",
    "volume_score",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify incremental IDX sector "
            "rotation calculations against "
            "stored historical results."
        )
    )

    parser.add_argument(
        "--days",
        type=int,
        default=10,
        help=(
            "Number of recent trading "
            "dates to verify."
        ),
    )

    return parser.parse_args()


def _float_matches(
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

    if args.days <= 0:
        raise ValueError(
            "days must be greater than zero."
        )

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

    model_version = (
        build_sector_model_version(
            snapshot_date
        )
    )

    with engine.connect() as connection:
        recent_dates = (
            get_recent_sector_dates(
                connection,
                model_version=model_version,
                limit=args.days + 1,
            )
        )

    if len(recent_dates) < (
        args.days + 1
    ):
        raise RuntimeError(
            "Not enough stored sector dates "
            "for verification."
        )

    ordered_dates = sorted(
        recent_dates
    )

    after_date = ordered_dates[0]

    expected_dates = set(
        ordered_dates[1:]
    )

    print(
        "IDX Sector Rotation "
        "Incremental Verification"
    )
    print(
        "-----------------------------------"
    )
    print(
        f"Model version   : "
        f"{model_version}"
    )
    print(
        f"Verify days     : "
        f"{args.days}"
    )
    print(
        f"After date      : "
        f"{after_date}"
    )
    print()

    with engine.connect() as connection:
        prior_history = (
            load_prior_score_history(
                connection,
                model_version=(
                    model_version
                ),
                through_date=(
                    after_date
                ),
                history_size=(
                    ROTATION_LOOKBACK
                ),
            )
        )

        inputs = (
            load_incremental_sector_inputs(
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
                after_date=(
                    after_date
                ),
            )
        )

        stored = (
            load_stored_sector_rows_after(
                connection,
                model_version=(
                    model_version
                ),
                after_date=(
                    after_date
                ),
            )
        )

    generated = (
        prepare_sector_score_rows(
            inputs=inputs,
            model_version=(
                model_version
            ),
            prior_score_history=(
                prior_history
            ),
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

    expected_keys = set(
        stored_by_key
    )

    generated_keys = set(
        generated_by_key
    )

    mismatches: list[str] = []

    if generated_keys != expected_keys:
        missing = (
            expected_keys
            - generated_keys
        )

        unexpected = (
            generated_keys
            - expected_keys
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
        expected_keys
    ):
        generated_row = (
            generated_by_key.get(key)
        )

        stored_row = (
            stored_by_key.get(key)
        )

        if (
            generated_row is None
            or stored_row is None
        ):
            continue

        for field in FLOAT_FIELDS:
            if not _float_matches(
                generated_row[field],
                stored_row[field],
            ):
                mismatches.append(
                    f"{key} "
                    f"{field}: "
                    f"generated="
                    f"{generated_row[field]} "
                    f"stored="
                    f"{stored_row[field]}"
                )

        generated_label = (
            generated_row[
                "rotation_label"
            ]
        )

        stored_label = (
            stored_row[
                "rotation_label"
            ]
        )

        if (
            generated_label
            != stored_label
        ):
            mismatches.append(
                f"{key} "
                "rotation_label: "
                f"generated="
                f"{generated_label} "
                f"stored="
                f"{stored_label}"
            )

        if (
            generated_row[
                "flow_score"
            ]
            is not None
        ):
            mismatches.append(
                f"{key} generated "
                "flow_score is not NULL."
            )

        if (
            generated_row[
                "catalyst_score"
            ]
            is not None
        ):
            mismatches.append(
                f"{key} generated "
                "catalyst_score is not NULL."
            )

        if (
            stored_row[
                "flow_score"
            ]
            is not None
        ):
            mismatches.append(
                f"{key} stored "
                "flow_score is not NULL."
            )

        if (
            stored_row[
                "catalyst_score"
            ]
            is not None
        ):
            mismatches.append(
                f"{key} stored "
                "catalyst_score is not NULL."
            )

    expected_row_count = len(
        expected_keys
    )

    if len(generated) != expected_row_count:
        mismatches.append(
            "Generated row count does not "
            "match expected row count: "
            f"generated={len(generated)}, "
            f"expected={expected_row_count}"
        )

    if len(stored) != expected_row_count:
        mismatches.append(
            "Stored row count does not "
            "match expected row count: "
            f"stored={len(stored)}, "
            f"expected={expected_row_count}"
        )

    elapsed = (
        perf_counter()
        - started
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