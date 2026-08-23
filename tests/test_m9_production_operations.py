from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as main_module
from app.audit.service import write_audit_log
from app.config import Settings
from app.db.base import Base
from app.db.models import Approval, AuditLog, Contact, Conversation, Message, Owner
from app.observability.health import ReadinessSnapshot, readiness_snapshot
from app.observability.logging import JsonLogFormatter
from app.observability.metrics import collect_metrics, record_ai_run, render_prometheus
from scripts.backup_postgres import prune_backups
from scripts.rotate_internal_secrets import render_updated_env


def make_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def seed_conversation(session: Session) -> tuple[Owner, Conversation, Message]:
    owner = Owner(telegram_user_id=9001)
    session.add(owner)
    session.flush()
    contact = Contact(owner_id=owner.id, telegram_user_id=9002, display_name="Test")
    session.add(contact)
    session.flush()
    conversation = Conversation(
        owner_id=owner.id,
        contact_id=contact.id,
        telegram_chat_id=9002,
        business_connection_id="test",
    )
    session.add(conversation)
    session.flush()
    message = Message(
        conversation_id=conversation.id,
        telegram_message_id=1,
        direction="IN",
        text="hello",
    )
    session.add(message)
    session.flush()
    return owner, conversation, message


def test_ai_run_metrics_are_aggregated_without_message_content() -> None:
    factory = make_factory()
    with factory() as session:
        owner, conversation, message = seed_conversation(session)
        approval = Approval(
            conversation_id=conversation.id,
            trigger_message_id=message.id,
            conversation_revision=conversation.revision,
            candidate_response="candidate",
            status="SENT",
        )
        session.add_all(
            [
                approval,
                *[
                    Approval(
                        conversation_id=conversation.id,
                        trigger_message_id=message.id,
                        conversation_revision=conversation.revision,
                        candidate_response="candidate",
                        status=status,
                    )
                    for status in ("PENDING", "REJECTED", "UNCERTAIN", "FAILED")
                ],
            ]
        )
        record_ai_run(
            session,
            owner_id=owner.id,
            conversation_id=conversation.id,
            trigger_message_id=message.id,
            trace_id="trace-1",
            operation="TEXT_RESPONSE",
            provider="test",
            model="test-model",
            status="SUCCESS",
            latency_ms=250,
            token_usage={"total_tokens": 42},
            knowledge_refs=[7],
        )
        for trace_id, status in (("trace-2", "ERROR"), ("trace-3", "DISCARDED")):
            record_ai_run(
                session,
                owner_id=owner.id,
                conversation_id=conversation.id,
                trigger_message_id=message.id,
                trace_id=trace_id,
                operation="TEXT_RESPONSE",
                provider="test",
                model="test-model",
                status=status,
            )
        session.commit()

        snapshot = collect_metrics(session, window_days=30)
        rendered = render_prometheus(snapshot)

        assert snapshot.ai_runs_total == 3
        assert snapshot.ai_runs_error == 1
        assert snapshot.ai_runs_discarded == 1
        assert snapshot.ai_tokens_total == 42
        assert snapshot.retrieval_hit_runs == 1
        assert snapshot.approvals_sent == 1
        assert snapshot.approvals_pending == 1
        assert snapshot.approvals_rejected == 1
        assert snapshot.approvals_uncertain == 1
        assert snapshot.approvals_failed == 1
        assert "hello" not in rendered
        assert "secretary_ai_latency_ms_average 250.0" in rendered


def test_readiness_requires_database_at_source_head() -> None:
    factory = make_factory()
    with factory() as session:
        session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        session.execute(text("INSERT INTO alembic_version VALUES ('0009')"))
        session.commit()
    settings = Settings(
        _env_file=None,
        readiness_require_telegram=False,
        readiness_require_ai=False,
    )

    snapshot = readiness_snapshot(settings, session_factory=factory)

    assert snapshot.ready is True
    assert snapshot.database_revision == "0009"
    assert snapshot.expected_revision == "0009"


def test_production_readiness_requires_metrics_authentication() -> None:
    factory = make_factory()
    with factory() as session:
        session.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32))"))
        session.execute(text("INSERT INTO alembic_version VALUES ('0007')"))
        session.commit()
    settings = Settings(
        _env_file=None,
        app_env="production",
        metrics_token="",
        readiness_require_telegram=False,
        readiness_require_ai=False,
    )

    snapshot = readiness_snapshot(settings, session_factory=factory)

    assert snapshot.ready is False
    assert snapshot.checks["metrics_auth"] is False


def test_metrics_endpoint_requires_bearer_token(monkeypatch) -> None:
    factory = make_factory()
    with factory() as session:
        seed_conversation(session)
        session.commit()
    monkeypatch.setattr(main_module, "SessionLocal", factory)
    monkeypatch.setattr(
        main_module,
        "settings",
        Settings(_env_file=None, metrics_token="m" * 32, metrics_window_days=30),
    )
    client = TestClient(main_module.app)

    assert client.get("/metrics").status_code == 401
    response = client.get("/metrics", headers={"Authorization": f"Bearer {'m' * 32}"})
    assert response.status_code == 200
    assert "secretary_messages_total 1" in response.text


def test_ready_endpoint_returns_service_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "readiness_snapshot",
        lambda settings: ReadinessSnapshot(
            ready=False,
            checks={"database": False, "telegram": True, "text_ai": True},
            database_revision="0006",
            expected_revision="0007",
        ),
    )
    response = TestClient(main_module.app).get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] is False


def test_json_logging_redacts_credentials() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="token=abc123 Authorization: Bearer top-secret",
        args=(),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert "abc123" not in payload["message"]
    assert "top-secret" not in payload["message"]
    assert payload["message"].count("[REDACTED]") == 2


def test_audit_metadata_never_persists_content_or_secrets() -> None:
    factory = make_factory()
    with factory() as session:
        owner = Owner(telegram_user_id=9010)
        session.add(owner)
        session.flush()
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="owner_telegram",
            action="delete",
            entity_type="knowledge",
            entity_id=4,
            metadata={"content": "private", "api_key": "secret", "affected": 2},
        )
        session.commit()
        row = session.query(AuditLog).one()
        assert row.metadata_json == {"affected": 2}


def test_backup_pruning_is_scoped_to_named_backup_files(tmp_path: Path) -> None:
    old = datetime.now(UTC) - timedelta(days=40)
    backup = tmp_path / "secretary-20250101T000000Z-deadbeef.dump"
    manifest = backup.with_suffix(".json")
    unrelated = tmp_path / "keep.dump"
    for path in (backup, manifest, unrelated):
        path.write_bytes(b"test")
    timestamp = old.timestamp()
    os.utime(backup, (timestamp, timestamp))
    os.utime(manifest, (timestamp, timestamp))

    removed = prune_backups(tmp_path, retention_days=30)

    assert removed == 2
    assert unrelated.exists()


def test_secret_env_rewrite_replaces_values_without_duplicate_keys() -> None:
    rendered = render_updated_env(
        "APP_ENV=development\nDATABASE_URL=old\n",
        {"DATABASE_URL": "new", "METRICS_TOKEN": "generated"},
    )

    assert rendered.count("DATABASE_URL=") == 1
    assert "DATABASE_URL=new" in rendered
    assert "METRICS_TOKEN=generated" in rendered
