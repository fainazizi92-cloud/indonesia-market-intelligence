from urllib.parse import (
    parse_qs,
    urlsplit,
)

import pytest

from imi.features.idx_report_contract import (
    build_report_url,
    extract_digital_stat_metadata,
    extract_download_types,
)


def test_extract_report_types():
    text = """
    foo.downloadReport("excel")
    foo.downloadReport("pdf")
    """

    result = (
        extract_download_types(
            text
        )
    )

    assert result == (
        "excel",
        "pdf",
    )


def test_report_types_deduplicated():
    text = """
    foo.downloadReport("excel")
    foo.downloadReport("EXCEL")
    """

    result = (
        extract_download_types(
            text
        )
    )

    assert result == (
        "excel",
    )


def test_no_report_types():
    result = (
        extract_download_types(
            "nothing here"
        )
    )

    assert not result


def test_extract_page_metadata():
    payload = {
        "downloadCode": {
            "type": "String",
            "value": "SDelisting",
        },

        "title": {
            "type": "String",
            "value": "Delisted Company",
        },

        "tableChartList": {
            "type": "JToken",
            "value": [
                {
                    "alias":
                        "DELISTING",

                    "apiUrl":
                        (
                            "/api/"
                            "statisticalhighlight/"
                            "stockdelisting"
                        ),
                }
            ],
        },
    }

    result = (
        extract_digital_stat_metadata(
            payload
        )
    )

    assert (
        result.download_code
        == "SDelisting"
    )

    assert (
        result.title
        == "Delisted Company"
    )

    assert result.aliases == (
        "DELISTING",
    )

    assert result.api_urls == (
        (
            "/api/"
            "statisticalhighlight/"
            "stockdelisting"
        ),
    )


def test_invalid_metadata_type():
    with pytest.raises(
        TypeError
    ):
        extract_digital_stat_metadata(
            []
        )


def test_missing_download_code():
    with pytest.raises(
        ValueError
    ):
        extract_digital_stat_metadata(
            {
                "title": {
                    "value": "Test"
                }
            }
        )


def test_build_report_contract():
    url = build_report_url(
        report_type="excel",
        year=2024,
        month=10,
        download_code=(
            "SDelisting"
        ),
        filename=(
            "Delisted Company"
        ),
    )

    query = parse_qs(
        urlsplit(
            url
        ).query
    )

    assert (
        query[
            "type"
        ][0]
        == "excel"
    )

    assert (
        query[
            "periodYear"
        ][0]
        == "2024"
    )

    assert (
        query[
            "periodMonth"
        ][0]
        == "10"
    )

    assert (
        query[
            "filecode"
        ][0]
        == "SDelisting"
    )


def test_invalid_month():
    with pytest.raises(
        ValueError
    ):
        build_report_url(
            report_type="excel",
            year=2024,
            month=13,
            download_code=(
                "SDelisting"
            ),
            filename=(
                "Delisted Company"
            ),
        )


def test_empty_report_type():
    with pytest.raises(
        ValueError
    ):
        build_report_url(
            report_type="",
            year=2024,
            month=10,
            download_code=(
                "SDelisting"
            ),
            filename=(
                "Delisted Company"
            ),
        )