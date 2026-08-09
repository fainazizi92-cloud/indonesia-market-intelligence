import argparse
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from time import sleep
from urllib.parse import urljoin, urlsplit

import httpx

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
        "listing-content-chunk-resolver"
    ),
    "Accept": (
        "text/html,"
        "application/javascript,"
        "text/javascript,"
        "*/*;q=0.8"
    ),
}


MODULE_ID = "1753"

DEFAULT_MAX_ASSETS = 120

DEFAULT_CONTEXT_SIZE = 3000

MODULE_REGION_SIZE = 40000


MODULE_PATTERNS = (
    re.compile(
        r"(?<!\d)1753:function\("
    ),
    re.compile(
        r"(?<!\d)1753:\s*function\("
    ),
    re.compile(
        r"(?<!\d)1753:\("
    ),
)


INTERESTING_MARKERS = (
    "$axios.get",
    "$axios.$get",
    "$axios.post",
    "$axios.$post",
    "axios.get",
    "axios.post",
    "this.dataTable",
    "dataTable",
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
    "indexFrom",
)


STRING_PATTERN = re.compile(
    r"""["']([^"']{1,700})["']"""
)


@dataclass(
    frozen=True,
    slots=True,
)
class JsAssetRef:
    url: str
    source_type: str


@dataclass(
    frozen=True,
    slots=True,
)
class ModuleMatch:
    asset: JsAssetRef
    body: str
    position: int
    marker: str


