from imi.db import engine
from imi.features.historical_source_contract import (
    LIFECYCLE_SOURCE_KEYS,
)
from imi.repositories.historical_source_contract import (
    get_contract_counts,
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

        counts = (
            get_contract_counts(
                connection
            )
        )

    latest_map = {
        row[
            "source_key"
        ]:
            row
        for row in latest
        if row[
            "source_key"
        ]
        in expected
    }

    missing = (
        expected
        - set(
            latest_map
        )
    )

    bad_http = 0
    bad_hash = 0
    empty_body = 0

    for source_key in expected:
        row = latest_map.get(
            source_key
        )

        if row is None:
            continue

        http_status = row[
            "http_status"
        ]

        if (
            http_status is None
            or not (
                200
                <= http_status
                <= 299
            )
        ):
            bad_http += 1

        digest = row[
            "body_sha256"
        ]

        if (
            digest is None
            or len(
                digest
            ) != 64
        ):
            bad_hash += 1

        body_length = row[
            "body_length"
        ]

        if (
            body_length is None
            or body_length <= 0
        ):
            empty_body += 1

    candidate_sources = sum(
        row[
            "candidate_url_count"
        ] > 0
        for row in latest_map.values()
    )

    candidate_ready = sum(
        row[
            "parser_status"
        ]
        == "CANDIDATE"
        for row in latest_map.values()
    )

    quality_pass = (
        not missing
        and bad_http == 0
        and bad_hash == 0
        and empty_body == 0
    )

    print(
        "Lifecycle Source Contract Audit"
    )

    print(
        "-------------------------------"
    )

    print(
        f"Expected lifecycle sources : "
        f"{len(expected)}"
    )

    print(
        f"Latest inspected sources   : "
        f"{len(latest_map)}"
    )

    print(
        f"Missing sources            : "
        f"{len(missing)}"
    )

    print(
        f"Bad HTTP                   : "
        f"{bad_http}"
    )

    print(
        f"Bad body hash              : "
        f"{bad_hash}"
    )

    print(
        f"Empty body                 : "
        f"{empty_body}"
    )

    print(
        f"Sources with candidates    : "
        f"{candidate_sources}"
    )

    print(
        f"Candidate parser status    : "
        f"{candidate_ready}"
    )

    print()

    print(
        "Contract quality : "
        + (
            "PASS"
            if quality_pass
            else "FAIL"
        )
    )

    print()

    print(
        "Contract history:"
    )

    print(
        f"Total snapshots   : "
        f"{counts['total_snapshots']}"
    )

    print(
        f"Distinct sources  : "
        f"{counts['distinct_sources']}"
    )

    print(
        f"Successful        : "
        f"{counts['successful_snapshots']}"
    )

    print(
        f"With candidates   : "
        f"{counts['candidate_snapshots']}"
    )

    print()

    print(
        "STRICT HISTORICAL READINESS:"
    )

    print(
        "READY : NO"
    )

    print(
        "Historical lifecycle rows "
        "have not been reconstructed."
    )

    if not quality_pass:
        raise RuntimeError(
            "Lifecycle source contract "
            "audit failed."
        )


if __name__ == "__main__":
    main()