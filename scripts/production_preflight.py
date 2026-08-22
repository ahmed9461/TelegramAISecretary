from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass

import httpx

from app.config import get_settings
from app.observability.health import readiness_snapshot
from scripts.backup_postgres import PROJECT_ROOT, _dotenv_values


@dataclass(frozen=True)
class Check:
    ok: bool
    detail: str


def _request_check(url: str, *, headers: dict[str, str]) -> Check:
    try:
        response = httpx.get(url, headers=headers, timeout=15.0)
        response.raise_for_status()
        return Check(True, f"HTTP {response.status_code}")
    except httpx.HTTPStatusError as exc:
        return Check(False, f"HTTP {exc.response.status_code}")
    except httpx.HTTPError as exc:
        return Check(False, type(exc).__name__)


def _configured_postgres_password() -> str:
    values = {**_dotenv_values(PROJECT_ROOT / ".env"), **os.environ}
    return values.get("POSTGRES_PASSWORD", "")


def run_preflight(*, live: bool, allow_development: bool) -> dict[str, Check]:
    settings = get_settings()
    postgres_password = _configured_postgres_password()
    snapshot = readiness_snapshot(settings)
    checks = {
        "environment": Check(
            allow_development or settings.app_env.lower() == "production",
            settings.app_env,
        ),
        "loopback_binding": Check(
            settings.app_host in {"127.0.0.1", "localhost", "::1"},
            settings.app_host,
        ),
        "database_revision": Check(
            snapshot.checks["database"],
            f"current={snapshot.database_revision} expected={snapshot.expected_revision}",
        ),
        "telegram_configuration": Check(settings.telegram_configured, "configured"),
        "text_ai_configuration": Check(settings.text_ai_configured, settings.ai_provider),
        "metrics_authentication": Check(
            len(settings.metrics_token) >= 32,
            "configured" if settings.metrics_token else "missing",
        ),
        "structured_logging": Check(settings.log_format.lower() == "json", settings.log_format),
        "postgres_password": Check(
            bool(postgres_password and postgres_password != "change-me"),
            "configured" if postgres_password else "missing",
        ),
    }
    if live and settings.telegram_configured:
        checks["telegram_api"] = _request_check(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe",
            headers={},
        )
    if live and settings.text_ai_configured:
        checks["deepseek_api"] = _request_check(
            f"{settings.deepseek_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
        )
    if live and settings.vision_provider == "gemini" and settings.gemini_api_key:
        checks["gemini_api"] = _request_check(
            (f"{settings.gemini_base_url.rstrip('/')}/v1beta/models/{settings.gemini_model}"),
            headers={"x-goog-api-key": settings.gemini_api_key},
        )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify production configuration and providers")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--allow-development", action="store_true")
    args = parser.parse_args()
    checks = run_preflight(live=args.live, allow_development=args.allow_development)
    print(
        json.dumps(
            {name: asdict(result) for name, result in checks.items()},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(result.ok for result in checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