class JsAssetParser(
    HTMLParser
):
    def __init__(
        self,
        *,
        base_url: str,
    ) -> None:
        super().__init__()

        self.base_url = (
            base_url
        )

        self._assets = []

        self._seen = set()

    @property
    def assets(
        self,
    ) -> tuple[
        JsAssetRef,
        ...
    ]:
        return tuple(
            self._assets
        )

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
            key.casefold():
                value
            for key, value
            in attrs
        }

        candidate = None

        source_type = (
            normalized_tag
        )

        if (
            normalized_tag
            == "script"
        ):
            candidate = (
                attributes.get(
                    "src"
                )
            )

            source_type = (
                "script"
            )

        elif (
            normalized_tag
            == "link"
        ):
            candidate = (
                attributes.get(
                    "href"
                )
            )

            relation = (
                attributes.get(
                    "rel"
                )
                or ""
            )

            source_type = (
                "link:"
                + relation
            )

        if not candidate:
            return

        absolute = urljoin(
            self.base_url,
            candidate,
        )

        parsed = urlsplit(
            absolute
        )

        if (
            parsed.scheme
            not in {
                "http",
                "https",
            }
        ):
            return

        if (
            parsed.netloc
            .casefold()
            not in {
                "www.idx.id",
                "idx.id",
            }
        ):
            return

        if not (
            parsed.path
            .casefold()
            .endswith(
                ".js"
            )
        ):
            return

        if absolute in self._seen:
            return

        self._seen.add(
            absolute
        )

        self._assets.append(
            JsAssetRef(
                url=absolute,
                source_type=(
                    source_type
                ),
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the actual Nuxt JS "
            "chunk containing IDX module "
            "1753 (LazyListingContent)."
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

    parser.add_argument(
        "--max-assets",
        type=int,
        default=(
            DEFAULT_MAX_ASSETS
        ),
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

    if args.max_assets <= 0:
        raise ValueError(
            "max-assets must be positive."
        )


def extract_js_assets(
    *,
    base_url: str,
    html: str,
) -> tuple[
    JsAssetRef,
    ...
]:
    parser = JsAssetParser(
        base_url=base_url
    )

    parser.feed(
        html
    )

    parser.close()

    return parser.assets


def module_position(
    text: str,
) -> tuple[
    int,
    str,
] | None:
    for pattern in (
        MODULE_PATTERNS
    ):
        match = pattern.search(
            text
        )

        if match is None:
            continue

        return (
            match.start(),
            match.group(
                0
            ),
        )

    return None


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
    radius: int = (
        DEFAULT_CONTEXT_SIZE
    ),
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

    return compact_text(
        text[
            start:end
        ]
    )


def extract_interesting_strings(
    text: str,
) -> tuple[
    str,
    ...
]:
    values = []

    seen = set()

    for match in (
        STRING_PATTERN
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
            "listingactivity"
            in lowered
            or "/primary/"
            in lowered
            or "delist"
            in lowered
            or "relist"
            in lowered
            or "listing"
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


def marker_contexts(
    *,
    text: str,
) -> tuple[
    tuple[
        str,
        str,
    ],
    ...
]:
    lowered = (
        text.casefold()
    )

    values = []

    seen = set()

    for marker in (
        INTERESTING_MARKERS
    ):
        normalized = (
            marker.casefold()
        )

        position = lowered.find(
            normalized
        )

        if position < 0:
            continue

        context = (
            build_context(
                text=text,
                position=position,
            )
        )

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
            (
                marker,
                context,
            )
        )

    return tuple(
        values
    )


def fetch_module(
    *,
    client: httpx.Client,
    assets: tuple[
        JsAssetRef,
        ...
    ],
    max_assets: int,
    pause: float,
) -> tuple[
    ModuleMatch | None,
    int,
]:
    scanned = 0

    for asset in (
        assets[
            :max_assets
        ]
    ):
        try:
            response = client.get(
                asset.url
            )

        except httpx.HTTPError:
            continue

        scanned += 1

        if (
            scanned == 1
            or scanned % 10 == 0
        ):
            print(
                f"  Scanned : "
                f"{scanned}"
            )

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
            and not asset.url
            .casefold()
            .endswith(
                ".js"
            )
        ):
            continue

        result = module_position(
            response.text
        )

        if result is not None:
            (
                position,
                marker,
            ) = result

            return (
                ModuleMatch(
                    asset=asset,
                    body=response.text,
                    position=position,
                    marker=marker,
                ),
                scanned,
            )

        if pause > 0:
            sleep(
                pause
            )

    return (
        None,
        scanned,
    )


def print_module_match(
    match: ModuleMatch,
) -> None:
    print(
        "MODULE FOUND"
    )

    print(
        f"  Module ID   : "
        f"{MODULE_ID}"
    )

    print(
        f"  Source      : "
        f"{match.asset.url}"
    )

    print(
        f"  Source type : "
        f"{match.asset.source_type}"
    )

    print(
        f"  JS bytes    : "
        f"{len(match.body.encode('utf-8'))}"
    )

    print(
        f"  Position    : "
        f"{match.position}"
    )

    print(
        f"  Marker      : "
        f"{match.marker}"
    )

    print()

    region_end = min(
        len(
            match.body
        ),
        match.position
        + MODULE_REGION_SIZE,
    )

    region = (
        match.body[
            match.position:
            region_end
        ]
    )

    strings = (
        extract_interesting_strings(
            region
        )
    )

    print(
        "INTERESTING STRINGS"
    )

    if strings:
        for value in strings:
            print(
                f"  S {value}"
            )

    else:
        print(
            "  -"
        )

    print()

    contexts = (
        marker_contexts(
            text=region
        )
    )

    print(
        "REQUEST / PARAMETER CONTEXTS"
    )

    if not contexts:
        print(
            "  No high-value marker "
            "found in module region."
        )

        print()

    for index, (
        marker,
        context,
    ) in enumerate(
        contexts,
        start=1,
    ):
        print(
            f"CONTEXT {index}"
        )

        print(
            f"  Marker : "
            f"{marker}"
        )

        print(
            "  Code:"
        )

        print(
            "    "
            + context
        )

        print()

    print(
        "MODULE START CONTEXT"
    )

    print(
        "  "
        + compact_text(
            region[
                :12000
            ]
        )
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
        "IDX ListingContent Chunk "
        "Resolver V1"
    )

    print(
        "-----------------------------"
    )

    print(
        f"Page URL   : "
        f"{LISTING_ACTIVITIES_URL}"
    )

    print(
        f"Module ID  : "
        f"{MODULE_ID}"
    )

    print(
        f"Max assets : "
        f"{args.max_assets}"
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
                "Page HTTP   : ERROR"
            )

            print(
                f"Error       : "
                f"{type(exc).__name__}"
            )

            print(
                f"Detail      : "
                f"{exc}"
            )

            return

        print(
            f"Page HTTP   : "
            f"{page_response.status_code}"
        )

        print(
            f"Page bytes  : "
            f"{len(page_response.content)}"
        )

        page_response.raise_for_status()

        assets = (
            extract_js_assets(
                base_url=str(
                    page_response.url
                ),
                html=(
                    page_response.text
                ),
            )
        )

        script_count = sum(
            asset.source_type
            == "script"
            for asset in assets
        )

        link_count = (
            len(
                assets
            )
            - script_count
        )

        print(
            f"JS assets   : "
            f"{len(assets)}"
        )

        print(
            f"  scripts   : "
            f"{script_count}"
        )

        print(
            f"  links     : "
            f"{link_count}"
        )

        print()

        if not assets:
            print(
                "No JavaScript assets "
                "were discovered."
            )

            return

        print(
            "Scanning assets..."
        )

        (
            match,
            scanned,
        ) = fetch_module(
            client=client,
            assets=assets,
            max_assets=(
                args.max_assets
            ),
            pause=args.pause,
        )

    print()

    print(
        f"Assets scanned : "
        f"{scanned}"
    )

    if match is None:
        print(
            "Module found   : NO"
        )

        print()

        print(
            "NEXT INTERPRETATION:"
        )

        print(
            "Module 1753 was not present "
            "in the HTML-linked JavaScript "
            "assets scanned."
        )

        print(
            "Do not probe ListingActivity "
            "query parameters yet."
        )

    else:
        print(
            "Module found   : YES"
        )

        print()

        print_module_match(
            match
        )

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "Only query parameters and "
        "request construction visible "
        "inside the actual module may "
        "be promoted to a live API probe."
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