from typing import Any

import httpx

from imi.features.historical_source import (
    HistoricalSourceDefinition,
)
from imi.features.historical_source_contract import (
    extract_source_contract,
    prepare_contract_row,
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "historical-contract-inspector"
    ),

    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/json,text/plain,"
        "*/*;q=0.8"
    ),
}


def create_contract_client(
    *,
    timeout: float,
) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    )


def inspect_contract(
    definition: HistoricalSourceDefinition,
    *,
    client: httpx.Client,
) -> dict[str, Any]:
    try:
        response = client.get(
            definition.probe_url
        )

        body = response.content

        content_type = (
            response.headers.get(
                "content-type"
            )
        )

        if response.is_success:
            extraction = (
                extract_source_contract(
                    base_url=str(
                        response.url
                    ),
                    body_text=(
                        response.text
                    ),
                )
            )

            error_type = None
            error_message = None

        else:
            extraction = None

            error_type = (
                "HTTP_STATUS_ERROR"
            )

            error_message = (
                f"HTTP "
                f"{response.status_code}"
            )

        return prepare_contract_row(
            source_key=(
                definition.source_key
            ),
            requested_url=(
                definition.probe_url
            ),
            final_url=str(
                response.url
            ),
            http_status=(
                response.status_code
            ),
            content_type=(
                content_type
            ),
            body=body,
            extraction=extraction,
            error_type=(
                error_type
            ),
            error_message=(
                error_message
            ),
        )

    except httpx.HTTPError as exc:
        return prepare_contract_row(
            source_key=(
                definition.source_key
            ),
            requested_url=(
                definition.probe_url
            ),
            final_url=None,
            http_status=None,
            content_type=None,
            body=None,
            extraction=None,
            error_type=(
                type(exc).__name__
            ),
            error_message=str(
                exc
            ),
        )