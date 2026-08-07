OFFICIAL_DATA_SOURCES = [
    {
        "code": "IDX_OFFICIAL",
        "name": "Indonesia Stock Exchange",
        "source_type": "OFFICIAL_EXCHANGE",
        "authority_rank": 1,
        "base_url": "https://www.idx.id/",
        "license_notes": (
            "Official IDX source. Production market-data endpoints "
            "and licensing must be audited before automated use."
        ),
    },
    {
        "code": "BI_OFFICIAL",
        "name": "Bank Indonesia",
        "source_type": "OFFICIAL_CENTRAL_BANK",
        "authority_rank": 1,
        "base_url": "https://www.bi.go.id/",
        "license_notes": "Official Bank Indonesia public data.",
    },
    {
        "code": "BPS_WEBAPI",
        "name": "BPS - Statistics Indonesia",
        "source_type": "OFFICIAL_STATISTICS",
        "authority_rank": 1,
        "base_url": "https://www.bps.go.id/",
        "license_notes": "Official BPS data and WebAPI.",
    },
    {
        "code": "OJK_OFFICIAL",
        "name": "Otoritas Jasa Keuangan",
        "source_type": "OFFICIAL_REGULATOR",
        "authority_rank": 1,
        "base_url": "https://www.ojk.go.id/",
        "license_notes": "Official OJK regulatory and statistical data.",
    },
    {
        "code": "KSEI_OFFICIAL",
        "name": "Kustodian Sentral Efek Indonesia",
        "source_type": "OFFICIAL_DEPOSITORY",
        "authority_rank": 1,
        "base_url": "https://www.ksei.co.id/",
        "license_notes": (
            "Official KSEI ownership and investor reference data."
        ),
    },
]


DEVELOPMENT_DATA_SOURCES = [
    {
        "code": "YAHOO_FINANCE",
        "name": "Yahoo Finance",
        "source_type": "THIRD_PARTY_MARKET_DATA",
        "authority_rank": 3,
        "base_url": "https://query1.finance.yahoo.com/",
        "license_notes": (
            "Third-party development and cross-check source. "
            "Do not classify as official IDX data. Review provider "
            "terms before production use or redistribution."
        ),
    },
]


ALL_DATA_SOURCES = (
    OFFICIAL_DATA_SOURCES + DEVELOPMENT_DATA_SOURCES
)