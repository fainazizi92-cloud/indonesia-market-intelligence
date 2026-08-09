import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import (
    urlencode,
    urlsplit,
    urlunsplit,
)

IDX_ORIGIN = (
    "https:"
    + "//www.idx.id"
)


DOWNLOAD_CALL_PATTERN = re.compile(
    r"""downloadReport\(
        \s*
        ["']
        ([A-Za-z0-9_.-]+)
        ["']
        \s*
    \)""",
    flags=(
        re.IGNORECASE
        | re.VERBOSE
    ),
)


@dataclass(
    frozen=True,
    slots=True,
)
class DigitalStatisticMetadata:
    download_code: str
    title: str

    aliases: tuple[
        str,
        ...
    ]

    api_urls: tuple[
        str,
        ...
    ]


def extract_download_types(
    text: str,
) -> tuple[str, ...]:
    found = (
        DOWNLOAD_CALL_PATTERN.findall(
            text
        )
    )

    result = []
    seen = set()

    for value in found:
        normalized = (
            value.strip()
            .casefold()
        )

        if not normalized:
            continue

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        result.append(
            normalized
        )

    return tuple(
        result
    )


def _metadata_value(
    payload: dict[str, Any],
    *,
    key: str,
) -> Any:
    container = payload.get(
        key
    )

    if not isinstance(
        container,
        dict,
    ):
        return None

    return container.get(
        "value"
    )


def extract_digital_stat_metadata(
    payload: Any,
) -> DigitalStatisticMetadata:
    if not isinstance(
        payload,
        dict,
    ):
        raise TypeError(
            "Page metadata must be "
            "an object."
        )

    download_code = (
        _metadata_value(
            payload,
            key="downloadCode",
        )
    )

    title = (
        _metadata_value(
            payload,
            key="title",
        )
    )

    if (
        not isinstance(
            download_code,
            str,
        )
        or not download_code.strip()
    ):
        raise ValueError(
            "Missing downloadCode."
        )

    if (
        not isinstance(
            title,
            str,
        )
        or not title.strip()
    ):
        raise ValueError(
            "Missing page title."
        )

    table_chart_list = (
        _metadata_value(
            payload,
            key="tableChartList",
        )
    )

    aliases = []
    api_urls = []

    if isinstance(
        table_chart_list,
        list,
    ):
        for item in table_chart_list:
            if not isinstance(
                item,
                dict,
            ):
                continue

            alias = item.get(
                "alias"
            )

            api_url = item.get(
                "apiUrl"
            )

            if (
                isinstance(
                    alias,
                    str,
                )
                and alias.strip()
            ):
                aliases.append(
                    alias.strip()
                )

            if (
                isinstance(
                    api_url,
                    str,
                )
                and api_url.strip()
            ):
                api_urls.append(
                    api_url.strip()
                )

    return DigitalStatisticMetadata(
        download_code=(
            download_code.strip()
        ),
        title=(
            title.strip()
        ),
        aliases=tuple(
            aliases
        ),
        api_urls=tuple(
            api_urls
        ),
    )


def build_report_url(
    *,
    report_type: str,
    year: int,
    month: int,
    download_code: str,
    filename: str,
) -> str:
    normalized_type = (
        report_type.strip()
    )

    normalized_code = (
        download_code.strip()
    )

    normalized_filename = (
        filename.strip()
    )

    if not normalized_type:
        raise ValueError(
            "report_type cannot be empty."
        )

    if year < 1900:
        raise ValueError(
            "year must be 1900 or later."
        )

    if not 1 <= month <= 12:
        raise ValueError(
            "month must be between 1 and 12."
        )

    if not normalized_code:
        raise ValueError(
            "download_code cannot be empty."
        )

    if not normalized_filename:
        raise ValueError(
            "filename cannot be empty."
        )

    base_url = (
        IDX_ORIGIN
        + "/primary/DigitalStatistic/"
        "GetReportData"
    )

    parsed = urlsplit(
        base_url
    )

    query = urlencode(
        {
            "type":
                normalized_type,

            "periodType":
                "monthly",

            "periodYear":
                year,

            "periodMonth":
                month,

            "cumulative":
                "false",

            "filecode":
                normalized_code,

            "filename":
                normalized_filename,
        }
    )

    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            query,
            "",
        )
    )