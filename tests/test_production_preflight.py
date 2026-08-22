from __future__ import annotations

from scripts import production_preflight


def test_postgres_password_prefers_environment(monkeypatch) -> None:
    monkeypatch.setattr(
        production_preflight,
        "_dotenv_values",
        lambda _path: {"POSTGRES_PASSWORD": "from-file"},
    )
    monkeypatch.setenv("POSTGRES_PASSWORD", "from-environment")

    assert production_preflight._configured_postgres_password() == "from-environment"


def test_postgres_password_falls_back_to_dotenv(monkeypatch) -> None:
    monkeypatch.setattr(
        production_preflight,
        "_dotenv_values",
        lambda _path: {"POSTGRES_PASSWORD": "from-file"},
    )
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    assert production_preflight._configured_postgres_password() == "from-file"
