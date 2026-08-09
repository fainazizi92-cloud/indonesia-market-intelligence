import argparse
import hashlib
from time import sleep

import httpx

from imi.features.idx_client_contract import (
    extract_script_urls,
)
from imi.features.idx_lifecycle_api_probe import (
    build_page_metadata_url,
)
from imi.features.idx_lifecycle_filter import (
    build_filtered_url,
)
from imi.features.idx_report_contract import (
    build_report_url,
    extract_digital_stat_metadata,
    extract_download_types,
)

DELISTED_ROUTE = (
    "/en/market-data/"
    "statistical-reports/"
    "digital-statistic/"
    "monthly/"
    "corporate-action-of-listed-companies/"
    "delisted-company"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "delisting-report-probe"
    ),

    "Accept": "*/*",

    "Referer": (
        "https:"
        + "//www.idx.id/"
    ),
}


MAX_SCRIPTS = 30

MAX_RESPONSE_BYTES = (
    20
    * 1024
    * 1024
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover and probe the "
            "official IDX delisting "
            "report download contract."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.10,
    )

    return parser.parse_args()


def fetch_script_texts(
    *,
    client: httpx.Client,
    page_url: str,
    html: str,
    pause: float,
) -> tuple[str, ...]:
    urls = (
        extract_script_urls(
            base_url=page_url,
            html=html,
        )
    )

    texts = []

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

        texts.append(
            response.text
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
        texts
    )


def read_limited_response(
    response: httpx.Response,
) -> tuple[
    bytes,
    bool,
]:
    buffer = bytearray()

    truncated = False

    for chunk in (
        response.iter_bytes()
    ):
        remaining = (
            MAX_RESPONSE_BYTES
            - len(
                buffer
            )
        )

        if remaining <= 0:
            truncated = True
            break

        if len(
            chunk
        ) > remaining:
            buffer.extend(
                chunk[
                    :remaining
                ]
            )

            truncated = True
            break

        buffer.extend(
            chunk
        )

    return (
        bytes(
            buffer
        ),
        truncated,
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
        "IDX Delisting Report Contract Probe V1"
    )

    print(
        "--------------------------------------"
    )

    print()

    page_url = (
        build_filtered_url(
            slug=(
                "delisted-company"
            ),
            year=2024,
            month=10,
        )
    )

    metadata_url = (
        build_page_metadata_url(
            route_path=(
                DELISTED_ROUTE
            )
        )
    )

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        metadata_response = (
            client.get(
                metadata_url
            )
        )

        print(
            f"Metadata HTTP : "
            f"{metadata_response.status_code}"
        )

        metadata_response.raise_for_status()

        metadata = (
            extract_digital_stat_metadata(
                metadata_response.json()
            )
        )

        print(
            f"Download code : "
            f"{metadata.download_code}"
        )

        print(
            f"Page title    : "
            f"{metadata.title}"
        )

        print(
            "Aliases       : "
            + (
                ", ".join(
                    metadata.aliases
                )
                if metadata.aliases
                else "-"
            )
        )

        print(
            "API URLs      : "
            + (
                ", ".join(
                    metadata.api_urls
                )
                if metadata.api_urls
                else "-"
            )
        )

        print()

        page_response = (
            client.get(
                page_url
            )
        )

        print(
            f"Page HTTP     : "
            f"{page_response.status_code}"
        )

        page_response.raise_for_status()

        scripts = (
            fetch_script_texts(
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

        download_types = []

        seen = set()

        for script_text in scripts:
            for report_type in (
                extract_download_types(
                    script_text
                )
            ):
                if (
                    report_type
                    in seen
                ):
                    continue

                seen.add(
                    report_type
                )

                download_types.append(
                    report_type
                )

        print(
            f"Scripts read  : "
            f"{len(scripts)}"
        )

        print(
            "Report types  : "
            + (
                ", ".join(
                    download_types
                )
                if download_types
                else "-"
            )
        )

        print()

        if not download_types:
            print(
                "No literal report type "
                "was discovered."
            )

        for report_type in (
            download_types
        ):
            report_url = (
                build_report_url(
                    report_type=(
                        report_type
                    ),
                    year=2024,
                    month=10,
                    download_code=(
                        metadata
                        .download_code
                    ),
                    filename=(
                        metadata.title
                    ),
                )
            )

            print(
                f"REPORT {report_type}"
            )

            print(
                f"  URL          : "
                f"{report_url}"
            )

            try:
                with client.stream(
                    "GET",
                    report_url,
                ) as response:
                    content, truncated = (
                        read_limited_response(
                            response
                        )
                    )

                    print(
                        f"  HTTP         : "
                        f"{response.status_code}"
                    )

                    print(
                        f"  Content type : "
                        f"{response.headers.get('content-type')}"
                    )

                    print(
                        f"  Disposition  : "
                        f"{response.headers.get('content-disposition')}"
                    )

                    print(
                        f"  Bytes read   : "
                        f"{len(content)}"
                    )

                    print(
                        f"  Truncated    : "
                        f"{truncated}"
                    )

                    print(
                        f"  SHA256       : "
                        f"{hashlib.sha256(content).hexdigest()}"
                    )

                    print(
                        "  First bytes  : "
                        f"{content[:24].hex()}"
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

    print(
        "DATABASE WRITE:"
    )

    print(
        "ENABLED : NO"
    )

    print(
        "No historical lifecycle "
        "records were persisted."
    )


if __name__ == "__main__":
    main()