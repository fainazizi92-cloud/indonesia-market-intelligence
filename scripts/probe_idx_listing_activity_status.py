import argparse
from dataclasses import dataclass
from time import sleep
from typing import Any

import httpx

IDX_ORIGIN = "https://www.idx.id"

LISTING_ACTIVITIES_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "listing-activity-status-probe"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),
    "Referer": LISTING_ACTIVITIES_URL,
}


MAX_RESULT_PREVIEW = 10


@dataclass(
    frozen=True,
    slots=True,
)
class ProbeTarget:
    name: str
    endpoint: str
    status: str


TARGETS = (
    ProbeTarget(
        name="IPO",
        endpoint=(
            "/primary/ListingActivity/"
            "GetIpoRelisting"
        ),
        status="ipo",
    ),
    ProbeTarget(
        name="RELISTING",
        endpoint=(
            "/primary/ListingActivity/"
            "GetIpoRelisting"
        ),
        status="relisting",
    ),
    ProbeTarget(
        name="DELISTING",
        endpoint=(
            "/primary/ListingActivity/"
            "GetDelisting"
        ),
        status="delisting",
    ),
)


IMPORTANT_FIELDS = (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe observed IDX "
            "ListingActivity endpoints "
            "using only observed Status "
            "values."
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


def value_type(
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


def print_search_criteria(
    payload: dict[str, Any],
) -> None:
    criteria = payload.get(
        "SearchCriteria"
    )

    print(
        "SearchCriteria:"
    )

    if not isinstance(
        criteria,
        dict,
    ):
        print(
            "  NOT PRESENT"
        )
        return

    for key, value in (
        criteria.items()
    ):
        print(
            f"  {key:<12} : "
            f"{value!r}"
        )


def print_result_item(
    *,
    item: Any,
    index: int,
) -> None:
    print(
        f"  ITEM {index}"
    )

    if not isinstance(
        item,
        dict,
    ):
        print(
            f"    Value : "
            f"{item!r}"
        )
        return

    for field in (
        IMPORTANT_FIELDS
    ):
        if field not in item:
            continue

        print(
            f"    {field:<18} : "
            f"{item[field]!r}"
        )


def print_results(
    payload: dict[str, Any],
) -> None:
    result = payload.get(
        "Result"
    )

    if not isinstance(
        result,
        list,
    ):
        print(
            "Result:"
        )
        print(
            f"  Type : "
            f"{value_type(result)}"
        )
        return

    print(
        f"Result count : "
        f"{len(result)}"
    )

    if not result:
        return

    first = result[
        0
    ]

    if isinstance(
        first,
        dict,
    ):
        print(
            "Result keys  : "
            + ", ".join(
                str(
                    key
                )
                for key in first
            )
        )

    preview_count = min(
        len(
            result
        ),
        MAX_RESULT_PREVIEW,
    )

    print(
        f"Preview       : "
        f"{preview_count}"
    )

    for index, item in enumerate(
        result[
            :preview_count
        ],
        start=1,
    ):
        print_result_item(
            item=item,
            index=index,
        )


def print_json_payload(
    payload: Any,
) -> None:
    print(
        f"JSON root    : "
        f"{value_type(payload)}"
    )

    if not isinstance(
        payload,
        dict,
    ):
        print(
            f"JSON value   : "
            f"{payload!r}"
        )
        return

    print(
        "Top keys     : "
        + ", ".join(
            str(
                key
            )
            for key in payload
        )
    )

    if "Message" in payload:
        print(
            f"Message      : "
            f"{payload['Message']!r}"
        )

    print_search_criteria(
        payload
    )

    print_results(
        payload
    )


def probe_target(
    *,
    client: httpx.Client,
    target: ProbeTarget,
) -> None:
    url = (
        IDX_ORIGIN
        + target.endpoint
    )

    params = {
        "Status": target.status,
    }

    print(
        target.name
    )

    print(
        f"Endpoint     : "
        f"{target.endpoint}"
    )

    print(
        f"Status sent  : "
        f"{target.status!r}"
    )

    try:
        response = client.get(
            url,
            params=params,
        )

    except httpx.HTTPError as exc:
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
        return

    print(
        f"Final URL    : "
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
        print(
            "JSON         : NO"
        )

        print(
            f"Body         : "
            f"{response.text[:1500]!r}"
        )

    else:
        print(
            "JSON         : YES"
        )

        print_json_payload(
            payload
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
        "IDX ListingActivity Status "
        "Contract Probe V1"
    )

    print(
        "--------------------------------"
    )

    print(
        "Only observed Status values "
        "are used."
    )

    print(
        "Year/pagination/search params "
        "are NOT supplied."
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
            probe_target(
                client=client,
                target=target,
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
        "Status parameter name comes "
        "from server SearchCriteria."
    )

    print(
        "Status values come directly "
        "from the IDX frontend."
    )

    print(
        "No Year, search, pagination, "
        "or other unverified values are "
        "introduced."
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