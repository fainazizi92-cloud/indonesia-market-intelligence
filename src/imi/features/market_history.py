from datetime import date
from typing import Any

MARKET_HISTORY_VERSION = (
    "market_history_v1"
)


BOARD_MAIN = "MAIN"
BOARD_DEVELOPMENT = "DEVELOPMENT"
BOARD_NEW_ECONOMY = "NEW_ECONOMY"
BOARD_ACCELERATION = "ACCELERATION"
BOARD_WATCHLIST = "WATCHLIST"
BOARD_UNKNOWN = "UNKNOWN"


def normalize_listing_board(
    value: Any,
) -> str:
    if value is None:
        return BOARD_UNKNOWN

    normalized = (
        " ".join(
            str(value)
            .strip()
            .lower()
            .replace("_", " ")
            .replace("-", " ")
            .split()
        )
    )

    mapping = {
        "utama":
            BOARD_MAIN,

        "papan utama":
            BOARD_MAIN,

        "main":
            BOARD_MAIN,

        "main board":
            BOARD_MAIN,

        "pengembangan":
            BOARD_DEVELOPMENT,

        "papan pengembangan":
            BOARD_DEVELOPMENT,

        "development":
            BOARD_DEVELOPMENT,

        "development board":
            BOARD_DEVELOPMENT,

        "ekonomi baru":
            BOARD_NEW_ECONOMY,

        "papan ekonomi baru":
            BOARD_NEW_ECONOMY,

        "new economy":
            BOARD_NEW_ECONOMY,

        "new economy board":
            BOARD_NEW_ECONOMY,

        "akselerasi":
            BOARD_ACCELERATION,

        "papan akselerasi":
            BOARD_ACCELERATION,

        "acceleration":
            BOARD_ACCELERATION,

        "acceleration board":
            BOARD_ACCELERATION,

        "pemantauan khusus":
            BOARD_WATCHLIST,

        "papan pemantauan khusus":
            BOARD_WATCHLIST,

        "watchlist":
            BOARD_WATCHLIST,

        "watchlist board":
            BOARD_WATCHLIST,
    }

    return mapping.get(
        normalized,
        BOARD_UNKNOWN,
    )


def board_group(
    board_code: str,
) -> str:
    if board_code in {
        BOARD_MAIN,
        BOARD_DEVELOPMENT,
        BOARD_NEW_ECONOMY,
    }:
        return "MAIN_DEV_NEW"

    if board_code in {
        BOARD_ACCELERATION,
        BOARD_WATCHLIST,
    }:
        return "ACCEL_WATCH"

    return "UNKNOWN"


