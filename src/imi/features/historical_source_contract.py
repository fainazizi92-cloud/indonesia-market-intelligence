import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

SOURCE_CONTRACT_VERSION = (
    "historical_source_contract_v1"
)


LIFECYCLE_SOURCE_KEYS = (
    "IDX_LISTING_ACTIVITIES",
    "IDX_DIGITAL_NEW_LISTINGS",
    "IDX_DIGITAL_DELISTED_COMPANY",
)


ABSOLUTE_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+",
    flags=re.IGNORECASE,
)


QUOTED_PATH_PATTERN = re.compile(
    r"""["'](
        /[^"'<>]{2,300}
    )["']""",
    flags=(
        re.IGNORECASE
        | re.VERBOSE
    ),
)


CANDIDATE_KEYWORDS = (
    "listing",
    "listed",
    "delist",
    "relist",
    "download",
    "primary",
    "api",
    "statistic",
    "excel",
    "csv",
    "xlsx",
    "xls",
    "zip",
    "json",
)


FILE_EXTENSIONS = (
    ".csv",
    ".xlsx",
    ".xls",
    ".zip",
    ".json",
)


@dataclass(frozen=True, slots=True)
class ContractExtraction:
    anchor_count: int
    script_count: int
    form_count: int

    candidate_urls: tuple[str, ...]

    endpoint_hints: dict[
        str,
        tuple[str, ...],
    ]


class ContractHTMLParser(
    HTMLParser
):
    def __init__(
        self,
    ) -> None:
        super().__init__()

        self.anchor_count = 0
        self.script_count = 0
        self.form_count = 0

        self.references: list[str] = []

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
        normalized_tag = (
            tag.casefold()
        )

        attributes = {
            key.casefold(): value
            for key, value in attrs
        }

        if normalized_tag == "a":
            self.anchor_count += 1

            href = attributes.get(
                "href"
            )

            if href:
                self.references.append(
                    href
                )

        elif normalized_tag == "script":
            self.script_count += 1

            src = attributes.get(
                "src"
            )

            if src:
                self.references.append(
                    src
                )

        elif normalized_tag == "form":
            self.form_count += 1

            action = attributes.get(
                "action"
            )

            if action:
                self.references.append(
                    action
                )

        for key in (
            "data-url",
            "data-api",
            "data-endpoint",
            "data-download",
            "data-source",
        ):
            value = attributes.get(
                key
            )

            if value:
                self.references.append(
                    value
                )


def body_sha256(
    body: bytes,
) -> str:
    return hashlib.sha256(
        body
    ).hexdigest()


