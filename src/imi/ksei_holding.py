from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from io import StringIO
from pathlib import Path
from time import strptime
from typing import Any
from zipfile import ZipFile

KSEI_HOLDING_FORMAT_VERSION = (
    "ksei_holding_composition_v1"
)

EXPECTED_COLUMN_COUNT = 25

EXPECTED_HEADER = (
    "Date",
    "Code",
    "Type",
    "Sec. Num",
    "Price",
    "Local IS",
    "Local CP",
    "Local PF",
    "Local IB",
    "Local ID",
    "Local MF",
    "Local SC",
    "Local FD",
    "Local OT",
    "Total",
    "Foreign IS",
    "Foreign CP",
    "Foreign PF",
    "Foreign IB",
    "Foreign ID",
    "Foreign MF",
    "Foreign SC",
    "Foreign FD",
    "Foreign OT",
    "Total",
)

INVESTOR_CATEGORIES = (
    "IS",
    "CP",
    "PF",
    "IB",
    "ID",
    "MF",
    "SC",
    "FD",
    "OT",
)

ARCHIVE_FILENAME_PATTERN = re.compile(
    r"^BalanceposEfek(?P<date>\d{8})\.zip$",
    re.IGNORECASE,
)

MEMBER_FILENAME_PATTERN = re.compile(
    r"^Balancepos(?P<date>\d{8})\.txt$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class KseiHoldingRecord:
    as_of_date: date
    code: str
    security_type: str
    security_number: int
    price: float
    local: dict[str, int]
    local_total: int
    foreign: dict[str, int]
    foreign_total: int

    @property
    def scripless_total(self) -> int:
        return (
            self.local_total
            + self.foreign_total
        )

    @property
    def local_ownership_pct(self) -> float:
        if self.security_number <= 0:
            return 0.0

        return (
            self.local_total
            / self.security_number
            * 100.0
        )

    @property
    def foreign_ownership_pct(self) -> float:
        if self.security_number <= 0:
            return 0.0

        return (
            self.foreign_total
            / self.security_number
            * 100.0
        )

    @property
    def scripless_pct(self) -> float:
        if self.security_number <= 0:
            return 0.0

        return (
            self.scripless_total
            / self.security_number
            * 100.0
        )


def _parse_integer(
    value: str,
    *,
    field_name: str,
) -> int:
    cleaned = value.strip()

    if not cleaned:
        raise ValueError(
            f"{field_name} is empty."
        )

    try:
        return int(cleaned)

    except ValueError as exc:
        raise ValueError(
            f"Invalid integer for "
            f"{field_name}: {value!r}"
        ) from exc


def _parse_float(
    value: str,
    *,
    field_name: str,
) -> float:
    cleaned = value.strip()

    if not cleaned:
        raise ValueError(
            f"{field_name} is empty."
        )

    try:
        return float(cleaned)

    except ValueError as exc:
        raise ValueError(
            f"Invalid number for "
            f"{field_name}: {value!r}"
        ) from exc


def _parse_date(
    value: str,
) -> date:
    try:
        parsed = strptime(
            value.strip(),
            "%d-%b-%Y",
        )

        return date(
            parsed.tm_year,
            parsed.tm_mon,
            parsed.tm_mday,
        )

    except ValueError as exc:
        raise ValueError(
            f"Invalid KSEI date: "
            f"{value!r}"
        ) from exc


def _parse_compact_date(
    value: str,
) -> date:
    if (
        len(value) != 8
        or not value.isdigit()
    ):
        raise ValueError(
            f"Invalid compact date: "
            f"{value!r}"
        )

    try:
        return date(
            int(value[0:4]),
            int(value[4:6]),
            int(value[6:8]),
        )

    except ValueError as exc:
        raise ValueError(
            f"Invalid compact date: "
            f"{value!r}"
        ) from exc


def extract_archive_snapshot_date(
    archive_path: Path,
) -> date:
    match = (
        ARCHIVE_FILENAME_PATTERN.fullmatch(
            archive_path.name
        )
    )

    if match is None:
        raise ValueError(
            "Unexpected KSEI archive "
            "filename: "
            f"{archive_path.name}"
        )

    return _parse_compact_date(
        match.group("date")
    )


def extract_member_snapshot_date(
    member_name: str,
) -> date:
    filename = Path(
        member_name
    ).name

    match = (
        MEMBER_FILENAME_PATTERN.fullmatch(
            filename
        )
    )

    if match is None:
        raise ValueError(
            "Unexpected KSEI archive "
            "member filename: "
            f"{filename}"
        )

    return _parse_compact_date(
        match.group("date")
    )


def decode_ksei_text(
    raw: bytes,
) -> str:
    for encoding in (
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin-1",
    ):
        try:
            return raw.decode(
                encoding
            )

        except UnicodeDecodeError:
            continue

    raise RuntimeError(
        "Unable to decode KSEI file."
    )


def select_holding_member(
    archive: ZipFile,
) -> str:
    members = [
        name
        for name in archive.namelist()
        if not name.endswith("/")
    ]

    candidates = [
        name
        for name in members
        if (
            "balancepos"
            in name.lower()
            and name.lower().endswith(
                ".txt"
            )
        )
    ]

    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        raise RuntimeError(
            "No Balancepos TXT file "
            "found inside KSEI archive."
        )

    raise RuntimeError(
        "Multiple Balancepos TXT files "
        "found inside KSEI archive."
    )


def parse_ksei_row(
    row: list[str],
) -> KseiHoldingRecord:
    if len(row) != EXPECTED_COLUMN_COUNT:
        raise ValueError(
            "Unexpected KSEI column count: "
            f"{len(row)}"
        )

    local_values = {
        category: _parse_integer(
            row[5 + index],
            field_name=(
                f"Local {category}"
            ),
        )
        for index, category
        in enumerate(
            INVESTOR_CATEGORIES
        )
    }

    foreign_values = {
        category: _parse_integer(
            row[15 + index],
            field_name=(
                f"Foreign {category}"
            ),
        )
        for index, category
        in enumerate(
            INVESTOR_CATEGORIES
        )
    }

    return KseiHoldingRecord(
        as_of_date=_parse_date(
            row[0]
        ),
        code=row[1].strip().upper(),
        security_type=(
            row[2].strip().upper()
        ),
        security_number=_parse_integer(
            row[3],
            field_name="Sec. Num",
        ),
        price=_parse_float(
            row[4],
            field_name="Price",
        ),
        local=local_values,
        local_total=_parse_integer(
            row[14],
            field_name="Local Total",
        ),
        foreign=foreign_values,
        foreign_total=_parse_integer(
            row[24],
            field_name="Foreign Total",
        ),
    )


def validate_ksei_record(
    record: KseiHoldingRecord,
) -> list[str]:
    errors: list[str] = []

    if not record.code:
        errors.append(
            "Empty security code."
        )

    if record.security_number <= 0:
        errors.append(
            "Security number must be "
            "greater than zero."
        )

    if record.price < 0:
        errors.append(
            "Price cannot be negative."
        )

    for category, value in (
        record.local.items()
    ):
        if value < 0:
            errors.append(
                f"Local {category} "
                "cannot be negative."
            )

    for category, value in (
        record.foreign.items()
    ):
        if value < 0:
            errors.append(
                f"Foreign {category} "
                "cannot be negative."
            )

    if record.local_total < 0:
        errors.append(
            "Local total cannot "
            "be negative."
        )

    if record.foreign_total < 0:
        errors.append(
            "Foreign total cannot "
            "be negative."
        )

    calculated_local = sum(
        record.local.values()
    )

    if (
        calculated_local
        != record.local_total
    ):
        errors.append(
            "Local category sum does "
            "not match Local Total: "
            f"sum={calculated_local}, "
            f"total={record.local_total}."
        )

    calculated_foreign = sum(
        record.foreign.values()
    )

    if (
        calculated_foreign
        != record.foreign_total
    ):
        errors.append(
            "Foreign category sum does "
            "not match Foreign Total: "
            f"sum={calculated_foreign}, "
            f"total={record.foreign_total}."
        )

    if (
        record.scripless_total
        > record.security_number
    ):
        errors.append(
            "Local + foreign holdings "
            "exceed total securities: "
            f"scripless="
            f"{record.scripless_total}, "
            f"securities="
            f"{record.security_number}."
        )

    for label, percentage in (
        (
            "local_ownership_pct",
            record.local_ownership_pct,
        ),
        (
            "foreign_ownership_pct",
            record.foreign_ownership_pct,
        ),
        (
            "scripless_pct",
            record.scripless_pct,
        ),
    ):
        if not (
            0.0
            <= percentage
            <= 100.0001
        ):
            errors.append(
                f"{label} outside "
                f"0-100: {percentage}"
            )

    return errors


def parse_ksei_holding_archive(
    archive_path: Path,
    *,
    equity_only: bool = True,
) -> tuple[
    list[KseiHoldingRecord],
    list[dict[str, Any]],
    str,
]:
    archive_path = (
        archive_path.resolve()
    )

    if not archive_path.exists():
        raise FileNotFoundError(
            archive_path
        )

    with ZipFile(
        archive_path,
        "r",
    ) as archive:
        member_name = (
            select_holding_member(
                archive
            )
        )

        raw = archive.read(
            member_name
        )

    text = decode_ksei_text(
        raw
    )

    reader = csv.reader(
        StringIO(text),
        delimiter="|",
    )

    try:
        header = next(reader)

    except StopIteration as exc:
        raise RuntimeError(
            "KSEI file is empty."
        ) from exc

    if len(header) != EXPECTED_COLUMN_COUNT:
        raise RuntimeError(
            "Unexpected KSEI header "
            f"column count: {len(header)}"
        )

    normalized_header = tuple(
        value.strip()
        for value in header
    )

    if normalized_header != EXPECTED_HEADER:
        raise RuntimeError(
            "Unexpected KSEI header layout. "
            "The archive format may have "
            "changed."
        )

    records: list[
        KseiHoldingRecord
    ] = []

    rejected: list[
        dict[str, Any]
    ] = []

    expected_date: date | None = None

    for line_number, row in enumerate(
        reader,
        start=2,
    ):
        if not row:
            continue

        # Non-equity securities can contain
        # empty fields that are valid for
        # their own security type.
        #
        # Skip them before parsing equity
        # numeric fields.
        if (
            equity_only
            and len(row) >= 3
            and row[2].strip().upper()
            != "EQUITY"
        ):
            continue

        try:
            record = parse_ksei_row(
                row
            )

        except ValueError as exc:
            rejected.append(
                {
                    "line_number":
                        line_number,
                    "code":
                        (
                            row[1]
                            if len(row) > 1
                            else None
                        ),
                    "security_type":
                        (
                            row[2]
                            if len(row) > 2
                            else None
                        ),
                    "errors": [
                        str(exc)
                    ],
                }
            )

            continue

        if (
            equity_only
            and record.security_type
            != "EQUITY"
        ):
            continue

        if expected_date is None:
            expected_date = (
                record.as_of_date
            )

        if (
            record.as_of_date
            != expected_date
        ):
            rejected.append(
                {
                    "line_number":
                        line_number,
                    "code":
                        record.code,
                    "security_type":
                        record.security_type,
                    "errors": [
                        (
                            "Mixed snapshot "
                            "dates in archive."
                        )
                    ],
                }
            )

            continue

        errors = validate_ksei_record(
            record
        )

        if errors:
            rejected.append(
                {
                    "line_number":
                        line_number,
                    "code":
                        record.code,
                    "security_type":
                        record.security_type,
                    "errors":
                        errors,
                }
            )

            continue

        records.append(
            record
        )

    return (
        records,
        rejected,
        member_name,
    )


def validate_archive_identity(
    *,
    archive_path: Path,
    member_name: str,
    records: list[KseiHoldingRecord],
) -> date:
    archive_date = (
        extract_archive_snapshot_date(
            archive_path
        )
    )

    member_date = (
        extract_member_snapshot_date(
            member_name
        )
    )

    if not records:
        raise RuntimeError(
            f"{archive_path.name}: "
            "archive contains no valid "
            "EQUITY records."
        )

    record_dates = {
        record.as_of_date
        for record in records
    }

    if len(record_dates) != 1:
        raise RuntimeError(
            f"{archive_path.name}: "
            "archive contains multiple "
            f"snapshot dates: "
            f"{sorted(record_dates)}"
        )

    record_date = next(
        iter(record_dates)
    )

    if archive_date != member_date:
        raise RuntimeError(
            f"{archive_path.name}: "
            "archive filename date does "
            "not match member filename: "
            f"archive={archive_date}, "
            f"member={member_date}"
        )

    if archive_date != record_date:
        raise RuntimeError(
            f"{archive_path.name}: "
            "filename date does not match "
            "record date: "
            f"filename={archive_date}, "
            f"records={record_date}"
        )

    return record_date


def build_holder_details(
    record: KseiHoldingRecord,
    *,
    archive_name: str,
    member_name: str,
) -> dict[str, Any]:
    return {
        "format_version":
            KSEI_HOLDING_FORMAT_VERSION,
        "archive_name":
            archive_name,
        "member_name":
            member_name,
        "as_of_date":
            record.as_of_date.isoformat(),
        "security_type":
            record.security_type,
        "security_number":
            record.security_number,
        "price":
            record.price,
        "local": {
            **record.local,
            "total":
                record.local_total,
        },
        "foreign": {
            **record.foreign,
            "total":
                record.foreign_total,
        },
        "local_ownership_pct":
            round(
                record.local_ownership_pct,
                8,
            ),
        "foreign_ownership_pct":
            round(
                record.foreign_ownership_pct,
                8,
            ),
        "scripless_total":
            record.scripless_total,
        "scripless_pct":
            round(
                record.scripless_pct,
                8,
            ),
    }