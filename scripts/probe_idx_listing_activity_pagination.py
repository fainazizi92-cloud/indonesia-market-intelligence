import argparse
from dataclasses import dataclass
from time import sleep
from typing import Any

import httpx

IDX_ORIGIN = "https://www.idx.id"

ENDPOINT = (
    "/primary/ListingActivity/"
    "GetIpoRelisting"
)

PAGE_URL = (
    IDX_ORIGIN
    + "/en/listed-companies/"
    "listing-activities"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "listing-activity-pagination-probe"
    ),
    "Accept": (
        "application/json,"
        "text/plain,"
        "*/*"
    ),
    "Referer": PAGE_URL,
}


DEFAULT_YEAR = 2023


@dataclass(
    frozen=True,
    slots=True,
)
class ProbeCase:
    name: str
    indexfrom: int
    pagesize: int


CASES = (
    ProbeCase(
        name="PAGE_A",
        indexfrom=0,
        pagesize=5,
    ),
    ProbeCase(
        name="PAGE_B",
        indexfrom=5,
        pagesize=5,
    ),
    ProbeCase(
        name="PAGE_C",
        indexfrom=10,
        pagesize=5,
    ),
    ProbeCase(
        name="WIDE_PAGE",
        indexfrom=0,
        pagesize=20,
    ),
)


@dataclass(
    frozen=True,
    slots=True,
)
class ProbeResult:
    name: str
    indexfrom_sent: int
    pagesize_sent: int
    http_status: int | None
    year_echo: str | None
    status_echo: str | None
    indexfrom_echo: int | None
    pagesize_echo: int | None
    result_count: int | None
    symbols: tuple[str, ...]
    dates: tuple[str, ...]
    error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate IDX ListingActivity "
            "indexfrom/pagesize pagination "
            "semantics."
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


def normalize_string(
    value: Any,
) -> str | None:
    if value is None:
        return None

    normalized = str(
        value
    ).strip()

    return (
        normalized
        if normalized
        else None
    )


def normalize_integer(
    value: Any,
) -> int | None:
    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):
        return None


def extract_symbol(
    item: Any,
) -> str | None:
    if not isinstance(
        item,
        dict,
    ):
        return None

    value = item.get(
        "KodeEmiten"
    )

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = (
        value.strip()
        .upper()
    )

    return (
        normalized
        if normalized
        else None
    )


def extract_date(
    item: Any,
) -> str | None:
    if not isinstance(
        item,
        dict,
    ):
        return None

    value = item.get(
        "TanggalPencatatan"
    )

    if not isinstance(
        value,
        str,
    ):
        return None

    normalized = (
        value.strip()
    )

    return (
        normalized
        if normalized
        else None
    )


def failure_result(
    *,
    case: ProbeCase,
    http_status: int | None,
    error: str,
) -> ProbeResult:
    return ProbeResult(
        name=case.name,
        indexfrom_sent=(
            case.indexfrom
        ),
        pagesize_sent=(
            case.pagesize
        ),
        http_status=http_status,
        year_echo=None,
        status_echo=None,
        indexfrom_echo=None,
        pagesize_echo=None,
        result_count=None,
        symbols=(),
        dates=(),
        error=error,
    )


def parse_response(
    *,
    case: ProbeCase,
    year: int,
    response: httpx.Response,
) -> ProbeResult:
    try:
        payload = (
            response.json()
        )

    except ValueError:
        return failure_result(
            case=case,
            http_status=(
                response.status_code
            ),
            error=(
                "Response is not JSON."
            ),
        )

    if not isinstance(
        payload,
        dict,
    ):
        return failure_result(
            case=case,
            http_status=(
                response.status_code
            ),
            error=(
                "JSON root is not "
                "an object."
            ),
        )

    criteria = payload.get(
        "SearchCriteria"
    )

    if not isinstance(
        criteria,
        dict,
    ):
        return failure_result(
            case=case,
            http_status=(
                response.status_code
            ),
            error=(
                "SearchCriteria is not "
                "an object."
            ),
        )

    result = payload.get(
        "Result"
    )

    if not isinstance(
        result,
        list,
    ):
        return failure_result(
            case=case,
            http_status=(
                response.status_code
            ),
            error=(
                "Result is not an array."
            ),
        )

    year_echo = (
        normalize_string(
            criteria.get(
                "Year"
            )
        )
    )

    status_echo = (
        normalize_string(
            criteria.get(
                "Status"
            )
        )
    )

    indexfrom_echo = (
        normalize_integer(
            criteria.get(
                "indexfrom"
            )
        )
    )

    pagesize_echo = (
        normalize_integer(
            criteria.get(
                "pagesize"
            )
        )
    )

    symbols = tuple(
        symbol
        for item in result
        if (
            symbol := extract_symbol(
                item
            )
        )
        is not None
    )

    dates = tuple(
        event_date
        for item in result
        if (
            event_date := extract_date(
                item
            )
        )
        is not None
    )

    error = None

    if response.status_code != 200:
        error = (
            f"Unexpected HTTP "
            f"{response.status_code}."
        )

    elif year_echo != str(
        year
    ):
        error = (
            "Year echo mismatch."
        )

    elif status_echo != "ipo":
        error = (
            "Status echo mismatch."
        )

    elif (
        indexfrom_echo
        != case.indexfrom
    ):
        error = (
            "indexfrom echo mismatch."
        )

    elif (
        pagesize_echo
        != case.pagesize
    ):
        error = (
            "pagesize echo mismatch."
        )

    return ProbeResult(
        name=case.name,
        indexfrom_sent=(
            case.indexfrom
        ),
        pagesize_sent=(
            case.pagesize
        ),
        http_status=(
            response.status_code
        ),
        year_echo=year_echo,
        status_echo=status_echo,
        indexfrom_echo=(
            indexfrom_echo
        ),
        pagesize_echo=(
            pagesize_echo
        ),
        result_count=len(
            result
        ),
        symbols=symbols,
        dates=dates,
        error=error,
    )


