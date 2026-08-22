from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditLog

_BLOCKED_KEYS = ("token", "password", "secret", "api_key", "content", "text", "message")


def _safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        normalized = str(key).strip().lower()
        if not normalized or any(blocked in normalized for blocked in _BLOCKED_KEYS):
            continue
        if isinstance(value, str):
            safe[normalized[:64]] = value[:255]
        elif isinstance(value, bool | int | float) or value is None:
            safe[normalized[:64]] = value
        elif isinstance(value, list):
            safe[normalized[:64]] = [
                item[:255] if isinstance(item, str) else item
                for item in value[:50]
                if isinstance(item, str | bool | int | float) or item is None
            ]
    return safe


def write_audit_log(
    session: Session,
    *,
    owner_id: int,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int | str,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        owner_id=owner_id,
        actor=actor.strip().upper()[:64],
        action=action.strip().upper()[:128],
        entity_type=entity_type.strip().upper()[:64],
        entity_id=str(entity_id)[:128],
        metadata_json=_safe_metadata(metadata),
    )
    session.add(row)
    session.flush()
    return row
