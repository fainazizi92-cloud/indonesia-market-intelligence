import json
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from imi.universe.models import (
    InstrumentProfile,
)

GET_SOURCE_ID = text(
    """
    SELECT id
    FROM data_sources
    WHERE code = :code
      AND is_active = TRUE
    """
)


UPSERT_INSTRUMENT = text(
    """
    INSERT INTO instruments (
        symbol,
        name,
        asset_type,
        exchange,
        currency,
        sector_code,
        industry_code,
        listed_date,
        is_active,
        metadata
    )
    VALUES (
        :symbol,
        :name,
        'EQUITY'::asset_type,
        'IDX',
        'IDR',
        :sector_code,
        :industry_code,
        :listed_date,
        TRUE,
        CAST(:metadata AS jsonb)
    )
    ON CONFLICT (
        symbol,
        exchange,
        asset_type
    )
    DO UPDATE SET
        name =
            EXCLUDED.name,
        currency =
            EXCLUDED.currency,
        sector_code =
            COALESCE(
                EXCLUDED.sector_code,
                instruments.sector_code
            ),
        industry_code =
            COALESCE(
                EXCLUDED.industry_code,
                instruments.industry_code
            ),
        listed_date =
            COALESCE(
                EXCLUDED.listed_date,
                instruments.listed_date
            ),
        is_active =
            TRUE,
        metadata =
            instruments.metadata
            || EXCLUDED.metadata
    """
)


GET_IDX_EQUITIES = text(
    """
    SELECT
        id,
        symbol
    FROM instruments
    WHERE exchange = 'IDX'
      AND asset_type = 'EQUITY'
    """
)


UPSERT_SNAPSHOT = text(
    """
    INSERT INTO
    instrument_universe_snapshots (
        snapshot_date,
        universe_code,
        instrument_id,
        source_id,
        is_member,
        listing_status,
        metadata
    )
    VALUES (
        :snapshot_date,
        :universe_code,
        :instrument_id,
        :source_id,
        TRUE,
        'CURRENT_PROFILE',
        CAST(:metadata AS jsonb)
    )
    ON CONFLICT (
        snapshot_date,
        universe_code,
        instrument_id
    )
    DO UPDATE SET
        source_id =
            EXCLUDED.source_id,
        is_member =
            EXCLUDED.is_member,
        listing_status =
            EXCLUDED.listing_status,
        metadata =
            EXCLUDED.metadata,
        ingested_at =
            NOW()
    """
)


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


def upsert_idx_instruments(
    connection: Connection,
    *,
    profiles: list[InstrumentProfile],
) -> int:
    parameters = [
        {
            "symbol":
                profile.symbol,
            "name":
                profile.name,
            "sector_code":
                profile.sector_code,
            "industry_code":
                profile.industry_code,
            "listed_date":
                profile.listed_date,
            "metadata":
                json.dumps(
                    profile.metadata
                ),
        }
        for profile in profiles
    ]

    if parameters:
        connection.execute(
            UPSERT_INSTRUMENT,
            parameters,
        )

    return len(parameters)


def get_idx_equity_ids(
    connection: Connection,
) -> dict[str, UUID]:
    return {
        row.symbol: row.id
        for row in connection.execute(
            GET_IDX_EQUITIES
        )
    }


def upsert_current_universe_snapshot(
    connection: Connection,
    *,
    profiles: list[InstrumentProfile],
    snapshot_date: date,
    source_id: UUID,
) -> int:
    instrument_ids = (
        get_idx_equity_ids(
            connection
        )
    )

    parameters = []

    for profile in profiles:
        instrument_id = (
            instrument_ids.get(
                profile.symbol
            )
        )

        if instrument_id is None:
            raise LookupError(
                "Instrument was not "
                "persisted: "
                f"{profile.symbol}"
            )

        parameters.append(
            {
                "snapshot_date":
                    snapshot_date,
                "universe_code":
                    "IDX_ALL_CURRENT",
                "instrument_id":
                    instrument_id,
                "source_id":
                    source_id,
                "metadata":
                    json.dumps(
                        {
                            "symbol":
                                profile.symbol,
                            "source":
                                "IDX company "
                                "profiles",
                        }
                    ),
            }
        )

    if parameters:
        connection.execute(
            UPSERT_SNAPSHOT,
            parameters,
        )

    return len(parameters)