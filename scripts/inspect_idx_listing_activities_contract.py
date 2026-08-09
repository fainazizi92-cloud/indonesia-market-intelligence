import argparse
import re
from dataclasses import dataclass
from time import sleep

import httpx

from imi.features.idx_client_contract import (
    extract_candidate_urls,
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
        "listing-activities-contract-inspector"
    ),
    "Accept": (
        "text/html,"
        "application/javascript,"
        "text/javascript,"
        "application/json,"
        "*/*;q=0.8"
    ),
}


MAX_SCRIPTS = 30

MAX_CONTEXTS = 30

MAX_OCCURRENCES_PER_TERM = 10

CONTEXT_RADIUS = 2200


ACTIVITY_TERMS = (
    "listingactivities",
    "listing-activities",
    "listing activity",
    "listingactivity",
    "new listing",
    "newlisting",
    "delisting",
    "delisted",
    "relisting",
    "relisted",
)


NETWORK_TERMS = (
    "$axios.get",
    "$axios.post",
    "axios.get",
    "axios.post",
    "fetch(",
    "XMLHttpRequest",
    "primary/",
    "/api/",
    "pageNumber",
    "pageSize",
    "start=",
    "length=",
    "search=",
)


FOCUS_TERMS = (
    "listingActivities",
    "listing-activities",
    "listingActivity",
    "New Listing",
    "newListing",
    "Delisting",
    "delisting",
    "Relisting",
    "relisting",
)


REQUEST_STRING_PATTERN = re.compile(
    r"""["']([^"']{1,700})["']"""
)


QUERY_KEY_PATTERN = re.compile(
    r"[?&]"
    r"([A-Za-z][A-Za-z0-9_]*)="
)


