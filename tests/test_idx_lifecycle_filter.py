import base64
import json
from urllib.parse import (
    parse_qs,
    urlsplit,
)

import pytest

from imi.features.idx_lifecycle_filter import (
    build_filtered_url,
    encode_filter,
    marker_result,
    normalize_text,
)


def decode_filter(
    value: str,
) -> dict[str, object]:
    raw = base64.b64decode(
        value
    ).decode(
        "utf-8"
    )

    return json.loads(
        raw
    )


def test_filter_round_trip():
    encoded = (
        encode_filter(
            year=2025,
            month=1,
        )
    )

    decoded = (
        decode_filter(
            encoded
        )
    )

    assert decoded == {
        "year": "2025",
        "month": "1",
        "quarter": 0,
        "type": "monthly",
    }


def test_filter_changes_year():
    first = encode_filter(
        year=2024,
        month=1,
    )

    second = encode_filter(
        year=2025,
        month=1,
    )

    assert (
        first
        != second
    )


def test_filter_changes_month():
    first = encode_filter(
        year=2025,
        month=1,
    )

    second = encode_filter(
        year=2025,
        month=2,
    )

    assert (
        first
        != second
    )


def test_invalid_month_zero():
    with pytest.raises(
        ValueError
    ):
        encode_filter(
            year=2025,
            month=0,
        )


def test_invalid_month_thirteen():
    with pytest.raises(
        ValueError
    ):
        encode_filter(
            year=2025,
            month=13,
        )


def test_invalid_year():
    with pytest.raises(
        ValueError
    ):
        encode_filter(
            year=1800,
            month=1,
        )


def test_filtered_url_slug():
    url = build_filtered_url(
        slug=(
            "stock-new-listings"
        ),
        year=2025,
        month=1,
    )

    assert (
        "stock-new-listings"
        in url
    )


def test_empty_slug_rejected():
    with pytest.raises(
        ValueError
    ):
        build_filtered_url(
            slug="",
            year=2025,
            month=1,
        )


def test_filtered_url_contains_filter():
    url = build_filtered_url(
        slug=(
            "stock-new-listings"
        ),
        year=2025,
        month=1,
    )

    parsed = urlsplit(
        url
    )

    params = parse_qs(
        parsed.query
    )

    assert (
        "filter"
        in params
    )


def test_filtered_url_payload():
    url = build_filtered_url(
        slug=(
            "delisted-company"
        ),
        year=2024,
        month=10,
    )

    parsed = urlsplit(
        url
    )

    params = parse_qs(
        parsed.query
    )

    encoded = params[
        "filter"
    ][0]

    decoded = (
        decode_filter(
            encoded
        )
    )

    assert (
        decoded[
            "year"
        ]
        == "2024"
    )

    assert (
        decoded[
            "month"
        ]
        == "10"
    )


def test_normalize_text():
    html = (
        " Hello   World "
        "\n Test "
    )

    assert (
        normalize_text(
            html
        )
        == "Hello World Test"
    )


def test_normalize_nbsp():
    html = (
        "Hello\xa0World"
    )

    assert (
        normalize_text(
            html
        )
        == "Hello World"
    )


def test_marker_complete():
    html = """
    <table>
      <tr>
        <th>Code</th>
        <th>Company Name</th>
        <th>Listing Date</th>
      </tr>
      <tr>
        <td>TEST</td>
        <td>Test Company</td>
        <td>01 Jan 2025</td>
      </tr>
    </table>
    """

    found, missing = (
        marker_result(
            html=html,
            markers=(
                "Code",
                "Company Name",
                "Listing Date",
                "TEST",
            ),
        )
    )

    assert len(
        found
    ) == 4

    assert not missing


def test_marker_partial():
    html = (
        "<html>Code "
        "Company Name</html>"
    )

    found, missing = (
        marker_result(
            html=html,
            markers=(
                "Code",
                "Listing Date",
            ),
        )
    )

    assert found == (
        "Code",
    )

    assert missing == (
        "Listing Date",
    )


def test_marker_case_insensitive():
    html = (
        "<html>"
        "listing date"
        "</html>"
    )

    found, missing = (
        marker_result(
            html=html,
            markers=(
                "Listing Date",
            ),
        )
    )

    assert found == (
        "Listing Date",
    )

    assert not missing