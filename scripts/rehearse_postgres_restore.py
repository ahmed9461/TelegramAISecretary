from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory

from scripts.backup_postgres import PROJECT_ROOT, _database_identity, _sha256

_SAFE_DATABASE_RE = re.compile(r"^secretary_restore_[a-f0-9]{12}$")


def _compose(*args: str, input_file: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose", "exec", "-T", "postgres", *args]
    if input_file is None:
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
    with input_file.open("rb") as handle:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            check=True,
            stdin=handle,
            capture_output=True,
        )
    return subprocess.CompletedProcess(
        result.args,
        result.returncode,
        result.stdout.decode("utf-8", errors="replace"),
        result.stderr.decode("utf-8", errors="replace"),
    )


def _expected_revision() -> str:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head() or ""


def rehearse_restore(backup: Path) -> dict[str, object]:
    backup = backup.resolve()
    if not backup.is_file():
        raise FileNotFoundError(backup)
    database = f"secretary_restore_{uuid4().hex[:12]}"
    if not _SAFE_DATABASE_RE.fullmatch(database):
        raise RuntimeError("Unsafe restore database name")
    user, _ = _database_identity()
    created = False
    try:
        _compose(
            "psql",
            "-U",
            user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            f'CREATE DATABASE "{database}"',
        )
        created = True
        _compose(
            "pg_restore",
            "-U",
            user,
            "-d",
            database,
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            input_file=backup,
        )
        query = (
            "SELECT version_num FROM alembic_version;"
            "SELECT 'owners=' || count(*) FROM owners;"
            "SELECT 'conversations=' || count(*) FROM conversations;"
            "SELECT 'messages=' || count(*) FROM messages;"
        )
        result = _compose("psql", "-U", user, "-d", database, "-At", "-c", query)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        revision = lines[0] if lines else ""
        expected = _expected_revision()
        if revision != expected:
            raise RuntimeError(f"Restored revision {revision!r} does not match {expected!r}")
        return {
            "restored": True,
            "database": database,
            "revision": revision,
            "checksum": _sha256(backup),
            "counts": lines[1:],
        }
    finally:
        if created:
            _compose(
                "psql",
                "-U",
                user,
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)',
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a backup into an isolated database")
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    print(json.dumps(rehearse_restore(args.backup), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
