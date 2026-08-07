import argparse
from datetime import datetime, timedelta, timezone

from imi.collectors.idx_company_profiles import (
    fetch_idx_company_profiles,
)
from imi.db import engine
from imi.repositories.instruments import (
    get_source_id,
    upsert_current_universe_snapshot,
    upsert_idx_instruments,
)
from imi.universe.validator import (
    validate_instrument_profile,
)

JAKARTA_TZ = timezone(
    timedelta(hours=7),
    name="Asia/Jakarta",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--min-count",
        type=int,
        default=900,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    snapshot_date = datetime.now(
        JAKARTA_TZ
    ).date()

    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IDX Instrument Universe Ingestion"
    )
    print(
        "---------------------------------"
    )

    result = fetch_idx_company_profiles()

    print(
        f"Raw rows       : "
        f"{result.raw_count}"
    )
    print(
        f"Provider total : "
        f"{result.provider_total}"
    )

    accepted = {}
    rejected = []

    for profile in result.profiles:
        validation = (
            validate_instrument_profile(
                profile,
                snapshot_date=snapshot_date,
            )
        )

        if not validation.valid:
            rejected.append(
                validation
            )
            continue

        accepted[
            profile.symbol
        ] = profile

    profiles = list(
        accepted.values()
    )

    print(
        f"Accepted       : "
        f"{len(profiles)}"
    )
    print(
        f"Rejected       : "
        f"{len(rejected)}"
    )

    if len(profiles) < args.min_count:
        raise RuntimeError(
            "IDX universe is unexpectedly "
            "small. Expected at least "
            f"{args.min_count}, received "
            f"{len(profiles)}. "
            "No database write performed."
        )

    with engine.begin() as connection:
        source_id = get_source_id(
            connection,
            code="IDX_OFFICIAL",
        )

        instrument_rows = (
            upsert_idx_instruments(
                connection,
                profiles=profiles,
            )
        )

        snapshot_rows = (
            upsert_current_universe_snapshot(
                connection,
                profiles=profiles,
                snapshot_date=snapshot_date,
                source_id=source_id,
            )
        )

    print(
        f"Instrument rows : "
        f"{instrument_rows}"
    )
    print(
        f"Snapshot rows   : "
        f"{snapshot_rows}"
    )
    print(
        f"Snapshot date   : "
        f"{snapshot_date}"
    )

    sector_count = sum(
        profile.sector_code is not None
        for profile in profiles
    )

    print(
        f"Sector mapped   : "
        f"{sector_count}"
    )

    if rejected:
        print()
        print(
            "Rejected samples:"
        )

        for item in rejected[:10]:
            print(
                item.profile.symbol,
                item.reasons,
            )


if __name__ == "__main__":
    main()