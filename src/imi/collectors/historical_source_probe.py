from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from imi.features.historical_source import (
    HistoricalSourceDefinition,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "historical-source-discovery"
    ),
    "Accept": (
        "text/html,application/json,"
        "text/plain;q=0.9,*/*;q=0.8"
    ),
}


@dataclass(frozen=True, slots=True)
class ProbeResult:
    source_key: str

    success: bool

    http_status: int | None

    final_url: str | None

    content_type: str | None

    content_length: int | None

    marker_hits: int
    marker_total: int

    elapsed_ms: float

    error_type: str | None
    error_message: str | None

    marker_details: dict[str, Any]

    evidence: dict[str, Any]

    def as_repository_row(
        self,
    ) -> dict[str, Any]:
        return {
            "source_key":
                self.source_key,

            "success":
                self.success,

            "http_status":
                self.http_status,

            "final_url":
                self.final_url,

            "content_type":
                self.content_type,

            "content_length":
                self.content_length,

            "marker_hits":
                self.marker_hits,

            "marker_total":
                self.marker_total,

            "elapsed_ms":
                round(
                    self.elapsed_ms,
                    3,
                ),

            "error_type":
                self.error_type,

            "error_message":
                self.error_message,

            "marker_details":
                self.marker_details,

            "evidence":
                self.evidence,
        }


def match_html_markers(
    *,
    text: str,
    markers: tuple[str, ...],
) -> tuple[str, ...]:
    lowered = text.casefold()

    return tuple(
        marker
        for marker in markers
        if marker.casefold()
        in lowered
    )


def count_json_rows(
    payload: Any,
) -> int:
    if isinstance(
        payload,
        list,
    ):
        return len(
            payload
        )

    if not isinstance(
        payload,
        dict,
    ):
        return 0

    for key in (
        "data",
        "Data",
        "results",
        "Results",
    ):
        value = payload.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            return len(
                value
            )

    return 0


def probe_source(
    definition: HistoricalSourceDefinition,
    *,
    client: httpx.Client,
) -> ProbeResult:
    started = perf_counter()

    try:
        response = client.get(
            definition.probe_url
        )

        elapsed_ms = (
            perf_counter()
            - started
        ) * 1000.0

        content_type = (
            response.headers.get(
                "content-type"
            )
        )

        content_length = len(
            response.content
        )

        if (
            definition.response_mode
            == "JSON_ROWS"
        ):
            try:
                payload = (
                    response.json()
                )

                row_count = (
                    count_json_rows(
                        payload
                    )
                )

                validation_ok = (
                    row_count > 0
                )

                marker_hits = (
                    1
                    if validation_ok
                    else 0
                )

                marker_total = 1

                marker_details = {
                    "response_mode":
                        "JSON_ROWS",

                    "json_rows":
                        row_count,
                }

                error_type = None
                error_message = None

            except ValueError as exc:
                validation_ok = False

                marker_hits = 0
                marker_total = 1

                marker_details = {
                    "response_mode":
                        "JSON_ROWS",

                    "json_rows":
                        0,
                }

                error_type = (
                    "JSON_DECODE_ERROR"
                )

                error_message = str(
                    exc
                )

        else:
            matched = (
                match_html_markers(
                    text=response.text,
                    markers=(
                        definition
                        .expected_markers
                    ),
                )
            )

            marker_hits = len(
                matched
            )

            marker_total = len(
                definition
                .expected_markers
            )

            validation_ok = (
                marker_hits
                >= definition
                .min_marker_hits
            )

            marker_details = {
                "response_mode":
                    "HTML_MARKERS",

                "expected":
                    list(
                        definition
                        .expected_markers
                    ),

                "matched":
                    list(
                        matched
                    ),

                "min_required":
                    definition
                    .min_marker_hits,
            }

            error_type = None
            error_message = None

        success = (
            response.is_success
            and validation_ok
        )

        if (
            response.is_success
            and not validation_ok
            and error_type is None
        ):
            error_type = (
                "CONTENT_VALIDATION_FAILED"
            )

            error_message = (
                "HTTP response succeeded "
                "but expected source "
                "content was not confirmed."
            )

        if not response.is_success:
            error_type = (
                "HTTP_STATUS_ERROR"
            )

            error_message = (
                f"HTTP {response.status_code}"
            )

        return ProbeResult(
            source_key=(
                definition.source_key
            ),
            success=success,
            http_status=(
                response.status_code
            ),
            final_url=str(
                response.url
            ),
            content_type=(
                content_type
            ),
            content_length=(
                content_length
            ),
            marker_hits=(
                marker_hits
            ),
            marker_total=(
                marker_total
            ),
            elapsed_ms=(
                elapsed_ms
            ),
            error_type=(
                error_type
            ),
            error_message=(
                error_message
            ),
            marker_details=(
                marker_details
            ),
            evidence={
                "probe_scope":
                    (
                        "SOURCE_DISCOVERY_ONLY"
                    ),

                "bulk_download":
                    False,

                "historical_rows_ingested":
                    False,
            },
        )

    except httpx.HTTPError as exc:
        elapsed_ms = (
            perf_counter()
            - started
        ) * 1000.0

        return ProbeResult(
            source_key=(
                definition.source_key
            ),
            success=False,
            http_status=None,
            final_url=None,
            content_type=None,
            content_length=None,
            marker_hits=0,
            marker_total=max(
                1,
                len(
                    definition
                    .expected_markers
                ),
            ),
            elapsed_ms=(
                elapsed_ms
            ),
            error_type=(
                type(exc).__name__
            ),
            error_message=str(
                exc
            ),
            marker_details={
                "response_mode":
                    definition
                    .response_mode,

                "expected":
                    list(
                        definition
                        .expected_markers
                    ),
            },
            evidence={
                "probe_scope":
                    (
                        "SOURCE_DISCOVERY_ONLY"
                    ),

                "bulk_download":
                    False,

                "historical_rows_ingested":
                    False,
            },
        )


def create_probe_client(
    *,
    timeout: float,
) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    )