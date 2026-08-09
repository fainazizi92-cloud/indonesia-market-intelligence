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
        "listing-activity-year-probe"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),
    "Referer": LISTING_ACTIVITIES_URL,
}


DEFAULT_YEAR = 2026

MAX_PREVIEW = 15


@dataclass(
    frozen=True,
    slots=True,
)
class ProbeTarget:
    name: str
    status: str


TARGETS = (
    ProbeTarget(
        name="IPO",
        status="ipo",
    ),
    ProbeTarget(
        name="RELISTING",
        status="relisting",
    ),
)


IMPORTANT_FIELDS = (
    "KodeEmiten",
    "NamaEmiten",
    "RencanaStatus",
    "TanggalPencatatan",
    "Delisting",
    "PapanPencatatan",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the observed IDX "
            "ListingActivity Year parameter "
            "using an observed listing year."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        default=DEFAULT_YEAR,
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
    if not 1900 <= args.year <= 2100:
        raise ValueError(
            "year must be between "
            "1900 and 2100."
        )

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


def date_year(
    value: Any,
) -> int | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    if len(value) < 4:
        return None

    prefix = value[
        :4
    ]

    if not prefix.isdigit():
        return None

    year = int(
        prefix
    )

    if year == 1:
        return None

    return year


def print_criteria(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
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

        return None

    for key, value in (
        criteria.items()
    ):
        print(
            f"  {key:<12} : "
            f"{value!r}"
        )

    return criteria


def print_item(
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


def analyze_result_years(
    *,
    result: list[Any],
    requested_year: int,
) -> None:
    valid_listing_years = []

    for item in result:
        if not isinstance(
            item,
            dict,
        ):
            continue

        year = date_year(
            item.get(
                "TanggalPencatatan"
            )
        )

        if year is not None:
            valid_listing_years.append(
                year
            )

    unique_years = tuple(
        sorted(
            set(
                valid_listing_years
            )
        )
    )

    print(
        "Observed listing years : "
        + (
            ", ".join(
                str(
                    year
                )
                for year in unique_years
            )
            if unique_years
            else "-"
        )
    )

    if not valid_listing_years:
        print(
            "All records match year : "
            "N/A"
        )

        return

    matches = all(
        year == requested_year
        for year in valid_listing_years
    )

    print(
        f"All records match year : "
        f"{matches}"
    )


def print_result(
    *,
    payload: dict[str, Any],
    requested_year: int,
) -> None:
    result = payload.get(
        "Result"
    )

    print(
        f"Result type  : "
        f"{value_type(result)}"
    )

    if not isinstance(
        result,
        list,
    ):
        return

    print(
        f"Result count : "
        f"{len(result)}"
    )

    analyze_result_years(
        result=result,
        requested_year=(
            requested_year
        ),
    )

    preview_count = min(
        len(
            result
        ),
        MAX_PREVIEW,
    )

    print(
        f"Preview      : "
        f"{preview_count}"
    )

    for index, item in enumerate(
        result[
            :preview_count
        ],
        start=1,
    ):
        print_item(
            item=item,
            index=index,
        )


def probe_target(
    *,
    client: httpx.Client,
    target: ProbeTarget,
    year: int,
) -> None:
    endpoint = (
        "/primary/ListingActivity/"
        "GetIpoRelisting"
    )

    url = (
        IDX_ORIGIN
        + endpoint
    )

    params = {
        "Status": target.status,
        "Year": year,
    }

    print(
        target.name
    )

    print(
        f"Endpoint     : "
        f"{endpoint}"
    )

    print(
        f"Status sent  : "
        f"{target.status!r}"
    )

    print(
        f"Year sent    : "
        f"{year}"
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

        print()

        return

    print(
        "JSON         : YES"
    )

    print(
        f"JSON root    : "
        f"{value_type(payload)}"
    )

    if not isinstance(
        payload,
        dict,
    ):
        print(
            f"Value        : "
            f"{payload!r}"
        )

        print()

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

    criteria = (
        print_criteria(
            payload
        )
    )

    if criteria is not None:
        echoed_year = (
            criteria.get(
                "Year"
            )
        )

        echoed_status = (
            criteria.get(
                "Status"
            )
        )

        print(
            f"Year echoed  : "
            f"{echoed_year!r}"
        )

        print(
            f"Year binding : "
            f"{echoed_year == year}"
        )

        print(
            f"Status echo  : "
            f"{echoed_status!r}"
        )

        print(
            f"Status bind  : "
            f"{echoed_status == target.status}"
        )

    print_result(
        payload=payload,
        requested_year=year,
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
        "IDX ListingActivity Year "
        "Contract Probe V1"
    )

    print(
        "-------------------------------"
    )

    print(
        f"Observed year tested : "
        f"{args.year}"
    )

    print(
        "Observed Status values: "
        "ipo, relisting"
    )

    print(
        "No pagination/search parameters "
        "are supplied."
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
                year=args.year,
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
        "Year is accepted only if the "
        "server echoes it in "
        "SearchCriteria."
    )

    print(
        "IPO result dates are additionally "
        "checked against the requested "
        "year."
    )

    print(
        "A zero Relisting result does not "
        "establish zero historical "
        "relistings."
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