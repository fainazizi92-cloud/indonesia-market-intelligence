from imi.features.historical_source import (
    evaluate_discovery_readiness,
    historical_source_definitions,
)

from imi.db import engine
from imi.repositories.historical_source import (
    get_probe_counts,
    load_latest_probes,
    load_source_catalog,
)

CORE_FIELDS = (
    "dataset_family",
    "source_kind",
    "authority_class",
    "base_url",
    "probe_url",
    "historical_access",
    "access_mode",
    "supports_download",
    "supports_date_filter",
    "point_in_time_potential",
    "automation_status",
    "priority",
)


def main() -> None:
    definitions = (
        historical_source_definitions()
    )

    definition_map = {
        item.source_key: item
        for item in definitions
    }

    with engine.connect() as connection:
        catalog = (
            load_source_catalog(
                connection
            )
        )

        latest_probes = (
            load_latest_probes(
                connection
            )
        )

        probe_counts = (
            get_probe_counts(
                connection
            )
        )

    catalog_map = {
        row[
            "source_key"
        ]:
            row
        for row in catalog
    }

    probe_map = {
        row[
            "source_key"
        ]:
            row
        for row in latest_probes
    }

    expected_keys = set(
        definition_map
    )

    actual_keys = set(
        catalog_map
    )

    missing_catalog = (
        expected_keys
        - actual_keys
    )

    extra_catalog = (
        actual_keys
        - expected_keys
    )

    catalog_mismatches = 0

    for (
        source_key,
        definition,
    ) in definition_map.items():
        actual = catalog_map.get(
            source_key
        )

        if actual is None:
            continue

        expected = {
            "dataset_family":
                definition.dataset_family,

            "source_kind":
                definition.source_kind,

            "authority_class":
                definition.authority_class,

            "base_url":
                definition.base_url,

            "probe_url":
                definition.probe_url,

            "historical_access":
                definition.historical_access,

            "access_mode":
                definition.access_mode,

            "supports_download":
                definition.supports_download,

            "supports_date_filter":
                definition.supports_date_filter,

            "point_in_time_potential":
                definition
                .point_in_time_potential,

            "automation_status":
                definition.automation_status,

            "priority":
                definition.priority,
        }

        if any(
            actual[field]
            != expected[field]
            for field in CORE_FIELDS
        ):
            catalog_mismatches += 1

    missing_probes = (
        expected_keys
        - set(
            probe_map
        )
    )

    approved_historical = [
        row[
            "source_key"
        ]
        for row in catalog
        if (
            row[
                "dataset_family"
            ]
            != "CURRENT_CROSSCHECK"
            and row[
                "automation_status"
            ]
            == "APPROVED"
        )
    ]

    readiness = (
        evaluate_discovery_readiness(
            latest_probes=(
                probe_map
            ),
        )
    )

    static_pass = (
        not missing_catalog
        and not extra_catalog
        and catalog_mismatches == 0
        and not approved_historical
    )

    probe_history_pass = (
        not missing_probes
    )

    print(
        "Historical Source Catalog Audit"
    )

    print(
        "-------------------------------"
    )

    print(
        f"Expected sources       : "
        f"{len(expected_keys)}"
    )

    print(
        f"Stored sources         : "
        f"{len(actual_keys)}"
    )

    print(
        f"Missing catalog        : "
        f"{len(missing_catalog)}"
    )

    print(
        f"Extra catalog          : "
        f"{len(extra_catalog)}"
    )

    print(
        f"Catalog mismatches     : "
        f"{catalog_mismatches}"
    )

    print(
        f"Historical APPROVED    : "
        f"{len(approved_historical)}"
    )

    print()

    print(
        "Probe history:"
    )

    print(
        f"Total probe runs       : "
        f"{probe_counts['total_runs']}"
    )

    print(
        f"Distinct probed sources: "
        f"{probe_counts['distinct_sources']}"
    )

    print(
        f"Latest probes          : "
        f"{len(latest_probes)}"
    )

    print(
        f"Missing latest probes  : "
        f"{len(missing_probes)}"
    )

    print(
        f"Successful latest      : "
        f"{readiness.successful_probes}"
        f"/{readiness.source_total}"
    )

    failed_latest = [
        row
        for row in latest_probes
        if not row[
            "success"
        ]
    ]

    if failed_latest:
        print()

        print(
            "Failed latest probes:"
        )

        for row in failed_latest:
            print(
                f"- {row['source_key']} | "
                f"HTTP="
                f"{row['http_status']} | "
                f"{row['error_type']}"
            )

    print()

    print(
        "Required family reachability:"
    )

    print(
        "Lifecycle        : "
        + (
            "YES"
            if readiness
            .lifecycle_reachable
            else "NO"
        )
    )

    print(
        "Board history    : "
        + (
            "YES"
            if readiness
            .board_history_reachable
            else "NO"
        )
    )

    print(
        "Corporate action : "
        + (
            "YES"
            if readiness
            .corporate_action_reachable
            else "NO"
        )
    )

    print()

    print(
        "Result:"
    )

    print(
        "Catalog quality : "
        + (
            "PASS"
            if static_pass
            else "FAIL"
        )
    )

    print(
        "Probe coverage  : "
        + (
            "PASS"
            if probe_history_pass
            else "FAIL"
        )
    )

    print()

    print(
        "Parser-work readiness : "
        + (
            "YES"
            if readiness
            .ready_for_parser_work
            else "NO"
        )
    )

    print()

    print(
        "STRICT HISTORICAL READINESS:"
    )

    print(
        "READY : NO"
    )

    print(
        "- Historical parsers are not "
        "implemented yet."
    )

    print(
        "- Source route reachability "
        "does not prove complete "
        "historical coverage."
    )

    print(
        "- Older announcement history "
        "may require TICMI access."
    )

    if not (
        static_pass
        and probe_history_pass
    ):
        raise RuntimeError(
            "Historical source catalog "
            "audit failed."
        )


if __name__ == "__main__":
    main()