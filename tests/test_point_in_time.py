from datetime import (
    UTC,
    date,
    datetime,
)
from uuid import UUID

import pytest

from imi.features.point_in_time import (
    build_observation_key,
    calculate_pit_coverage,
    evaluate_availability,
    historical_membership_active,
    information_available_on,
    prepare_current_lifecycle_rows,
    prepare_current_universe_membership_rows,
    prepare_known_availability_row,
    prepare_unknown_availability_row,
)

INSTRUMENT_ID = UUID(
    "00000000-0000-0000-0000-000000000001"
)


def universe_row(
    *,
    ingested_at=None,
    delisted_date=None,
):
    if ingested_at is None:
        ingested_at = datetime(
            2026,
            8,
            8,
            10,
            0,
            tzinfo=UTC,
        )

    return {
        "instrument_id":
            INSTRUMENT_ID,

        "symbol":
            "TEST",

        "listed_date":
            date(
                2020,
                1,
                2,
            ),

        "delisted_date":
            delisted_date,

        "snapshot_date":
            date(
                2026,
                8,
                8,
            ),

        "ingested_at":
            ingested_at,

        "metadata":
            {},
    }


def test_observation_key():
    assert (
        build_observation_key(
            "A",
            "B",
            1,
        )
        == "A|B|1"
    )


def test_empty_observation_key():
    with pytest.raises(
        ValueError
    ):
        build_observation_key(
            None,
            "",
        )


def test_unknown_is_not_safe():
    result = evaluate_availability(
        observation_date=date(
            2026,
            1,
            31,
        ),
        published_at=None,
        available_at=None,
        status="UNKNOWN",
    )

    assert (
        result.point_in_time_safe
        is False
    )


def test_known_available_is_safe():
    result = evaluate_availability(
        observation_date=date(
            2026,
            1,
            31,
        ),
        published_at=None,
        available_at=datetime(
            2026,
            2,
            1,
            tzinfo=UTC,
        ),
        status="KNOWN",
    )

    assert (
        result.point_in_time_safe
        is True
    )


def test_estimated_is_not_safe():
    result = evaluate_availability(
        observation_date=date(
            2026,
            1,
            31,
        ),
        published_at=None,
        available_at=datetime(
            2026,
            2,
            1,
            tzinfo=UTC,
        ),
        status="ESTIMATED",
    )

    assert (
        result.point_in_time_safe
        is False
    )


def test_available_before_publication_rejected():
    with pytest.raises(
        ValueError
    ):
        evaluate_availability(
            observation_date=date(
                2026,
                1,
                31,
            ),
            published_at=datetime(
                2026,
                2,
                2,
                tzinfo=UTC,
            ),
            available_at=datetime(
                2026,
                2,
                1,
                tzinfo=UTC,
            ),
            status="KNOWN",
        )


def test_information_available_on_signal_date():
    decision = evaluate_availability(
        observation_date=date(
            2026,
            1,
            31,
        ),
        published_at=None,
        available_at=datetime(
            2026,
            2,
            1,
            tzinfo=UTC,
        ),
        status="KNOWN",
    )

    assert information_available_on(
        signal_date=date(
            2026,
            2,
            2,
        ),
        decision=decision,
    )


def test_information_not_available_before_release():
    decision = evaluate_availability(
        observation_date=date(
            2026,
            1,
            31,
        ),
        published_at=None,
        available_at=datetime(
            2026,
            2,
            2,
            tzinfo=UTC,
        ),
        status="KNOWN",
    )

    assert not information_available_on(
        signal_date=date(
            2026,
            2,
            1,
        ),
        decision=decision,
    )


def test_membership_active():
    assert historical_membership_active(
        signal_date=date(
            2026,
            8,
            9,
        ),
        valid_from=date(
            2026,
            8,
            8,
        ),
        valid_to=None,
        membership_status="ACTIVE",
        point_in_time_safe=True,
    )


def test_membership_before_valid_from():
    assert not historical_membership_active(
        signal_date=date(
            2026,
            8,
            7,
        ),
        valid_from=date(
            2026,
            8,
            8,
        ),
        valid_to=None,
        membership_status="ACTIVE",
        point_in_time_safe=True,
    )


def test_unsafe_membership_is_false():
    assert not historical_membership_active(
        signal_date=date(
            2026,
            8,
            9,
        ),
        valid_from=date(
            2026,
            8,
            8,
        ),
        valid_to=None,
        membership_status="ACTIVE",
        point_in_time_safe=False,
    )


def test_coverage():
    rows = [
        {
            "availability_status":
                "KNOWN",
            "point_in_time_safe":
                True,
        },
        {
            "availability_status":
                "UNKNOWN",
            "point_in_time_safe":
                False,
        },
        {
            "availability_status":
                "ESTIMATED",
            "point_in_time_safe":
                False,
        },
    ]

    coverage = (
        calculate_pit_coverage(
            rows
        )
    )

    assert coverage.total == 3
    assert coverage.known == 1
    assert coverage.unknown == 1
    assert coverage.estimated == 1
    assert coverage.safe == 1


def test_prepare_unknown_row():
    row = (
        prepare_unknown_availability_row(
            dataset_code="TEST",
            observation_key="A",
            observation_date=date(
                2026,
                1,
                31,
            ),
            source_code="SOURCE",
            source_reference=None,
        )
    )

    assert (
        row[
            "availability_status"
        ]
        == "UNKNOWN"
    )

    assert (
        row[
            "point_in_time_safe"
        ]
        is False
    )


def test_prepare_known_row():
    row = (
        prepare_known_availability_row(
            dataset_code="TEST",
            observation_key="A",
            observation_date=date(
                2026,
                8,
                8,
            ),
            available_at=datetime(
                2026,
                8,
                8,
                10,
                tzinfo=UTC,
            ),
            source_code="SOURCE",
            source_reference=None,
        )
    )

    assert (
        row[
            "availability_status"
        ]
        == "KNOWN"
    )

    assert (
        row[
            "point_in_time_safe"
        ]
        is True
    )


def test_current_membership_starts_at_snapshot():
    row = (
        prepare_current_universe_membership_rows(
            [
                universe_row()
            ]
        )[0]
    )

    assert (
        row[
            "valid_from"
        ]
        == date(
            2026,
            8,
            8,
        )
    )

    assert (
        row[
            "valid_from"
        ]
        != date(
            2020,
            1,
            2,
        )
    )


def test_current_membership_is_safe_prospectively():
    row = (
        prepare_current_universe_membership_rows(
            [
                universe_row()
            ]
        )[0]
    )

    assert (
        row[
            "point_in_time_safe"
        ]
        is True
    )


def test_lifecycle_starts_at_observation_date():
    row = (
        prepare_current_lifecycle_rows(
            [
                universe_row()
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

    assert (
        row[
            "listing_date"
        ]
        == date(
            2020,
            1,
            2,
        )
    )


def test_delisted_lifecycle_status():
    row = (
        prepare_current_lifecycle_rows(
            [
                universe_row(
                    delisted_date=date(
                        2026,
                        8,
                        7,
                    )
                )
            ]
        )[0]
    )

    assert (
        row[
            "lifecycle_status"
        ]
        == "DELISTED"
    )