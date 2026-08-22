"""Rehearse the complete Alembic ladder in an isolated temporary PostgreSQL database."""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from uuid import uuid4

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from alembic import command
from app.config import get_settings

_DATABASE_PREFIX = "secretary_migration_rehearsal_"


def main() -> None:
    source_url = make_url(get_settings().database_url)
    if source_url.get_backend_name() != "postgresql" or not source_url.database:
        raise RuntimeError("Migration rehearsal requires a configured PostgreSQL database")

    suffix = f"{datetime.now(UTC):%Y%m%d%H%M%S}_{uuid4().hex[:8]}"
    database_name = f"{_DATABASE_PREFIX}{suffix}"
    if not re.fullmatch(r"[a-z0-9_]+", database_name):
        raise RuntimeError("Unsafe temporary database name")

    maintenance_url = source_url.set(database="postgres")
    rehearsal_url = source_url.set(database=database_name)
    maintenance_engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    rehearsal_engine = None
    previous_database_url = os.environ.get("DATABASE_URL")
    created = False
    try:
        with maintenance_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        os.environ["DATABASE_URL"] = rehearsal_url.render_as_string(hide_password=False)
        get_settings.cache_clear()
        alembic_config = Config("alembic.ini")
        command.upgrade(alembic_config, "head")
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")

        rehearsal_engine = create_engine(rehearsal_url)
        with rehearsal_engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != "0006":
            raise RuntimeError(f"Unexpected final migration revision: {revision!r}")
        print(f"Migration rehearsal passed at revision {revision}.")
    finally:
        if rehearsal_engine is not None:
            rehearsal_engine.dispose()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()
        if created:
            with maintenance_engine.connect() as connection:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": database_name},
                )
                connection.execute(text(f'DROP DATABASE "{database_name}"'))
        maintenance_engine.dispose()


if __name__ == "__main__":
    main()
