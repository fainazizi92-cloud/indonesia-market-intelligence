import argparse
from time import sleep

from imi.features.historical_source import (
    evaluate_discovery_readiness,
    historical_source_definitions,
)

from imi.collectors.historical_source_probe import (
    create_probe_client,
    probe_source,
)
from imi.db import engine
from imi.repositories.historical_source import (
    insert_probe_runs,
)

DEFAULT_TIMEOUT = 20.0
DEFAULT_PAUSE = 0.50


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe official historical "
            "IDX source routes without "
            "bulk downloading data."
        )
    )

    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help=(
            "Optional source key. "
            "Can be specified multiple "
            "times."
        ),
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
        help=(
            "Probe routes but do not "
            "write probe history."
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be greater "
            "than zero."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )

    definitions = list(
        historical_source_definitions()
    )

    if args.only:
        requested = {
            value.strip()
            for value in args.only
        }

        known = {
            definition.source_key
            for definition in definitions
        }

        unknown = (
            requested
            - known
        )

        if unknown:
            raise ValueError(
                "Unknown source key(s): "
                + ", ".join(
                    sorted(
                        unknown
                    )
                )
            )

        definitions = [
            definition
            for definition in definitions
            if definition.source_key
            in requested
        ]

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Historical Source Probe V1"
    )

    print(
        "--------------------------"
    )

    print(
        f"Sources       : "
        f"{len(definitions)}"
    )

    print(
        f"Timeout       : "
        f"{args.timeout:.1f}s"
    )

    print(
        f"Pause         : "
        f"{args.pause:.2f}s"
    )

    print(
        f"Dry run       : "
        f"{args.dry_run}"
    )

    print()

    results = []

    with create_probe_client(
        timeout=args.timeout
    ) as client:
        for index, definition in enumerate(
            definitions
        ):
            result = probe_source(
                definition,
                client=client,
            )

            results.append(
                result
            )

            status = (
                "PASS"
                if result.success
                else "FAIL"
            )

            http_status = (
                "-"
                if result.http_status
                is None
                else str(
                    result.http_status
                )
            )

            print(
                f"{definition.source_key:<36} "
                f"{status:<5} "
                f"HTTP={http_status:<3} "
                f"markers="
                f"{result.marker_hits}/"
                f"{result.marker_total} "
                f"{result.elapsed_ms:.0f}ms"
            )

            if (
                not result.success
                and result.error_type
            ):
                print(
                    f"  error: "
                    f"{result.error_type}"
                )

                if result.error_message:
                    print(
                        f"  detail: "
                        f"{result.error_message}"
                    )

            if (
                index
                < len(definitions) - 1
                and args.pause > 0
            ):
                sleep(
                    args.pause
                )

    if not args.dry_run:
        with engine.begin() as connection:
            written = (
                insert_probe_runs(
                    connection,
                    rows=[
                        result
                        .as_repository_row()
                        for result
                        in results
                    ],
                )
            )
    else:
        written = 0

    probe_map = {
        result.source_key: {
            "success":
                result.success,
        }
        for result in results
    }

    readiness = (
        evaluate_discovery_readiness(
            latest_probes=probe_map,
        )
    )

    print()

    print(
        "Summary:"
    )

    print(
        f"Successful     : "
        f"{readiness.successful_probes}"
        f"/{len(results)}"
    )

    print(
        f"Rows written   : "
        f"{written}"
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
        "READY FOR PARSER WORK : "
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
        "This probe validates source "
        "route availability only."
    )

    print(
        "No historical records were "
        "ingested by this script."
    )


if __name__ == "__main__":
    main()