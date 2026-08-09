import argparse
import re
from collections import deque
from dataclasses import dataclass
from time import sleep
from urllib.parse import urljoin, urlsplit

import httpx

from imi.features.idx_client_contract import (
    extract_script_urls,
)

IDX_ORIGIN = (
    "https:"
    + "//www.idx.id"
)


LISTING_ACTIVITIES_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "listing-content-component-inspector"
    ),
    "Accept": (
        "text/html,"
        "application/javascript,"
        "text/javascript,"
        "*/*;q=0.8"
    ),
}


MAX_INITIAL_SCRIPTS = 30

MAX_ASSETS = 80

MAX_DEPTH = 2

MAX_CONTEXTS = 20

CONTEXT_RADIUS = 3000


MODULE_ID = "1753"


EXACT_MARKERS = (
    "1753:function",
    "1753:",
    "dataTable",
    "data-table",
    "this.dataTable",
)


REQUEST_MARKERS = (
    "$axios.get",
    "$axios.$get",
    "$axios.post",
    "$axios.$post",
    "axios.get",
    "axios.post",
    "fetch(",
)


PARAMETER_MARKERS = (
    "params:",
    "pageNumber",
    "pageSize",
    "page:",
    "size:",
    "start:",
    "length:",
    "year:",
    "search:",
    "keyword:",
    "status:",
    "tab:",
)


