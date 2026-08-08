from datetime import date

from imi.ksei_holding import (
    parse_ksei_row,
    validate_ksei_record,
)


def test_parse_aadi_row() -> None:
    row = ["31-JUL-2026", "AADI", "EQUITY", "7786891760", "9225", "127413578", "5109623659", "11401520", "41", "1715402583", "101301243", "6979604", "2024003", "167775", "7074314006", "1150700", "37238217", "42111446", "227483904", "2355296", "333731190", "19934568", "167300", "48405133", "712577754"]

    record = parse_ksei_row(
        row
    )

    assert (
        record.as_of_date
        == date(
            2026,
            7,
            31,
        )
    )

    assert record.code == "AADI"

    assert (
        record.security_number
        == 7_786_891_760
    )

    assert (
        record.local_total
        == 7_074_314_006
    )

    assert (
        record.foreign_total
        == 712_577_754
    )

    assert (
        record.scripless_total
        == 7_786_891_760
    )

    assert (
        validate_ksei_record(
            record
        )
        == []
    )


def test_aali_can_have_partial_scripless() -> None:
    row = ["31-JUL-2026", "AALI", "EQUITY", "1924688333", "6875", "72828116", "24250098", "6517818", "49700", "134774035", "15774533", "137766", "4022812", "4750027", "263104905", "273800", "13686952", "18669214", "29773412", "1855952", "32771144", "22751953", "190500", "7719261", "127692188"]

    record = parse_ksei_row(
        row
    )

    assert (
        record.scripless_total
        < record.security_number
    )

    assert (
        record.scripless_pct
        < 100.0
    )

    assert (
        validate_ksei_record(
            record
        )
        == []
    )


def test_foreign_percentage_uses_sec_num() -> None:
    row = ["31-JUL-2026", "AADI", "EQUITY", "7786891760", "9225", "127413578", "5109623659", "11401520", "41", "1715402583", "101301243", "6979604", "2024003", "167775", "7074314006", "1150700", "37238217", "42111446", "227483904", "2355296", "333731190", "19934568", "167300", "48405133", "712577754"]

    record = parse_ksei_row(
        row
    )

    expected = (
        712_577_754
        / 7_786_891_760
        * 100.0
    )

    assert abs(
        record.foreign_ownership_pct
        - expected
    ) < 1e-10