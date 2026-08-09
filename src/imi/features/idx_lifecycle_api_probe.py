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


NEW_LISTING_API_PATH = (
    "/primary/DigitalStatistic/"
    "GetApiDataPaginated"
)


DELISTING_STAT_PATH = (
    "/api/statisticalhighlight/"
    "stockdelisting"
)


@dataclass(
    frozen=True,
    slots=True,
)
class JsonShape:
    payload_type: str

    top_keys: tuple[
        str,
        ...
    ]

    data_type: str | None

    data_keys: tuple[
        str,
        ...
    ]

    meta_keys: tuple[
        str,
        ...
    ]

    item_count: int | None

    first_item_keys: tuple[
        str,
        ...
    ]


def build_url(
    *,
    path: str,
    params: dict[
        str,
        Any,
    ] | None = None,
) -> str:
    parsed = urlsplit(
        IDX_ORIGIN
        + path
    )

    query = ""

    if params:
        query = urlencode(
            params
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


def build_new_listing_api_url(
    *,
    year: int,
    month: int,
    page_size: int = 100,
    page_number: int = 1,
    order_by: str = "",
    search: str = "",
) -> str:
    if year < 1900:
        raise ValueError(
            "year must be 1900 or later."
        )

    if not 1 <= month <= 12:
        raise ValueError(
            "month must be between 1 and 12."
        )

    if page_size <= 0:
        raise ValueError(
            "page_size must be positive."
        )

    if page_number <= 0:
        raise ValueError(
            "page_number must be positive."
        )

    return build_url(
        path=(
            NEW_LISTING_API_PATH
        ),
        params={
            "urlName":
                "LINK_STOCK_NEW_LISTING",

            "periodYear":
                year,

            "periodMonth":
                month,

            "periodType":
                "monthly",

            "isPrint":
                "False",

            "cumulative":
                "false",

            "pageSize":
                page_size,

            "pageNumber":
                page_number,

            "orderBy":
                order_by,

            "search":
                search,
        },
    )


def build_page_metadata_url(
    *,
    route_path: str,
) -> str:
    normalized = (
        route_path.strip()
    )

    if not normalized:
        raise ValueError(
            "route_path cannot be empty."
        )

    if not normalized.startswith(
        "/"
    ):
        normalized = (
            "/"
            + normalized
        )

    return build_url(
        path=(
            "/primary/page"
            + normalized
        )
    )


def build_delisting_stat_url() -> str:
    return build_url(
        path=(
            DELISTING_STAT_PATH
        )
    )


def _sorted_keys(
    value: dict[
        Any,
        Any,
    ],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(
                key
            )
            for key in value
        )
    )


def _find_items(
    payload: Any,
) -> list[Any] | None:
    if isinstance(
        payload,
        list,
    ):
        return payload

    if not isinstance(
        payload,
        dict,
    ):
        return None

    for key in (
        "items",
        "data",
        "results",
        "rows",
        "records",
    ):
        value = payload.get(
            key
        )

        if isinstance(
            value,
            list,
        ):
            return value

    data = payload.get(
        "data"
    )

    if isinstance(
        data,
        dict,
    ):
        for key in (
            "items",
            "results",
            "rows",
            "records",
            "data",
        ):
            value = data.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return value

    return None


def summarize_json(
    payload: Any,
) -> JsonShape:
    payload_type = (
        type(
            payload
        ).__name__
    )

    top_keys: tuple[
        str,
        ...
    ] = ()

    data_type = None

    data_keys: tuple[
        str,
        ...
    ] = ()

    meta_keys: tuple[
        str,
        ...
    ] = ()

    if isinstance(
        payload,
        dict,
    ):
        top_keys = (
            _sorted_keys(
                payload
            )
        )

        data = payload.get(
            "data"
        )

        if data is not None:
            data_type = (
                type(
                    data
                ).__name__
            )

        if isinstance(
            data,
            dict,
        ):
            data_keys = (
                _sorted_keys(
                    data
                )
            )

            meta = data.get(
                "meta"
            )

            if isinstance(
                meta,
                dict,
            ):
                meta_keys = (
                    _sorted_keys(
                        meta
                    )
                )

        meta = payload.get(
            "meta"
        )

        if (
            not meta_keys
            and isinstance(
                meta,
                dict,
            )
        ):
            meta_keys = (
                _sorted_keys(
                    meta
                )
            )

    items = (
        _find_items(
            payload
        )
    )

    item_count = None

    first_item_keys: tuple[
        str,
        ...
    ] = ()

    if items is not None:
        item_count = len(
            items
        )

        if (
            items
            and isinstance(
                items[0],
                dict,
            )
        ):
            first_item_keys = (
                _sorted_keys(
                    items[0]
                )
            )

    return JsonShape(
        payload_type=(
            payload_type
        ),
        top_keys=(
            top_keys
        ),
        data_type=(
            data_type
        ),
        data_keys=(
            data_keys
        ),
        meta_keys=(
            meta_keys
        ),
        item_count=(
            item_count
        ),
        first_item_keys=(
            first_item_keys
        ),
    )