def prepare_current_board_rows(
    inputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []

    for item in inputs:
        raw_board = item.get(
            "listing_board"
        )

        normalized_board = (
            normalize_listing_board(
                raw_board
            )
        )

        available_at = item.get(
            "ingested_at"
        )

        point_safe = (
            available_at is not None
            and normalized_board
            != BOARD_UNKNOWN
        )

        rows.append(
            {
                "instrument_id":
                    item[
                        "instrument_id"
                    ],

                # Never backdate current
                # board information.
                "effective_from":
                    item[
                        "snapshot_date"
                    ],

                "effective_to":
                    None,

                "board_code":
                    normalized_board,

                "raw_board_name":
                    (
                        None
                        if raw_board is None
                        else str(
                            raw_board
                        )
                    ),

                "source_code":
                    (
                        "IDX_OFFICIAL_"
                        "CURRENT_PROFILE"
                    ),

                "available_at":
                    available_at,

                "availability_status":
                    (
                        "KNOWN"
                        if available_at
                        is not None
                        else "UNKNOWN"
                    ),

                "point_in_time_safe":
                    point_safe,

                "evidence": {
                    "scope":
                        MARKET_HISTORY_VERSION,

                    "symbol":
                        item[
                            "symbol"
                        ],

                    "snapshot_date":
                        item[
                            "snapshot_date"
                        ].isoformat(),

                    "warning":
                        (
                            "Current board "
                            "classification only. "
                            "It is not backdated "
                            "to historical signals."
                        ),
                },
            }
        )

    return rows


def market_rule_seed_rows(
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    # Lot size.
    #
    # Historical effective date is
    # supported by references to
    # Kep-00071/BEI/11-2013, but this
    # phase does not possess the original
    # decree artifact itself. Therefore
    # verification_status is deliberately
    # REFERENCE_ONLY.
    rows.append(
        {
            "rule_key":
                "LOT_REGULAR_CASH_"
                "20140106_100",

            "rule_type":
                "LOT_SIZE",

            "market":
                "REGULAR_CASH",

            "board_group":
                "ALL",

            "effective_from":
                date(
                    2014,
                    1,
                    6,
                ),

            "effective_to":
                None,

            "price_min":
                None,

            "price_min_inclusive":
                None,

            "price_max":
                None,

            "price_max_inclusive":
                None,

            "lot_size":
                100,

            "tick_size":
                None,

            "ara_pct":
                None,

            "arb_pct":
                None,

            "ara_absolute":
                None,

            "arb_absolute":
                None,

            "source_reference":
                (
                    "Kep-00071/BEI/"
                    "11-2013"
                ),

            "verification_status":
                "REFERENCE_ONLY",

            "evidence": {
                "scope":
                    MARKET_HISTORY_VERSION,

                "effective_date":
                    "2014-01-06",

                "warning":
                    (
                        "Effective date is "
                        "reference-backed but "
                        "the original decree "
                        "artifact has not yet "
                        "been archived locally."
                    ),
            },
        }
    )

    tick_bands = (
        (
            "LT_200",
            None,
            None,
            200.0,
            False,
            1.0,
        ),
        (
            "200_TO_LT_500",
            200.0,
            True,
            500.0,
            False,
            2.0,
        ),
        (
            "500_TO_LT_2000",
            500.0,
            True,
            2000.0,
            False,
            5.0,
        ),
        (
            "2000_TO_LT_5000",
            2000.0,
            True,
            5000.0,
            False,
            10.0,
        ),
        (
            "GE_5000",
            5000.0,
            True,
            None,
            None,
            25.0,
        ),
    )

    for (
        label,
        minimum,
        minimum_inclusive,
        maximum,
        maximum_inclusive,
        tick_size,
    ) in tick_bands:
        rows.append(
            {
                "rule_key":
                    (
                        "TICK_"
                        f"{label}_"
                        "20160502"
                    ),

                "rule_type":
                    "TICK_SIZE",

                "market":
                    "REGULAR_CASH",

                "board_group":
                    "ALL",

                "effective_from":
                    date(
                        2016,
                        5,
                        2,
                    ),

                "effective_to":
                    None,

                "price_min":
                    minimum,

                "price_min_inclusive":
                    minimum_inclusive,

                "price_max":
                    maximum,

                "price_max_inclusive":
                    maximum_inclusive,

                "lot_size":
                    None,

                "tick_size":
                    tick_size,

                "ara_pct":
                    None,

                "arb_pct":
                    None,

                "ara_absolute":
                    None,

                "arb_absolute":
                    None,

                "source_reference":
                    (
                        "Kep-00023/BEI/"
                        "04-2016"
                    ),

                "verification_status":
                    "OFFICIAL",

                "evidence": {
                    "scope":
                        MARKET_HISTORY_VERSION,

                    "effective_date":
                        "2016-05-02",
                },
            }
        )

    main_ar = (
        (
            "50_TO_200",
            50.0,
            True,
            200.0,
            True,
            0.35,
            0.15,
        ),
        (
            "GT_200_TO_5000",
            200.0,
            False,
            5000.0,
            True,
            0.25,
            0.15,
        ),
        (
            "GT_5000",
            5000.0,
            False,
            None,
            None,
            0.20,
            0.15,
        ),
    )

    for (
        label,
        minimum,
        minimum_inclusive,
        maximum,
        maximum_inclusive,
        ara_pct,
        arb_pct,
    ) in main_ar:
        rows.append(
            {
                "rule_key":
                    (
                        "AR_MAIN_DEV_NEW_"
                        f"{label}_"
                        "20250408"
                    ),

                "rule_type":
                    "AUTO_REJECTION",

                "market":
                    "REGULAR_CASH",

                "board_group":
                    "MAIN_DEV_NEW",

                "effective_from":
                    date(
                        2025,
                        4,
                        8,
                    ),

                "effective_to":
                    None,

                "price_min":
                    minimum,

                "price_min_inclusive":
                    minimum_inclusive,

                "price_max":
                    maximum,

                "price_max_inclusive":
                    maximum_inclusive,

                "lot_size":
                    None,

                "tick_size":
                    None,

                "ara_pct":
                    ara_pct,

                "arb_pct":
                    arb_pct,

                "ara_absolute":
                    None,

                "arb_absolute":
                    None,

                "source_reference":
                    (
                        "Kep-00003/BEI/"
                        "04-2025"
                    ),

                "verification_status":
                    "OFFICIAL",

                "evidence": {
                    "scope":
                        MARKET_HISTORY_VERSION,

                    "effective_date":
                        "2025-04-08",
                },
            }
        )

    # Acceleration / Watchlist:
    # Rp1-Rp10 => Rp1 absolute AR.
    rows.append(
        {
            "rule_key":
                (
                    "AR_ACCEL_WATCH_"
                    "1_TO_10_20250408"
                ),

            "rule_type":
                "AUTO_REJECTION",

            "market":
                "REGULAR_CASH",

            "board_group":
                "ACCEL_WATCH",

            "effective_from":
                date(
                    2025,
                    4,
                    8,
                ),

            "effective_to":
                None,

            "price_min":
                1.0,

            "price_min_inclusive":
                True,

            "price_max":
                10.0,

            "price_max_inclusive":
                True,

            "lot_size":
                None,

            "tick_size":
                None,

            "ara_pct":
                None,

            "arb_pct":
                None,

            "ara_absolute":
                1.0,

            "arb_absolute":
                1.0,

            "source_reference":
                (
                    "Kep-00003/BEI/"
                    "04-2025"
                ),

            "verification_status":
                "OFFICIAL",

            "evidence": {
                "scope":
                    MARKET_HISTORY_VERSION,

                "effective_date":
                    "2025-04-08",
            },
        }
    )

    rows.append(
        {
            "rule_key":
                (
                    "AR_ACCEL_WATCH_"
                    "GT_10_20250408"
                ),

            "rule_type":
                "AUTO_REJECTION",

            "market":
                "REGULAR_CASH",

            "board_group":
                "ACCEL_WATCH",

            "effective_from":
                date(
                    2025,
                    4,
                    8,
                ),

            "effective_to":
                None,

            "price_min":
                10.0,

            "price_min_inclusive":
                False,

            "price_max":
                None,

            "price_max_inclusive":
                None,

            "lot_size":
                None,

            "tick_size":
                None,

            "ara_pct":
                0.10,

            "arb_pct":
                0.10,

            "ara_absolute":
                None,

            "arb_absolute":
                None,

            "source_reference":
                (
                    "Kep-00003/BEI/"
                    "04-2025"
                ),

            "verification_status":
                "OFFICIAL",

            "evidence": {
                "scope":
                    MARKET_HISTORY_VERSION,

                "effective_date":
                    "2025-04-08",
            },
        }
    )

    return rows


def price_matches_rule(
    *,
    price: float,
    rule: dict[str, Any],
) -> bool:
    value = float(
        price
    )

    minimum = rule[
        "price_min"
    ]

    maximum = rule[
        "price_max"
    ]

    if minimum is not None:
        minimum_value = float(
            minimum
        )

        if rule[
            "price_min_inclusive"
        ]:
            if value < minimum_value:
                return False

        elif value <= minimum_value:
            return False

    if maximum is not None:
        maximum_value = float(
            maximum
        )

        if rule[
            "price_max_inclusive"
        ]:
            if value > maximum_value:
                return False

        elif value >= maximum_value:
            return False

    return True


def rule_active_on(
    *,
    trading_date: date,
    rule: dict[str, Any],
) -> bool:
    if (
        trading_date
        < rule[
            "effective_from"
        ]
    ):
        return False

    effective_to = rule[
        "effective_to"
    ]

    return (
        effective_to is None
        or trading_date
        <= effective_to
    )


def idx_lot_size_on(
    *,
    trading_date: date,
    rules: list[dict[str, Any]],
) -> int | None:
    candidates = [
        rule
        for rule in rules
        if (
            rule[
                "rule_type"
            ]
            == "LOT_SIZE"
            and rule_active_on(
                trading_date=(
                    trading_date
                ),
                rule=rule,
            )
        )
    ]

    if not candidates:
        return None

    selected = max(
        candidates,
        key=lambda rule:
            rule[
                "effective_from"
            ],
    )

    lot_size = selected[
        "lot_size"
    ]

    return (
        None
        if lot_size is None
        else int(
            lot_size
        )
    )


def idx_tick_size_on(
    *,
    trading_date: date,
    price: float,
    rules: list[dict[str, Any]],
) -> float | None:
    candidates = [
        rule
        for rule in rules
        if (
            rule[
                "rule_type"
            ]
            == "TICK_SIZE"
            and rule_active_on(
                trading_date=(
                    trading_date
                ),
                rule=rule,
            )
            and price_matches_rule(
                price=price,
                rule=rule,
            )
        )
    ]

    if not candidates:
        return None

    newest_date = max(
        rule[
            "effective_from"
        ]
        for rule in candidates
    )

    newest = [
        rule
        for rule in candidates
        if rule[
            "effective_from"
        ]
        == newest_date
    ]

    if len(
        newest
    ) != 1:
        raise RuntimeError(
            "Ambiguous tick-size rules."
        )

    value = newest[0][
        "tick_size"
    ]

    return (
        None
        if value is None
        else float(
            value
        )
    )


def idx_auto_rejection_on(
    *,
    trading_date: date,
    price: float,
    board_code: str,
    rules: list[dict[str, Any]],
) -> dict[str, Any] | None:
    group = board_group(
        board_code
    )

    if group == "UNKNOWN":
        return None

    candidates = [
        rule
        for rule in rules
        if (
            rule[
                "rule_type"
            ]
            == "AUTO_REJECTION"
            and rule[
                "board_group"
            ]
            == group
            and rule_active_on(
                trading_date=(
                    trading_date
                ),
                rule=rule,
            )
            and price_matches_rule(
                price=price,
                rule=rule,
            )
        )
    ]

    if not candidates:
        return None

    newest_date = max(
        rule[
            "effective_from"
        ]
        for rule in candidates
    )

    newest = [
        rule
        for rule in candidates
        if rule[
            "effective_from"
        ]
        == newest_date
    ]

    if len(
        newest
    ) != 1:
        raise RuntimeError(
            "Ambiguous auto-rejection "
            "rules."
        )

    return newest[0]