from sqlalchemy import text

from imi.db import engine

SUMMARY = text(
    """
    SELECT
        COUNT(*) AS equities,
        COUNT(*) FILTER (
            WHERE is_active = TRUE
        ) AS active,
        COUNT(*) FILTER (
            WHERE listed_date IS NULL
        ) AS missing_listing_date,
        COUNT(*) FILTER (
            WHERE sector_code IS NULL
        ) AS missing_sector
    FROM instruments
    WHERE exchange = 'IDX'
      AND asset_type = 'EQUITY'
    """
)


LATEST_SNAPSHOT = text(
    """
    SELECT
        snapshot_date,
        universe_code,
        COUNT(*) AS members
    FROM instrument_universe_snapshots
    WHERE universe_code =
        'IDX_ALL_CURRENT'
    GROUP BY
        snapshot_date,
        universe_code
    ORDER BY snapshot_date DESC
    LIMIT 1
    """
)


SAMPLE = text(
    """
    SELECT
        symbol,
        name,
        listed_date,
        sector_code,
        is_active
    FROM instruments
    WHERE exchange = 'IDX'
      AND asset_type = 'EQUITY'
    ORDER BY symbol
    LIMIT 20
    """
)


def main() -> None:
    with engine.connect() as connection:
        summary = (
            connection.execute(
                SUMMARY
            )
            .mappings()
            .one()
        )

        snapshot = (
            connection.execute(
                LATEST_SNAPSHOT
            )
            .mappings()
            .one_or_none()
        )

        sample = list(
            connection.execute(
                SAMPLE
            )
        )

    print(
        "IDX Instrument Universe Audit"
    )
    print(
        "-----------------------------"
    )

    for key, value in (
        summary.items()
    ):
        print(
            f"{key:22}: {value}"
        )

    print()
    print(
        "Latest snapshot:"
    )
    print(snapshot)

    print()
    print(
        "Sample instruments:"
    )

    for row in sample:
        print(row)


if __name__ == "__main__":
    main()