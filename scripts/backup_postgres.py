from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _database_identity() -> tuple[str, str]:
    values = {**_dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    return values.get("POSTGRES_USER", "secretary"), values.get("POSTGRES_DB", "secretary")


def _configured_retention_days() -> int:
    values = {**_dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    try:
        return max(1, min(int(values.get("BACKUP_RETENTION_DAYS", "30")), 3650))
    except ValueError as exc:
        raise RuntimeError("BACKUP_RETENTION_DAYS must be an integer") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_backup(output_dir: Path) -> tuple[Path, Path]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = output_dir / f"secretary-{timestamp}-{uuid4().hex[:8]}.dump"
    partial = output_dir / f".{target.name}.partial"
    user, database = _database_identity()
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "-U",
        user,
        "-d",
        database,
        "--format=custom",
        "--no-owner",
        "--no-privileges",
    ]
    try:
        with partial.open("wb") as output:
            subprocess.run(command, cwd=PROJECT_ROOT, stdout=output, check=True)
        if partial.stat().st_size < 100:
            raise RuntimeError("PostgreSQL backup is unexpectedly small")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise

    manifest = target.with_suffix(".json")
    manifest.write_text(
        json.dumps(
            {
                "created_at": datetime.now(UTC).isoformat(),
                "database": database,
                "format": "postgres-custom",
                "file": target.name,
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        output_dir.chmod(0o700)
        target.chmod(0o600)
        manifest.chmod(0o600)
    except OSError:
        pass
    return target, manifest


def prune_backups(output_dir: Path, retention_days: int) -> int:
    output_dir = output_dir.resolve()
    cutoff = datetime.now(UTC) - timedelta(days=max(1, retention_days))
    removed = 0
    for path in output_dir.glob("secretary-*.*"):
        if path.suffix not in {".dump", ".json"} or not path.is_file():
            continue
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if modified < cutoff:
            path.unlink()
            removed += 1
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a private PostgreSQL custom-format backup")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_ROOT / "backups")
    parser.add_argument("--retention-days", type=int)
    args = parser.parse_args()
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required for the repository backup workflow")
    backup, manifest = create_backup(args.output_dir)
    retention_days = (
        args.retention_days
        if args.retention_days is not None
        else _configured_retention_days()
    )
    removed = prune_backups(args.output_dir, retention_days)
    print(f"backup={backup} manifest={manifest} pruned={removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
