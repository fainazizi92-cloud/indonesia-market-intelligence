from imi.features.historical_source_contract import (
    body_sha256,
    classify_endpoint_hints,
    determine_parser_status,
    extract_source_contract,
    is_candidate_url,
    normalize_candidate_url,
)

BASE_URL = (
    "https://www.idx.id/"
    "en/listed-companies/"
    "listing-activities"
)


def test_sha256_stable():
    first = body_sha256(
        b"abc"
    )

    second = body_sha256(
        b"abc"
    )

    assert first == second

    assert len(
        first
    ) == 64


def test_relative_url_normalized():
    result = (
        normalize_candidate_url(
            base_url=BASE_URL,
            value=(
                "/primary/"
                "ListedCompany/Test"
            ),
        )
    )

    assert result == (
        "https://www.idx.id/"
        "primary/ListedCompany/Test"
    )


def test_javascript_url_ignored():
    result = (
        normalize_candidate_url(
            base_url=BASE_URL,
            value=(
                "javascript:void(0)"
            ),
        )
    )

    assert result is None


def test_download_candidate():
    url = (
        "https://www.idx.id/"
        "files/listing.xlsx"
    )

    assert (
        is_candidate_url(
            url
        )
        is True
    )


def test_primary_candidate():
    url = (
        "https://www.idx.id/"
        "primary/ListedCompany/Test"
    )

    assert (
        is_candidate_url(
            url
        )
        is True
    )


def test_irrelevant_url_not_candidate():
    url = (
        "https://www.idx.id/"
        "images/logo.png"
    )

    assert (
        is_candidate_url(
            url
        )
        is False
    )


def test_extract_counts_html_elements():
    html = """
    <html>
      <body>
        <a href="/download/listing.xlsx">
            Download
        </a>

        <script src="/assets/listing.js"></script>

        <form action="/primary/listing/search">
        </form>
      </body>
    </html>
    """

    result = (
        extract_source_contract(
            base_url=BASE_URL,
            body_text=html,
        )
    )

    assert (
        result.anchor_count
        == 1
    )

    assert (
        result.script_count
        == 1
    )

    assert (
        result.form_count
        == 1
    )


def test_extract_relative_candidates():
    html = """
    <a href="/download/new-listing.xlsx">
        file
    </a>

    <form action="/primary/listing/search">
    </form>
    """

    result = (
        extract_source_contract(
            base_url=BASE_URL,
            body_text=html,
        )
    )

    assert len(
        result.candidate_urls
    ) == 2


def test_extract_absolute_inline_url():
    html = """
    <script>
    const url =
      "https://www.idx.id/primary/ListedCompany/Test";
    </script>
    """

    result = (
        extract_source_contract(
            base_url=BASE_URL,
            body_text=html,
        )
    )

    assert any(
        "/primary/" in url
        for url in (
            result
            .candidate_urls
        )
    )


def test_candidate_urls_are_deduplicated():
    html = """
    <a href="/download/listing.xlsx">A</a>
    <a href="/download/listing.xlsx">B</a>
    """

    result = (
        extract_source_contract(
            base_url=BASE_URL,
            body_text=html,
        )
    )

    assert len(
        result.candidate_urls
    ) == 1


def test_endpoint_hint_classification():
    primary_url = (
        "https://www.idx.id/"
        "primary/ListedCompany/Test"
    )

    download_url = (
        "https://www.idx.id/"
        "download/listing.xlsx"
    )

    urls = (
        primary_url,
        download_url,
    )

    hints = (
        classify_endpoint_hints(
            urls
        )
    )

    assert len(
        hints[
            "primary_like"
        ]
    ) == 1

    assert len(
        hints[
            "download_like"
        ]
    ) == 1


def test_candidate_parser_status():
    result = (
        extract_source_contract(
            base_url=BASE_URL,
            body_text=(
                '<a href="/download/'
                'listing.xlsx">x</a>'
            ),
        )
    )

    assert (
        determine_parser_status(
            result
        )
        == "CANDIDATE"
    )