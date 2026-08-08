from urllib.parse import urlparse
from uuid import UUID

from imi.features.historical_source import (
    REQUIRED_HISTORICAL_FAMILIES,
    evaluate_discovery_readiness,
    historical_source_definitions,
    prepare_catalog_rows,
    source_definition_map,
)

from imi.collectors.historical_source_probe import (
    count_json_rows,
    match_html_markers,
)

SOURCE_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def definitions():
    return (
        historical_source_definitions()
    )


def test_definition_count():
    assert len(
        definitions()
    ) == 11


def test_source_keys_unique():
    keys = [
        item.source_key
        for item in definitions()
    ]

    assert len(
        keys
    ) == len(
        set(
            keys
        )
    )


def test_required_families_present():
    families = {
        item.dataset_family
        for item in definitions()
    }

    assert set(
        REQUIRED_HISTORICAL_FAMILIES
    ).issubset(
        families
    )


def test_all_routes_use_idx_domain():
    for item in definitions():
        assert (
            urlparse(
                item.probe_url
            ).hostname
            == "www.idx.id"
        )


def test_listing_activities_family():
    item = (
        source_definition_map()[
            "IDX_LISTING_ACTIVITIES"
        ]
    )

    assert (
        item.dataset_family
        == "LIFECYCLE"
    )

    assert (
        item.priority
        == 1
    )


def test_announcements_limited_window():
    item = (
        source_definition_map()[
            "IDX_ANNOUNCEMENTS"
        ]
    )

    assert (
        item.historical_access
        == "THREE_YEAR_WINDOW"
    )


def test_company_profile_api_current_only():
    item = (
        source_definition_map()[
            "IDX_COMPANY_PROFILES_API"
        ]
    )

    assert (
        item.dataset_family
        == "CURRENT_CROSSCHECK"
    )

    assert (
        item.historical_access
        == "CURRENT_ONLY"
    )

    assert (
        item.point_in_time_potential
        is False
    )


def test_digital_stat_count():
    digital = [
        item
        for item in definitions()
        if item.source_kind
        == "DIGITAL_STAT"
    ]

    assert len(
        digital
    ) == 6


def test_digital_stats_are_downloadable():
    digital = [
        item
        for item in definitions()
        if item.source_kind
        == "DIGITAL_STAT"
    ]

    assert all(
        item.supports_download
        for item in digital
    )


def test_watchlist_supports_date_filter():
    item = (
        source_definition_map()[
            "IDX_WATCHLIST_BOARD"
        ]
    )

    assert (
        item.supports_date_filter
        is True
    )

    assert (
        item.dataset_family
        == "BOARD_HISTORY"
    )


def test_catalog_row_count():
    rows = prepare_catalog_rows(
        source_id=SOURCE_ID
    )

    assert len(
        rows
    ) == 11


def test_catalog_row_source_id():
    rows = prepare_catalog_rows(
        source_id=SOURCE_ID
    )

    assert all(
        row[
            "source_id"
        ]
        == SOURCE_ID
        for row in rows
    )


def test_catalog_probe_config():
    rows = prepare_catalog_rows(
        source_id=SOURCE_ID
    )

    listing = next(
        row
        for row in rows
        if row[
            "source_key"
        ]
        == "IDX_LISTING_ACTIVITIES"
    )

    assert (
        listing[
            "probe_config"
        ][
            "response_mode"
        ]
        == "HTML_MARKERS"
    )


def test_html_marker_case_insensitive():
    matched = (
        match_html_markers(
            text=(
                "stock splits and "
                "REVERSE stocks"
            ),
            markers=(
                "Stock Splits",
                "Reverse",
            ),
        )
    )

    assert len(
        matched
    ) == 2


def test_html_marker_partial():
    matched = (
        match_html_markers(
            text="Delisted Company",
            markers=(
                "Delisted Company",
                "Download",
            ),
        )
    )

    assert matched == (
        "Delisted Company",
    )


def test_json_rows_data_key():
    assert (
        count_json_rows(
            {
                "data": [
                    {"a": 1},
                    {"a": 2},
                ]
            }
        )
        == 2
    )


def test_json_rows_list():
    assert (
        count_json_rows(
            [
                {"a": 1},
                {"a": 2},
                {"a": 3},
            ]
        )
        == 3
    )


def test_json_rows_invalid_payload():
    assert (
        count_json_rows(
            "not-json-object"
        )
        == 0
    )


def test_readiness_with_required_families():
    probes = {
        "IDX_LISTING_ACTIVITIES": {
            "success": True,
        },

        "IDX_WATCHLIST_BOARD": {
            "success": True,
        },

        "IDX_DIGITAL_STOCK_SPLITS": {
            "success": True,
        },
    }

    result = (
        evaluate_discovery_readiness(
            latest_probes=probes,
        )
    )

    assert (
        result.ready_for_parser_work
        is True
    )


def test_readiness_missing_board_family():
    probes = {
        "IDX_LISTING_ACTIVITIES": {
            "success": True,
        },

        "IDX_DIGITAL_STOCK_SPLITS": {
            "success": True,
        },
    }

    result = (
        evaluate_discovery_readiness(
            latest_probes=probes,
        )
    )

    assert (
        result.board_history_reachable
        is False
    )

    assert (
        result.ready_for_parser_work
        is False
    )


def test_historical_routes_not_approved():
    historical = [
        item
        for item in definitions()
        if item.dataset_family
        != "CURRENT_CROSSCHECK"
    ]

    assert all(
        item.automation_status
        != "APPROVED"
        for item in historical
    )