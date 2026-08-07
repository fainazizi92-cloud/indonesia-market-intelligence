import json
from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection

from imi.collectors.yahoo_equity_history import (
    EquityDailyBar,
)

GET_SOURCE = text(
    """
    SELECT id
    FROM data_sources
    WHERE code = :code
      AND is_active = TRUE
    """
)


GET_LATEST_IDX_SESSION = text(
    """
    SELECT MAX(trading_date)
    FROM trading_calendar
    WHERE market = 'IDX'
      AND is_trading_day = TRUE
    """
)


GET_CURRENT_IDX_EQUITIES = text(
    """
    WITH latest_snapshot AS (
        SELECT MAX(snapshot_date)
            AS snapshot_date
        FROM instrument_universe_snapshots
        WHERE universe_code =
            'IDX_ALL_CURRENT'
    )
    SELECT
        i.id,
        i.symbol,
        i.listed_date
    FROM instrument_universe_snapshots s
    JOIN latest_snapshot ls
      ON ls.snapshot_date =
         s.snapshot_date
    JOIN instruments i
      ON i.id =
         s.instrument_id
    WHERE s.universe_code =
          'IDX_ALL_CURRENT'
      AND s.is_member = TRUE
      AND i.exchange = 'IDX'
      AND i.asset_type = 'EQUITY'
    ORDER BY i.symbol
    """
)


UPSERT_STATE = text(
    """
    INSERT INTO eod_ingestion_state (
        instrument_id,
        source_id,
        status,
        start_date,
        target_end_date,
        next_start_date,
        updated_at
    )
    VALUES (
        :instrument_id,
        :source_id,
        'PENDING',
        :start_date,
        :target_end_date,
        :start_date,
        NOW()
    )
    ON CONFLICT (
        instrument_id,
        source_id
    )
    DO UPDATE SET
        target_end_date =
            EXCLUDED.target_end_date,
        updated_at =
            NOW()
    """
)


GET_WORK_QUEUE = text(
    """
    SELECT
        s.instrument_id,
        i.symbol,
        i.listed_date,
        s.status,
        s.start_date,
        s.target_end_date,
        s.next_start_date,
        s.attempts,
        s.rows_loaded
    FROM eod_ingestion_state s
    JOIN instruments i
      ON i.id = s.instrument_id
    WHERE s.source_id = :source_id
      AND s.status IN (
        'PENDING',
        'PARTIAL',
        'RUNNING',
        'FAILED'
        )
    ORDER BY
        CASE s.status
            WHEN 'PARTIAL' THEN 1
            WHEN 'RUNNING' THEN 2
            WHEN 'PENDING' THEN 3
            WHEN 'FAILED' THEN 4
            ELSE 5
        END,
        i.symbol
    """
)


MARK_RUNNING = text(
    """
    UPDATE eod_ingestion_state
    SET
        status = 'RUNNING',
        attempts = attempts + 1,
        started_at =
            COALESCE(
                started_at,
                NOW()
            ),
        last_error = NULL,
        updated_at = NOW()
    WHERE instrument_id =
          :instrument_id
      AND source_id =
          :source_id
    """
)


MARK_PROGRESS = text(
    """
    UPDATE eod_ingestion_state
    SET
        status = 'PARTIAL',
        next_start_date =
            :next_start_date,
        last_attempted_date =
            :last_attempted_date,
        last_success_date =
            COALESCE(
                :last_success_date,
                last_success_date
            ),
        rows_loaded =
            rows_loaded
            + :rows_loaded,
        updated_at = NOW()
    WHERE instrument_id =
          :instrument_id
      AND source_id =
          :source_id
    """
)


MARK_COMPLETE = text(
    """
    UPDATE eod_ingestion_state
    SET
        status = 'COMPLETE',
        next_start_date = NULL,
        last_attempted_date =
            :last_attempted_date,
        last_success_date =
            COALESCE(
                :last_success_date,
                last_success_date
            ),
        completed_at = NOW(),
        updated_at = NOW()
    WHERE instrument_id =
          :instrument_id
      AND source_id =
          :source_id
    """
)


MARK_FAILED = text(
    """
    UPDATE eod_ingestion_state
    SET
        status = 'FAILED',
        last_error = :last_error,
        updated_at = NOW()
    WHERE instrument_id =
          :instrument_id
      AND source_id =
          :source_id
    """
)


UPSERT_BAR = text(
    """
    INSERT INTO market_prices_eod (
        instrument_id,
        trading_date,
        open,
        high,
        low,
        close,
        adjusted_close,
        volume,
        source_id,
        observed_at,
        quality,
        raw_ref
    )
    VALUES (
        :instrument_id,
        :trading_date,
        :open,
        :high,
        :low,
        :close,
        :adjusted_close,
        :volume,
        :source_id,
        :observed_at,
        'VALID',
        :raw_ref
    )
    ON CONFLICT (
        instrument_id,
        trading_date,
        source_id
    )
    DO UPDATE SET
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        adjusted_close =
            EXCLUDED.adjusted_close,
        volume = EXCLUDED.volume,
        observed_at =
            EXCLUDED.observed_at,
        quality =
            EXCLUDED.quality,
        raw_ref =
            EXCLUDED.raw_ref,
        ingested_at = NOW()
    """
)


