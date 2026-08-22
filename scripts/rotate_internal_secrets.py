from __future__ import annotations

import argparse
import json
import os
import re
import secrets
from pathlib import Path

from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts.backup_postgres import PROJECT_ROOT, _dotenv_values

_SAFE_ROLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]{0,62}$")


def render_updated_env(content: str, updates: dict[str, str]) -> str:
    pending = dict(updates)
    rendered: list[str] = []
    for raw_line in content.splitlines():
        if "=" in raw_line and not raw_line.lstrip().startswith("#"):
            key = raw_line.split("=", 1)[0].strip()
            if key in pending:
                rendered.append(f"{key}={pending.pop(key)}")
                continue
        rendered.append(raw_line)
    if pending:
        if rendered and rendered[-1]:
            rendered.append("")
        rendered.extend(f"{key}={value}" for key, value in pending.items())
    return "\n".join(rendered) + "\n"


def _alter_role_password(database_url: str, role: str, password: str) -> None:
    if not _SAFE_ROLE_RE.fullmatch(role):
        raise RuntimeError("Unsafe PostgreSQL role name")
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            driver_connection = connection.connection.driver_connection
            try:
                with driver_connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                            sql.Identifier(role),
                            sql.Literal(password),
                        )
                    )
            except Exception:
                raise RuntimeError("PostgreSQL role rotation failed") from None
    finally:
        engine.dispose()


def rotate_internal_secrets(env_path: Path) -> dict[str, bool]:
    env_path = env_path.resolve()
    original = env_path.read_text(encoding="utf-8")
    values = _dotenv_values(env_path)
    raw_database_url = values.get("DATABASE_URL", "")
    url = make_url(raw_database_url)
    if url.get_backend_name() != "postgresql" or not url.username or not url.database:
        raise RuntimeError("DATABASE_URL must point to PostgreSQL")
    old_password = url.password
    if not old_password:
        raise RuntimeError("DATABASE_URL must include the current PostgreSQL password")

    database_password = secrets.token_urlsafe(48)
    metrics_token = secrets.token_urlsafe(48)
    rotated_url = url.set(password=database_password).render_as_string(hide_password=False)
    updated = render_updated_env(
        original,
        {
            "POSTGRES_DB": url.database,
            "POSTGRES_USER": url.username,
            "POSTGRES_PASSWORD": database_password,
            "DATABASE_URL": rotated_url,
            "METRICS_TOKEN": metrics_token,
        },
    )
    partial = env_path.with_name(f"{env_path.name}.rotate.partial")
    partial.write_text(updated, encoding="utf-8")
    try:
        partial.chmod(0o600)
    except OSError:
        pass

    _alter_role_password(raw_database_url, url.username, database_password)
    try:
        os.replace(partial, env_path)
    except Exception:
        _alter_role_password(rotated_url, url.username, old_password)
        partial.unlink(missing_ok=True)
        raise

    verification_engine = create_engine(rotated_url, pool_pre_ping=True)
    try:
        with verification_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        verification_engine.dispose()
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    return {"postgres_password_rotated": True, "metrics_token_rotated": True}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rotate local PostgreSQL and metrics secrets")
    parser.add_argument("--env-file", type=Path, default=PROJECT_ROOT / ".env")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"ready": True, "applied": False}))
        return 0
    print(json.dumps(rotate_internal_secrets(args.env_file)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
