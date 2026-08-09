import argparse
from dataclasses import dataclass

import httpx

from imi.features.idx_lifecycle_filter import (
    build_filtered_url,
    marker_result,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "lifecycle-filter-inspector"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/json,text/plain,"
        "*/*;q=0.8"
    ),
}


@dataclass(
    frozen=True,
    slots=True,
)
class InspectionTarget:
    name: str
    slug: str
    year: int
    month: int
    expected_markers: tuple[
        str,
        ...
    ]


TARGETS = (
    InspectionTarget(
        name=(
            "NEW_LISTINGS_2025_01"
        ),
        slug=(
            "stock-new-listings"
        ),
        year=2025,
        month=1,
        expected_markers=(
            "Code",
            "Company Name",
            "Listing Date",
            "KSIX",
            "RATU",
        ),
    ),
    InspectionTarget(
        name=(
            "NEW_LISTINGS_2024_11"
        ),
        slug=(
            "stock-new-listings"
        ),
        year=2024,
        month=11,
        expected_markers=(
            "Code",
            "Company Name",
            "Listing Date",
            "DAAZ",
            "BOAT",
        ),
    ),
    InspectionTarget(
        name=(
            "DELISTED_2024_10"
        ),
        slug=(
            "delisted-company"
        ),
        year=2024,
        month=10,
        expected_markers=(
            "Code",
            "Company Name",
            "Listing Date",
            "Delisting Date",
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate IDX Digital "
            "Statistics monthly lifecycle "
            "filter contracts."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX Monthly Lifecycle Filter Inspector"
    )

    print(
        "--------------------------------------"
    )

    print()

    successful_http = 0
    marker_complete = 0

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for target in TARGETS:
            url = (
                build_filtered_url(
                    slug=target.slug,
                    year=target.year,
                    month=target.month,
                )
            )

            try:
                response = client.get(
                    url
                )

            except httpx.HTTPError as exc:
                print(
                    target.name
                )

                print(
                    "  HTTP          : ERROR"
                )

                print(
                    f"  Error         : "
                    f"{type(exc).__name__}"
                )

                print(
                    f"  Detail        : "
                    f"{exc}"
                )

                print()

                continue

            if response.is_success:
                successful_http += 1

            (
                found,
                missing,
            ) = marker_result(
                html=response.text,
                markers=(
                    target
                    .expected_markers
                ),
            )

            complete = (
                len(
                    missing
                )
                == 0
            )

            if complete:
                marker_complete += 1

            print(
                target.name
            )

            print(
                f"  HTTP          : "
                f"{response.status_code}"
            )

            print(
                f"  Final URL     : "
                f"{response.url}"
            )

            print(
                f"  Content type  : "
                f"{response.headers.get('content-type')}"
            )

            print(
                f"  Body bytes    : "
                f"{len(response.content)}"
            )

            print(
                f"  Markers found : "
                f"{len(found)}/"
                f"{len(target.expected_markers)}"
            )

            print(
                "  Data markers  : "
                + (
                    "PASS"
                    if complete
                    else "PARTIAL"
                )
            )

            if found:
                print(
                    "  Found:"
                )

                for marker in found:
                    print(
                        f"    + {marker}"
                    )

            if missing:
                print(
                    "  Missing:"
                )

                for marker in missing:
                    print(
                        f"    - {marker}"
                    )

            print()

    print(
        "Summary:"
    )

    print(
        f"HTTP successful : "
        f"{successful_http}/"
        f"{len(TARGETS)}"
    )

    print(
        f"Marker complete : "
        f"{marker_complete}/"
        f"{len(TARGETS)}"
    )

    print()

    print(
        "HISTORICAL INGESTION:"
    )

    print(
        "APPROVED : NO"
    )

    print(
        "This script validates the "
        "filtered-page contract only."
    )


if __name__ == "__main__":
    main()