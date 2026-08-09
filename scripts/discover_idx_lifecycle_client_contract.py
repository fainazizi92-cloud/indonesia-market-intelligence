import argparse
from dataclasses import dataclass
from time import sleep

import httpx

from imi.features.idx_client_contract import (
    extract_script_urls,
    scan_client_contract,
)
from imi.features.idx_lifecycle_filter import (
    build_filtered_url,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "client-contract-discovery"
    ),

    "Accept": (
        "text/html,application/javascript,"
        "text/javascript,*/*;q=0.8"
    ),
}


MAX_ASSETS = 30
MAX_CANDIDATES_PRINT = 40
MAX_SNIPPETS_PRINT = 30


@dataclass(
    frozen=True,
    slots=True,
)
class DiscoveryTarget:
    name: str
    slug: str
    year: int
    month: int


TARGETS = (
    DiscoveryTarget(
        name=(
            "NEW_LISTINGS_2025_01"
        ),
        slug=(
            "stock-new-listings"
        ),
        year=2025,
        month=1,
    ),

    DiscoveryTarget(
        name=(
            "DELISTED_2024_10"
        ),
        slug=(
            "delisted-company"
        ),
        year=2024,
        month=10,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover browser-side IDX "
            "lifecycle data contracts."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.15,
    )

    return parser.parse_args()


def shorten(
    value: str,
    *,
    limit: int = 320,
) -> str:
    normalized = " ".join(
        value.split()
    )

    if len(
        normalized
    ) <= limit:
        return normalized

    return (
        normalized[
            :limit - 3
        ]
        + "..."
    )


def fetch_script_assets(
    *,
    client: httpx.Client,
    page_url: str,
    html: str,
    pause: float,
) -> tuple[
    tuple[
        str,
        str,
    ],
    ...,
]:
    script_urls = (
        extract_script_urls(
            base_url=page_url,
            html=html,
        )
    )

    collected = []

    for index, script_url in enumerate(
        script_urls[
            :MAX_ASSETS
        ]
    ):
        try:
            response = client.get(
                script_url
            )

        except httpx.HTTPError:
            continue

        if not response.is_success:
            continue

        content_type = (
            response.headers.get(
                "content-type",
                "",
            ).casefold()
        )

        if (
            "javascript"
            not in content_type
            and not script_url
            .casefold()
            .endswith(
                ".js"
            )
        ):
            continue

        collected.append(
            (
                script_url,
                response.text,
            )
        )

        if (
            index
            < len(
                script_urls
            ) - 1
            and pause > 0
        ):
            sleep(
                pause
            )

    return tuple(
        collected
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

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX Lifecycle Client Contract Discovery"
    )

    print(
        "---------------------------------------"
    )

    print()

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for target in TARGETS:
            page_url = (
                build_filtered_url(
                    slug=target.slug,
                    year=target.year,
                    month=target.month,
                )
            )

            print(
                target.name
            )

            try:
                page_response = client.get(
                    page_url
                )

            except httpx.HTTPError as exc:
                print(
                    "  Page HTTP     : ERROR"
                )

                print(
                    f"  Error         : "
                    f"{type(exc).__name__}"
                )

                print()

                continue

            print(
                f"  Page HTTP     : "
                f"{page_response.status_code}"
            )

            print(
                f"  Page bytes    : "
                f"{len(page_response.content)}"
            )

            script_urls = (
                extract_script_urls(
                    base_url=str(
                        page_response.url
                    ),
                    html=(
                        page_response.text
                    ),
                )
            )

            print(
                f"  Script URLs   : "
                f"{len(script_urls)}"
            )

            scripts = (
                fetch_script_assets(
                    client=client,
                    page_url=str(
                        page_response.url
                    ),
                    html=(
                        page_response.text
                    ),
                    pause=args.pause,
                )
            )

            print(
                f"  Scripts read  : "
                f"{len(scripts)}"
            )

            total_script_bytes = sum(
                len(
                    text.encode(
                        "utf-8",
                        errors="ignore",
                    )
                )
                for _, text
                in scripts
            )

            print(
                f"  Script bytes  : "
                f"{total_script_bytes}"
            )

            scan = (
                scan_client_contract(
                    base_url=str(
                        page_response.url
                    ),
                    html=(
                        page_response.text
                    ),
                    script_texts=(
                        scripts
                    ),
                )
            )

            print(
                f"  URL candidates: "
                f"{len(scan.candidate_urls)}"
            )

            if scan.candidate_urls:
                print(
                    "  Candidate URLs:"
                )

                for url in (
                    scan.candidate_urls[
                        :MAX_CANDIDATES_PRINT
                    ]
                ):
                    print(
                        "    - "
                        + shorten(
                            url,
                            limit=260,
                        )
                    )

            print()

            print(
                f"  Keyword hits  : "
                f"{len(scan.keyword_snippets)}"
            )

            for snippet in (
                scan.keyword_snippets[
                    :MAX_SNIPPETS_PRINT
                ]
            ):
                print(
                    "    K "
                    + shorten(
                        snippet
                    )
                )

            print()

            print(
                f"  Network hits  : "
                f"{len(scan.network_snippets)}"
            )

            for snippet in (
                scan.network_snippets[
                    :MAX_SNIPPETS_PRINT
                ]
            ):
                print(
                    "    N "
                    + shorten(
                        snippet
                    )
                )

            print()

    print(
        "IMPORTANT:"
    )

    print(
        "This is contract discovery only."
    )

    print(
        "No lifecycle rows were written "
        "to the database."
    )


if __name__ == "__main__":
    main()