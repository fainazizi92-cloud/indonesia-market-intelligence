import json
from uuid import UUID

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

LOAD_IHSG_PRICES = text(
    """
    SELECT
        mp.trading_date,
        mp.open,
        mp.high,
        mp.low,
        mp.close,
        mp.volume
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


GET_IHSG_ID = text(
    """
    SELECT id
    FROM instruments
    WHERE symbol = 'IHSG'
      AND exchange = 'IDX'
      AND asset_type = 'INDEX'
    """
)


UPSERT_FEATURE = text(
    """
    INSERT INTO technical_features_daily (
        instrument_id,
        trading_date,
        return_1d,
        return_5d,
        return_20d,
        return_60d,
        ema20,
        ema50,
        ema100,
        ema200,
        rsi14,
        atr14,
        volume_z20,
        rs_ihsg_20d,
        rs_sector_20d,
        breakout_flag,
        failed_breakout_flag,
        feature_version
    )
    VALUES (
        :instrument_id,
        :trading_date,
        :return_1d,
        :return_5d,
        :return_20d,
        :return_60d,
        :ema20,
        :ema50,
        :ema100,
        :ema200,
        :rsi14,
        :atr14,
        :volume_z20,
        :rs_ihsg_20d,
        :rs_sector_20d,
        :breakout_flag,
        :failed_breakout_flag,
        :feature_version
    )
    ON CONFLICT (
        instrument_id,
        trading_date,
        feature_version
    )
    DO UPDATE SET
        return_1d =
            EXCLUDED.return_1d,
        return_5d =
            EXCLUDED.return_5d,
        return_20d =
            EXCLUDED.return_20d,
        return_60d =
            EXCLUDED.return_60d,
        ema20 =
            EXCLUDED.ema20,
        ema50 =
            EXCLUDED.ema50,
        ema100 =
            EXCLUDED.ema100,
        ema200 =
            EXCLUDED.ema200,
        rsi14 =
            EXCLUDED.rsi14,
        atr14 =
            EXCLUDED.atr14,
        volume_z20 =
            EXCLUDED.volume_z20,
        rs_ihsg_20d =
            EXCLUDED.rs_ihsg_20d,
        rs_sector_20d =
            EXCLUDED.rs_sector_20d,
        breakout_flag =
            EXCLUDED.breakout_flag,
        failed_breakout_flag =
            EXCLUDED.failed_breakout_flag,
        calculated_at =
            NOW()
    """
)


GET_REGIME_LABELS = text(
    """
    SELECT e.enumlabel
    FROM pg_type t
    JOIN pg_enum e
        ON t.oid = e.enumtypid
    WHERE t.typname = 'regime_label'
    ORDER BY e.enumsortorder
    """
)


UPSERT_REGIME = text(
    """
    INSERT INTO market_regimes_daily (
        trading_date,
        regime,
        confidence,
        global_score,
        indonesia_macro_score,
        ihsg_trend_score,
        breadth_score,
        flow_score,
        volatility_score,
        model_version,
        evidence
    )
    VALUES (
        :trading_date,
        CAST(
            :regime
            AS regime_label
        ),
        :confidence,
        NULL,
        NULL,
        :ihsg_trend_score,
        NULL,
        NULL,
        :volatility_score,
        :model_version,
        CAST(
            :evidence
            AS jsonb
        )
    )
    ON CONFLICT (
        trading_date,
        model_version
    )
    DO UPDATE SET
        regime =
            EXCLUDED.regime,
        confidence =
            EXCLUDED.confidence,
        global_score =
            EXCLUDED.global_score,
        indonesia_macro_score =
            EXCLUDED.indonesia_macro_score,
        ihsg_trend_score =
            EXCLUDED.ihsg_trend_score,
        breadth_score =
            EXCLUDED.breadth_score,
        flow_score =
            EXCLUDED.flow_score,
        volatility_score =
            EXCLUDED.volatility_score,
        evidence =
            EXCLUDED.evidence,
        calculated_at =
            NOW()
    """
)


def _number(
    value: object,
) -> float | None:
    if value is None:
        return None

    if pd.isna(value):
        return None

    return float(value)


def _boolean(
    value: object,
) -> bool | None:
    if value is None:
        return None

    if pd.isna(value):
        return None

    return bool(value)


def load_ihsg_prices(
    connection: Connection,
) -> pd.DataFrame:
    rows = (
        connection.execute(
            LOAD_IHSG_PRICES
        )
        .mappings()
        .all()
    )

    if not rows:
        raise RuntimeError(
            "No IHSG market prices found."
        )

    return pd.DataFrame(rows)


def get_ihsg_id(
    connection: Connection,
) -> UUID:
    instrument_id = (
        connection.execute(
            GET_IHSG_ID
        ).scalar_one_or_none()
    )

    if instrument_id is None:
        raise RuntimeError(
            "IHSG instrument not found."
        )

    return instrument_id


def upsert_technical_features(
    connection: Connection,
    *,
    instrument_id: UUID,
    features: pd.DataFrame,
    feature_version: str,
) -> int:
    parameters = []

    for row in features.itertuples(
        index=False
    ):
        parameters.append(
            {
                "instrument_id":
                    instrument_id,
                "trading_date":
                    row.trading_date,
                "return_1d":
                    _number(
                        row.return_1d
                    ),
                "return_5d":
                    _number(
                        row.return_5d
                    ),
                "return_20d":
                    _number(
                        row.return_20d
                    ),
                "return_60d":
                    _number(
                        row.return_60d
                    ),
                "ema20":
                    _number(
                        row.ema20
                    ),
                "ema50":
                    _number(
                        row.ema50
                    ),
                "ema100":
                    _number(
                        row.ema100
                    ),
                "ema200":
                    _number(
                        row.ema200
                    ),
                "rsi14":
                    _number(
                        row.rsi14
                    ),
                "atr14":
                    _number(
                        row.atr14
                    ),
                "volume_z20":
                    _number(
                        row.volume_z20
                    ),
                "rs_ihsg_20d":
                    _number(
                        row.rs_ihsg_20d
                    ),
                "rs_sector_20d":
                    _number(
                        row.rs_sector_20d
                    ),
                "breakout_flag":
                    _boolean(
                        row.breakout_flag
                    ),
                "failed_breakout_flag":
                    _boolean(
                        row.failed_breakout_flag
                    ),
                "feature_version":
                    feature_version,
            }
        )

    connection.execute(
        UPSERT_FEATURE,
        parameters,
    )

    return len(parameters)


def get_regime_labels(
    connection: Connection,
) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            GET_REGIME_LABELS
        )
    ]


def build_regime_label_map(
    labels: list[str],
) -> dict[str, str]:
    available = set(labels)

    candidates = {
        "BULLISH": (
            "BULLISH",
            "BULL",
            "RISK_ON",
        ),
        "NEUTRAL": (
            "NEUTRAL",
            "SIDEWAYS",
        ),
        "BEARISH": (
            "BEARISH",
            "BEAR",
            "RISK_OFF",
        ),
    }

    mapping = {}

    for (
        direction,
        options,
    ) in candidates.items():
        selected = next(
            (
                option
                for option in options
                if option in available
            ),
            None,
        )

        if selected is None:
            raise RuntimeError(
                "No compatible "
                "regime_label for "
                f"{direction}. "
                f"Available labels: "
                f"{labels}"
            )

        mapping[
            direction
        ] = selected

    return mapping


def upsert_partial_regimes(
    connection: Connection,
    *,
    regimes: pd.DataFrame,
    label_map: dict[str, str],
    model_version: str,
) -> int:
    parameters = []

    for row in regimes.itertuples(
        index=False
    ):
        direction = str(
            row.direction
        )

        evidence = {
            "partial_model": True,
            "price_source":
                "YAHOO_FINANCE",
            "available_components": [
                "ihsg_trend",
                "volatility",
            ],
            "missing_components": [
                "global",
                "indonesia_macro",
                "breadth",
                "flow",
            ],
            "composite_score":
                _number(
                    row.composite_score
                ),
            "score_scale":
                "0-100",
            "confidence_scale":
                "0-1",
            "notes": (
                "Research-only partial "
                "market regime."
            ),
        }

        parameters.append(
            {
                "trading_date":
                    row.trading_date,
                "regime":
                    label_map[
                        direction
                    ],
                "confidence":
                    _number(
                        row.confidence
                    ),
                "ihsg_trend_score":
                    _number(
                        row.ihsg_trend_score
                    ),
                "volatility_score":
                    _number(
                        row.volatility_score
                    ),
                "model_version":
                    model_version,
                "evidence":
                    json.dumps(
                        evidence
                    ),
            }
        )

    connection.execute(
        UPSERT_REGIME,
        parameters,
    )

    return len(parameters)