import re
from dataclasses import dataclass

QUERY_KEY_PATTERN = re.compile(
    r"[?&]([A-Za-z][A-Za-z0-9_]*)="
)


PRIMARY_ENDPOINT_PATTERN = re.compile(
    (
        r"primary/"
        r"DigitalStatistic/"
        r"GetApiDataPaginated"
        r"[^\"']*"
    ),
    flags=re.IGNORECASE,
)


STATISTICAL_ENDPOINT_PATTERN = re.compile(
    (
        r"/api/"
        r"statisticalhighlight/"
        r"[A-Za-z0-9_/-]+"
    ),
    flags=re.IGNORECASE,
)


JS_ESCAPE_REPLACEMENTS = {
    "\\u002F": "/",
    "\\u002f": "/",
    "\\u003F": "?",
    "\\u003f": "?",
    "\\u0026": "&",
    "\\u003D": "=",
    "\\u003d": "=",
    "\\u002D": "-",
    "\\u002d": "-",
}


@dataclass(
    frozen=True,
    slots=True,
)
class EndpointEvidence:
    source_url: str
    needle: str

    query_keys: tuple[
        str,
        ...
    ]

    endpoint_fragments: tuple[
        str,
        ...
    ]

    context: str


def decode_common_js_escapes(
    text: str,
) -> str:
    decoded = text

    for (
        escaped,
        replacement,
    ) in JS_ESCAPE_REPLACEMENTS.items():
        decoded = decoded.replace(
            escaped,
            replacement,
        )

    return decoded


def compact_text(
    text: str,
) -> str:
    return " ".join(
        text.split()
    )


def extract_query_keys(
    text: str,
) -> tuple[str, ...]:
    found = (
        QUERY_KEY_PATTERN.findall(
            text
        )
    )

    result = []

    seen = set()

    for value in found:
        if value in seen:
            continue

        seen.add(
            value
        )

        result.append(
            value
        )

    return tuple(
        result
    )


def extract_endpoint_fragments(
    text: str,
) -> tuple[str, ...]:
    decoded = (
        decode_common_js_escapes(
            text
        )
    )

    found = []

    found.extend(
        PRIMARY_ENDPOINT_PATTERN.findall(
            decoded
        )
    )

    found.extend(
        STATISTICAL_ENDPOINT_PATTERN.findall(
            decoded
        )
    )

    normalized = []

    seen = set()

    for value in found:
        compact = (
            compact_text(
                value
            )
        )

        if compact in seen:
            continue

        seen.add(
            compact
        )

        normalized.append(
            compact
        )

    return tuple(
        normalized
    )


def context_around(
    *,
    text: str,
    position: int,
    radius: int,
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


def find_endpoint_evidence(
    *,
    source_url: str,
    text: str,
    needles: tuple[str, ...],
    radius: int = 900,
    max_matches_per_needle: int = 3,
) -> tuple[
    EndpointEvidence,
    ...
]:
    if radius <= 0:
        raise ValueError(
            "radius must be positive."
        )

    if max_matches_per_needle <= 0:
        raise ValueError(
            "max_matches_per_needle "
            "must be positive."
        )

    decoded = (
        decode_common_js_escapes(
            text
        )
    )

    lowered = (
        decoded.casefold()
    )

    results = []

    for needle in needles:
        normalized_needle = (
            needle.casefold()
        )

        start = 0
        matches = 0

        while (
            matches
            < max_matches_per_needle
        ):
            position = lowered.find(
                normalized_needle,
                start,
            )

            if position < 0:
                break

            context = (
                context_around(
                    text=decoded,
                    position=position,
                    radius=radius,
                )
            )

            results.append(
                EndpointEvidence(
                    source_url=(
                        source_url
                    ),
                    needle=needle,
                    query_keys=(
                        extract_query_keys(
                            context
                        )
                    ),
                    endpoint_fragments=(
                        extract_endpoint_fragments(
                            context
                        )
                    ),
                    context=context,
                )
            )

            matches += 1

            start = (
                position
                + len(
                    normalized_needle
                )
            )

    return tuple(
        results
    )