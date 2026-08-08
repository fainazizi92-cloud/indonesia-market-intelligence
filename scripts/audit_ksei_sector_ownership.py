import math

from imi.db import engine
from imi.features.ownership_trend import (
    OWNERSHIP_TREND_MODEL_VERSION,
)
from imi.features.sector_ownership import (
    LOW_COVERAGE_THRESHOLD_PCT,
    build_sector_ownership_model_version,
    calculate_coverage_pct,
    calculate_ownership_breadth_score,
    calculate_ownership_intensity_score,
    calculate_sector_ownership_score,
    classify_sector_ownership_signal,
)
from imi.repositories.equity_eod import (
    get_source_id,
)
from imi.repositories.sector_ownership import (
    get_duplicate_groups,
    get_expected_coverage,
    get_latest_input_state,
    get_latest_universe_snapshot_date,
    get_stored_coverage,
    load_all_stored,
    load_latest_ranking,
)


def close(
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

        snapshot_date = (
            get_latest_universe_snapshot_date(
                connection
            )
        )

        model_version = (
            build_sector_ownership_model_version(
                snapshot_date
            )
        )

        expected = (
            get_expected_coverage(
                connection,
                source_id=source_id,
                input_model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
            )
        )

        actual = (
            get_stored_coverage(
                connection,
                source_id=source_id,
                model_version=model_version,
            )
        )

        latest_input = (
            get_latest_input_state(
                connection,
                source_id=source_id,
                input_model_version=(
                    OWNERSHIP_TREND_MODEL_VERSION
                ),
            )
        )

        rows = load_all_stored(
            connection,
            source_id=source_id,
            model_version=model_version,
        )

        duplicates = (
            get_duplicate_groups(
                connection,
                source_id=source_id,
                model_version=model_version,
            )
        )

        ranking = (
            load_latest_ranking(
                connection,
                source_id=source_id,
                model_version=model_version,
                as_of_date=(
                    latest_input[
                        "latest_input_date"
                    ]
                ),
            )
        )

    quality = {
        "invalid_population": 0,
        "invalid_risk_counts": 0,
        "coverage_mismatch": 0,
        "breadth_mismatch": 0,
        "intensity_mismatch": 0,
        "score_mismatch": 0,
        "label_mismatch": 0,
        "low_coverage_mismatch": 0,
        "invalid_scores": 0,
    }

    for row in rows:
        eligible = int(
            row["eligible_count"]
        )

        current = int(
            row[
                "current_universe_count"
            ]
        )

        clean = int(
            row["clean_count"]
        )

        accumulating = int(
            row[
                "accumulating_count"
            ]
        )

        stable = int(
            row["stable_count"]
        )

        distributing = int(
            row[
                "distributing_count"
            ]
        )

        if (
            accumulating
            + stable
            + distributing
            != clean
            or clean < 0
            or clean > eligible
        ):
            quality[
                "invalid_population"
            ] += 1

        for field in (
            "corporate_action_risk_count",
            "snapshot_gap_count",
            "extreme_move_count",
        ):
            value = int(
                row[field]
            )

            if (
                value < 0
                or value > eligible
            ):
                quality[
                    "invalid_risk_counts"
                ] += 1

                break

        expected_coverage = (
            calculate_coverage_pct(
                eligible_count=eligible,
                current_universe_count=(
                    current
                ),
            )
        )

        if not close(
            row["coverage_pct"],
            expected_coverage,
        ):
            quality[
                "coverage_mismatch"
            ] += 1

        expected_breadth = (
            calculate_ownership_breadth_score(
                clean_count=clean,
                accumulating_count=(
                    accumulating
                ),
                distributing_count=(
                    distributing
                ),
            )
        )

        if not close(
            row["breadth_score"],
            expected_breadth,
        ):
            quality[
                "breadth_mismatch"
            ] += 1

        expected_intensity = (
            calculate_ownership_intensity_score(
                avg_clean_clipped_delta_pp=(
                    float(
                        row[
                            "avg_clean_clipped_delta_pp"
                        ]
                    )
                ),
            )
        )

        if not close(
            row["intensity_score"],
            expected_intensity,
        ):
            quality[
                "intensity_mismatch"
            ] += 1

        expected_score = (
            calculate_sector_ownership_score(
                breadth_score=(
                    expected_breadth
                ),
                intensity_score=(
                    expected_intensity
                ),
                coverage_pct=(
                    expected_coverage
                ),
            )
        )

        if not close(
            row["score"],
            expected_score,
        ):
            quality[
                "score_mismatch"
            ] += 1

        expected_label = (
            classify_sector_ownership_signal(
                expected_score
            )
        )

        if (
            row["signal_label"]
            != expected_label
        ):
            quality[
                "label_mismatch"
            ] += 1

        expected_low_coverage = (
            expected_coverage
            < LOW_COVERAGE_THRESHOLD_PCT
        )

        if (
            bool(
                row[
                    "low_coverage_flag"
                ]
            )
            != expected_low_coverage
        ):
            quality[
                "low_coverage_mismatch"
            ] += 1

        for field in (
            "coverage_pct",
            "breadth_score",
            "intensity_score",
            "score",
        ):
            value = float(
                row[field]
            )

            if not (
                0.0
                <= value
                <= 100.0
            ):
                quality[
                    "invalid_scores"
                ] += 1

                break

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
        all(
            value == 0
            for value
            in quality.values()
        )
        and duplicates == 0
    )

    latest_pass = (
        ranking
        and ranking[0][
            "as_of_date"
        ]
        == latest_input[
            "latest_input_date"
        ]
        and len(
            ranking
        )
        == int(
            latest_input[
                "latest_sector_count"
            ]
        )
    )

    print(
        "KSEI Sector Ownership Audit"
    )
    print(
        "---------------------------"
    )
    print(
        f"Universe        : "
        f"{snapshot_date}"
    )
    print(
        f"Input model     : "
        f"{OWNERSHIP_TREND_MODEL_VERSION}"
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

    for key, value in (
        quality.items()
    ):
        print(
            f"{key:<28}: "
            f"{value}"
        )

    print(
        f"{'duplicate_groups':<28}: "
        f"{duplicates}"
    )

    print()
    print(
        "Latest sector ranking:"
    )

    for position, row in enumerate(
        ranking,
        start=1,
    ):
        print(
            f"{position:>2}. "
            f"{row['sector_code']:<12} "
            f"score="
            f"{float(row['score']):>7.2f} "
            f"breadth="
            f"{float(row['breadth_score']):>7.2f} "
            f"intensity="
            f"{float(row['intensity_score']):>7.2f} "
            f"coverage="
            f"{float(row['coverage_pct']):>6.2f}% "
            f"A/S/D="
            f"{row['accumulating_count']}/"
            f"{row['stable_count']}/"
            f"{row['distributing_count']} "
            f"{row['signal_label']}"
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
        "Sector ownership is based "
        "on monthly KSEI ownership "
        "snapshots, not daily foreign "
        "transaction flow."
    )
    print(
        "Historical results remain "
        "current-universe biased."
    )


if __name__ == "__main__":
    main()