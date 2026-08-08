import argparse
import csv
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

CANDIDATE_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin-1",
)

CANDIDATE_DELIMITERS = (
    "|",
    ",",
    ";",
    "\t",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a KSEI holding "
            "composition ZIP archive."
        )
    )

    parser.add_argument(
        "archive",
        type=Path,
        help=(
            "Path to the downloaded "
            "KSEI ZIP archive."
        ),
    )

    return parser.parse_args()


def decode_content(
    raw: bytes,
) -> tuple[str, str]:
    for encoding in CANDIDATE_ENCODINGS:
        try:
            return (
                raw.decode(
                    encoding
                ),
                encoding,
            )

        except UnicodeDecodeError:
            continue

    raise RuntimeError(
        "Could not decode "
        "archive member."
    )


def detect_delimiter(
    text: str,
) -> str:
    sample = text[:10000]

    try:
        dialect = csv.Sniffer().sniff(
            sample,
            delimiters="|,;\t",
        )

        return dialect.delimiter

    except csv.Error:
        lines = text.splitlines()

        first_line = (
            lines[0]
            if lines
            else ""
        )

        counts = {
            delimiter:
                first_line.count(
                    delimiter
                )
            for delimiter
            in CANDIDATE_DELIMITERS
        }

        return max(
            counts,
            key=counts.get,
        )


def main() -> None:
    args = parse_args()

    archive_path = (
        args.archive.resolve()
    )

    if not archive_path.exists():
        raise FileNotFoundError(
            f"Archive not found: "
            f"{archive_path}"
        )

    if (
        archive_path.suffix.lower()
        != ".zip"
    ):
        raise ValueError(
            "Expected a .zip archive."
        )

    print(
        "KSEI Holding Archive Inspector"
    )
    print(
        "------------------------------"
    )
    print(
        f"Archive : "
        f"{archive_path.name}"
    )
    print()

    with ZipFile(
        archive_path,
        "r",
    ) as archive:
        members = archive.namelist()

        print(
            f"Members : "
            f"{len(members)}"
        )

        for index, member in enumerate(
            members,
            start=1,
        ):
            info = archive.getinfo(
                member
            )

            print(
                f"{index:>2}. "
                f"{member} "
                f"({info.file_size} bytes)"
            )

        candidates = [
            member
            for member in members
            if (
                "balancepos"
                in member.lower()
                and not member.endswith("/")
            )
        ]

        if not candidates:
            candidates = [
                member
                for member in members
                if not member.endswith("/")
            ]

        if not candidates:
            raise RuntimeError(
                "Archive contains no files."
            )

        member_name = candidates[0]

        print()
        print(
            f"Selected member : "
            f"{member_name}"
        )

        raw = archive.read(
            member_name
        )

    text, encoding = decode_content(
        raw
    )

    delimiter = detect_delimiter(
        text
    )

    print(
        f"Encoding        : "
        f"{encoding}"
    )
    print(
        f"Delimiter       : "
        f"{delimiter!r}"
    )

    lines = text.splitlines()

    print(
        f"Total lines     : "
        f"{len(lines)}"
    )

    print()
    print(
        "First raw lines:"
    )

    for index, line in enumerate(
        lines[:5],
        start=1,
    ):
        print(
            f"{index:>2}: "
            f"{line[:500]}"
        )

    reader = csv.reader(
        StringIO(text),
        delimiter=delimiter,
    )

    rows = []

    for index, row in enumerate(
        reader
    ):
        rows.append(
            row
        )

        if index >= 4:
            break

    print()
    print(
        "Parsed sample:"
    )

    for index, row in enumerate(
        rows,
        start=1,
    ):
        print(
            f"Row {index}: "
            f"{len(row)} columns"
        )

        for (
            column_index,
            value,
        ) in enumerate(
            row,
            start=1,
        ):
            print(
                f"  {column_index:>2}: "
                f"{value!r}"
            )

        print()

    if rows:
        print(
            "Detected first-row "
            f"column count: "
            f"{len(rows[0])}"
        )


if __name__ == "__main__":
    main()