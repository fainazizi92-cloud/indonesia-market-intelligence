import argparse
from dataclasses import dataclass
from time import sleep

import httpx

from imi.features.idx_client_contract import (
    extract_candidate_urls,
    extract_script_urls,
)
from imi.features.idx_lifecycle_filter import (
    build_filtered_url,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "delisting-api-usage-inspector"
    ),
    "Accept": (
        "text/html,"
        "application/javascript,"
        "text/javascript,"
        "*/*;q=0.8"
    ),
}


MAX_SCRIPTS = 30

MAX_MATCHES_PER_TERM = 5

MAX_CONTEXTS_TOTAL = 40

CONTEXT_RADIUS = 1800


FOCUS_TERMS = (
    "stockdelisting",
    'alias:"DELISTING"',
    "tableChartList",
    "apiUrl",
    "periodYear",
    "periodMonth",
    "periodType",
)


NETWORK_TERMS = (
    "$axios.get",
    "axios.get",
    ".get(",
    "fetch(",
    "XMLHttpRequest",
    "pageNumber",
    "pageSize",
    "periodYear",
    "periodMonth",
    "periodType",
    "cumulative",
)


@dataclass(
    frozen=True,
    slots=True,
)
class ContextHit:
    source_url: str
    term: str
    context: str
    has_network_hint: bool
    has_delisting_hint: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect how official IDX "
            "frontend code consumes the "
            "delisting apiUrl contract."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2024,
    )

    parser.add_argument(
        "--month",
        type=int,
        default=10,
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
    if args.year < 1900:
        raise ValueError(
            "year must be 1900 or later."
        )

    if not 1 <= args.month <= 12:
        raise ValueError(
            "month must be between "
            "1 and 12."
        )

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
        len(text),
        position + CONTEXT_RADIUS,
    )

    return compact_text(
        text[
            start:end
        ]
    )


def has_any(
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
    lowered = (
        context.casefold()
    )

    if (
        "stockdelisting"
        in lowered
    ):
        return True

    if (
        "tablechartlist"
        in lowered
        and "apiurl"
        in lowered
    ):
        return True

    return (
        "apiurl"
        in lowered
        and has_any(
            text=context,
            terms=NETWORK_TERMS,
        )
    )


def find_context_hits(
    *,
    source_url: str,
    text: str,
) -> tuple[
    ContextHit,
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
        count = 0

        while (
            count
            < MAX_MATCHES_PER_TERM
        ):
            position = lowered.find(
                normalized_term,
                start,
            )

            if position < 0:
                break

            context = build_context(
                text=text,
                position=position,
            )

            start = (
                position
                + len(
                    normalized_term
                )
            )

            count += 1

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
                ContextHit(
                    source_url=(
                        source_url
                    ),
                    term=term,
                    context=context,
                    has_network_hint=(
                        has_any(
                            text=context,
                            terms=(
                                NETWORK_TERMS
                            ),
                        )
                    ),
                    has_delisting_hint=(
                        "stockdelisting"
                        in context.casefold()
                        or "delisting"
                        in context.casefold()
                    ),
                )
            )

            if (
                len(results)
                >= MAX_CONTEXTS_TOTAL
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

        results.append(
            (
                script_url,
                response.text,
            )
        )

        if (
            pause > 0
            and index
            < len(
                script_urls
            )
        ):
            sleep(
                pause
            )

    return tuple(
        results
    )


def print_candidates(
    *,
    source_url: str,
    text: str,
) -> int:
    candidates = (
        extract_candidate_urls(
            base_url=source_url,
            text=text,
        )
    )

    selected = []

    for candidate in candidates:
        lowered = (
            candidate.casefold()
        )

        if (
            "delist"
            in lowered
            or "statisticalhighlight"
            in lowered
            or "digitalstatistic"
            in lowered
        ):
            selected.append(
                candidate
            )

    if not selected:
        return 0

    print(
        f"  Candidate URLs from "
        f"{source_url}"
    )

    for candidate in selected:
        print(
            f"    U {candidate}"
        )

    return len(
        selected
    )


def print_hit(
    *,
    hit: ContextHit,
    index: int,
) -> None:
    print(
        f"CONTEXT {index}"
    )

    print(
        f"  Source          : "
        f"{hit.source_url}"
    )

    print(
        f"  Trigger term    : "
        f"{hit.term}"
    )

    print(
        f"  Network hint    : "
        f"{hit.has_network_hint}"
    )

    print(
        f"  Delisting hint  : "
        f"{hit.has_delisting_hint}"
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

    page_url = (
        build_filtered_url(
            slug=(
                "delisted-company"
            ),
            year=args.year,
            month=args.month,
        )
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX Delisting API Usage Inspector V1"
    )

    print(
        "------------------------------------"
    )

    print(
        f"Target year  : {args.year}"
    )

    print(
        f"Target month : {args.month}"
    )

    print(
        f"Page URL     : {page_url}"
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
                    page_url
                )
            )

        except httpx.HTTPError as exc:
            print(
                "Page HTTP    : ERROR"
            )

            print(
                f"Error        : "
                f"{type(exc).__name__}"
            )

            print(
                f"Detail       : "
                f"{exc}"
            )

            return

        print(
            f"Page HTTP    : "
            f"{page_response.status_code}"
        )

        print(
            f"Page bytes   : "
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
            f"Scripts read : "
            f"{len(scripts)}"
        )

        print()

        all_sources = [
            (
                str(
                    page_response.url
                ),
                page_response.text,
            )
        ]

        all_sources.extend(
            scripts
        )

        candidate_count = 0

        all_hits = []

        for (
            source_url,
            source_text,
        ) in all_sources:
            candidate_count += (
                print_candidates(
                    source_url=(
                        source_url
                    ),
                    text=source_text,
                )
            )

            hits = (
                find_context_hits(
                    source_url=(
                        source_url
                    ),
                    text=source_text,
                )
            )

            all_hits.extend(
                hits
            )

        print()

        print(
            f"Candidate URL count : "
            f"{candidate_count}"
        )

        print(
            f"Relevant contexts   : "
            f"{len(all_hits)}"
        )

        print()

        for index, hit in enumerate(
            all_hits[
                :MAX_CONTEXTS_TOTAL
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
        "Do not construct or call a "
        "new delisting endpoint solely "
        "from parameter guesses."
    )

    print(
        "Only an endpoint/request pattern "
        "directly visible in IDX frontend "
        "code should be promoted to the "
        "next probe."
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