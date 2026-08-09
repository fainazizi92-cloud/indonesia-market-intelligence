import argparse
from dataclasses import dataclass
from time import sleep

import httpx

from imi.features.idx_client_contract import (
    extract_script_urls,
)
from imi.features.idx_lifecycle_endpoint_contract import (
    EndpointEvidence,
    find_endpoint_evidence,
)
from imi.features.idx_lifecycle_filter import (
    build_filtered_url,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "lifecycle-endpoint-inspector"
    ),

    "Accept": (
        "text/html,"
        "application/javascript,"
        "text/javascript,"
        "*/*;q=0.8"
    ),
}


@dataclass(
    frozen=True,
    slots=True,
)
class Target:
    name: str

    slug: str

    year: int
    month: int

    needles: tuple[
        str,
        ...
    ]


TARGETS = (
    Target(
        name=(
            "NEW_LISTINGS_2025_01"
        ),

        slug=(
            "stock-new-listings"
        ),

        year=2025,
        month=1,

        needles=(
            "GetApiDataPaginated",
            "LINK_STOCK_NEW_LISTING",
            "periodYear",
            "periodMonth",
            "pageSize",
            "pageNumber",
        ),
    ),

    Target(
        name=(
            "DELISTED_2024_10"
        ),

        slug=(
            "delisted-company"
        ),

        year=2024,
        month=10,

        needles=(
            "stockdelisting",
            'alias:"DELISTING"',
            "delistedCompany",
            "apiUrl",
            "downloadCode",
        ),
    ),
)


MAX_SCRIPTS = 30
CONTEXT_RADIUS = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect exact IDX lifecycle "
            "API contracts discovered "
            "from official page assets."
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
        default=0.10,
    )

    return parser.parse_args()


def fetch_scripts(
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
    ...
]:
    urls = (
        extract_script_urls(
            base_url=page_url,
            html=html,
        )
    )

    results = []

    for index, url in enumerate(
        urls[
            :MAX_SCRIPTS
        ]
    ):
        try:
            response = client.get(
                url
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
            and not url
            .casefold()
            .endswith(
                ".js"
            )
        ):
            continue

        results.append(
            (
                url,
                response.text,
            )
        )

        if (
            pause > 0
            and index
            < len(
                urls
            ) - 1
        ):
            sleep(
                pause
            )

    return tuple(
        results
    )


def print_evidence(
    *,
    evidence: EndpointEvidence,
    number: int,
) -> None:
    print(
        f"  Evidence {number}"
    )

    print(
        f"    Source      : "
        f"{evidence.source_url}"
    )

    print(
        f"    Needle      : "
        f"{evidence.needle}"
    )

    print(
        "    Query keys  : "
        + (
            ", ".join(
                evidence.query_keys
            )
            if evidence.query_keys
            else "-"
        )
    )

    print(
        f"    Endpoints   : "
        f"{len(evidence.endpoint_fragments)}"
    )

    for endpoint in (
        evidence.endpoint_fragments
    ):
        print(
            f"      E {endpoint}"
        )

    print(
        "    Context:"
    )

    print(
        "      "
        + evidence.context
    )

    print()


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
        "IDX Lifecycle Exact Endpoint Inspector"
    )

    print(
        "--------------------------------------"
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
                page_response = (
                    client.get(
                        page_url
                    )
                )

            except httpx.HTTPError as exc:
                print(
                    "  Page HTTP : ERROR"
                )

                print(
                    f"  Error     : "
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

            scripts = (
                fetch_scripts(
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

            all_evidence = []

            page_evidence = (
                find_endpoint_evidence(
                    source_url=(
                        str(
                            page_response.url
                        )
                    ),
                    text=(
                        page_response.text
                    ),
                    needles=(
                        target.needles
                    ),
                    radius=(
                        CONTEXT_RADIUS
                    ),
                )
            )

            all_evidence.extend(
                page_evidence
            )

            for (
                script_url,
                script_text,
            ) in scripts:
                evidence = (
                    find_endpoint_evidence(
                        source_url=(
                            script_url
                        ),
                        text=(
                            script_text
                        ),
                        needles=(
                            target.needles
                        ),
                        radius=(
                            CONTEXT_RADIUS
                        ),
                    )
                )

                all_evidence.extend(
                    evidence
                )

            print(
                f"  Evidence blocks: "
                f"{len(all_evidence)}"
            )

            print()

            for (
                index,
                evidence,
            ) in enumerate(
                all_evidence,
                start=1,
            ):
                print_evidence(
                    evidence=evidence,
                    number=index,
                )

            if not all_evidence:
                print(
                    "  No targeted endpoint "
                    "evidence found."
                )

                print()

    print(
        "IMPORTANT:"
    )

    print(
        "No API response has been "
        "accepted as canonical data yet."
    )

    print(
        "No lifecycle rows were written."
    )


if __name__ == "__main__":
    main()