def probe_case(
    *,
    client: httpx.Client,
    case: ProbeCase,
    year: int,
) -> ProbeResult:
    url = (
        IDX_ORIGIN
        + ENDPOINT
    )

    params = {
        "Status": "ipo",
        "Year": year,
        "indexfrom": (
            case.indexfrom
        ),
        "pagesize": (
            case.pagesize
        ),
    }

    try:
        response = client.get(
            url,
            params=params,
        )

    except httpx.HTTPError as exc:
        return failure_result(
            case=case,
            http_status=None,
            error=(
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

    return parse_response(
        case=case,
        year=year,
        response=response,
    )


def print_result(
    result: ProbeResult,
) -> None:
    print(
        result.name
    )

    print(
        f"  Sent indexfrom : "
        f"{result.indexfrom_sent}"
    )

    print(
        f"  Sent pagesize  : "
        f"{result.pagesize_sent}"
    )

    print(
        f"  HTTP           : "
        f"{result.http_status}"
    )

    print(
        f"  Year echo      : "
        f"{result.year_echo!r}"
    )

    print(
        f"  Status echo    : "
        f"{result.status_echo!r}"
    )

    print(
        f"  indexfrom echo : "
        f"{result.indexfrom_echo!r}"
    )

    print(
        f"  pagesize echo  : "
        f"{result.pagesize_echo!r}"
    )

    print(
        f"  Result count   : "
        f"{result.result_count}"
    )

    print(
        "  Symbols        : "
        + (
            ", ".join(
                result.symbols
            )
            if result.symbols
            else "-"
        )
    )

    print(
        "  Dates          : "
        + (
            ", ".join(
                result.dates
            )
            if result.dates
            else "-"
        )
    )

    print(
        "  Validation     : "
        + (
            "PASS"
            if result.error is None
            else (
                "FAIL — "
                + result.error
            )
        )
    )

    print()


def result_by_name(
    *,
    results: list[
        ProbeResult
    ],
    name: str,
) -> ProbeResult | None:
    for result in results:
        if result.name == name:
            return result

    return None


def print_sequence_analysis(
    results: list[
        ProbeResult
    ],
) -> None:
    page_a = result_by_name(
        results=results,
        name="PAGE_A",
    )

    page_b = result_by_name(
        results=results,
        name="PAGE_B",
    )

    page_c = result_by_name(
        results=results,
        name="PAGE_C",
    )

    wide = result_by_name(
        results=results,
        name="WIDE_PAGE",
    )

    print(
        "PAGINATION SEQUENCE ANALYSIS"
    )

    if (
        page_a is None
        or page_b is None
        or page_c is None
        or wide is None
    ):
        print(
            "  Complete probe set "
            "not available."
        )

        return

    narrow_sequence = (
        page_a.symbols
        + page_b.symbols
        + page_c.symbols
    )

    comparable_length = min(
        len(
            narrow_sequence
        ),
        len(
            wide.symbols
        ),
    )

    sequence_match = (
        narrow_sequence[
            :comparable_length
        ]
        == wide.symbols[
            :comparable_length
        ]
    )

    overlap_ab = (
        set(
            page_a.symbols
        )
        & set(
            page_b.symbols
        )
    )

    overlap_bc = (
        set(
            page_b.symbols
        )
        & set(
            page_c.symbols
        )
    )

    print(
        f"  Narrow rows      : "
        f"{len(narrow_sequence)}"
    )

    print(
        f"  Wide rows        : "
        f"{len(wide.symbols)}"
    )

    print(
        f"  Sequence match   : "
        f"{sequence_match}"
    )

    print(
        "  PAGE_A/B overlap : "
        + (
            ", ".join(
                sorted(
                    overlap_ab
                )
            )
            if overlap_ab
            else "-"
        )
    )

    print(
        "  PAGE_B/C overlap : "
        + (
            ", ".join(
                sorted(
                    overlap_bc
                )
            )
            if overlap_bc
            else "-"
        )
    )

    contract_confirmed = (
        page_a.error is None
        and page_b.error is None
        and page_c.error is None
        and wide.error is None
        and sequence_match
        and not overlap_ab
        and not overlap_bc
    )

    print(
        f"  Offset contract  : "
        f"{'CONFIRMED' if contract_confirmed else 'NOT YET CONFIRMED'}"
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX ListingActivity Pagination "
        "Contract Probe V1"
    )

    print(
        "--------------------------------"
    )

    print(
        f"Year tested : "
        f"{args.year}"
    )

    print(
        "Status      : ipo"
    )

    print(
        "Cases       : "
        "0/5, 5/5, 10/5, 0/20"
    )

    print()

    results = []

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        for index, case in enumerate(
            CASES,
            start=1,
        ):
            result = probe_case(
                client=client,
                case=case,
                year=args.year,
            )

            results.append(
                result
            )

            print_result(
                result
            )

            if (
                index < len(
                    CASES
                )
                and args.pause > 0
            ):
                sleep(
                    args.pause
                )

    print_sequence_analysis(
        results
    )

    print()

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "indexfrom/pagesize semantics "
        "must be established from echoed "
        "criteria and observed result "
        "sequence."
    )

    print(
        "The previous annual scanner "
        "must not be treated as complete "
        "historical coverage until "
        "pagination is resolved."
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