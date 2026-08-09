import argparse
import json
from dataclasses import dataclass
from typing import Any

import httpx

from imi.features.idx_lifecycle_api_probe import (
    build_delisting_stat_url,
    build_new_listing_api_url,
    build_page_metadata_url,
    summarize_json,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "lifecycle-api-probe"
    ),

    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),

    "Referer": (
        "https:"
        + "//www.idx.id/"
    ),
}


NEW_LISTING_ROUTE = (
    "/en/market-data/"
    "statistical-reports/"
    "digital-statistic/"
    "monthly/"
    "corporate-action-of-listed-companies/"
    "stock-new-listings"
)


DELISTED_ROUTE = (
    "/en/market-data/"
    "statistical-reports/"
    "digital-statistic/"
    "monthly/"
    "corporate-action-of-listed-companies/"
    "delisted-company"
)


@dataclass(
    frozen=True,
    slots=True,
)
class ProbeTarget:
    name: str
    url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe known read-only IDX "
            "lifecycle API contracts."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    return parser.parse_args()


def make_targets() -> tuple[
    ProbeTarget,
    ...
]:
    return (
        ProbeTarget(
            name=(
                "NEW_LISTINGS_2025_01"
            ),
            url=(
                build_new_listing_api_url(
                    year=2025,
                    month=1,
                )
            ),
        ),

        ProbeTarget(
            name=(
                "NEW_LISTINGS_2024_11"
            ),
            url=(
                build_new_listing_api_url(
                    year=2024,
                    month=11,
                )
            ),
        ),

        ProbeTarget(
            name=(
                "NEW_LISTING_PAGE_METADATA"
            ),
            url=(
                build_page_metadata_url(
                    route_path=(
                        NEW_LISTING_ROUTE
                    )
                )
            ),
        ),

        ProbeTarget(
            name=(
                "DELISTED_PAGE_METADATA"
            ),
            url=(
                build_page_metadata_url(
                    route_path=(
                        DELISTED_ROUTE
                    )
                )
            ),
        ),

        ProbeTarget(
            name=(
                "DELISTING_STAT_BARE"
            ),
            url=(
                build_delisting_stat_url()
            ),
        ),
    )


def compact_preview(
    payload: Any,
    *,
    limit: int = 1800,
) -> str:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        default=str,
        separators=(
            ",",
            ":",
        ),
    )

    if len(
        text
    ) <= limit:
        return text

    return (
        text[
            :limit - 3
        ]
        + "..."
    )


def main() -> None:
    args = parse_args()

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    targets = make_targets()

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX Lifecycle Direct API Probe V1"
    )

    print(
        "---------------------------------"
    )

    print(
        f"Targets : "
        f"{len(targets)}"
    )

    print()

    successful_http = 0
    valid_json = 0

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for target in targets:
            print(
                target.name
            )

            print(
                f"  URL          : "
                f"{target.url}"
            )

            try:
                response = client.get(
                    target.url
                )

            except httpx.HTTPError as exc:
                print(
                    "  HTTP         : ERROR"
                )

                print(
                    f"  Error        : "
                    f"{type(exc).__name__}"
                )

                print(
                    f"  Detail       : "
                    f"{exc}"
                )

                print()

                continue

            print(
                f"  HTTP         : "
                f"{response.status_code}"
            )

            print(
                f"  Content type : "
                f"{response.headers.get('content-type')}"
            )

            print(
                f"  Bytes        : "
                f"{len(response.content)}"
            )

            if response.is_success:
                successful_http += 1

            try:
                payload = (
                    response.json()
                )

            except ValueError:
                print(
                    "  JSON         : NO"
                )

                preview = (
                    " ".join(
                        response.text.split()
                    )
                )

                print(
                    "  Body preview : "
                    + preview[
                        :1000
                    ]
                )

                print()

                continue

            valid_json += 1

            print(
                "  JSON         : YES"
            )

            shape = (
                summarize_json(
                    payload
                )
            )

            print(
                f"  Payload type : "
                f"{shape.payload_type}"
            )

            print(
                "  Top keys     : "
                + (
                    ", ".join(
                        shape.top_keys
                    )
                    if shape.top_keys
                    else "-"
                )
            )

            print(
                f"  Data type    : "
                f"{shape.data_type}"
            )

            print(
                "  Data keys    : "
                + (
                    ", ".join(
                        shape.data_keys
                    )
                    if shape.data_keys
                    else "-"
                )
            )

            print(
                "  Meta keys    : "
                + (
                    ", ".join(
                        shape.meta_keys
                    )
                    if shape.meta_keys
                    else "-"
                )
            )

            print(
                f"  Item count   : "
                f"{shape.item_count}"
            )

            print(
                "  First keys   : "
                + (
                    ", ".join(
                        shape.first_item_keys
                    )
                    if shape.first_item_keys
                    else "-"
                )
            )

            print(
                "  JSON preview :"
            )

            print(
                "    "
                + compact_preview(
                    payload
                )
            )

            print()

    print(
        "Summary:"
    )

    print(
        f"HTTP successful : "
        f"{successful_http}/"
        f"{len(targets)}"
    )

    print(
        f"Valid JSON      : "
        f"{valid_json}/"
        f"{len(targets)}"
    )

    print()

    print(
        "HISTORICAL INGESTION:"
    )

    print(
        "APPROVED : NO"
    )

    print(
        "This probe only inspects "
        "response contracts."
    )

    print(
        "No lifecycle records were "
        "written to the database."
    )


if __name__ == "__main__":
    main()
    