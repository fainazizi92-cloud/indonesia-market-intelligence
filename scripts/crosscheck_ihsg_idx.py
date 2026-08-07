from datetime import date
from decimal import Decimal

from sqlalchemy import text

from imi.db import engine

REFERENCES = {
    date(
        2025,
        1,
        31,
    ): Decimal("7109.20"),
    date(
        2025,
        9,
        30,
    ): Decimal("8061.06"),
}


QUERY = text(
    """
    SELECT mp.close
    FROM market_prices_eod mp
    JOIN instruments i
        ON i.id = mp.instrument_id
    JOIN data_sources ds
        ON ds.id = mp.source_id
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND ds.code = 'YAHOO_FINANCE'
      AND mp.trading_date =
          :trading_date
    """
)


def main() -> None:
    tolerance = Decimal("0.05")

    print(
        "IHSG IDX Reference Cross-check"
    )
    print(
        "------------------------------"
    )

    with engine.connect() as connection:
        for (
            trading_date,
            official_close,
        ) in REFERENCES.items():
            yahoo_close = (
                connection.execute(
                    QUERY,
                    {
                        "trading_date":
                            trading_date
                    },
                ).scalar_one_or_none()
            )

            if yahoo_close is None:
                print(
                    trading_date,
                    "MISSING",
                )
                continue

            difference = abs(
                yahoo_close
                - official_close
            )

            status = (
                "PASS"
                if difference
                <= tolerance
                else "FAIL"
            )

            print(
                trading_date,
                f"IDX={official_close}",
                f"DB={yahoo_close}",
                f"diff={difference}",
                status,
            )


if __name__ == "__main__":
    main()