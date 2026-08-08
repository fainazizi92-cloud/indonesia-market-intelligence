from imi.db import engine
from imi.features.execution_sensitivity import (
    build_execution_sensitivity_version,
    classify_execution_fragility,
    prepare_execution_sensitivity_rows,
    summarize_all_scenarios,
    summarize_group,
)
from imi.repositories.execution_sensitivity import (
    get_latest_execution_model_state,
    load_mature_execution_inputs,
)


def format_r(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return (
        f"{value:.4f}R"
    )


def format_pf(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return (
        f"{value:.4f}"
    )


def format_pct(
    value: float | None,
) -> str:
    if value is None:
        return "-"

    return (
        f"{value * 100:.2f}%"
    )


def print_group_summary(
    *,
    title: str,
    rows,
    field: str,
) -> None:
    print()
    print(
        title
    )

    print(
        "-" * len(
            title
        )
    )

    for row in rows:
        print(
            f"{row[field]!s:<16} "
            f"n={int(row['trades']):>3} "
            f"raw={format_r(row['raw_avg_r']):>9} "
            f"net={format_r(row['net_avg_r']):>9} "
            f"drag={format_r(row['avg_drag_r']):>9} "
            f"PF={format_pf(row['net_profit_factor']):>7} "
            f"positive={format_pct(row['positive_rate'])}"
        )


def main() -> None:
    with engine.connect() as connection:
        model_state = (
            get_latest_execution_model_state(
                connection
            )
        )

        execution_model = str(
            model_state[
                "model_version"
            ]
        )

        inputs = (
            load_mature_execution_inputs(
                connection,
                model_version=(
                    execution_model
                ),
            )
        )

    sensitivity_version = (
        build_execution_sensitivity_version(
            execution_model
        )
    )

    rows = (
        prepare_execution_sensitivity_rows(
            inputs=inputs
        )
    )

    summaries = (
        summarize_all_scenarios(
            rows
        )
    )

    classification = (
        classify_execution_fragility(
            summaries
        )
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Execution Sensitivity & "
        "Microstructure Diagnostics"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Version          : "
        f"{sensitivity_version}"
    )

    print(
        f"Execution model  : "
        f"{execution_model}"
    )

    print(
        f"Mature trades    : "
        f"{len(inputs)}"
    )

    print(
        f"Scenario rows    : "
        f"{len(rows)}"
    )

    print()
    print(
        "Scenario sensitivity:"
    )

    print(
        "---------------------"
    )

    for summary in summaries:
        print(
            f"{summary.scenario:<26} "
            f"n={summary.trades:>3} "
            f"avg={format_r(summary.average_r):>9} "
            f"median={format_r(summary.median_r):>9} "
            f"PF={format_pf(summary.profit_factor):>7} "
            f"positive={format_pct(summary.positive_rate):>7} "
            f"drag={format_r(summary.average_drag_r):>9}"
        )

    print()
    print(
        "Execution fragility:"
    )

    print(
        "--------------------"
    )

    print(
        classification
    )

    price_rows = summarize_group(
        rows=rows,
        scenario=(
            "BASELINE_CONSERVATIVE"
        ),
        group_field=(
            "price_bucket"
        ),
    )

    risk_rows = summarize_group(
        rows=rows,
        scenario=(
            "BASELINE_CONSERVATIVE"
        ),
        group_field=(
            "risk_tick_bucket"
        ),
    )

    liquidity_rows = summarize_group(
        rows=rows,
        scenario=(
            "BASELINE_CONSERVATIVE"
        ),
        group_field=(
            "liquidity_bucket"
        ),
    )

    sector_rows = summarize_group(
        rows=rows,
        scenario=(
            "BASELINE_CONSERVATIVE"
        ),
        group_field=(
            "sector_code"
        ),
    )

    print_group_summary(
        title=(
            "Baseline by IDX price bucket"
        ),
        rows=price_rows,
        field="price_bucket",
    )

    print_group_summary(
        title=(
            "Baseline by risk-distance ticks"
        ),
        rows=risk_rows,
        field="risk_tick_bucket",
    )

    print_group_summary(
        title=(
            "Baseline by liquidity bucket"
        ),
        rows=liquidity_rows,
        field="liquidity_bucket",
    )

    print_group_summary(
        title=(
            "Baseline by sector"
        ),
        rows=sector_rows,
        field="sector_code",
    )

    print()
    print(
        "INTERPRETATION:"
    )

    if classification == (
        "FRAGILE_TO_EXTRA_SLIPPAGE"
    ):
        print(
            "The strategy remains positive "
            "with valid tick rounding and "
            "minimum infrastructure costs, "
            "but loses its edge when the "
            "current conservative extra-tick "
            "slippage is applied."
        )

    elif classification == (
        "NEGATIVE_AFTER_MINIMUM_"
        "FEES_ZERO_EXTRA_SLIPPAGE"
    ):
        print(
            "The raw strategy survives tick "
            "rounding, but minimum modeled "
            "fees are enough to remove its "
            "edge even before extra slippage."
        )

    elif classification == (
        "NEGATIVE_AFTER_TICK_"
        "ROUNDING_ONLY"
    ):
        print(
            "The apparent raw edge does not "
            "survive valid IDX tick rounding "
            "even with zero fee and zero "
            "extra slippage."
        )

    elif classification == (
        "ROBUST_TO_BASELINE"
    ):
        print(
            "The strategy remains positive "
            "under the current Phase 3L "
            "baseline execution assumptions."
        )

    elif classification == (
        "ROBUST_TO_STRESS_2T"
    ):
        print(
            "The strategy remains positive "
            "even under the two-tick stress "
            "scenario."
        )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This diagnostic does not change "
        "Phase 3I rules and does not "
        "optimize thresholds."
    )

    print(
        "Risk-distance and price buckets "
        "are diagnostic evidence only."
    )

    print(
        "Do not select a favorable bucket "
        "as a trading rule until it is "
        "validated chronologically and "
        "out-of-sample."
    )


if __name__ == "__main__":
    main()