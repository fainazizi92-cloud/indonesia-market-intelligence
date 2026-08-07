from sqlalchemy import text

from imi.db import engine
from imi.features.technical import (
    FEATURE_VERSION,
)
from imi.regimes.ihsg import (
    MODEL_VERSION,
)

FEATURE_SUMMARY = text(
    """
    SELECT
        COUNT(*) AS rows,
        MIN(trading_date) AS first_date,
        MAX(trading_date) AS last_date,
        COUNT(ema200) AS ema200_rows,
        COUNT(rsi14) AS rsi_rows,
        COUNT(atr14) AS atr_rows
    FROM technical_features_daily
    WHERE feature_version =
        :feature_version
    """
)


LATEST_FEATURE = text(
    """
    SELECT
        tf.trading_date,
        mp.close,
        tf.return_1d,
        tf.return_20d,
        tf.return_60d,
        tf.ema20,
        tf.ema50,
        tf.ema100,
        tf.ema200,
        tf.rsi14,
        tf.atr14,
        tf.breakout_flag,
        tf.failed_breakout_flag
    FROM technical_features_daily tf
    JOIN instruments i
        ON i.id = tf.instrument_id
    JOIN market_prices_eod mp
        ON mp.instrument_id =
            tf.instrument_id
       AND mp.trading_date =
            tf.trading_date
    JOIN data_sources ds
        ON ds.id = mp.source_id
    WHERE i.symbol = 'IHSG'
      AND tf.feature_version =
          :feature_version
      AND ds.code =
          'YAHOO_FINANCE'
    ORDER BY tf.trading_date DESC
    LIMIT 1
    """
)


REGIME_SUMMARY = text(
    """
    SELECT
        regime::text,
        COUNT(*)
    FROM market_regimes_daily
    WHERE model_version =
        :model_version
    GROUP BY regime
    ORDER BY regime
    """
)


LATEST_REGIME = text(
    """
    SELECT
        trading_date,
        regime::text,
        confidence,
        ihsg_trend_score,
        volatility_score,
        evidence
    FROM market_regimes_daily
    WHERE model_version =
        :model_version
    ORDER BY trading_date DESC
    LIMIT 1
    """
)


def main() -> None:
    with engine.connect() as connection:
        feature_summary = (
            connection.execute(
                FEATURE_SUMMARY,
                {
                    "feature_version":
                        FEATURE_VERSION
                },
            )
            .mappings()
            .one()
        )

        latest_feature = (
            connection.execute(
                LATEST_FEATURE,
                {
                    "feature_version":
                        FEATURE_VERSION
                },
            )
            .mappings()
            .one_or_none()
        )

        regime_summary = list(
            connection.execute(
                REGIME_SUMMARY,
                {
                    "model_version":
                        MODEL_VERSION
                },
            )
        )

        latest_regime = (
            connection.execute(
                LATEST_REGIME,
                {
                    "model_version":
                        MODEL_VERSION
                },
            )
            .mappings()
            .one_or_none()
        )

    print(
        "IHSG Analytics Check"
    )
    print(
        "--------------------"
    )

    for key, value in (
        feature_summary.items()
    ):
        print(
            f"{key:12}: {value}"
        )

    print()
    print(
        "Latest feature:"
    )
    print(latest_feature)

    print()
    print(
        "Regime distribution:"
    )

    for row in regime_summary:
        print(row)

    print()
    print(
        "Latest regime:"
    )
    print(latest_regime)


if __name__ == "__main__":
    main()