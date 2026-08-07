import argparse

from sqlalchemy import text

from imi.db import engine

COUNT_QUERY = text(
    """
    SELECT COUNT(*)
    FROM market_prices_eod mp
    JOIN instruments i
        ON i.id = mp.instrument_id
    JOIN data_sources ds
        ON ds.id = mp.source_id
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND ds.code = 'YAHOO_FINANCE'
    """
)


DELETE_QUERY = text(
    """
    DELETE FROM market_prices_eod mp
    USING instruments i, data_sources ds
    WHERE mp.instrument_id = i.id
      AND mp.source_id = ds.id
      AND i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND ds.code = 'YAHOO_FINANCE'
    """
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Confirm deletion of Yahoo "
            "IHSG historical price rows."
        ),
    )

    args = parser.parse_args()

    with engine.connect() as connection:
        total = connection.execute(
            COUNT_QUERY
        ).scalar_one()

    print(
        "Yahoo IHSG rows currently stored:"
        f" {total}"
    )

    if not args.yes:
        print(
            "Nothing deleted. Run again "
            "with --yes to confirm."
        )
        return

    with engine.begin() as connection:
        result = connection.execute(
            DELETE_QUERY
        )

        deleted = result.rowcount

    print(
        f"Deleted rows: {deleted}"
    )


if __name__ == "__main__":
    main()