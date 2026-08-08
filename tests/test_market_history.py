from datetime import (
    UTC,
    date,
    datetime,
)
from uuid import UUID

from imi.features.market_history import (
    BOARD_ACCELERATION,
    BOARD_DEVELOPMENT,
    BOARD_MAIN,
    BOARD_NEW_ECONOMY,
    BOARD_UNKNOWN,
    BOARD_WATCHLIST,
    idx_auto_rejection_on,
    idx_lot_size_on,
    idx_tick_size_on,
    market_rule_seed_rows,
    normalize_listing_board,
    prepare_current_board_rows,
)

INSTRUMENT_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def rules():
    return (
        market_rule_seed_rows()
    )


def current_input(
    board="Utama",
):
    return {
        "instrument_id":
            INSTRUMENT_ID,

        "symbol":
            "TEST",

        "listing_board":
            board,

        "snapshot_date":
            date(
                2026,
                8,
                8,
            ),

        "ingested_at":
            datetime(
                2026,
                8,
                8,
                3,
                0,
                tzinfo=UTC,
            ),
    }


def test_normalize_main():
    assert (
        normalize_listing_board(
            "Utama"
        )
        == BOARD_MAIN
    )


def test_normalize_development():
    assert (
        normalize_listing_board(
            "Pengembangan"
        )
        == BOARD_DEVELOPMENT
    )


def test_normalize_new_economy():
    assert (
        normalize_listing_board(
            "Ekonomi Baru"
        )
        == BOARD_NEW_ECONOMY
    )


def test_normalize_acceleration():
    assert (
        normalize_listing_board(
            "Akselerasi"
        )
        == BOARD_ACCELERATION
    )


def test_normalize_watchlist():
    assert (
        normalize_listing_board(
            "Pemantauan Khusus"
        )
        == BOARD_WATCHLIST
    )


def test_unknown_board():
    assert (
        normalize_listing_board(
            "UNRECOGNIZED"
        )
        == BOARD_UNKNOWN
    )


def test_current_board_not_backdated():
    row = (
        prepare_current_board_rows(
            [
                current_input()
            ]
        )[0]
    )

    assert (
        row[
            "effective_from"
        ]
        == date(
            2026,
            8,
            8,
        )
    )


def test_known_board_is_safe():
    row = (
        prepare_current_board_rows(
            [
                current_input()
            ]
        )[0]
    )

    assert (
        row[
            "point_in_time_safe"
        ]
        is True
    )


def test_unknown_board_not_safe():
    row = (
        prepare_current_board_rows(
            [
                current_input(
                    board="???"
                )
            ]
        )[0]
    )

    assert (
        row[
            "point_in_time_safe"
        ]
        is False
    )


def test_seed_rule_count():
    assert len(
        rules()
    ) == 11


def test_lot_size_2026():
    assert (
        idx_lot_size_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            rules=rules(),
        )
        == 100
    )


def test_lot_before_2014_missing():
    assert (
        idx_lot_size_on(
            trading_date=date(
                2013,
                12,
                31,
            ),
            rules=rules(),
        )
        is None
    )


def test_tick_below_200():
    assert (
        idx_tick_size_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=199,
            rules=rules(),
        )
        == 1
    )


def test_tick_at_200():
    assert (
        idx_tick_size_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=200,
            rules=rules(),
        )
        == 2
    )


def test_tick_at_500():
    assert (
        idx_tick_size_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=500,
            rules=rules(),
        )
        == 5
    )


def test_tick_at_2000():
    assert (
        idx_tick_size_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=2000,
            rules=rules(),
        )
        == 10
    )


def test_tick_at_5000():
    assert (
        idx_tick_size_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=5000,
            rules=rules(),
        )
        == 25
    )


def test_main_ar_200():
    rule = (
        idx_auto_rejection_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=200,
            board_code=(
                BOARD_MAIN
            ),
            rules=rules(),
        )
    )

    assert rule is not None
    assert (
        float(
            rule[
                "ara_pct"
            ]
        )
        == 0.35
    )

    assert (
        float(
            rule[
                "arb_pct"
            ]
        )
        == 0.15
    )


def test_main_ar_1000():
    rule = (
        idx_auto_rejection_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=1000,
            board_code=(
                BOARD_DEVELOPMENT
            ),
            rules=rules(),
        )
    )

    assert rule is not None

    assert (
        float(
            rule[
                "ara_pct"
            ]
        )
        == 0.25
    )


def test_main_ar_above_5000():
    rule = (
        idx_auto_rejection_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=6000,
            board_code=(
                BOARD_NEW_ECONOMY
            ),
            rules=rules(),
        )
    )

    assert rule is not None

    assert (
        float(
            rule[
                "ara_pct"
            ]
        )
        == 0.20
    )


def test_acceleration_low_price_absolute():
    rule = (
        idx_auto_rejection_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=8,
            board_code=(
                BOARD_ACCELERATION
            ),
            rules=rules(),
        )
    )

    assert rule is not None

    assert (
        float(
            rule[
                "ara_absolute"
            ]
        )
        == 1
    )

    assert (
        float(
            rule[
                "arb_absolute"
            ]
        )
        == 1
    )


def test_watchlist_above_10():
    rule = (
        idx_auto_rejection_on(
            trading_date=date(
                2026,
                8,
                6,
            ),
            price=50,
            board_code=(
                BOARD_WATCHLIST
            ),
            rules=rules(),
        )
    )

    assert rule is not None

    assert (
        float(
            rule[
                "ara_pct"
            ]
        )
        == 0.10
    )

    assert (
        float(
            rule[
                "arb_pct"
            ]
        )
        == 0.10
    )


def test_ar_before_effective_date_missing():
    assert (
        idx_auto_rejection_on(
            trading_date=date(
                2025,
                4,
                7,
            ),
            price=1000,
            board_code=(
                BOARD_MAIN
            ),
            rules=rules(),
        )
        is None
    )