from datetime import date

from imi.collectors.idx_company_profiles import (
    normalize_idx_company_profile,
)
from imi.universe.validator import (
    validate_instrument_profile,
)


def test_normalizes_idx_profile() -> None:
    row = {
        "KodeEmiten": "TEST",
        "NamaEmiten": "PT Test Indonesia Tbk",
        "TanggalPencatatan": "2025-01-08",
        "Sector": "Technology",
        "Industry": "Software",
    }

    profile = normalize_idx_company_profile(
        row
    )

    assert profile.symbol == "TEST"

    assert (
        profile.name
        == "PT Test Indonesia Tbk"
    )

    assert (
        profile.listed_date
        == date(2025, 1, 8)
    )

    assert (
        profile.sector_code
        == "IDXTECHNO"
    )

def test_normalizes_indonesian_idx_sector() -> None:
    row = {
        "KodeEmiten": "AADI",
        "NamaEmiten": (
            "PT Adaro Andalan Indonesia Tbk"
        ),
        "TanggalPencatatan": (
            "2024-12-05T00:00:00"
        ),
        "Sektor": "Energi",
        "SubSektor": (
            "Minyak, Gas & Batu Bara"
        ),
        "Industri": "Batu Bara",
        "SubIndustri": (
            "Produksi Batu Bara"
        ),
        "PapanPencatatan": "Utama",
    }

    profile = (
        normalize_idx_company_profile(
            row
        )
    )

    assert (
        profile.sector_code
        == "IDXENERGY"
    )

    assert (
        profile.metadata["sector_name"]
        == "Energi"
    )

    assert (
        profile.metadata["subsector_name"]
        == "Minyak, Gas & Batu Bara"
    )

    assert (
        profile.metadata["industry_name"]
        == "Batu Bara"
    )

    assert (
        profile.metadata["subindustry_name"]
        == "Produksi Batu Bara"
    )

    assert (
        profile.metadata["listing_board"]
        == "Utama"
    )


def test_valid_profile() -> None:
    profile = normalize_idx_company_profile(
        {
            "KodeEmiten": "ABCD",
            "NamaEmiten": "PT ABCD Tbk",
            "TanggalPencatatan": "2020-01-01",
        }
    )

    result = validate_instrument_profile(
        profile,
        snapshot_date=date(
            2026,
            8,
            8,
        ),
    )

    assert result.valid
    assert result.reasons == ()