@dataclass(
    frozen=True,
    slots=True,
)
class ContractHit:
    source_url: str
    trigger_term: str
    context: str

    request_fragments: tuple[
        str,
        ...
    ]

    query_keys: tuple[
        str,
        ...
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect official IDX Listing "
            "Activities frontend contracts "
            "for New Listing, Delisting, "
            "and Relisting."
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


def contains_any(
    *,
    text: str,
    terms: tuple[str, ...],
) -> bool:
    lowered = (
        text.casefold()
    )

    return any(
        term.casefold()
        in lowered
        for term in terms
    )


def context_is_relevant(
    context: str,
) -> bool:
    return (
        contains_any(
            text=context,
            terms=ACTIVITY_TERMS,
        )
        and contains_any(
            text=context,
            terms=NETWORK_TERMS,
        )
    )


def extract_request_fragments(
    text: str,
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for match in (
        REQUEST_STRING_PATTERN
        .finditer(
            text
        )
    ):
        value = (
            match.group(
                1
            )
            .strip()
        )

        if not value:
            continue

        lowered = (
            value.casefold()
        )

        interesting = (
            "primary/"
            in lowered
            or "/api/"
            in lowered
            or "listingactiv"
            in lowered
            or "delist"
            in lowered
            or "relist"
            in lowered
        )

        if not interesting:
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


def extract_query_keys(
    text: str,
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for match in (
        QUERY_KEY_PATTERN
        .finditer(
            text
        )
    ):
        key = match.group(
            1
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        values.append(
            key
        )

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


def find_contract_hits(
    *,
    source_url: str,
    text: str,
) -> tuple[
    ContractHit,
    ...
]:
    lowered = (
        text.casefold()
    )

    results = []

    seen_contexts = set()

    for term in FOCUS_TERMS:
        normalized_term = (
            term.casefold()
        )

        start = 0

        occurrences = 0

        while (
            occurrences
            < MAX_OCCURRENCES_PER_TERM
        ):
            position = (
                lowered.find(
                    normalized_term,
                    start,
                )
            )

            if position < 0:
                break

            occurrences += 1

            start = (
                position
                + len(
                    normalized_term
                )
            )

            context = (
                build_context(
                    text=text,
                    position=position,
                )
            )

            if not context_is_relevant(
                context
            ):
                continue

            if context in seen_contexts:
                continue

            seen_contexts.add(
                context
            )

            results.append(
                ContractHit(
                    source_url=(
                        source_url
                    ),
                    trigger_term=(
                        term
                    ),
                    context=context,
                    request_fragments=(
                        extract_request_fragments(
                            context
                        )
                    ),
                    query_keys=(
                        extract_query_keys(
                            context
                        )
                    ),
                )
            )

            if (
                len(
                    results
                )
                >= MAX_CONTEXTS
            ):
                return tuple(
                    results
                )

    return tuple(
        results
    )


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
    script_urls = (
        extract_script_urls(
            base_url=page_url,
            html=html,
        )
    )

    results = []

    for index, script_url in enumerate(
        script_urls[
            :MAX_SCRIPTS
        ],
        start=1,
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
            )
            .casefold()
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

        results.append(
            (
                script_url,
                response.text,
            )
        )

        if (
            pause > 0
            and index
            < min(
                len(
                    script_urls
                ),
                MAX_SCRIPTS,
            )
        ):
            sleep(
                pause
            )

    return tuple(
        results
    )


def candidate_is_relevant(
    candidate: str,
) -> bool:
    lowered = (
        candidate.casefold()
    )

    return (
        "listing-activ"
        in lowered
        or "listingactiv"
        in lowered
        or "delist"
        in lowered
        or "relist"
        in lowered
        or "listedcompany"
        in lowered
        or "primary/"
        in lowered
        or "/api/"
        in lowered
    )


def collect_candidate_urls(
    *,
    sources: list[
        tuple[
            str,
            str,
        ]
    ],
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for (
        source_url,
        source_text,
    ) in sources:
        candidates = (
            extract_candidate_urls(
                base_url=source_url,
                text=source_text,
            )
        )

        for candidate in candidates:
            if not candidate_is_relevant(
                candidate
            ):
                continue

            if candidate in seen:
                continue

            seen.add(
                candidate
            )

            values.append(
                candidate
            )

    return tuple(
        values
    )


def collect_request_fragments(
    hits: list[
        ContractHit
    ],
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for hit in hits:
        for fragment in (
            hit.request_fragments
        ):
            if fragment in seen:
                continue

            seen.add(
                fragment
            )

            values.append(
                fragment
            )

    return tuple(
        values
    )


def collect_query_keys(
    hits: list[
        ContractHit
    ],
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for hit in hits:
        for key in (
            hit.query_keys
        ):
            if key in seen:
                continue

            seen.add(
                key
            )

            values.append(
                key
            )

    return tuple(
        values
    )


def print_hit(
    *,
    hit: ContractHit,
    index: int,
) -> None:
    print(
        f"CONTEXT {index}"
    )

    print(
        f"  Source       : "
        f"{hit.source_url}"
    )

    print(
        f"  Trigger      : "
        f"{hit.trigger_term}"
    )

    print(
        "  Query keys   : "
        + (
            ", ".join(
                hit.query_keys
            )
            if hit.query_keys
            else "-"
        )
    )

    print(
        f"  Requests     : "
        f"{len(hit.request_fragments)}"
    )

    for fragment in (
        hit.request_fragments
    ):
        print(
            f"    R {fragment}"
        )

    print(
        "  Context:"
    )

    print(
        "    "
        + hit.context
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
        "IDX Listing Activities "
        "Contract Inspector V1"
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
            f"Scripts    : "
            f"{len(scripts)}"
        )

        print()

        sources = [
            (
                str(
                    page_response.url
                ),
                page_response.text,
            )
        ]

        sources.extend(
            scripts
        )

        candidates = (
            collect_candidate_urls(
                sources=sources
            )
        )

        all_hits = []

        for (
            source_url,
            source_text,
        ) in sources:
            all_hits.extend(
                find_contract_hits(
                    source_url=(
                        source_url
                    ),
                    text=(
                        source_text
                    ),
                )
            )

        request_fragments = (
            collect_request_fragments(
                all_hits
            )
        )

        query_keys = (
            collect_query_keys(
                all_hits
            )
        )

        print(
            "SUMMARY"
        )

        print(
            f"  Sources scanned    : "
            f"{len(sources)}"
        )

        print(
            f"  Candidate URLs     : "
            f"{len(candidates)}"
        )

        print(
            f"  Relevant contexts  : "
            f"{len(all_hits)}"
        )

        print(
            f"  Request fragments  : "
            f"{len(request_fragments)}"
        )

        print(
            "  Query keys         : "
            + (
                ", ".join(
                    query_keys
                )
                if query_keys
                else "-"
            )
        )

        print()

        if candidates:
            print(
                "CANDIDATE URLS"
            )

            for candidate in (
                candidates
            ):
                print(
                    f"  U {candidate}"
                )

            print()

        if request_fragments:
            print(
                "REQUEST FRAGMENTS"
            )

            for fragment in (
                request_fragments
            ):
                print(
                    f"  R {fragment}"
                )

            print()

        for index, hit in enumerate(
            all_hits[
                :MAX_CONTEXTS
            ],
            start=1,
        ):
            print_hit(
                hit=hit,
                index=index,
            )

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "Only request contracts directly "
        "observed in official IDX page or "
        "frontend code may be probed next."
    )

    print(
        "Do not infer missing endpoint names, "
        "query parameters, type codes, or "
        "historical coverage."
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