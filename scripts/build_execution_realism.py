import argparse
import time
from typing import Any

from imi.db import engine
from imi.features.execution_realism import (
    build_execution_realism_model_version,
    compute_execution_summary,
    prepare_execution_realism_rows,
    resolve_execution_build_mode,
)
from imi.features.trade_setup import (
    extract_current_universe_date,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.execution_realism import (
    delete_model_rows,
    get_build_state,
    get_latest_calibration_model_state,
    get_sector_summary,
    get_stored_coverage,
    load_execution_inputs,
    load_stored_rows,
    upsert_build_state,
    upsert_execution_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
    )

    return parser.parse_args()


def max_input_timestamp(
    rows: list[dict[str, Any]],
):
    values = [
        row[
            "input_updated_at"
        ]
        for row in rows
        if row[
            "input_updated_at"
        ]
        is not None
    ]

    if not values:
        return None

    return max(
        values
    )


def value_r(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return (
        f"{value:.4f}R"
    )


def print_summary(
    *,
    rows: list[dict[str, Any]],
    model_version: str,
) -> None:
    summary = (
        compute_execution_summary(
            rows
        )
    )

    with engine.connect() as connection:
        sectors = (
            get_sector_summary(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    print()
    print(
        "Execution realism summary:"
    )

    print(
        f"Total rows              : "
        f"{summary.total_rows}"
    )

    print(
        f"Mature trades           : "
        f"{summary.mature_trades}"
    )

    print(
        f"Execution metrics       : "
        f"{summary.execution_metrics_available}"
    )

    print(
        f"Strict eligible         : "
        f"{summary.strict_eligible}"
    )

    print()
    print(
        "Before / after realism:"
    )

    print(
        f"Raw average R           : "
        f"{value_r(summary.raw_average_r)}"
    )

    print(
        f"Gross modeled average R : "
        f"{value_r(summary.gross_average_r)}"
    )

    print(
        f"Net modeled average R   : "
        f"{value_r(summary.net_average_r)}"
    )

    print(
        f"Raw median R            : "
        f"{value_r(summary.raw_median_r)}"
    )

    print(
        f"Net median R            : "
        f"{value_r(summary.net_median_r)}"
    )

    print(
        f"Raw profit factor       : "
        f"{summary.raw_profit_factor}"
    )

    print(
        f"Net profit factor       : "
        f"{summary.net_profit_factor}"
    )

    print()
    print(
        "Execution drag:"
    )

    print(
        f"Average slippage drag   : "
        f"{value_r(summary.average_slippage_drag_r)}"
    )

    print(
        f"Average fee drag        : "
        f"{value_r(summary.average_fee_drag_r)}"
    )

    print(
        f"Average total drag      : "
        f"{value_r(summary.average_total_drag_r)}"
    )

    print()
    print(
        "Baseline edge after modeled "
        "minimum costs:"
    )

    print(
        "POSITIVE : "
        + (
            "YES"
            if summary.baseline_edge_positive
            else "NO"
        )
    )

    print()
    print(
        "Sector execution summary:"
    )

    for row in sectors:
        raw = (
            "-"
            if row[
                "raw_avg_r"
            ]
            is None
            else (
                f"{float(row['raw_avg_r']):.4f}R"
            )
        )

        net = (
            "-"
            if row[
                "net_avg_r"
            ]
            is None
            else (
                f"{float(row['net_avg_r']):.4f}R"
            )
        )

        drag = (
            "-"
            if row[
                "avg_drag_r"
            ]
            is None
            else (
                f"{float(row['avg_drag_r']):.4f}R"
            )
        )

        print(
            f"{row['sector_code']!s:<12} "
            f"n={int(row['trades']):>3} "
            f"raw={raw:>9} "
            f"net={net:>9} "
            f"drag={drag:>9}"
        )

    print()
    print(
        "STRICT CALIBRATION:"
    )

    if summary.strict_eligible == 0:
        print(
            "READY : NO"
        )

        print(
            "- KSEI publication-time "
            "safety not established"
        )

        print(
            "- current-universe "
            "survivorship bias remains"
        )

        print(
            "- historical corporate-action "
            "coverage incomplete"
        )

        print(
            "- broker commission not modeled"
        )

        print(
            "- board-specific auto rejection "
            "not modeled"
        )

    else:
        print(
            f"Strict eligible rows : "
            f"{summary.strict_eligible}"
        )


def main() -> None:
    args = parse_args()

    started = time.perf_counter()

    with engine.connect() as connection:
        calibration_state = (
            get_latest_calibration_model_state(
                connection
            )
        )

        dataset_version = str(
            calibration_state[
                "dataset_version"
            ]
        )

        universe_date = (
            extract_current_universe_date(
                dataset_version
            )
        )

        model_version = (
            build_execution_realism_model_version(
                universe_date
            )
        )

        yahoo_source_id = (
            get_source_id(
                connection,
                code="YAHOO_FINANCE",
            )
        )

        inputs = (
            load_execution_inputs(
                connection,
                dataset_version=(
                    dataset_version
                ),
                price_source_id=(
                    yahoo_source_id
                ),
            )
        )

        stored = (
            get_stored_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        build_state = (
            get_build_state(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    expected_rows = len(
        inputs
    )

    stored_rows = int(
        stored["rows"]
        or 0
    )

    latest_input_date = (
        calibration_state[
            "latest_input_date"
        ]
    )

    if latest_input_date is None:
        raise RuntimeError(
            "Calibration dataset has "
            "no latest input date."
        )

    current_timestamp = (
        max_input_timestamp(
            inputs
        )
    )

    if build_state is None:
        state_exists = False
        input_model_matches = False
        processed_through = None
        stored_timestamp = None

    else:
        state_exists = True

        input_model_matches = (
            build_state[
                "input_model_version"
            ]
            == dataset_version
        )

        processed_through = (
            build_state[
                "processed_through"
            ]
        )

        stored_timestamp = (
            build_state[
                "processed_input_updated_at"
            ]
        )

    build_mode = (
        resolve_execution_build_mode(
            force=args.force,
            state_exists=(
                state_exists
            ),
            input_model_matches=(
                input_model_matches
            ),
            stored_rows=(
                stored_rows
            ),
            expected_rows=(
                expected_rows
            ),
            processed_through=(
                processed_through
            ),
            latest_input_date=(
                latest_input_date
            ),
            stored_input_updated_at=(
                stored_timestamp
            ),
            current_input_updated_at=(
                current_timestamp
            ),
        )
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Execution Realism & "
        "Point-in-Time Hardening V1"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Model version     : "
        f"{model_version}"
    )

    print(
        f"Calibration input : "
        f"{dataset_version}"
    )

    print(
        f"Universe          : "
        f"{universe_date}"
    )

    print(
        f"Latest input      : "
        f"{latest_input_date}"
    )

    print(
        f"Expected rows     : "
        f"{expected_rows}"
    )

    print(
        f"Stored rows       : "
        f"{stored_rows}"
    )

    print(
        f"Build mode        : "
        f"{build_mode}"
    )

    if build_mode == "UP_TO_DATE":
        with engine.connect() as connection:
            stored_dataset = (
                load_stored_rows(
                    connection,
                    model_version=(
                        model_version
                    ),
                )
            )

        elapsed = (
            time.perf_counter()
            - started
        )

        print()
        print(
            "Execution realism dataset is "
            "already up-to-date."
        )

        print(
            "Rows written      : 0"
        )

        print(
            f"Elapsed seconds   : "
            f"{elapsed:.3f}"
        )

        print_summary(
            rows=stored_dataset,
            model_version=(
                model_version
            ),
        )

        return

    generated = (
        prepare_execution_realism_rows(
            inputs=inputs,
            model_version=(
                model_version
            ),
        )
    )

    if len(
        generated
    ) != expected_rows:
        raise RuntimeError(
            "Generated execution rows "
            "do not match input coverage."
        )

    with engine.begin() as connection:
        rows_deleted = (
            delete_model_rows(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        rows_written = (
            upsert_execution_rows(
                connection,
                rows=generated,
                batch_size=(
                    args.batch_size
                ),
            )
        )

        final = (
            get_stored_coverage(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

        final_rows = int(
            final["rows"]
            or 0
        )

        if final_rows != expected_rows:
            raise RuntimeError(
                "Stored execution realism "
                "coverage mismatch."
            )

        upsert_build_state(
            connection,
            model_version=(
                model_version
            ),
            input_model_version=(
                dataset_version
            ),
            processed_through=(
                latest_input_date
            ),
            processed_input_updated_at=(
                current_timestamp
            ),
            output_rows=(
                final_rows
            ),
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    print()
    print(
        f"Generated rows    : "
        f"{len(generated)}"
    )

    print(
        f"Rows deleted      : "
        f"{rows_deleted}"
    )

    print(
        f"Rows written      : "
        f"{rows_written}"
    )

    print(
        f"Stored total      : "
        f"{expected_rows}"
    )

    print(
        f"Elapsed seconds   : "
        f"{elapsed:.3f}"
    )

    print_summary(
        rows=generated,
        model_version=(
            model_version
        ),
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "Net modeled R includes current "
        "IDX infrastructure fees and "
        "conservative EOD tick slippage."
    )

    print(
        "Broker-specific commission is "
        "not included."
    )

    print(
        "Strict calibration remains "
        "blocked until point-in-time, "
        "survivorship, corporate-action, "
        "and board-specific AR issues "
        "are resolved."
    )


if __name__ == "__main__":
    main()