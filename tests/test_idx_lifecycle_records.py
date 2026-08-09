from decimal import Decimal

import pytest

from imi.features.idx_lifecycle_records import (
    parse_new_listing_payload,
    parse_new_listing_record,
)


def make_row():
    return {
        "code": "TEST",
        "issuerName":
            "Test Company Tbk.",
        "ListedShares":
            1000000.0,
        "NumOfShares":
            200000.0,
        "Nominal":
            100.0,
        "Offering":
            250.0,
        "FundRaised":
            50000000.0,
        "Type":
            None,
        "ListingDate":
            "2025-01-08",
    }


def make_payload():
    return {
        "data": [
            make_row()
        ],
        "meta": {
            "totalItems": 1,
            "pageSize": 100,
            "pageNumber": 1,
            "orderBy": "",
            "search": "",
        },
    }


def test_parse_valid_record():
    result = (
        parse_new_listing_record(
            make_row(),
            expected_year=2025,
            expected_month=1,
        )
    )

    assert (
        result.code
        == "TEST"
    )

    assert (
        result.listed_shares
        == 1000000
    )

    assert (
        result.offering_price
        == Decimal(
            "250.0"
        )
    )


def test_symbol_normalized():
    row = make_row()

    row[
        "code"
    ] = "test"

    result = (
        parse_new_listing_record(
            row,
            expected_year=2025,
            expected_month=1,
        )
    )

    assert (
        result.code
        == "TEST"
    )


def test_wrong_month_rejected():
    with pytest.raises(
        ValueError
    ):
        parse_new_listing_record(
            make_row(),
            expected_year=2025,
            expected_month=2,
        )


def test_invalid_symbol_rejected():
    row = make_row()

    row[
        "code"
    ] = "BAD CODE"

    with pytest.raises(
        ValueError
    ):
        parse_new_listing_record(
            row,
            expected_year=2025,
            expected_month=1,
        )


def test_non_integral_shares_rejected():
    row = make_row()

    row[
        "ListedShares"
    ] = 100.5

    with pytest.raises(
        ValueError
    ):
        parse_new_listing_record(
            row,
            expected_year=2025,
            expected_month=1,
        )


def test_negative_value_rejected():
    row = make_row()

    row[
        "Offering"
    ] = -1

    with pytest.raises(
        ValueError
    ):
        parse_new_listing_record(
            row,
            expected_year=2025,
            expected_month=1,
        )


def test_payload_parsed():
    result = (
        parse_new_listing_payload(
            make_payload(),
            expected_year=2025,
            expected_month=1,
        )
    )

    assert len(
        result.records
    ) == 1

    assert (
        result.total_items
        == 1
    )

    assert (
        result.page_number
        == 1
    )


def test_payload_requires_dict():
    with pytest.raises(
        TypeError
    ):
        parse_new_listing_payload(
            [],
            expected_year=2025,
            expected_month=1,
        )


def test_payload_requires_data_list():
    payload = (
        make_payload()
    )

    payload[
        "data"
    ] = {}

    with pytest.raises(
        TypeError
    ):
        parse_new_listing_payload(
            payload,
            expected_year=2025,
            expected_month=1,
        )


def test_payload_requires_meta():
    payload = (
        make_payload()
    )

    payload.pop(
        "meta"
    )

    with pytest.raises(
        TypeError
    ):
        parse_new_listing_payload(
            payload,
            expected_year=2025,
            expected_month=1,
        )


def test_duplicate_symbol_rejected():
    payload = (
        make_payload()
    )

    payload[
        "data"
    ] = [
        make_row(),
        make_row(),
    ]

    payload[
        "meta"
    ][
        "totalItems"
    ] = 2

    with pytest.raises(
        ValueError
    ):
        parse_new_listing_payload(
            payload,
            expected_year=2025,
            expected_month=1,
        )


def test_empty_month_valid():
    payload = {
        "data": [],
        "meta": {
            "totalItems": 0,
            "pageSize": 100,
            "pageNumber": 1,
            "orderBy": "",
            "search": "",
        },
    }

    result = (
        parse_new_listing_payload(
            payload,
            expected_year=2020,
            expected_month=1,
        )
    )

    assert not result.records

    assert (
        result.total_items
        == 0
    )