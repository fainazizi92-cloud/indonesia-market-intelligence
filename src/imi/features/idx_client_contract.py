import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import (
    urljoin,
    urlparse,
)

STRONG_KEYWORDS = (
    "stock-new-listings",
    "delisted-company",
    "digital-statistic",
    "listedcompany",
    "listing",
    "delist",
    "/primary/",
    "/api/",
    "download",
)


NETWORK_KEYWORDS = (
    "fetch(",
    "axios",
    "$.ajax",
    "$.get",
    "$.post",
    "xmlhttprequest",
)


ABSOLUTE_URL_PATTERN = re.compile(
    r"""https?://[^\s"'<>\\]+""",
    flags=re.IGNORECASE,
)


QUOTED_PATH_PATTERN = re.compile(
    r"""["'](
        /[^"'<>\\]{2,350}
    )["']""",
    flags=(
        re.IGNORECASE
        | re.VERBOSE
    ),
)


@dataclass(
    frozen=True,
    slots=True,
)
class ClientContractScan:
    script_urls: tuple[str, ...]

    candidate_urls: tuple[str, ...]

    keyword_snippets: tuple[str, ...]

    network_snippets: tuple[str, ...]


class ScriptHTMLParser(
    HTMLParser
):
    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.script_urls: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[
            tuple[
                str,
                str | None,
            ]
        ],
    ) -> None:
        if tag.casefold() != "script":
            return

        attributes = {
            key.casefold(): value
            for key, value
            in attrs
        }

        src = attributes.get(
            "src"
        )

        if src:
            self.script_urls.append(
                src
            )


def normalize_asset_url(
    *,
    base_url: str,
    value: str,
) -> str | None:
    candidate = (
        value.strip()
        .strip(
            "\"'"
        )
    )

    if not candidate:
        return None

    if candidate.startswith(
        (
            "javascript:",
            "data:",
            "#",
        )
    ):
        return None

    absolute = urljoin(
        base_url,
        candidate,
    )

    parsed = urlparse(
        absolute
    )

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return None

    if not parsed.netloc:
        return None

    return absolute


def same_idx_origin(
    url: str,
) -> bool:
    hostname = (
        urlparse(
            url
        ).hostname
        or ""
    ).casefold()

    return hostname in {
        "www.idx.id",
        "idx.id",
        "www.idx.co.id",
        "idx.co.id",
    }


def extract_script_urls(
    *,
    base_url: str,
    html: str,
) -> tuple[str, ...]:
    parser = (
        ScriptHTMLParser()
    )

    parser.feed(
        html
    )

    normalized = []

    for value in (
        parser.script_urls
    ):
        url = normalize_asset_url(
            base_url=base_url,
            value=value,
        )

        if url is None:
            continue

        if not same_idx_origin(
            url
        ):
            continue

        normalized.append(
            url
        )

    return tuple(
        sorted(
            set(
                normalized
            )
        )
    )


def normalize_candidate(
    *,
    base_url: str,
    value: str,
) -> str | None:
    candidate = (
        normalize_asset_url(
            base_url=base_url,
            value=value,
        )
    )

    if candidate is None:
        return None

    lowered = (
        candidate.casefold()
    )

    if not any(
        keyword in lowered
        for keyword
        in STRONG_KEYWORDS
    ):
        return None

    return candidate


def extract_candidate_urls(
    *,
    base_url: str,
    text: str,
) -> tuple[str, ...]:
    raw = []

    raw.extend(
        ABSOLUTE_URL_PATTERN.findall(
            text
        )
    )

    raw.extend(
        QUOTED_PATH_PATTERN.findall(
            text
        )
    )

    candidates = []

    for value in raw:
        normalized = (
            normalize_candidate(
                base_url=base_url,
                value=value,
            )
        )

        if normalized is None:
            continue

        candidates.append(
            normalized
        )

    return tuple(
        sorted(
            set(
                candidates
            )
        )
    )


def compact_context(
    *,
    text: str,
    position: int,
    radius: int = 170,
) -> str:
    start = max(
        0,
        position - radius,
    )

    end = min(
        len(
            text
        ),
        position + radius,
    )

    snippet = text[
        start:end
    ]

    return " ".join(
        snippet.split()
    )


def find_keyword_snippets(
    *,
    text: str,
    keywords: tuple[str, ...],
    maximum: int = 30,
) -> tuple[str, ...]:
    lowered = (
        text.casefold()
    )

    snippets = []

    for keyword in keywords:
        needle = (
            keyword.casefold()
        )

        start = 0

        while True:
            position = (
                lowered.find(
                    needle,
                    start,
                )
            )

            if position < 0:
                break

            snippet = (
                compact_context(
                    text=text,
                    position=position,
                )
            )

            snippets.append(
                f"[{keyword}] "
                f"{snippet}"
            )

            if len(
                snippets
            ) >= maximum:
                return tuple(
                    snippets
                )

            start = (
                position
                + len(
                    needle
                )
            )

    return tuple(
        snippets
    )


def scan_client_contract(
    *,
    base_url: str,
    html: str,
    script_texts: tuple[
        tuple[
            str,
            str,
        ],
        ...
    ],
) -> ClientContractScan:
    script_urls = (
        extract_script_urls(
            base_url=base_url,
            html=html,
        )
    )

    combined_candidates = list(
        extract_candidate_urls(
            base_url=base_url,
            text=html,
        )
    )

    keyword_snippets = list(
        find_keyword_snippets(
            text=html,
            keywords=(
                STRONG_KEYWORDS
            ),
            maximum=20,
        )
    )

    network_snippets = list(
        find_keyword_snippets(
            text=html,
            keywords=(
                NETWORK_KEYWORDS
            ),
            maximum=20,
        )
    )

    for (
        script_url,
        script_text,
    ) in script_texts:
        combined_candidates.extend(
            extract_candidate_urls(
                base_url=script_url,
                text=script_text,
            )
        )

        script_keywords = (
            find_keyword_snippets(
                text=script_text,
                keywords=(
                    STRONG_KEYWORDS
                ),
                maximum=30,
            )
        )

        keyword_snippets.extend(
            f"{script_url} :: {item}"
            for item
            in script_keywords
        )

        script_network = (
            find_keyword_snippets(
                text=script_text,
                keywords=(
                    NETWORK_KEYWORDS
                ),
                maximum=30,
            )
        )

        network_snippets.extend(
            f"{script_url} :: {item}"
            for item
            in script_network
        )

    return ClientContractScan(
        script_urls=(
            script_urls
        ),

        candidate_urls=tuple(
            sorted(
                set(
                    combined_candidates
                )
            )
        ),

        keyword_snippets=tuple(
            keyword_snippets[
                :100
            ]
        ),

        network_snippets=tuple(
            network_snippets[
                :100
            ]
        ),
    )