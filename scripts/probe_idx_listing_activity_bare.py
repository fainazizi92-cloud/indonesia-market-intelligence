import argparse
from dataclasses import dataclass
from time import sleep
from typing import Any

import httpx

IDX_ORIGIN = (
    "https:"
    + "//www.idx.id"
)


LISTING_ACTIVITIES_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "listing-activity-bare-probe"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),
    "Referer": (
        LISTING_ACTIVITIES_URL
    ),
}


MAX_ARRAY_PREVIEW = 10

MAX_TEXT_LENGTH = 1000


IMPORTANT_RESULT_FIELDS = (
    "DataID",
    "id",
    "KodeEmiten",
    "NamaEmiten",
    "JenisEmiten",
    "EfekType",
    "RencanaStatus",
    "TanggalPencatatan",
    "Delisting",
    "PapanPencatatan",
    "SahamIPOValue",
)


@dataclass(
    frozen=True,
    slots=True,
)
class ProbeTarget:
    name: str
    endpoint: str


TARGETS = (
    ProbeTarget(
        name="DELISTING",
        endpoint=(
            "/primary/ListingActivity/"
            "GetDelisting"
        ),
    ),
    ProbeTarget(
        name="IPO_RELISTING",
        endpoint=(
            "/primary/ListingActivity/"
            "GetIpoRelisting"
        ),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect bare responses from "
            "observed IDX ListingActivity "
            "endpoints without supplying "
            "query parameters."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.25,
    )

    parser.add_argument(
        "--preview",
        type=int,
        default=1500,
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )

    if args.preview <= 0:
        raise ValueError(
            "preview must be positive."
        )


def compact_text(
    value: str,
) -> str:
    return " ".join(
        value.split()
    )


def truncate_text(
    value: str,
    *,
    limit: int = MAX_TEXT_LENGTH,
) -> str:
    normalized = compact_text(
        value
    )

    if len(
        normalized
    ) <= limit:
        return normalized

    return (
        normalized[
            :limit
        ]
        + "..."
    )


def display_value_type(
    value: Any,
) -> str:
    if value is None:
        return "null"

    if isinstance(
        value,
        bool,
    ):
        return "bool"

    if isinstance(
        value,
        dict,
    ):
        return (
            f"object[{len(value)}]"
        )

    if isinstance(
        value,
        list,
    ):
        return (
            f"array[{len(value)}]"
        )

    return type(
        value
    ).__name__


def render_scalar(
    value: Any,
) -> str:
    if value is None:
        return "None"

    if isinstance(
        value,
        str,
    ):
        return repr(
            truncate_text(
                value
            )
        )

    return repr(
        value
    )


def print_object_values(
    *,
    value: dict[Any, Any],
    indent: str,
) -> None:
    if not value:
        print(
            f"{indent}-"
        )

        return

    for key, item in (
        value.items()
    ):
        item_type = (
            display_value_type(
                item
            )
        )

        if isinstance(
            item,
            dict,
        ):
            print(
                f"{indent}{key} "
                f": {item_type}"
            )

            print_object_values(
                value=item,
                indent=(
                    indent
                    + "  "
                ),
            )

        elif isinstance(
            item,
            list,
        ):
            print(
                f"{indent}{key} "
                f": {item_type}"
            )

        else:
            print(
                f"{indent}{key} "
                f": {item_type} "
                f"= {render_scalar(item)}"
            )


def selected_result_fields(
    value: dict[Any, Any],
) -> tuple[
    tuple[
        str,
        Any,
    ],
    ...
]:
    results = []

    for field in (
        IMPORTANT_RESULT_FIELDS
    ):
        if field not in value:
            continue

        results.append(
            (
                field,
                value[
                    field
                ],
            )
        )

    return tuple(
        results
    )


def print_result_item(
    *,
    item: Any,
    index: int,
) -> None:
    print(
        f"    ITEM {index}"
    )

    if not isinstance(
        item,
        dict,
    ):
        print(
            f"      Value : "
            f"{render_scalar(item)}"
        )

        return

    selected = (
        selected_result_fields(
            item
        )
    )

    if selected:
        for field, value in (
            selected
        ):
            print(
                f"      {field:<18} "
                f": {render_scalar(value)}"
            )

    else:
        for key, value in (
            item.items()
        ):
            if isinstance(
                value,
                (
                    dict,
                    list,
                ),
            ):
                print(
                    f"      {key:<18} "
                    f": "
                    f"{display_value_type(value)}"
                )

            else:
                print(
                    f"      {key:<18} "
                    f": {render_scalar(value)}"
                )


def print_array_values(
    *,
    value: list[Any],
    indent: str,
) -> None:
    print(
        f"{indent}Array items : "
        f"{len(value)}"
    )

    if not value:
        return

    preview_count = min(
        len(
            value
        ),
        MAX_ARRAY_PREVIEW,
    )

    print(
        f"{indent}Preview     : "
        f"{preview_count}"
    )

    for index, item in enumerate(
        value[
            :preview_count
        ],
        start=1,
    ):
        print_result_item(
            item=item,
            index=index,
        )


def print_json_summary(
    payload: Any,
) -> None:
    print(
        f"JSON root type : "
        f"{display_value_type(payload)}"
    )

    if isinstance(
        payload,
        list,
    ):
        print_array_values(
            value=payload,
            indent="  ",
        )

        return

    if not isinstance(
        payload,
        dict,
    ):
        print(
            f"JSON value     : "
            f"{render_scalar(payload)}"
        )

        return

    keys = tuple(
        str(
            key
        )
        for key in payload
    )

    print(
        "Top-level keys : "
        + (
            ", ".join(
                keys
            )
            if keys
            else "-"
        )
    )

    for key, value in (
        payload.items()
    ):
        value_type = (
            display_value_type(
                value
            )
        )

        print(
            f"{key} : "
            f"{value_type}"
        )

        if isinstance(
            value,
            dict,
        ):
            print_object_values(
                value=value,
                indent="  ",
            )

        elif isinstance(
            value,
            list,
        ):
            print_array_values(
                value=value,
                indent="  ",
            )

        else:
            print(
                "  Value : "
                + render_scalar(
                    value
                )
            )


def print_response(
    *,
    target: ProbeTarget,
    response: httpx.Response,
    preview_length: int,
) -> None:
    print(
        target.name
    )

    print(
        f"URL          : "
        f"{response.url}"
    )

    print(
        f"HTTP         : "
        f"{response.status_code}"
    )

    print(
        f"Content type : "
        f"{response.headers.get('content-type')}"
    )

    print(
        f"Bytes        : "
        f"{len(response.content)}"
    )

    print(
        f"Redirects    : "
        f"{len(response.history)}"
    )

    try:
        payload = (
            response.json()
        )

    except ValueError:
        payload = None

        print(
            "JSON         : NO"
        )

    else:
        print(
            "JSON         : YES"
        )

        print_json_summary(
            payload
        )

    if payload is None:
        preview = truncate_text(
            response.text,
            limit=(
                preview_length
            ),
        )

        print(
            f"Body preview : "
            f"{preview}"
        )

    print()


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX ListingActivity Bare "
        "API Probe V2"
    )

    print(
        "----------------------------"
    )

    print(
        "Query parameters : NONE"
    )

    print(
        f"Targets          : "
        f"{len(TARGETS)}"
    )

    print()

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for index, target in enumerate(
            TARGETS,
            start=1,
        ):
            url = (
                IDX_ORIGIN
                + target.endpoint
            )

            try:
                response = client.get(
                    url
                )

            except httpx.HTTPError as exc:
                print(
                    target.name
                )

                print(
                    "HTTP         : ERROR"
                )

                print(
                    f"Error type   : "
                    f"{type(exc).__name__}"
                )

                print(
                    f"Detail       : "
                    f"{exc}"
                )

                print()

            else:
                print_response(
                    target=target,
                    response=response,
                    preview_length=(
                        args.preview
                    ),
                )

            if (
                index
                < len(
                    TARGETS
                )
                and args.pause > 0
            ):
                sleep(
                    args.pause
                )

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "This probe supplies zero query "
        "parameters."
    )

    print(
        "SearchCriteria values and server "
        "messages are treated as observed "
        "contract evidence."
    )

    print(
        "No historical database rows are "
        "written by this probe."
    )

    print()

    print(
        "DATABASE WRITE:"
    )

    print(
        "ENABLED : NO"
    )


if __name__ == "__main__":
    main()