REBUILD_PREVIOUS_CLOSE = text(
    """
    WITH ordered AS (
        SELECT
            instrument_id,
            trading_date,
            source_id,
            LAG(close) OVER (
                PARTITION BY
                    instrument_id,
                    source_id
                ORDER BY
                    trading_date
            ) AS previous_close
        FROM market_prices_eod
        WHERE instrument_id =
              :instrument_id
          AND source_id =
              :source_id
    )
    UPDATE market_prices_eod p
    SET previous_close =
        ordered.previous_close
    FROM ordered
    WHERE p.instrument_id =
          ordered.instrument_id
      AND p.trading_date =
          ordered.trading_date
      AND p.source_id =
          ordered.source_id
    """
)

MARK_NO_DATA = text(
    """
    UPDATE eod_ingestion_state
    SET
        status = 'NO_DATA',
        next_start_date = NULL,
        last_attempted_date =
            :last_attempted_date,
        completed_at = NOW(),
        last_error =
            'No valid historical EOD '
            'data available from source.',
        updated_at = NOW()
    WHERE instrument_id =
          :instrument_id
      AND source_id =
          :source_id
    """
)


def get_source_id(
    connection: Connection,
    *,
    code: str,
) -> UUID:
    value = connection.execute(
        GET_SOURCE,
        {"code": code},
    ).scalar_one_or_none()

    if value is None:
        raise LookupError(
            f"Data source not found: {code}"
        )

    return value


def get_latest_idx_session(
    connection: Connection,
) -> date:
    value = connection.execute(
        GET_LATEST_IDX_SESSION
    ).scalar_one_or_none()

    if value is None:
        raise RuntimeError(
            "IDX trading calendar is empty."
        )

    return value


def seed_ingestion_states(
    connection: Connection,
    *,
    source_id: UUID,
    target_end_date: date,
) -> int:
    rows = list(
        connection.execute(
            GET_CURRENT_IDX_EQUITIES
        )
    )

    parameters = []

    for row in rows:
        if row.listed_date is None:
            continue

        parameters.append(
            {
                "instrument_id":
                    row.id,
                "source_id":
                    source_id,
                "start_date":
                    row.listed_date,
                "target_end_date":
                    target_end_date,
            }
        )

    if parameters:
        connection.execute(
            UPSERT_STATE,
            parameters,
        )

    return len(parameters)


def load_work_queue(
    connection: Connection,
    *,
    source_id: UUID,
) -> list:
    return list(
        connection.execute(
            GET_WORK_QUEUE,
            {
                "source_id":
                    source_id
            },
        )
    )


def mark_running(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
) -> None:
    connection.execute(
        MARK_RUNNING,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
        },
    )


def mark_progress(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
    next_start_date: date,
    last_attempted_date: date,
    last_success_date: date | None,
    rows_loaded: int,
) -> None:
    connection.execute(
        MARK_PROGRESS,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
            "next_start_date":
                next_start_date,
            "last_attempted_date":
                last_attempted_date,
            "last_success_date":
                last_success_date,
            "rows_loaded":
                rows_loaded,
        },
    )


def mark_complete(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
    last_attempted_date: date,
    last_success_date: date | None,
) -> None:
    connection.execute(
        MARK_COMPLETE,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
            "last_attempted_date":
                last_attempted_date,
            "last_success_date":
                last_success_date,
        },
    )


def mark_failed(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
    error: str,
) -> None:
    connection.execute(
        MARK_FAILED,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
            "last_error":
                error[:4000],
        },
    )


def upsert_equity_bars(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
    yahoo_symbol: str,
    bars: list[EquityDailyBar],
) -> int:
    parameters = []

    for bar in bars:
        parameters.append(
            {
                "instrument_id":
                    instrument_id,
                "trading_date":
                    bar.trading_date,
                "open":
                    bar.open,
                "high":
                    bar.high,
                "low":
                    bar.low,
                "close":
                    bar.close,
                "adjusted_close":
                    bar.adjusted_close,
                "volume":
                    bar.volume,
                "source_id":
                    source_id,
                "observed_at":
                    None,
                "raw_ref":
                    json.dumps(
                        {
                            "provider":
                                "Yahoo Finance",
                            "symbol":
                                yahoo_symbol,
                            "interval":
                                "1d",
                        }
                    ),
            }
        )

    if parameters:
        connection.execute(
            UPSERT_BAR,
            parameters,
        )

    return len(parameters)


def rebuild_previous_close(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
) -> None:
    connection.execute(
        REBUILD_PREVIOUS_CLOSE,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
        },
    )

def mark_no_data(
    connection: Connection,
    *,
    instrument_id: UUID,
    source_id: UUID,
    last_attempted_date: date,
) -> None:
    connection.execute(
        MARK_NO_DATA,
        {
            "instrument_id":
                instrument_id,
            "source_id":
                source_id,
            "last_attempted_date":
                last_attempted_date,
        },
    )