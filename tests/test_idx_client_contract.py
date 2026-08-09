from imi.features.idx_client_contract import (
    extract_candidate_urls,
    extract_script_urls,
    find_keyword_snippets,
    same_idx_origin,
    scan_client_contract,
)

IDX_ORIGIN = (
    "https:"
    + "//www.idx.id"
)

IDX_CO_ORIGIN = (
    "https:"
    + "//www.idx.co.id"
)

EXTERNAL_ORIGIN = (
    "https:"
    + "//example.com"
)

BASE_URL = (
    f"{IDX_ORIGIN}/"
    "en/market-data/page"
)


def test_idx_origin():
    url = (
        f"{IDX_ORIGIN}/a.js"
    )

    assert (
        same_idx_origin(
            url
        )
        is True
    )


def test_idx_co_id_origin():
    url = (
        f"{IDX_CO_ORIGIN}/a.js"
    )

    assert (
        same_idx_origin(
            url
        )
        is True
    )


def test_external_origin_false():
    url = (
        f"{EXTERNAL_ORIGIN}/a.js"
    )

    assert (
        same_idx_origin(
            url
        )
        is False
    )


def test_extract_same_origin_scripts():
    html = """
    <script src="/assets/a.js"></script>
    <script src="//example.com/b.js"></script>
    """

    result = (
        extract_script_urls(
            base_url=BASE_URL,
            html=html,
        )
    )

    expected = (
        f"{IDX_ORIGIN}/"
        "assets/a.js"
    )

    assert result == (
        expected,
    )


def test_candidate_primary_endpoint():
    text = (
        'const url = '
        '"/primary/ListedCompany/Test";'
    )

    result = (
        extract_candidate_urls(
            base_url=BASE_URL,
            text=text,
        )
    )

    expected = (
        f"{IDX_ORIGIN}/"
        "primary/ListedCompany/Test"
    )

    assert result == (
        expected,
    )


def test_candidate_download():
    text = (
        'const url = '
        '"/download/listing.xlsx";'
    )

    result = (
        extract_candidate_urls(
            base_url=BASE_URL,
            text=text,
        )
    )

    expected = (
        f"{IDX_ORIGIN}/"
        "download/listing.xlsx"
    )

    assert result == (
        expected,
    )


def test_irrelevant_candidate_ignored():
    text = (
        'const image = '
        '"/images/logo.png";'
    )

    result = (
        extract_candidate_urls(
            base_url=BASE_URL,
            text=text,
        )
    )

    assert not result


def test_keyword_snippet():
    text = (
        "abc stock-new-listings xyz"
    )

    result = (
        find_keyword_snippets(
            text=text,
            keywords=(
                "stock-new-listings",
            ),
        )
    )

    assert len(
        result
    ) == 1


def test_scan_contract_combines_html_and_js():
    html = """
    <script src="/assets/app.js"></script>
    """

    script_url = (
        f"{IDX_ORIGIN}/"
        "assets/app.js"
    )

    script_text = (
        'fetch("/primary/'
        'ListedCompany/Test")'
    )

    scripts = (
        (
            script_url,
            script_text,
        ),
    )

    result = (
        scan_client_contract(
            base_url=BASE_URL,
            html=html,
            script_texts=scripts,
        )
    )

    assert any(
        "/primary/"
        in candidate
        for candidate
        in result.candidate_urls
    )

    assert (
        result.network_snippets
    )