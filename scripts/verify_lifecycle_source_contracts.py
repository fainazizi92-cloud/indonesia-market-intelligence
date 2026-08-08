from imi.db import engine
from imi.features.historical_source_contract import (
    LIFECYCLE_SOURCE_KEYS,
)
from imi.repositories.historical_source_contract import (
    load_latest_contract_snapshots,
)


def main() -> None:
    expected = set(
        LIFECYCLE_SOURCE_KEYS
    )

    with engine.connect() as connection:
        latest = (
            load_latest_contract_snapshots(
                connection
            )
        )

    actual = {
        row[
            "source_key"
        ]
        for row in latest
        if row[
            "source_key"
        ]
        in expected
    }

    missing = (
        expected
        - actual
    )

    extra = (
        actual
        - expected
    )

    successful = sum(
        row[
            "source_key"
        ]
        in expected
        and row[
            "http_status"
        ] is not None
        and 200
        <= row[
            "http_status"
        ]
        <= 299
        for row in latest
    )

    passed = (
        not missing
        and not extra
        and successful
        == len(
            expected
        )
    )

    print(
        "Lifecycle Source Contract Verification"
    )

    print(
        "--------------------------------------"
    )

    print(
        f"Expected sources : "
        f"{len(expected)}"
    )

    print(
        f"Stored sources   : "
        f"{len(actual)}"
    )

    print(
        f"Successful       : "
        f"{successful}"
    )

    print(
        f"Missing          : "
        f"{len(missing)}"
    )

    print(
        f"Extra            : "
        f"{len(extra)}"
    )

    print(
        "Result           : "
        + (
            "PASS"
            if passed
            else "FAIL"
        )
    )

    if not passed:
        raise RuntimeError(
            "Lifecycle contract "
            "verification failed."
        )


if __name__ == "__main__":
    main()