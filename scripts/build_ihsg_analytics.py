from imi.db import engine
from imi.features.technical import (
    FEATURE_VERSION,
    compute_ihsg_technical_features,
)
from imi.regimes.ihsg import (
    MODEL_VERSION,
    compute_ihsg_partial_regimes,
)
from imi.repositories.analytics import (
    build_regime_label_map,
    get_ihsg_id,
    get_regime_labels,
    load_ihsg_prices,
    upsert_partial_regimes,
    upsert_technical_features,
)


def main() -> None:
    print(
        "Indonesia Market Intelligence"
    )
    print(
        "IHSG Analytics Builder"
    )
    print(
        "-----------------------------"
    )

    with engine.connect() as connection:
        prices = load_ihsg_prices(
            connection
        )

        instrument_id = get_ihsg_id(
            connection
        )

    print(
        f"Price rows      : "
        f"{len(prices)}"
    )

    features = (
        compute_ihsg_technical_features(
            prices
        )
    )

    with engine.begin() as connection:
        feature_rows = (
            upsert_technical_features(
                connection,
                instrument_id=(
                    instrument_id
                ),
                features=features,
                feature_version=(
                    FEATURE_VERSION
                ),
            )
        )

    print(
        f"Feature rows    : "
        f"{feature_rows}"
    )
    print(
        f"Feature version : "
        f"{FEATURE_VERSION}"
    )

    regimes = (
        compute_ihsg_partial_regimes(
            features
        )
    )

    with engine.connect() as connection:
        labels = get_regime_labels(
            connection
        )

    print(
        f"Regime labels   : "
        f"{labels}"
    )

    label_map = (
        build_regime_label_map(
            labels
        )
    )

    print(
        f"Regime mapping  : "
        f"{label_map}"
    )

    with engine.begin() as connection:
        regime_rows = (
            upsert_partial_regimes(
                connection,
                regimes=regimes,
                label_map=label_map,
                model_version=(
                    MODEL_VERSION
                ),
            )
        )

    print(
        f"Regime rows     : "
        f"{regime_rows}"
    )
    print(
        f"Model version   : "
        f"{MODEL_VERSION}"
    )

    latest_feature = (
        features.iloc[-1]
    )

    print()
    print("Latest technical state")
    print(
        "----------------------"
    )

    print(
        f"Date       : "
        f"{latest_feature['trading_date']}"
    )
    print(
        f"Close      : "
        f"{latest_feature['close']}"
    )
    print(
        f"EMA20      : "
        f"{latest_feature['ema20']}"
    )
    print(
        f"EMA50      : "
        f"{latest_feature['ema50']}"
    )
    print(
        f"EMA200     : "
        f"{latest_feature['ema200']}"
    )
    print(
        f"RSI14      : "
        f"{latest_feature['rsi14']}"
    )
    print(
        f"ATR14      : "
        f"{latest_feature['atr14']}"
    )

    if not regimes.empty:
        latest_regime = (
            regimes.iloc[-1]
        )

        print()
        print(
            "Latest partial regime"
        )
        print(
            "---------------------"
        )
        print(
            f"Date       : "
            f"{latest_regime['trading_date']}"
        )
        print(
            f"Direction  : "
            f"{latest_regime['direction']}"
        )
        print(
            f"Trend      : "
            f"{latest_regime['ihsg_trend_score']:.2f}"
        )
        print(
            f"Volatility : "
            f"{latest_regime['volatility_score']:.2f}"
        )
        print(
            f"Composite  : "
            f"{latest_regime['composite_score']:.2f}"
        )
        print(
            f"Confidence : "
            f"{latest_regime['confidence']:.3f}"
        )


if __name__ == "__main__":
    main()