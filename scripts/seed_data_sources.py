from sqlalchemy import text

from imi.data_sources import ALL_DATA_SOURCES
from imi.db import engine

UPSERT_SOURCE = text(
    """
    INSERT INTO data_sources (
        code,
        name,
        source_type,
        authority_rank,
        base_url,
        license_notes,
        is_active
    )
    VALUES (
        :code,
        :name,
        :source_type,
        :authority_rank,
        :base_url,
        :license_notes,
        TRUE
    )
    ON CONFLICT (code)
    DO UPDATE SET
        name = EXCLUDED.name,
        source_type = EXCLUDED.source_type,
        authority_rank = EXCLUDED.authority_rank,
        base_url = EXCLUDED.base_url,
        license_notes = EXCLUDED.license_notes,
        is_active = TRUE
    """
)


def main() -> None:
    with engine.begin() as connection:
        for source in ALL_DATA_SOURCES:
            connection.execute(
                UPSERT_SOURCE,
                source,
            )

    print(
        f"Seeded {len(ALL_DATA_SOURCES)} data sources."
    )


if __name__ == "__main__":
    main()