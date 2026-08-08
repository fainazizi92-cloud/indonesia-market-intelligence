from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlunsplit
from uuid import UUID

HISTORICAL_SOURCE_VERSION = (
    "historical_source_discovery_v1"
)


REQUIRED_HISTORICAL_FAMILIES = (
    "LIFECYCLE",
    "BOARD_HISTORY",
    "CORPORATE_ACTION",
)


@dataclass(frozen=True, slots=True)
class HistoricalSourceDefinition:
    source_key: str

    dataset_family: str
    source_kind: str
    authority_class: str

    base_url: str
    probe_url: str

    historical_access: str
    access_mode: str

    supports_download: bool
    supports_date_filter: bool

    point_in_time_potential: bool

    automation_status: str

    priority: int

    response_mode: str

    expected_markers: tuple[str, ...]
    min_marker_hits: int

    evidence: dict[str, Any]


@dataclass(frozen=True, slots=True)
class DiscoveryReadiness:
    source_total: int

    probes_present: int
    successful_probes: int

    lifecycle_reachable: bool
    board_history_reachable: bool
    corporate_action_reachable: bool

    ready_for_parser_work: bool


def _idx_url(
    path: str,
    *,
    query: str = "",
) -> str:
    return urlunsplit(
        (
            "https",
            "www.idx.id",
            path,
            query,
            "",
        )
    )


