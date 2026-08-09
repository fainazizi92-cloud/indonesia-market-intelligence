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
        "listing-activity-page-index-probe"
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
        name="DEFAULT_ALIAS",
        indexfrom=0,
        pagesize=5,
    ),
    ProbeCase(
        name="PAGE_1_SMALL",
        indexfrom=1,
        pagesize=5,
    ),
    ProbeCase(
        name="PAGE_2_SMALL",
        indexfrom=2,
        pagesize=5,
    ),
    ProbeCase(
        name="PAGE_3_SMALL",
        indexfrom=3,
        pagesize=5,
    ),
    ProbeCase(
        name="PAGE_1_LARGE",
        indexfrom=1,
        pagesize=200,
    ),
    ProbeCase(
        name="PAGE_2_LARGE",
        indexfrom=2,
        pagesize=200,
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
    min_date: str | None
    max_date: str | None
    error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Confirm IDX ListingActivity "
            "one-based page-number semantics."
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
        indexfrom_sent=case.indexfrom,
        pagesize_sent=case.pagesize,
        http_status=http_status,
        year_echo=None,
        status_echo=None,
        indexfrom_echo=None,
        pagesize_echo=None,
        result_count=None,
        symbols=(),
        min_date=None,
        max_date=None,
        error=error,
    )


def parse_response(
    *,
    case: ProbeCase,
    year: int,
    response: httpx.Response,
) -> ProbeResult:
    try:
        payload = response.json()

    except ValueError:
        return failure_result(
            case=case,
            http_status=response.status_code,
            error="Response is not JSON.",
        )

    if not isinstance(
        payload,
        dict,
    ):
        return failure_result(
            case=case,
            http_status=response.status_code,
            error=(
                "JSON root is not "
                "an object."
            ),
        )

    criteria = payload.get(
        "SearchCriteria"
    )

    result = payload.get(
        "Result"
    )

    if not isinstance(
        criteria,
        dict,
    ):
        return failure_result(
            case=case,
            http_status=response.status_code,
            error=(
                "SearchCriteria is not "
                "an object."
            ),
        )

    if not isinstance(
        result,
        list,
    ):
        return failure_result(
            case=case,
            http_status=response.status_code,
            error=(
                "Result is not an array."
            ),
        )

    year_echo = normalize_string(
        criteria.get(
            "Year"
        )
    )

    status_echo = normalize_string(
        criteria.get(
            "Status"
        )
    )

    indexfrom_echo = normalize_integer(
        criteria.get(
            "indexfrom"
        )
    )

    pagesize_echo = normalize_integer(
        criteria.get(
            "pagesize"
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
        indexfrom_sent=case.indexfrom,
        pagesize_sent=case.pagesize,
        http_status=response.status_code,
        year_echo=year_echo,
        status_echo=status_echo,
        indexfrom_echo=indexfrom_echo,
        pagesize_echo=pagesize_echo,
        result_count=len(
            result
        ),
        symbols=symbols,
        min_date=(
            min(
                dates
            )
            if dates
            else None
        ),
        max_date=(
            max(
                dates
            )
            if dates
            else None
        ),
        error=error,
    )


def probe_case(
    *,
    client: httpx.Client,
    case: ProbeCase,
    year: int,
) -> ProbeResult:
    params = {
        "Status": "ipo",
        "Year": year,
        "indexfrom": case.indexfrom,
        "pagesize": case.pagesize,
    }

    try:
        response = client.get(
            IDX_ORIGIN + ENDPOINT,
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
        f"  indexfrom sent : "
        f"{result.indexfrom_sent}"
    )

    print(
        f"  pagesize sent  : "
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
        f"  Date range     : "
        f"{result.min_date} "
        f"→ "
        f"{result.max_date}"
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


def get_result(
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


def analyze_results(
    results: list[
        ProbeResult
    ],
) -> None:
    default_alias = get_result(
        results=results,
        name="DEFAULT_ALIAS",
    )

    page_1 = get_result(
        results=results,
        name="PAGE_1_SMALL",
    )

    page_2 = get_result(
        results=results,
        name="PAGE_2_SMALL",
    )

    page_3 = get_result(
        results=results,
        name="PAGE_3_SMALL",
    )

    large_1 = get_result(
        results=results,
        name="PAGE_1_LARGE",
    )

    large_2 = get_result(
        results=results,
        name="PAGE_2_LARGE",
    )

    print(
        "CONTRACT ANALYSIS"
    )

    required = (
        default_alias,
        page_1,
        page_2,
        page_3,
        large_1,
        large_2,
    )

    if any(
        result is None
        for result in required
    ):
        print(
            "  Complete probe set "
            "not available."
        )
        return

    assert default_alias is not None
    assert page_1 is not None
    assert page_2 is not None
    assert page_3 is not None
    assert large_1 is not None
    assert large_2 is not None

    zero_aliases_page_one = (
        default_alias.symbols
        == page_1.symbols
        and default_alias.result_count
        == page_1.result_count
    )

    set_1 = set(
        page_1.symbols
    )

    set_2 = set(
        page_2.symbols
    )

    set_3 = set(
        page_3.symbols
    )

    overlap_12 = (
        set_1
        & set_2
    )

    overlap_23 = (
        set_2
        & set_3
    )

    overlap_13 = (
        set_1
        & set_3
    )

    small_union = (
        set_1
        | set_2
        | set_3
    )

    large_set = set(
        large_1.symbols
    )

    small_subset_large = (
        small_union
        <= large_set
    )

    one_based_supported = (
        zero_aliases_page_one
        and page_1.result_count == 5
        and page_2.result_count == 5
        and page_3.result_count == 5
        and not overlap_12
        and not overlap_23
        and not overlap_13
        and small_subset_large
    )

    annual_page_complete = (
        large_1.error is None
        and large_2.error is None
        and large_1.result_count
        is not None
        and large_1.result_count
        < 200
        and large_2.result_count == 0
    )

    print(
        f"  indexfrom=0 aliases 1 : "
        f"{zero_aliases_page_one}"
    )

    print(
        f"  PAGE 1/2 overlap      : "
        f"{sorted(overlap_12)}"
    )

    print(
        f"  PAGE 2/3 overlap      : "
        f"{sorted(overlap_23)}"
    )

    print(
        f"  PAGE 1/3 overlap      : "
        f"{sorted(overlap_13)}"
    )

    print(
        f"  Small subset large    : "
        f"{small_subset_large}"
    )

    print(
        "  One-based page model  : "
        + (
            "CONFIRMED"
            if one_based_supported
            else "NOT YET CONFIRMED"
        )
    )

    print(
        f"  Large page 1 rows     : "
        f"{large_1.result_count}"
    )

    print(
        f"  Large page 2 rows     : "
        f"{large_2.result_count}"
    )

    print(
        "  2023 response coverage: "
        + (
            "CONFIRMED"
            if annual_page_complete
            else "NOT YET CONFIRMED"
        )
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
        "IDX ListingActivity Final "
        "Pagination Contract Probe V2"
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
        "0/5, 1/5, 2/5, 3/5, "
        "1/200, 2/200"
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

    analyze_results(
        results
    )

    print()

    print(
        "INTERPRETATION RULE:"
    )

    print(
        "indexfrom=0 may be treated "
        "only as a default alias if its "
        "result exactly matches page 1."
    )

    print(
        "Normal pagination starts at "
        "indexfrom=1."
    )

    print(
        "Historical completeness is "
        "still separate from endpoint "
        "response coverage."
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