EMBEDDED_JS_PATTERN = re.compile(
    r"""
    (?:
        https?:)?//www\.idx\.id
        /_nuxt/
        [A-Za-z0-9._/-]+\.js
    |
        /_nuxt/
        [A-Za-z0-9._/-]+\.js
    |
        ["']
        ([A-Za-z0-9._/-]+\.js)
        ["']
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


WEBPACK_CHUNK_PATTERN = re.compile(
    r"""
    \.push\(
        \[
            \[
                ([0-9,\s]+)
            \]
            ,
            \{
    """,
    flags=re.VERBOSE,
)


@dataclass(
    frozen=True,
    slots=True,
)
class Asset:
    url: str
    text: str
    depth: int


@dataclass(
    frozen=True,
    slots=True,
)
class Evidence:
    source_url: str
    marker: str
    context: str

    has_request_marker: bool

    parameter_markers: tuple[
        str,
        ...
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover the implementation "
            "contract of IDX LazyListingContent "
            "without calling lifecycle APIs."
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
        default=0.08,
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )


def compact_text(
    text: str,
) -> str:
    return " ".join(
        text.split()
    )


def same_idx_origin(
    url: str,
) -> bool:
    parsed = urlsplit(
        url
    )

    return (
        parsed.scheme
        in {
            "http",
            "https",
        }
        and parsed.netloc.casefold()
        in {
            "www.idx.id",
            "idx.id",
        }
    )


def normalize_js_url(
    *,
    source_url: str,
    candidate: str,
) -> str | None:
    normalized = (
        candidate.strip()
        .strip(
            "\"'"
        )
    )

    if not normalized:
        return None

    if normalized.startswith(
        "//"
    ):
        normalized = (
            "https:"
            + normalized
        )

    absolute = urljoin(
        source_url,
        normalized,
    )

    if not same_idx_origin(
        absolute
    ):
        return None

    if not (
        urlsplit(
            absolute
        )
        .path
        .casefold()
        .endswith(
            ".js"
        )
    ):
        return None

    return absolute


def extract_embedded_js_urls(
    *,
    source_url: str,
    text: str,
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for match in (
        EMBEDDED_JS_PATTERN
        .finditer(
            text
        )
    ):
        raw = match.group(
            0
        )

        captured = match.group(
            1
        )

        if captured:
            raw = captured

        normalized = (
            normalize_js_url(
                source_url=source_url,
                candidate=raw,
            )
        )

        if normalized is None:
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        values.append(
            normalized
        )

    return tuple(
        values
    )


def extract_chunk_ids(
    text: str,
) -> tuple[
    int,
    ...
]:
    values = []

    seen = set()

    for match in (
        WEBPACK_CHUNK_PATTERN
        .finditer(
            text
        )
    ):
        raw_values = (
            match.group(
                1
            )
            .split(
                ","
            )
        )

        for raw in raw_values:
            normalized = (
                raw.strip()
            )

            if not normalized:
                continue

            try:
                value = int(
                    normalized
                )

            except ValueError:
                continue

            if value in seen:
                continue

            seen.add(
                value
            )

            values.append(
                value
            )

    return tuple(
        values
    )


def marker_positions(
    *,
    text: str,
    marker: str,
) -> tuple[
    int,
    ...
]:
    lowered = (
        text.casefold()
    )

    target = (
        marker.casefold()
    )

    values = []

    start = 0

    while True:
        position = lowered.find(
            target,
            start,
        )

        if position < 0:
            break

        values.append(
            position
        )

        start = (
            position
            + len(
                target
            )
        )

        if len(
            values
        ) >= 10:
            break

    return tuple(
        values
    )


def build_context(
    *,
    text: str,
    position: int,
) -> str:
    start = max(
        0,
        position - CONTEXT_RADIUS,
    )

    end = min(
        len(
            text
        ),
        position + CONTEXT_RADIUS,
    )

    return compact_text(
        text[
            start:end
        ]
    )


def contains_request_marker(
    text: str,
) -> bool:
    lowered = (
        text.casefold()
    )

    return any(
        marker.casefold()
        in lowered
        for marker in REQUEST_MARKERS
    )


def found_parameter_markers(
    text: str,
) -> tuple[
    str,
    ...
]:
    lowered = (
        text.casefold()
    )

    values = []

    for marker in (
        PARAMETER_MARKERS
    ):
        if (
            marker.casefold()
            in lowered
        ):
            values.append(
                marker
            )

    return tuple(
        values
    )


def relevant_context(
    *,
    marker: str,
    context: str,
) -> bool:
    lowered = (
        context.casefold()
    )

    if marker.startswith(
        MODULE_ID
    ):
        return True

    if (
        "datatable"
        in lowered
        or "data-table"
        in lowered
    ):
        return (
            contains_request_marker(
                context
            )
            or "params:"
            in lowered
            or "status"
            in lowered
        )

    return False


def find_evidence(
    *,
    asset: Asset,
) -> tuple[
    Evidence,
    ...
]:
    values = []

    seen = set()

    for marker in (
        EXACT_MARKERS
    ):
        positions = (
            marker_positions(
                text=asset.text,
                marker=marker,
            )
        )

        for position in positions:
            context = (
                build_context(
                    text=asset.text,
                    position=position,
                )
            )

            if not relevant_context(
                marker=marker,
                context=context,
            ):
                continue

            key = (
                marker,
                context,
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            values.append(
                Evidence(
                    source_url=(
                        asset.url
                    ),
                    marker=marker,
                    context=context,
                    has_request_marker=(
                        contains_request_marker(
                            context
                        )
                    ),
                    parameter_markers=(
                        found_parameter_markers(
                            context
                        )
                    ),
                )
            )

            if (
                len(
                    values
                )
                >= MAX_CONTEXTS
            ):
                return tuple(
                    values
                )

    return tuple(
        values
    )


def fetch_asset(
    *,
    client: httpx.Client,
    url: str,
    depth: int,
) -> Asset | None:
    try:
        response = client.get(
            url
        )

    except httpx.HTTPError:
        return None

    if not response.is_success:
        return None

    content_type = (
        response.headers.get(
            "content-type",
            "",
        )
        .casefold()
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
        return None

    return Asset(
        url=url,
        text=response.text,
        depth=depth,
    )


def crawl_assets(
    *,
    client: httpx.Client,
    page_url: str,
    html: str,
    pause: float,
) -> tuple[
    Asset,
    ...
]:
    initial_urls = (
        extract_script_urls(
            base_url=page_url,
            html=html,
        )
    )

    queue = deque(
        (
            url,
            0,
        )
        for url in initial_urls[
            :MAX_INITIAL_SCRIPTS
        ]
    )

    seen = set()

    assets = []

    while (
        queue
        and len(
            assets
        )
        < MAX_ASSETS
    ):
        (
            url,
            depth,
        ) = queue.popleft()

        if url in seen:
            continue

        seen.add(
            url
        )

        asset = (
            fetch_asset(
                client=client,
                url=url,
                depth=depth,
            )
        )

        if asset is None:
            continue

        assets.append(
            asset
        )

        if depth < MAX_DEPTH:
            embedded = (
                extract_embedded_js_urls(
                    source_url=url,
                    text=asset.text,
                )
            )

            for child_url in embedded:
                if child_url in seen:
                    continue

                queue.append(
                    (
                        child_url,
                        depth + 1,
                    )
                )

        if pause > 0:
            sleep(
                pause
            )

    return tuple(
        assets
    )


def find_module_references(
    *,
    asset: Asset,
) -> tuple[
    str,
    ...
]:
    values = []

    for marker in (
        "n(1753)",
        "1753:function",
        "1753:",
    ):
        positions = marker_positions(
            text=asset.text,
            marker=marker,
        )

        for position in positions:
            context = build_context(
                text=asset.text,
                position=position,
            )

            values.append(
                context
            )

            if len(
                values
            ) >= 5:
                return tuple(
                    values
                )

    return tuple(
        values
    )


def print_evidence(
    *,
    evidence: Evidence,
    index: int,
) -> None:
    print(
        f"EVIDENCE {index}"
    )

    print(
        f"  Source       : "
        f"{evidence.source_url}"
    )

    print(
        f"  Marker       : "
        f"{evidence.marker}"
    )

    print(
        f"  Network call : "
        f"{evidence.has_request_marker}"
    )

    print(
        "  Param markers: "
        + (
            ", ".join(
                evidence.parameter_markers
            )
            if evidence.parameter_markers
            else "-"
        )
    )

    print(
        "  Context:"
    )

    print(
        "    "
        + evidence.context
    )

    print()


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX ListingContent Component "
        "Inspector V1"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Page URL : "
        f"{LISTING_ACTIVITIES_URL}"
    )

    print()

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        try:
            page_response = (
                client.get(
                    LISTING_ACTIVITIES_URL
                )
            )

        except httpx.HTTPError as exc:
            print(
                "Page HTTP  : ERROR"
            )

            print(
                f"Error      : "
                f"{type(exc).__name__}"
            )

            print(
                f"Detail     : "
                f"{exc}"
            )

            return

        print(
            f"Page HTTP  : "
            f"{page_response.status_code}"
        )

        print(
            f"Final URL  : "
            f"{page_response.url}"
        )

        print(
            f"Page bytes : "
            f"{len(page_response.content)}"
        )

        page_response.raise_for_status()

        assets = (
            crawl_assets(
                client=client,
                page_url=str(
                    page_response.url
                ),
                html=page_response.text,
                pause=args.pause,
            )
        )

    print(
        f"JS assets  : "
        f"{len(assets)}"
    )

    print()

    all_chunk_ids = []

    seen_chunk_ids = set()

    module_reference_sources = []

    evidence_items = []

    for asset in assets:
        chunk_ids = (
            extract_chunk_ids(
                asset.text
            )
        )

        for chunk_id in chunk_ids:
            if chunk_id in seen_chunk_ids:
                continue

            seen_chunk_ids.add(
                chunk_id
            )

            all_chunk_ids.append(
                chunk_id
            )

        references = (
            find_module_references(
                asset=asset
            )
        )

        if references:
            module_reference_sources.append(
                (
                    asset.url,
                    references,
                )
            )

        evidence_items.extend(
            find_evidence(
                asset=asset
            )
        )

    print(
        "SUMMARY"
    )

    print(
        f"  Assets scanned        : "
        f"{len(assets)}"
    )

    print(
        f"  Webpack chunk IDs     : "
        f"{len(all_chunk_ids)}"
    )

    print(
        f"  Module 1753 sources   : "
        f"{len(module_reference_sources)}"
    )

    print(
        f"  Relevant evidence     : "
        f"{len(evidence_items)}"
    )

    print()

    if all_chunk_ids:
        print(
            "CHUNK IDS"
        )

        print(
            "  "
            + ", ".join(
                str(
                    value
                )
                for value in (
                    all_chunk_ids
                )
            )
        )

        print()

    if module_reference_sources:
        print(
            "MODULE 1753 REFERENCES"
        )

        for (
            source_url,
            references,
        ) in module_reference_sources:
            print(
                f"  Source: "
                f"{source_url}"
            )

            for reference in references:
                print(
                    "    "
                    + reference
                )

            print()

    if evidence_items:
        print(
            "COMPONENT / REQUEST EVIDENCE"
        )

        print()

        for index, evidence in enumerate(
            evidence_items[
                :MAX_CONTEXTS
            ],
            start=1,
        ):
            print_evidence(
                evidence=evidence,
                index=index,
            )

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "Endpoint query parameters are "
        "not approved until their request "
        "construction is directly observed."
    )

    print(
        "Do not infer year, search, status, "
        "pagination, or type parameters from "
        "UI labels alone."
    )

    print()

    print(
        "DATABASE WRITE:"
    )

    print(
        "ENABLED : NO"
    )


if __name__ == "__main__":
    main()