from datetime import date
from pathlib import Path
from zipfile import ZipFile

import pytest

from imi.ksei_holding import (
    build_holder_details,
    extract_archive_snapshot_date,
    extract_member_snapshot_date,
    parse_ksei_holding_archive,
    parse_ksei_row,
    validate_archive_identity,
    validate_ksei_record,
)

HEADER = (
    "Date|Code|Type|Sec. Num|Price|"
    "Local IS|Local CP|Local PF|"
    "Local IB|Local ID|Local MF|"
    "Local SC|Local FD|Local OT|"
    "Total|Foreign IS|Foreign CP|"
    "Foreign PF|Foreign IB|"
    "Foreign ID|Foreign MF|"
    "Foreign SC|Foreign FD|"
    "Foreign OT|Total"
)


AADI_ROW = (
    "31-JUL-2026|AADI|EQUITY|"
    "7786891760|9225|"
    "127413578|5109623659|"
    "11401520|41|1715402583|"
    "101301243|6979604|"
    "2024003|167775|"
    "7074314006|"
    "1150700|37238217|"
    "42111446|227483904|"
    "2355296|333731190|"
    "19934568|167300|"
    "48405133|712577754"
)


AALI_ROW = (
    "31-JUL-2026|AALI|EQUITY|"
    "1924688333|6875|"
    "72828116|24250098|"
    "6517818|49700|134774035|"
    "15774533|137766|"
    "4022812|4750027|"
    "263104905|"
    "273800|13686952|"
    "18669214|29773412|"
    "1855952|32771144|"
    "22751953|190500|"
    "7719261|127692188"
)


def test_parse_aadi_row() -> None:
    record = parse_ksei_row(
        AADI_ROW.split("|")
    )

    assert record.as_of_date == date(
        2026,
        7,
        31,
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
    record = parse_ksei_row(
        AALI_ROW.split("|")
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
    record = parse_ksei_row(
        AADI_ROW.split("|")
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


def test_extract_archive_snapshot_date() -> None:
    result = (
        extract_archive_snapshot_date(
            Path(
                "BalanceposEfek20260731.zip"
            )
        )
    )

    assert result == date(
        2026,
        7,
        31,
    )


def test_extract_member_snapshot_date() -> None:
    result = (
        extract_member_snapshot_date(
            "Balancepos20260731.txt"
        )
    )

    assert result == date(
        2026,
        7,
        31,
    )


def test_archive_identity_rejects_mismatch(
    tmp_path: Path,
) -> None:
    record = parse_ksei_row(
        AADI_ROW.split("|")
    )

    archive_path = (
        tmp_path
        / "BalanceposEfek20260630.zip"
    )

    with pytest.raises(
        RuntimeError
    ):
        validate_archive_identity(
            archive_path=archive_path,
            member_name=(
                "Balancepos20260731.txt"
            ),
            records=[record],
        )


def test_non_equity_with_empty_sec_num_is_skipped(
    tmp_path: Path,
) -> None:
    archive_path = (
        tmp_path
        / "BalanceposEfek20260731.zip"
    )

    non_equity = (
        "31-JUL-2026|ADEL02X3SCF|"
        "CORPORATE BOND||0|"
        "0|0|0|0|0|0|0|0|0|0|"
        "0|0|0|0|0|0|0|0|0|0"
    )

    text = (
        HEADER
        + "\n"
        + AADI_ROW
        + "\n"
        + non_equity
        + "\n"
    )

    with ZipFile(
        archive_path,
        "w",
    ) as archive:
        archive.writestr(
            "Balancepos20260731.txt",
            text,
        )

    records, rejected, _ = (
        parse_ksei_holding_archive(
            archive_path
        )
    )

    assert len(records) == 1

    assert (
        records[0].code
        == "AADI"
    )

    assert rejected == []


def test_holder_details_contains_snapshot_date() -> None:
    record = parse_ksei_row(
        AADI_ROW.split("|")
    )

    result = build_holder_details(
        record,
        archive_name=(
            "BalanceposEfek20260731.zip"
        ),
        member_name=(
            "Balancepos20260731.txt"
        ),
    )

    assert (
        result["as_of_date"]
        == "2026-07-31"
    )