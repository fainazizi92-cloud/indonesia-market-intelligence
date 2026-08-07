from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from imi.config import settings


def create_db_engine() -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


engine = create_db_engine()


def check_database_health() -> dict[str, object]:
    with engine.connect() as connection:
        database_name, database_user = connection.execute(
            text("SELECT current_database(), current_user")
        ).one()

        total_tables = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                """
            )
        ).scalar_one()

    return {
        "status": "ok",
        "database": database_name,
        "user": database_user,
        "total_tables": total_tables,
    }