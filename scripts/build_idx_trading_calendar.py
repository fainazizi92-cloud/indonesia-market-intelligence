from collections import Counter

from imi.calendar.builder import (
    build_derived_idx_calendar,
)
from imi.db import engine
from imi.repositories.trading_calendar import (
    get_source_id,
    load_observed_ihsg_dates,
    upsert_calendar_records,
)


def main() -> None:
    with engine.begin() as connection:
        observed_dates = (
            load_observed_ihsg_dates(
                connection
            )
        )

        if not observed_dates:
            raise RuntimeError(
                "No validated IHSG dates found."
            )

        start = min(observed_dates)
        end = max(observed_dates)

        records = (
            build_derived_idx_calendar(
                observed_dates=observed_dates,
                start=start,
                end=end,
            )
        )

        yahoo_source_id = get_source_id(
            connection,
            code="YAHOO_FINANCE",
        )

        total = upsert_calendar_records(
            connection,
            records=records,
            yahoo_source_id=(
                yahoo_source_id
            ),
        )

    counts = Counter(
        record.day_type
        for record in records
    )

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Derived Trading Calendar"
    )
    print(
        "----------------------------"
    )
    print(
        f"Start               : {start}"
    )
    print(
        f"End                 : {end}"
    )
    print(
        f"Calendar rows       : {total}"
    )

    for key in sorted(counts):
        print(
            f"{key:20}: "
            f"{counts[key]}"
        )


if __name__ == "__main__":
    main()