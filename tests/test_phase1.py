from pathlib import Path


def test_phase1_docs_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "docs" / "ARCHITECTURE.md").exists()
    assert (root / "docs" / "SOURCE_MAP.md").exists()
    assert (root / "docs" / "DATA_DICTIONARY.csv").exists()
    assert (root / "db" / "schema.sql").exists()
