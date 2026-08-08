import argparse
from time import sleep

from imi.collectors.historical_source_contract import (
    create_contract_client,
    inspect_contract,
)
from imi.db import engine
from imi.features.historical_source import (
    historical_source_definitions,
)
from imi.features.historical_source_contract import (
    LIFECYCLE_SOURCE_KEYS,
)
from imi.repositories.historical_source_contract import (
    insert_contract_snapshots,
)

DEFAULT_TIMEOUT = 20.0
DEFAULT_PAUSE = 0.50
MAX_PRINTED_CANDIDATES = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect lifecycle source "
            "contracts without ingesting "
            "historical lifecycle rows."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def shorten(
    value: str,
    *,
    limit: int = 180,
) -> str:
    if len(
        value
    ) <= limit:
        return value

    return (
        value[
            : limit - 3
        ]
        + "..."
    )


def main() -> None:
    args = parse_args()

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )

    definition_map = {
        item.source_key: item
        for item in (
            historical_source_definitions()
        )
    }

    definitions = [
        definition_map[
            source_key
        ]
        for source_key
        in LIFECYCLE_SOURCE_KEYS
    ]

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Lifecycle Source Contract Inspector V1"
    )

    print(
        "--------------------------------------"
    )

    print(
        f"Sources : "
        f"{len(definitions)}"
    )

    print(
        f"Dry run : "
        f"{args.dry_run}"
    )

    print()

    results = []

    with create_contract_client(
        timeout=args.timeout
    ) as client:
        for index, definition in enumerate(
            definitions
        ):
            row = inspect_contract(
                definition,
                client=client,
            )

            results.append(
                row
            )

            print(
                definition.source_key
            )

            print(
                f"  HTTP          : "
                f"{row['http_status']}"
            )

            print(
                f"  Content type  : "
                f"{row['content_type']}"
            )

            print(
                f"  Body bytes    : "
                f"{row['body_length']}"
            )

            print(
                f"  Anchors       : "
                f"{row['anchor_count']}"
            )

            print(
                f"  Scripts       : "
                f"{row['script_count']}"
            )

            print(
                f"  Forms         : "
                f"{row['form_count']}"
            )

            print(
                f"  Candidates    : "
                f"{row['candidate_url_count']}"
            )

            print(
                f"  Parser status : "
                f"{row['parser_status']}"
            )

            if row[
                "error_type"
            ]:
                print(
                    f"  Error         : "
                    f"{row['error_type']}"
                )

            candidates = row[
                "candidate_urls"
            ]

            if candidates:
                print(
                    "  Candidate URLs:"
                )

                for candidate in (
                    candidates[
                        :MAX_PRINTED_CANDIDATES
                    ]
                ):
                    print(
                        "    - "
                        + shorten(
                            candidate
                        )
                    )

                remaining = (
                    len(
                        candidates
                    )
                    - MAX_PRINTED_CANDIDATES
                )

                if remaining > 0:
                    print(
                        f"    ... "
                        f"{remaining} more"
                    )

            hints = row[
                "endpoint_hints"
            ]

            print(
                "  Hint counts:"
            )

            for key in (
                "download_like",
                "api_like",
                "primary_like",
                "idx_domain",
            ):
                print(
                    f"    "
                    f"{key:<14}: "
                    f"{len(hints.get(key, []))}"
                )

            print()

            if (
                index
                < len(definitions) - 1
                and args.pause > 0
            ):
                sleep(
                    args.pause
                )

    if args.dry_run:
        written = 0
    else:
        with engine.begin() as connection:
            written = (
                insert_contract_snapshots(
                    connection,
                    rows=results,
                )
            )

    successful = sum(
        row[
            "http_status"
        ] is not None
        and 200
        <= row[
            "http_status"
        ]
        <= 299
        for row in results
    )

    candidate_sources = sum(
        row[
            "candidate_url_count"
        ] > 0
        for row in results
    )

    print(
        "Summary:"
    )

    print(
        f"Successful routes : "
        f"{successful}/"
        f"{len(results)}"
    )

    print(
        f"Candidate sources : "
        f"{candidate_sources}/"
        f"{len(results)}"
    )

    print(
        f"Rows written      : "
        f"{written}"
    )

    print()

    print(
        "HISTORICAL LIFECYCLE INGESTION:"
    )

    print(
        "APPROVED : NO"
    )

    print(
        "Contract candidates must be "
        "validated before a parser "
        "writes lifecycle history."
    )


if __name__ == "__main__":
    main()