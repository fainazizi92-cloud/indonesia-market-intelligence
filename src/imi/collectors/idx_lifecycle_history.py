from dataclasses import dataclass
from math import ceil
from time import sleep

import httpx

from imi.features.idx_lifecycle_api_probe import (
    build_new_listing_api_url,
)
from imi.features.idx_lifecycle_records import (
    NewListingRecord,
    parse_new_listing_payload,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "historical-lifecycle-collector"
    ),

    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),

    "Referer": (
        "https:"
        + "//www.idx.id/"
    ),
}


@dataclass(
    frozen=True,
    slots=True,
)
class NewListingCollection:
    year: int

    month: int

    records: tuple[
        NewListingRecord,
        ...
    ]

    total_items: int

    pages_fetched: int

    source_urls: tuple[
        str,
        ...
    ]


def create_lifecycle_client(
    *,
    timeout: float = 20.0,
) -> httpx.Client:
    if timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    )


def _fetch_json(
    *,
    client: httpx.Client,
    url: str,
) -> object:
    response = client.get(
        url
    )

    response.raise_for_status()

    content_type = (
        response.headers.get(
            "content-type",
            "",
        ).casefold()
    )

    if (
        "json"
        not in content_type
    ):
        raise ValueError(
            "IDX lifecycle endpoint "
            "did not return JSON."
        )

    try:
        return response.json()

    except ValueError as exc:
        raise ValueError(
            "IDX lifecycle response "
            "contains invalid JSON."
        ) from exc


def fetch_new_listings_month(
    *,
    client: httpx.Client,
    year: int,
    month: int,
    page_size: int = 100,
    pause: float = 0.20,
    max_pages: int = 100,
) -> NewListingCollection:
    if pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )

    if max_pages <= 0:
        raise ValueError(
            "max_pages must be positive."
        )

    first_url = (
        build_new_listing_api_url(
            year=year,
            month=month,
            page_size=page_size,
            page_number=1,
        )
    )

    first_payload = (
        _fetch_json(
            client=client,
            url=first_url,
        )
    )

    first_page = (
        parse_new_listing_payload(
            first_payload,
            expected_year=year,
            expected_month=month,
        )
    )

    total_pages = max(
        1,
        ceil(
            first_page.total_items
            / first_page.page_size
        ),
    )

    if total_pages > max_pages:
        raise ValueError(
            "Unexpectedly large number "
            f"of pages: {total_pages}"
        )

    records = list(
        first_page.records
    )

    urls = [
        first_url
    ]

    for page_number in range(
        2,
        total_pages + 1,
    ):
        if pause > 0:
            sleep(
                pause
            )

        url = (
            build_new_listing_api_url(
                year=year,
                month=month,
                page_size=page_size,
                page_number=(
                    page_number
                ),
            )
        )

        payload = (
            _fetch_json(
                client=client,
                url=url,
            )
        )

        page = (
            parse_new_listing_payload(
                payload,
                expected_year=year,
                expected_month=month,
            )
        )

        if (
            page.page_number
            != page_number
        ):
            raise ValueError(
                "IDX returned unexpected "
                "page number."
            )

        records.extend(
            page.records
        )

        urls.append(
            url
        )

    if (
        len(
            records
        )
        != first_page.total_items
    ):
        raise ValueError(
            "Collected record count "
            "does not match totalItems: "
            f"{len(records)} != "
            f"{first_page.total_items}"
        )

    codes = [
        record.code
        for record in records
    ]

    if (
        len(
            codes
        )
        != len(
            set(
                codes
            )
        )
    ):
        raise ValueError(
            "Duplicate symbols across "
            "pagination."
        )

    return NewListingCollection(
        year=year,

        month=month,

        records=tuple(
            records
        ),

        total_items=(
            first_page.total_items
        ),

        pages_fetched=(
            total_pages
        ),

        source_urls=tuple(
            urls
        ),
    )