def normalize_candidate_url(
    *,
    base_url: str,
    value: str,
) -> str | None:
    candidate = (
        value.strip()
        .strip(
            "\"'"
        )
        .rstrip(
            "),.;"
        )
    )

    if not candidate:
        return None

    lowered = candidate.casefold()

    if lowered.startswith(
        (
            "javascript:",
            "mailto:",
            "tel:",
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


def is_candidate_url(
    value: str,
) -> bool:
    lowered = (
        value.casefold()
    )

    if any(
        lowered.endswith(
            extension
        )
        for extension
        in FILE_EXTENSIONS
    ):
        return True

    return any(
        keyword in lowered
        for keyword
        in CANDIDATE_KEYWORDS
    )


def classify_endpoint_hints(
    urls: tuple[str, ...],
) -> dict[
    str,
    tuple[str, ...],
]:
    downloads = []
    api_like = []
    primary_like = []
    idx_domain = []

    for url in urls:
        lowered = (
            url.casefold()
        )

        if any(
            extension in lowered
            for extension
            in FILE_EXTENSIONS
        ):
            downloads.append(
                url
            )

        if (
            "/api/" in lowered
            or "api." in lowered
            or "json" in lowered
        ):
            api_like.append(
                url
            )

        if (
            "/primary/" in lowered
        ):
            primary_like.append(
                url
            )

        hostname = (
            urlparse(
                url
            ).hostname
            or ""
        )

        if (
            hostname.casefold()
            in {
                "www.idx.id",
                "idx.id",
            }
        ):
            idx_domain.append(
                url
            )

    return {
        "download_like":
            tuple(
                sorted(
                    set(
                        downloads
                    )
                )
            ),

        "api_like":
            tuple(
                sorted(
                    set(
                        api_like
                    )
                )
            ),

        "primary_like":
            tuple(
                sorted(
                    set(
                        primary_like
                    )
                )
            ),

        "idx_domain":
            tuple(
                sorted(
                    set(
                        idx_domain
                    )
                )
            ),
    }


def extract_source_contract(
    *,
    base_url: str,
    body_text: str,
) -> ContractExtraction:
    parser = (
        ContractHTMLParser()
    )

    parser.feed(
        body_text
    )

    raw_candidates = list(
        parser.references
    )

    raw_candidates.extend(
        ABSOLUTE_URL_PATTERN.findall(
            body_text
        )
    )

    raw_candidates.extend(
        QUOTED_PATH_PATTERN.findall(
            body_text
        )
    )

    normalized = []

    for value in raw_candidates:
        candidate = (
            normalize_candidate_url(
                base_url=base_url,
                value=value,
            )
        )

        if candidate is None:
            continue

        if not is_candidate_url(
            candidate
        ):
            continue

        normalized.append(
            candidate
        )

    candidate_urls = tuple(
        sorted(
            set(
                normalized
            )
        )
    )

    return ContractExtraction(
        anchor_count=(
            parser.anchor_count
        ),
        script_count=(
            parser.script_count
        ),
        form_count=(
            parser.form_count
        ),
        candidate_urls=(
            candidate_urls
        ),
        endpoint_hints=(
            classify_endpoint_hints(
                candidate_urls
            )
        ),
    )


def determine_parser_status(
    extraction: ContractExtraction,
) -> str:
    hints = (
        extraction.endpoint_hints
    )

    if (
        hints["download_like"]
        or hints["api_like"]
        or hints["primary_like"]
    ):
        return "CANDIDATE"

    return "DISCOVERY"


def prepare_contract_row(
    *,
    source_key: str,
    requested_url: str,
    final_url: str | None,
    http_status: int | None,
    content_type: str | None,
    body: bytes | None,
    extraction: ContractExtraction | None,
    error_type: str | None,
    error_message: str | None,
) -> dict[str, Any]:
    if body is None:
        digest = None
        body_length = None
    else:
        digest = body_sha256(
            body
        )

        body_length = len(
            body
        )

    if extraction is None:
        candidate_urls: list[str] = []

        endpoint_hints: dict[
            str,
            list[str],
        ] = {}

        anchor_count = 0
        script_count = 0
        form_count = 0

        parser_status = (
            "BLOCKED"
            if error_type
            else "DISCOVERY"
        )

    else:
        candidate_urls = list(
            extraction
            .candidate_urls
        )

        endpoint_hints = {
            key: list(
                values
            )
            for key, values
            in extraction
            .endpoint_hints
            .items()
        }

        anchor_count = (
            extraction
            .anchor_count
        )

        script_count = (
            extraction
            .script_count
        )

        form_count = (
            extraction
            .form_count
        )

        parser_status = (
            determine_parser_status(
                extraction
            )
        )

    return {
        "source_key":
            source_key,

        "requested_url":
            requested_url,

        "final_url":
            final_url,

        "http_status":
            http_status,

        "content_type":
            content_type,

        "body_sha256":
            digest,

        "body_length":
            body_length,

        "anchor_count":
            anchor_count,

        "script_count":
            script_count,

        "form_count":
            form_count,

        "candidate_url_count":
            len(
                candidate_urls
            ),

        "candidate_urls":
            candidate_urls,

        "endpoint_hints":
            endpoint_hints,

        "parser_ready":
            False,

        "parser_status":
            parser_status,

        "error_type":
            error_type,

        "error_message":
            error_message,

        "evidence": {
            "scope":
                SOURCE_CONTRACT_VERSION,

            "raw_body_stored":
                False,

            "historical_rows_ingested":
                False,

            "warning":
                (
                    "Candidate endpoints are "
                    "discovery evidence only. "
                    "They are not approved "
                    "historical ingestion "
                    "contracts yet."
                ),
        },
    }