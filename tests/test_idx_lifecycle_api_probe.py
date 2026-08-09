from urllib.parse import (
    parse_qs,
    urlsplit,
)

import pytest

from imi.features.idx_lifecycle_api_probe import (
    build_delisting_stat_url,
    build_new_listing_api_url,
    build_page_metadata_url,
    summarize_json,
)


def test_new_listing_url_path():
    url = (
        build_new_listing_api_url(
            year=2025,
            month=1,
        )
    )

    assert (
        "GetApiDataPaginated"
        in url
    )


def test_new_listing_query_contract():
    url = (
        build_new_listing_api_url(
            year=2025,
            month=1,
        )
    )

    parsed = urlsplit(
        url
    )

    query = parse_qs(
        parsed.query,
        keep_blank_values=True,
    )

    assert (
        query[
            "urlName"
        ][0]
        == "LINK_STOCK_NEW_LISTING"
    )

    assert (
        query[
            "periodYear"
        ][0]
        == "2025"
    )

    assert (
        query[
            "periodMonth"
        ][0]
        == "1"
    )

    assert (
        query[
            "periodType"
        ][0]
        == "monthly"
    )


def test_new_listing_pagination():
    url = (
        build_new_listing_api_url(
            year=2025,
            month=1,
            page_size=77,
            page_number=3,
        )
    )

    query = parse_qs(
        urlsplit(
            url
        ).query,
        keep_blank_values=True,
    )

    assert (
        query[
            "pageSize"
        ][0]
        == "77"
    )

    assert (
        query[
            "pageNumber"
        ][0]
        == "3"
    )


def test_invalid_month():
    with pytest.raises(
        ValueError
    ):
        build_new_listing_api_url(
            year=2025,
            month=13,
        )


def test_invalid_page_size():
    with pytest.raises(
        ValueError
    ):
        build_new_listing_api_url(
            year=2025,
            month=1,
            page_size=0,
        )


def test_metadata_url():
    url = (
        build_page_metadata_url(
            route_path=(
                "/en/test-page"
            )
        )
    )

    assert (
        "/primary/page/"
        "en/test-page"
        in url
    )


def test_empty_metadata_route():
    with pytest.raises(
        ValueError
    ):
        build_page_metadata_url(
            route_path=""
        )


def test_delisting_stat_url():
    url = (
        build_delisting_stat_url()
    )

    assert (
        "/api/statisticalhighlight/"
        "stockdelisting"
        in url
    )


def test_summarize_paginated_payload():
    payload = {
        "data": {
            "meta": {
                "totalItems": 2,
                "pageSize": 100,
            },
            "items": [
                {
                    "code": "AAA",
                    "listingDate":
                        "2025-01-01",
                },
                {
                    "code": "BBB",
                    "listingDate":
                        "2025-01-02",
                },
            ],
        }
    }

    result = (
        summarize_json(
            payload
        )
    )

    assert (
        result.payload_type
        == "dict"
    )

    assert (
        result.item_count
        == 2
    )

    assert (
        "totalItems"
        in result.meta_keys
    )

    assert (
        "code"
        in result.first_item_keys
    )


def test_summarize_list_payload():
    payload = [
        {
            "code": "AAA",
        }
    ]

    result = (
        summarize_json(
            payload
        )
    )

    assert (
        result.item_count
        == 1
    )

    assert result.first_item_keys == (
        "code",
    )