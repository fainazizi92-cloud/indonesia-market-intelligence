import argparse
from dataclasses import dataclass

from imi.collectors.idx_lifecycle_history import (
    create_lifecycle_client,
    fetch_new_listings_month,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ValidationTarget:
    name: str
    year: int
    month: int


TARGETS = (
    ValidationTarget(
        name="JAN_2025",
        year=2025,
        month=1,
    ),

    ValidationTarget(
        name="NOV_2024",
        year=2024,
        month=11,
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate normalized IDX "
            "new-listing parser against "
            "live official-domain data."
        )
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "IDX New Listing Parser Validation V1"
    )

    print(
        "------------------------------------"
    )

    print()

    total_records = 0

    with create_lifecycle_client(
        timeout=args.timeout
    ) as client:
        for target in TARGETS:
            result = (
                fetch_new_listings_month(
                    client=client,
                    year=target.year,
                    month=target.month,
                )
            )

            total_records += len(
                result.records
            )

            print(
                target.name
            )

            print(
                f"  API total      : "
                f"{result.total_items}"
            )

            print(
                f"  Parsed records : "
                f"{len(result.records)}"
            )

            print(
                f"  Pages fetched  : "
                f"{result.pages_fetched}"
            )

            print(
                "  Records:"
            )

            for record in (
                result.records
            ):
                print(
                    "    "
                    f"{record.code:<6} "
                    f"{record.listing_date} | "
                    f"{record.issuer_name}"
                )

            print()

    print(
        "Summary:"
    )

    print(
        f"Targets validated : "
        f"{len(TARGETS)}"
    )

    print(
        f"Records parsed    : "
        f"{total_records}"
    )

    print()

    print(
        "DATABASE WRITE:"
    )

    print(
        "ENABLED : NO"
    )

    print(
        "This validation performs "
        "read-only normalization only."
    )


if __name__ == "__main__":
    main()