def historical_source_definitions(
) -> tuple[HistoricalSourceDefinition, ...]:
    company_profile_query = urlencode(
        {
            "emitenType": "s",
            "start": 0,
            "length": 1,
        }
    )

    digital_base = (
        "/en/market-data/"
        "statistical-reports/"
        "digital-statistic/monthly/"
        "corporate-action-of-listed-companies/"
    )

    return (
        HistoricalSourceDefinition(
            source_key=(
                "IDX_LISTING_ACTIVITIES"
            ),
            dataset_family="LIFECYCLE",
            source_kind="HTML_PAGE",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                "/en/listed-companies/"
                "listing-activities"
            ),
            probe_url=_idx_url(
                "/en/listed-companies/"
                "listing-activities"
            ),
            historical_access=(
                "YEAR_FILTER"
            ),
            access_mode="PUBLIC_WEB",
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "New Listing",
                "Delisting",
                "Relisting",
            ),
            min_marker_hits=2,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Primary lifecycle "
                        "discovery route."
                    ),

                "warning":
                    (
                        "No historical rows "
                        "are ingested in "
                        "Phase 3N.2A."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_DIGITAL_NEW_LISTINGS"
            ),
            dataset_family="LIFECYCLE",
            source_kind="DIGITAL_STAT",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                digital_base
                + "stock-new-listings"
            ),
            probe_url=_idx_url(
                digital_base
                + "stock-new-listings"
            ),
            historical_access=(
                "MONTHLY_ARCHIVE"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Stock New Listing",
                "Download",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Monthly official "
                        "listing cross-check."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_DIGITAL_DELISTED_COMPANY"
            ),
            dataset_family="LIFECYCLE",
            source_kind="DIGITAL_STAT",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                digital_base
                + "delisted-company"
            ),
            probe_url=_idx_url(
                digital_base
                + "delisted-company"
            ),
            historical_access=(
                "MONTHLY_ARCHIVE"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Delisted Company",
                "Download",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Primary delisting "
                        "historical source."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_WATCHLIST_BOARD"
            ),
            dataset_family="BOARD_HISTORY",
            source_kind="HTML_PAGE",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                "/id/perusahaan-tercatat/"
                "daftar-efek-pemantauan-khusus/"
            ),
            probe_url=_idx_url(
                "/id/perusahaan-tercatat/"
                "daftar-efek-pemantauan-khusus/"
            ),
            historical_access=(
                "DATE_FILTER"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Pemantauan Khusus",
                "Tanggal Masuk",
                "Unduh",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Historical watchlist "
                        "board discovery."
                    ),

                "warning":
                    (
                        "This route does not "
                        "alone reconstruct Main, "
                        "Development, Acceleration, "
                        "or New Economy history."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_ANNOUNCEMENTS"
            ),
            dataset_family="BOARD_HISTORY",
            source_kind=(
                "ANNOUNCEMENT_ARCHIVE"
            ),
            authority_class=(
                "PRIMARY_OFFICIAL_LIMITED"
            ),
            base_url=_idx_url(
                "/en/news/announcement"
            ),
            probe_url=_idx_url(
                "/en/news/announcement"
            ),
            historical_access=(
                "THREE_YEAR_WINDOW"
            ),
            access_mode="PUBLIC_WEB",
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Announcements",
                "3 years",
                "TICMI",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Board-change and "
                        "exchange-announcement "
                        "evidence."
                    ),

                "public_history_limit":
                    (
                        "IDX states that the "
                        "public announcement "
                        "page provides only "
                        "recent years; older "
                        "history is routed "
                        "to TICMI."
                    ),

                "warning":
                    (
                        "Do not mark board "
                        "history complete from "
                        "this route alone."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_CORPORATE_ACTIONS_PAGE"
            ),
            dataset_family=(
                "CORPORATE_ACTION"
            ),
            source_kind="HTML_PAGE",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                "/en/listed-companies/"
                "corporate-actions"
            ),
            probe_url=_idx_url(
                "/en/listed-companies/"
                "corporate-actions"
            ),
            historical_access=(
                "DATE_FILTER"
            ),
            access_mode="PUBLIC_WEB",
            supports_download=False,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=2,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Corporate Actions",
                "Start",
                "End",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Generic corporate "
                        "action cross-check."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_DIGITAL_STOCK_SPLITS"
            ),
            dataset_family=(
                "CORPORATE_ACTION"
            ),
            source_kind="DIGITAL_STAT",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                digital_base
                + "stock-splits-and-reverse-stocks"
            ),
            probe_url=_idx_url(
                digital_base
                + "stock-splits-and-reverse-stocks"
            ),
            historical_access=(
                "MONTHLY_ARCHIVE"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Stock Splits",
                "Reverse",
                "Download",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Critical price-scale "
                        "corporate actions."
                    ),

                "priority_reason":
                    (
                        "Stock splits and reverse "
                        "splits can materially "
                        "distort unadjusted "
                        "historical comparisons."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_DIGITAL_RIGHT_OFFERINGS"
            ),
            dataset_family=(
                "CORPORATE_ACTION"
            ),
            source_kind="DIGITAL_STAT",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                digital_base
                + "right-offerings"
            ),
            probe_url=_idx_url(
                digital_base
                + "right-offerings"
            ),
            historical_access=(
                "MONTHLY_ARCHIVE"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=1,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Right Offerings",
                "Download",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Rights issue "
                        "corporate actions."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_DIGITAL_ADDITIONAL_SHARES"
            ),
            dataset_family=(
                "CORPORATE_ACTION"
            ),
            source_kind="DIGITAL_STAT",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                digital_base
                + "additional-listed-shares"
            ),
            probe_url=_idx_url(
                digital_base
                + "additional-listed-shares"
            ),
            historical_access=(
                "MONTHLY_ARCHIVE"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=2,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Additional Listed Shares",
                "Download",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Share-count change "
                        "cross-check."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_DIGITAL_DIVIDENDS"
            ),
            dataset_family=(
                "CORPORATE_ACTION"
            ),
            source_kind="DIGITAL_STAT",
            authority_class=(
                "PRIMARY_OFFICIAL"
            ),
            base_url=_idx_url(
                digital_base
                + "dividend-announcement"
            ),
            probe_url=_idx_url(
                digital_base
                + "dividend-announcement"
            ),
            historical_access=(
                "MONTHLY_ARCHIVE"
            ),
            access_mode=(
                "PUBLIC_DOWNLOAD"
            ),
            supports_download=True,
            supports_date_filter=True,
            point_in_time_potential=True,
            automation_status=(
                "DISCOVERY_ONLY"
            ),
            priority=3,
            response_mode="HTML_MARKERS",
            expected_markers=(
                "Dividend Announcement",
                "Download",
            ),
            min_marker_hits=1,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Dividend event "
                        "cross-check."
                    ),

                "warning":
                    (
                        "Cash dividend data "
                        "will not automatically "
                        "be treated as a split "
                        "adjustment factor."
                    ),
            },
        ),

        HistoricalSourceDefinition(
            source_key=(
                "IDX_COMPANY_PROFILES_API"
            ),
            dataset_family=(
                "CURRENT_CROSSCHECK"
            ),
            source_kind=(
                "UNDOCUMENTED_API"
            ),
            authority_class=(
                "OFFICIAL_UNDOCUMENTED"
            ),
            base_url=_idx_url(
                "/primary/ListedCompany/"
                "GetCompanyProfiles"
            ),
            probe_url=_idx_url(
                "/primary/ListedCompany/"
                "GetCompanyProfiles",
                query=company_profile_query,
            ),
            historical_access=(
                "CURRENT_ONLY"
            ),
            access_mode=(
                "UNDOCUMENTED_API"
            ),
            supports_download=False,
            supports_date_filter=False,
            point_in_time_potential=False,
            automation_status="APPROVED",
            priority=2,
            response_mode="JSON_ROWS",
            expected_markers=(),
            min_marker_hits=0,
            evidence={
                "scope":
                    HISTORICAL_SOURCE_VERSION,

                "role":
                    (
                        "Current listing-date "
                        "and board cross-check."
                    ),

                "warning":
                    (
                        "Official-domain but "
                        "undocumented endpoint. "
                        "Not a historical board "
                        "source and may change "
                        "without notice."
                    ),
            },
        ),
    )


