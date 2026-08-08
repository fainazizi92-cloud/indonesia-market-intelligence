from imi.db import engine
from imi.features.execution_sensitivity import (
    BASELINE_CONSERVATIVE,
    SCENARIOS,
    prepare_execution_sensitivity_rows,
)
from imi.repositories.execution_sensitivity import (
    get_latest_execution_model_state,
    load_mature_execution_inputs,
)

TOLERANCE = 0.0001


def number_equal(
    left,
    right,
) -> bool:
    if (
        left is None
        and right is None
    ):
        return True

    if (
        left is None
        or right is None
    ):
        return False

    return (
        abs(
            float(left)
            - float(right)
        )
        <= TOLERANCE
    )


def main() -> None:
    with engine.connect() as connection:
        model_state = (
            get_latest_execution_model_state(
                connection
            )
        )

        model_version = str(
            model_state[
                "model_version"
            ]
        )

        inputs = (
            load_mature_execution_inputs(
                connection,
                model_version=(
                    model_version
                ),
            )
        )

    rows = (
        prepare_execution_sensitivity_rows(
            inputs=inputs
        )
    )

    expected_rows = (
        len(inputs)
        * len(SCENARIOS)
    )

    baseline_rows = {
        row["signal_id"]:
            row
        for row in rows
        if row[
            "scenario"
        ]
        == BASELINE_CONSERVATIVE.name
    }

    baseline_mismatches = 0
    invalid_risk_ticks = 0
    invalid_bucket = 0

    for item in inputs:
        signal_id = (
            item[
                "signal_id"
            ]
        )

        row = baseline_rows.get(
            signal_id
        )

        if row is None:
            baseline_mismatches += 1
            continue

        if not number_equal(
            row[
                "gross_r"
            ],
            item[
                "stored_baseline_gross_r"
            ],
        ):
            baseline_mismatches += 1
            continue

        if not number_equal(
            row[
                "net_r"
            ],
            item[
                "stored_baseline_net_r"
            ],
        ):
            baseline_mismatches += 1
            continue

        if not number_equal(
            row[
                "total_drag_r"
            ],
            item[
                "stored_baseline_drag_r"
            ],
        ):
            baseline_mismatches += 1

    for row in rows:
        if (
            float(
                row[
                    "raw_risk_ticks"
                ]
            )
            <= 0
        ):
            invalid_risk_ticks += 1

        if not row[
            "price_bucket"
        ]:
            invalid_bucket += 1

        if not row[
            "risk_tick_bucket"
        ]:
            invalid_bucket += 1

    scenario_counts = {}

    for scenario in SCENARIOS:
        scenario_counts[
            scenario.name
        ] = sum(
            row[
                "scenario"
            ]
            == scenario.name
            for row in rows
        )

    scenario_coverage_pass = all(
        count
        == len(inputs)
        for count
        in scenario_counts.values()
    )

    coverage_pass = (
        len(rows)
        == expected_rows
        and scenario_coverage_pass
    )

    quality_pass = (
        baseline_mismatches == 0
        and invalid_risk_ticks == 0
        and invalid_bucket == 0
    )

    print(
        "Execution Sensitivity Audit"
    )

    print(
        "---------------------------"
    )

    print(
        f"Execution model      : "
        f"{model_version}"
    )

    print(
        f"Mature inputs        : "
        f"{len(inputs)}"
    )

    print(
        f"Scenarios            : "
        f"{len(SCENARIOS)}"
    )

    print(
        f"Expected rows        : "
        f"{expected_rows}"
    )

    print(
        f"Generated rows       : "
        f"{len(rows)}"
    )

    print()
    print(
        "Scenario coverage:"
    )

    for name, count in (
        scenario_counts.items()
    ):
        print(
            f"{name:<26}: "
            f"{count}"
        )

    print()
    print(
        "Quality:"
    )

    print(
        f"Baseline mismatches  : "
        f"{baseline_mismatches}"
    )

    print(
        f"Invalid risk ticks   : "
        f"{invalid_risk_ticks}"
    )

    print(
        f"Invalid buckets      : "
        f"{invalid_bucket}"
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

    if not (
        coverage_pass
        and quality_pass
    ):
        raise RuntimeError(
            "Execution sensitivity "
            "audit failed."
        )


if __name__ == "__main__":
    main()