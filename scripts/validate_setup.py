import sys
from pathlib import Path

REQUIRED = [
    "README.md",
    ".env.example",
    "pyproject.toml",
    "docs/ARCHITECTURE.md",
    "docs/SOURCE_MAP.md",
    "docs/DATA_DICTIONARY.csv",
    "db/schema.sql",
    "config/sources.example.yml",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [path for path in REQUIRED if not (root / path).exists()]
    if missing:
        print("Missing required Phase-1 files:")
        for item in missing:
            print(f" - {item}")
        return 1
    print("Phase-1 repository structure: OK")
    print(f"Project root: {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
