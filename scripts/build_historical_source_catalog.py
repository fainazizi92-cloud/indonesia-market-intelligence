from collections import Counter

from imi.features.historical_source import (
    catalog_family_counts,
    historical_source_definitions,
    prepare_catalog_rows,
)

from imi.db import engine
from imi.repositories.historical_source import (
    load_source_catalog,
    upsert_source_catalog,
)
from imi.repositories.instruments import (
    get_source_id,
)


def main() -> None:
    definitions = (
        historical_source_definitions()
    )

    with engine.begin() as connection:
        source_id = get_source_id(
            connection,
            code="IDX_OFFICIAL",
        )

        prepared = (
            prepare_catalog_rows(
                source_id=source_id,
            )
        )

        written = (
            upsert_source_catalog(
                connection,
                rows=prepared,
            )
        )

    with engine.connect() as connection:
        stored = (
            load_source_catalog(
                connection
            )
        )

    family_counts = (
        catalog_family_counts(
            definitions
        )
    )

    automation_counts = Counter(
        item.automation_status
        for item in definitions
    )

    print(
        "Indonesia Market Intelligence"
    )

    print(
        "Historical Source Catalog V1"
    )

    print(
        "----------------------------"
    )

    print(
        f"Definitions       : "
        f"{len(definitions)}"
    )

    print(
        f"Rows prepared     : "
        f"{len(prepared)}"
    )

    print(
        f"Rows upserted     : "
        f"{written}"
    )

    print(
        f"Rows stored       : "
        f"{len(stored)}"
    )

    print()

    print(
        "Dataset families:"
    )

    for (
        family,
        count,
    ) in sorted(
        family_counts.items()
    ):
        print(
            f"{family:<20} : "
            f"{count}"
        )

    print()

    print(
        "Automation status:"
    )

    for (
        status,
        count,
    ) in sorted(
        automation_counts.items()
    ):
        print(
            f"{status:<20} : "
            f"{count}"
        )

    print()

    print(
        "HISTORICAL INGESTION:"
    )

    print(
        "APPROVED : NO"
    )

    print(
        "The APPROVED company-profile "
        "API is current-data only."
    )

    print(
        "All historical routes remain "
        "DISCOVERY_ONLY until their "
        "download/parser contracts are "
        "validated."
    )


if __name__ == "__main__":
    main()