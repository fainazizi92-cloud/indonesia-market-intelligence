import base64
import json
from html import unescape
from urllib.parse import (
    urlencode,
    urlsplit,
    urlunsplit,
)

IDX_DIGITAL_STAT_BASE_URL = (
    "https://www.idx.id/en/market-data/"
    "statistical-reports/digital-statistic/"
    "monthly/corporate-action-of-listed-companies"
)


def encode_filter(
    *,
    year: int,
    month: int,
) -> str:
    if year < 1900:
        raise ValueError(
            "year must be 1900 or later."
        )

    if not 1 <= month <= 12:
        raise ValueError(
            "month must be between 1 and 12."
        )

    payload = {
        "year": str(
            year
        ),
        "month": str(
            month
        ),
        "quarter": 0,
        "type": "monthly",
    }

    raw = json.dumps(
        payload,
        separators=(
            ",",
            ":",
        ),
    ).encode(
        "utf-8"
    )

    return base64.b64encode(
        raw
    ).decode(
        "ascii"
    )


def build_filtered_url(
    *,
    slug: str,
    year: int,
    month: int,
) -> str:
    normalized_slug = (
        slug.strip()
        .strip(
            "/"
        )
    )

    if not normalized_slug:
        raise ValueError(
            "slug cannot be empty."
        )

    filter_value = (
        encode_filter(
            year=year,
            month=month,
        )
    )

    base_url = (
        f"{IDX_DIGITAL_STAT_BASE_URL}/"
        f"{normalized_slug}"
    )

    parsed = urlsplit(
        base_url
    )

    query = urlencode(
        {
            "filter":
                filter_value,
        }
    )

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            query,
            "",
        )
    )


def normalize_text(
    html: str,
) -> str:
    text = unescape(
        html
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    return " ".join(
        text.split()
    )


def marker_result(
    *,
    html: str,
    markers: tuple[str, ...],
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
]:
    normalized = (
        normalize_text(
            html
        ).casefold()
    )

    found = tuple(
        marker
        for marker in markers
        if marker.casefold()
        in normalized
    )

    missing = tuple(
        marker
        for marker in markers
        if marker.casefold()
        not in normalized
    )

    return (
        found,
        missing,
    )