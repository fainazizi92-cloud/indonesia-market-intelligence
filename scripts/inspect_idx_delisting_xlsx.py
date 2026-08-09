import argparse
import hashlib
from dataclasses import dataclass
from time import sleep

import httpx

from imi.features.idx_lifecycle_api_probe import (
    build_page_metadata_url,
)
from imi.features.idx_report_contract import (
    build_report_url,
    extract_digital_stat_metadata,
)
from imi.features.idx_xlsx_inspection import (
    inspect_xlsx_bytes,
    is_xlsx_bytes,
)

DELISTED_ROUTE = (
    "/en/market-data/"
    "statistical-reports/"
    "digital-statistic/"
    "monthly/"
    "corporate-action-of-listed-companies/"
    "delisted-company"
)


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "Indonesia-Market-Intelligence/"
        "delisting-xlsx-inspector"
    ),

    "Accept": (
        "application/octet-stream,"
        "application/vnd.openxmlformats-"
        "officedocument.spreadsheetml.sheet,"
        "*/*"
    ),

    "Referer": (
        "https:"
        + "//www.idx.id/"
    ),
}


@dataclass(
    frozen=True,
    slots=True,
)
class MonthTarget:
    year: int
    month: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect official IDX "
            "delisting XLSX workbook "
            "structure without writing "
            "historical data."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        default=2024,
    )

    parser.add_argument(
        "--start-month",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--end-month",
        type=int,
        default=12,
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=0.25,
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=20,
    )

    return parser.parse_args()


def validate_args(
    args: argparse.Namespace,
) -> None:
    if args.year < 1900:
        raise ValueError(
            "year must be 1900 or later."
        )

    if not 1 <= args.start_month <= 12:
        raise ValueError(
            "start-month must be "
            "between 1 and 12."
        )

    if not 1 <= args.end_month <= 12:
        raise ValueError(
            "end-month must be "
            "between 1 and 12."
        )

    if (
        args.start_month
        > args.end_month
    ):
        raise ValueError(
            "start-month cannot be "
            "after end-month."
        )

    if args.timeout <= 0:
        raise ValueError(
            "timeout must be positive."
        )

    if args.pause < 0:
        raise ValueError(
            "pause cannot be negative."
        )

    if args.rows <= 0:
        raise ValueError(
            "rows must be positive."
        )


def build_targets(
    *,
    year: int,
    start_month: int,
    end_month: int,
) -> tuple[
    MonthTarget,
    ...
]:
    return tuple(
        MonthTarget(
            year=year,
            month=month,
        )
        for month in range(
            start_month,
            end_month + 1,
        )
    )


def format_row(
    values: tuple[
        object,
        ...
    ],
) -> str:
    rendered = []

    for value in values:
        if value is None:
            rendered.append(
                ""
            )
        else:
            rendered.append(
                str(
                    value
                )
            )

    return " | ".join(
        rendered
    )


def main() -> None:
    args = parse_args()

    validate_args(
        args
    )

    targets = build_targets(
        year=args.year,
        start_month=(
            args.start_month
        ),
        end_month=(
            args.end_month
        ),
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX Delisting XLSX Inspector V1"
    )

    print(
        "-------------------------------"
    )

    print(
        f"Year          : {args.year}"
    )

    print(
        f"Months        : "
        f"{args.start_month}-"
        f"{args.end_month}"
    )

    print(
        f"Targets       : "
        f"{len(targets)}"
    )

    print()

    metadata_url = (
        build_page_metadata_url(
            route_path=(
                DELISTED_ROUTE
            )
        )
    )

    successful = 0
    valid_xlsx = 0

    with httpx.Client(
        timeout=args.timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
    ) as client:
        metadata_response = (
            client.get(
                metadata_url
            )
        )

        metadata_response.raise_for_status()

        metadata = (
            extract_digital_stat_metadata(
                metadata_response.json()
            )
        )

        print(
            f"Download code : "
            f"{metadata.download_code}"
        )

        print(
            f"Page title    : "
            f"{metadata.title}"
        )

        print()

        for index, target in enumerate(
            targets,
            start=1,
        ):
            report_url = (
                build_report_url(
                    report_type="excel",
                    year=target.year,
                    month=target.month,
                    download_code=(
                        metadata
                        .download_code
                    ),
                    filename=(
                        metadata.title
                    ),
                )
            )

            print(
                f"{target.year}-"
                f"{target.month:02d}"
            )

            try:
                response = client.get(
                    report_url
                )

            except httpx.HTTPError as exc:
                print(
                    "  HTTP          : ERROR"
                )

                print(
                    f"  Error         : "
                    f"{type(exc).__name__}"
                )

                print(
                    f"  Detail        : "
                    f"{exc}"
                )

                print()

                continue

            print(
                f"  HTTP          : "
                f"{response.status_code}"
            )

            print(
                f"  Content type  : "
                f"{response.headers.get('content-type')}"
            )

            print(
                f"  Disposition   : "
                f"{response.headers.get('content-disposition')}"
            )

            print(
                f"  Bytes         : "
                f"{len(response.content)}"
            )

            print(
                f"  SHA256        : "
                f"{hashlib.sha256(response.content).hexdigest()}"
            )

            if response.is_success:
                successful += 1

            xlsx = is_xlsx_bytes(
                response.content
            )

            print(
                f"  XLSX signature: "
                f"{xlsx}"
            )

            if not xlsx:
                preview = (
                    " ".join(
                        response.text.split()
                    )
                    if response.text
                    else ""
                )

                print(
                    "  Body preview  : "
                    + preview[
                        :500
                    ]
                )

                print()

                continue

            valid_xlsx += 1

            inspection = (
                inspect_xlsx_bytes(
                    response.content,
                    max_non_empty_rows=(
                        args.rows
                    ),
                )
            )

            print(
                "  Sheets        : "
                + ", ".join(
                    inspection.sheet_names
                )
            )

            for worksheet in (
                inspection.worksheets
            ):
                print(
                    f"  Sheet         : "
                    f"{worksheet.title}"
                )

                print(
                    f"    max_row     : "
                    f"{worksheet.max_row}"
                )

                print(
                    f"    max_column  : "
                    f"{worksheet.max_column}"
                )

                print(
                    f"    non-empty   : "
                    f"{len(worksheet.non_empty_rows)}"
                )

                for (
                    row_number,
                    values,
                ) in (
                    worksheet.non_empty_rows
                ):
                    print(
                        f"    R{row_number:<4} "
                        + format_row(
                            values
                        )
                    )

            print()

            if (
                index
                < len(
                    targets
                )
                and args.pause > 0
            ):
                sleep(
                    args.pause
                )

    print(
        "Summary:"
    )

    print(
        f"HTTP successful : "
        f"{successful}/"
        f"{len(targets)}"
    )

    print(
        f"Valid XLSX      : "
        f"{valid_xlsx}/"
        f"{len(targets)}"
    )

    print()

    print(
        "DATABASE WRITE:"
    )

    print(
        "ENABLED : NO"
    )

    print(
        "This is workbook structure "
        "inspection only."
    )


if __name__ == "__main__":
    main()