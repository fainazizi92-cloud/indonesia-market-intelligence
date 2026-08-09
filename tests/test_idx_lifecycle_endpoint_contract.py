import pytest

from imi.features.idx_lifecycle_endpoint_contract import (
    decode_common_js_escapes,
    extract_endpoint_fragments,
    extract_query_keys,
    find_endpoint_evidence,
)

IDX_ORIGIN = (
    "https:"
    + "//www.idx.id"
)


def test_decode_js_slash():
    value = (
        "\\u002Fapi"
        "\\u002Fstatisticalhighlight"
        "\\u002Fstockdelisting"
    )

    result = (
        decode_common_js_escapes(
            value
        )
    )

    assert result == (
        "/api/"
        "statisticalhighlight/"
        "stockdelisting"
    )


def test_decode_js_query_symbols():
    value = (
        "test"
        "\\u003F"
        "a"
        "\\u003D"
        "1"
        "\\u0026"
        "b"
        "\\u003D"
        "2"
    )

    result = (
        decode_common_js_escapes(
            value
        )
    )

    assert result == (
        "test?a=1&b=2"
    )


def test_extract_query_keys():
    text = (
        "GetApiDataPaginated"
        "?urlName=X"
        "&periodYear="
        "&periodMonth="
        "&pageSize="
        "&pageNumber="
    )

    result = (
        extract_query_keys(
            text
        )
    )

    assert result == (
        "urlName",
        "periodYear",
        "periodMonth",
        "pageSize",
        "pageNumber",
    )


def test_query_keys_deduplicated():
    text = (
        "?pageSize=1"
        "&pageNumber=1"
        "&pageSize=2"
    )

    result = (
        extract_query_keys(
            text
        )
    )

    assert result == (
        "pageSize",
        "pageNumber",
    )


def test_extract_primary_endpoint():
    text = (
        "primary/"
        "DigitalStatistic/"
        "GetApiDataPaginated"
        "?urlName="
        "LINK_STOCK_NEW_LISTING"
        "&periodYear="
    )

    result = (
        extract_endpoint_fragments(
            text
        )
    )

    assert result

    assert (
        "GetApiDataPaginated"
        in result[0]
    )


def test_extract_statistical_endpoint():
    text = (
        'apiUrl:"'
        "\\u002Fapi"
        "\\u002Fstatisticalhighlight"
        "\\u002Fstockdelisting"
        '"'
    )

    result = (
        extract_endpoint_fragments(
            text
        )
    )

    assert (
        "/api/"
        "statisticalhighlight/"
        "stockdelisting"
        in result
    )


def test_find_evidence():
    source = (
        f"{IDX_ORIGIN}/"
        "_nuxt/test.js"
    )

    text = (
        'axios.get("primary/'
        'DigitalStatistic/'
        'GetApiDataPaginated'
        '?urlName='
        'LINK_STOCK_NEW_LISTING'
        '&periodYear=")'
    )

    result = (
        find_endpoint_evidence(
            source_url=source,
            text=text,
            needles=(
                "GetApiDataPaginated",
            ),
            radius=200,
        )
    )

    assert len(
        result
    ) == 1

    assert (
        result[0].source_url
        == source
    )

    assert (
        "periodYear"
        in result[0]
        .query_keys
    )


def test_find_evidence_case_insensitive():
    result = (
        find_endpoint_evidence(
            source_url="test",
            text="ABC STOCKDELISTING XYZ",
            needles=(
                "stockdelisting",
            ),
            radius=100,
        )
    )

    assert len(
        result
    ) == 1


def test_find_evidence_no_match():
    result = (
        find_endpoint_evidence(
            source_url="test",
            text="nothing relevant",
            needles=(
                "stockdelisting",
            ),
        )
    )

    assert not result


def test_invalid_radius():
    with pytest.raises(
        ValueError
    ):
        find_endpoint_evidence(
            source_url="test",
            text="abc",
            needles=(
                "abc",
            ),
            radius=0,
        )


def test_invalid_max_matches():
    with pytest.raises(
        ValueError
    ):
        find_endpoint_evidence(
            source_url="test",
            text="abc",
            needles=(
                "abc",
            ),
            max_matches_per_needle=0,
        )