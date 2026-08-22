from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.session import SessionLocal


@dataclass(frozen=True)
class ReadinessSnapshot:
    ready: bool
    checks: dict[str, bool]
    database_revision: str
    expected_revision: str

    def as_dict(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "checks": self.checks,
            "database_revision": self.database_revision,
            "expected_revision": self.expected_revision,
        }


def _expected_revision() -> str:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head() or ""


def readiness_snapshot(
    settings: Settings,
    session_factory: Callable[[], Session] = SessionLocal,
) -> ReadinessSnapshot:
    expected_revision = _expected_revision()
    database_ok = False
    database_revision = ""
    try:
        with session_factory() as db:
            db.execute(text("SELECT 1"))
            database_revision = str(
                db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            )
            database_ok = database_revision == expected_revision
    except Exception:  # Readiness reports failure without leaking connection details.
        database_ok = False

    checks = {
        "database": database_ok,
        "telegram": (not settings.readiness_require_telegram) or settings.telegram_configured,
        "text_ai": (not settings.readiness_require_ai) or settings.text_ai_configured,
        "metrics_auth": settings.app_env.lower() != "production"
        or len(settings.metrics_token) >= 32,
    }
    return ReadinessSnapshot(
        ready=all(checks.values()),
        checks=checks,
        database_revision=database_revision,
        expected_revision=expected_revision,
    )
