import json
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from imi.calendar.builder import CalendarRecord

LOAD_OBSERVED_IHSG_DATES = text(
    """
    SELECT mp.trading_date
    FROM market_prices_eod mp
    JOIN instruments i
        ON i.id = mp.instrument_id
    JOIN data_sources ds
        ON ds.id = mp.source_id
    WHERE i.symbol = 'IHSG'
      AND i.exchange = 'IDX'
      AND i.asset_type = 'INDEX'
      AND ds.code = 'YAHOO_FINANCE'
      AND mp.quality = 'VALID'
    ORDER BY mp.trading_date
    """
)


GET_SOURCE_ID = text(
    """
    SELECT id
    FROM data_sources
    WHERE code = :code
      AND is_active = TRUE
    """
)


UPSERT_CALENDAR = text(
    """
    INSERT INTO trading_calendar (
        trading_date,
        market,
        is_trading_day,
        session_notes,
        day_type,
        source_id,
        verified,
        evidence
    )
    VALUES (
        :trading_date,
        :market,
        :is_trading_day,
        :session_notes,
        :day_type,
        :source_id,
        :verified,
        CAST(:evidence AS jsonb)
    )
    ON CONFLICT (
        trading_date,
        market
    )
    DO UPDATE SET
        is_trading_day =
            EXCLUDED.is_trading_day,
        session_notes =
            EXCLUDED.session_notes,
        day_type =
            EXCLUDED.day_type,
        source_id =
            EXCLUDED.source_id,
        verified =
            EXCLUDED.verified,
        evidence =
            EXCLUDED.evidence,
        updated_at =
            NOW()
    """
)


def load_observed_ihsg_dates(
    connection: Connection,
) -> set[date]:
    return {
        row[0]
        for row in connection.execute(
            LOAD_OBSERVED_IHSG_DATES
        )
    }


def get_source_id(
    connection: Connection,
    *,
    code: str,
) -> UUID:
    source_id = connection.execute(
        GET_SOURCE_ID,
        {"code": code},
    ).scalar_one_or_none()

    if source_id is None:
        raise LookupError(
            f"Source not found: {code}"
        )

    return source_id


def upsert_calendar_records(
    connection: Connection,
    *,
    records: list[CalendarRecord],
    yahoo_source_id: UUID,
) -> int:
    parameters = []

    for record in records:
        source_id = None

        if (
            record.source_code
            == "YAHOO_FINANCE"
        ):
            source_id = yahoo_source_id

        parameters.append(
            {
                "trading_date":
                    record.trading_date,
                "market":
                    record.market,
                "is_trading_day":
                    record.is_trading_day,
                "session_notes":
                    record.session_notes,
                "day_type":
                    record.day_type,
                "source_id":
                    source_id,
                "verified":
                    record.verified,
                "evidence":
                    json.dumps(
                        record.evidence
                    ),
            }
        )

    if parameters:
        connection.execute(
            UPSERT_CALENDAR,
            parameters,
        )

    return len(parameters)