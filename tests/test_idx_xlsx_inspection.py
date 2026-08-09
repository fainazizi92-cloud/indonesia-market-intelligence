from datetime import (
    UTC,
    date,
    datetime,
)
from io import BytesIO

import pytest
from openpyxl import Workbook

from imi.features.idx_xlsx_inspection import (
    inspect_xlsx_bytes,
    is_xlsx_bytes,
    normalize_cell_value,
    row_has_value,
)


def make_workbook_bytes() -> bytes:
    workbook = Workbook()

    worksheet = (
        workbook.active
    )

    worksheet.title = (
        "Delisting"
    )

    worksheet.append(
        [
            "Code",
            "Company Name",
            "Listing Date",
            "Delisting Date",
        ]
    )

    worksheet.append(
        [
            "TEST",
            "Test Company Tbk.",
            date(
                2020,
                1,
                2,
            ),
            date(
                2024,
                10,
                3,
            ),
        ]
    )

    buffer = BytesIO()

    workbook.save(
        buffer
    )

    workbook.close()

    return buffer.getvalue()


def test_xlsx_signature():
    content = (
        make_workbook_bytes()
    )

    assert (
        is_xlsx_bytes(
            content
        )
        is True
    )


def test_non_xlsx_signature():
    assert (
        is_xlsx_bytes(
            b"not-an-xlsx"
        )
        is False
    )


def test_normalize_datetime():
    value = datetime(
        2024,
        10,
        3,
        0,
        0,
        tzinfo=UTC,
    )

    assert (
        normalize_cell_value(
            value
        )
        == "2024-10-03T00:00:00+00:00"
    )


def test_normalize_date():
    value = date(
        2024,
        10,
        3,
    )

    assert (
        normalize_cell_value(
            value
        )
        == "2024-10-03"
    )


def test_normalize_text():
    assert (
        normalize_cell_value(
            "  Test   Company  "
        )
        == "Test Company"
    )


def test_empty_text_becomes_none():
    assert (
        normalize_cell_value(
            "   "
        )
        is None
    )


def test_empty_row():
    assert (
        row_has_value(
            (
                None,
                "",
                None,
            )
        )
        is False
    )


def test_non_empty_row():
    assert (
        row_has_value(
            (
                None,
                "TEST",
            )
        )
        is True
    )


def test_inspect_workbook():
    result = (
        inspect_xlsx_bytes(
            make_workbook_bytes()
        )
    )

    assert result.sheet_names == (
        "Delisting",
    )

    assert len(
        result.worksheets
    ) == 1

    worksheet = (
        result.worksheets[
            0
        ]
    )

    assert (
        worksheet.title
        == "Delisting"
    )

    assert (
        len(
            worksheet.non_empty_rows
        )
        == 2
    )

    assert (
        worksheet
        .non_empty_rows[
            0
        ][1][0]
        == "Code"
    )

    assert (
        worksheet
        .non_empty_rows[
            1
        ][1][0]
        == "TEST"
    )

    assert (
        worksheet
        .non_empty_rows[
            1
        ][1][2]
        == "2020-01-02T00:00:00"
    )

    assert (
        worksheet
        .non_empty_rows[
            1
        ][1][3]
        == "2024-10-03T00:00:00"
    )


def test_row_limit():
    result = (
        inspect_xlsx_bytes(
            make_workbook_bytes(),
            max_non_empty_rows=1,
        )
    )

    worksheet = (
        result.worksheets[
            0
        ]
    )

    assert (
        len(
            worksheet.non_empty_rows
        )
        == 1
    )


def test_content_must_be_bytes():
    with pytest.raises(
        TypeError
    ):
        inspect_xlsx_bytes(
            "not bytes"
        )


def test_invalid_signature():
    with pytest.raises(
        ValueError
    ):
        inspect_xlsx_bytes(
            b"not-an-xlsx"
        )


def test_invalid_row_limit():
    with pytest.raises(
        ValueError
    ):
        inspect_xlsx_bytes(
            make_workbook_bytes(),
            max_non_empty_rows=0,
        )