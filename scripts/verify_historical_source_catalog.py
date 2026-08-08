from imi.features.historical_source import (
    historical_source_definitions,
)

from imi.db import engine
from imi.repositories.historical_source import (
    load_latest_probes,
    load_source_catalog,
)


def main() -> None:
    definitions = (
        historical_source_definitions()
    )

    expected_keys = {
        item.source_key
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

    stored_keys = {
        row[
            "source_key"
        ]
        for row in catalog
    }

    probe_keys = {
        row[
            "source_key"
        ]
        for row in latest_probes
    }

    missing_catalog = (
        expected_keys
        - stored_keys
    )

    extra_catalog = (
        stored_keys
        - expected_keys
    )

    missing_probes = (
        expected_keys
        - probe_keys
    )

    failed_probes = {
        row[
            "source_key"
        ]
        for row in latest_probes
        if not row[
            "success"
        ]
    }

    passed = (
        not missing_catalog
        and not extra_catalog
        and not missing_probes
    )

    print(
        "Historical Source Verification"
    )

    print(
        "------------------------------"
    )

    print(
        f"Expected sources      : "
        f"{len(expected_keys)}"
    )

    print(
        f"Stored sources        : "
        f"{len(stored_keys)}"
    )

    print(
        f"Missing catalog       : "
        f"{len(missing_catalog)}"
    )

    print(
        f"Extra catalog         : "
        f"{len(extra_catalog)}"
    )

    print(
        f"Sources with probe    : "
        f"{len(probe_keys)}"
    )

    print(
        f"Missing probes        : "
        f"{len(missing_probes)}"
    )

    print(
        f"Failed latest probes  : "
        f"{len(failed_probes)}"
    )

    print(
        "Result               : "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    print()

    print(
        "Note:"
    )

    print(
        "A failed live probe does not "
        "delete or falsify a source."
    )

    print(
        "It remains explicit evidence "
        "that the route may need manual "
        "or alternate acquisition."
    )

    if not passed:
        raise RuntimeError(
            "Historical source "
            "verification failed."
        )


if __name__ == "__main__":
    main()