def source_definition_map(
) -> dict[str, HistoricalSourceDefinition]:
    return {
        item.source_key: item
        for item in historical_source_definitions()
    }


def catalog_family_counts(
    definitions: tuple[
        HistoricalSourceDefinition,
        ...
    ],
) -> dict[str, int]:
    return dict(
        Counter(
            item.dataset_family
            for item in definitions
        )
    )


def prepare_catalog_rows(
    *,
    source_id: UUID,
) -> list[dict[str, Any]]:
    rows = []

    for definition in (
        historical_source_definitions()
    ):
        rows.append(
            {
                "source_key":
                    definition.source_key,

                "source_id":
                    source_id,

                "dataset_family":
                    definition.dataset_family,

                "source_kind":
                    definition.source_kind,

                "authority_class":
                    definition.authority_class,

                "base_url":
                    definition.base_url,

                "probe_url":
                    definition.probe_url,

                "historical_access":
                    definition.historical_access,

                "access_mode":
                    definition.access_mode,

                "supports_download":
                    definition.supports_download,

                "supports_date_filter":
                    definition.supports_date_filter,

                "point_in_time_potential":
                    definition
                    .point_in_time_potential,

                "automation_status":
                    definition.automation_status,

                "priority":
                    definition.priority,

                "probe_config": {
                    "response_mode":
                        definition.response_mode,

                    "expected_markers":
                        list(
                            definition
                            .expected_markers
                        ),

                    "min_marker_hits":
                        definition
                        .min_marker_hits,
                },

                "evidence":
                    definition.evidence,
            }
        )

    return rows


def evaluate_discovery_readiness(
    *,
    latest_probes: dict[
        str,
        dict[str, Any],
    ],
) -> DiscoveryReadiness:
    definitions = (
        historical_source_definitions()
    )

    probes_present = 0
    successful_probes = 0

    family_success = {
        family: False
        for family
        in REQUIRED_HISTORICAL_FAMILIES
    }

    for definition in definitions:
        probe = latest_probes.get(
            definition.source_key
        )

        if probe is None:
            continue

        probes_present += 1

        success = bool(
            probe.get(
                "success"
            )
        )

        if success:
            successful_probes += 1

            if (
                definition.dataset_family
                in family_success
            ):
                family_success[
                    definition.dataset_family
                ] = True

    ready = all(
        family_success.values()
    )

    return DiscoveryReadiness(
        source_total=len(
            definitions
        ),
        probes_present=(
            probes_present
        ),
        successful_probes=(
            successful_probes
        ),
        lifecycle_reachable=(
            family_success[
                "LIFECYCLE"
            ]
        ),
        board_history_reachable=(
            family_success[
                "BOARD_HISTORY"
            ]
        ),
        corporate_action_reachable=(
            family_success[
                "CORPORATE_ACTION"
            ]
        ),
        ready_for_parser_work=(
            ready
        ),
    )