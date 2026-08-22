from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.db.enums import Visibility
from app.db.models import KnowledgeBatch, KnowledgeItem, Owner

_VISIBILITY_ALIASES = {
    "public": Visibility.PUBLIC.value,
    "عام": Visibility.PUBLIC.value,
    "internal": Visibility.INTERNAL.value,
    "داخلي": Visibility.INTERNAL.value,
    "private": Visibility.PRIVATE.value,
    "خاص": Visibility.PRIVATE.value,
}


def normalize_visibility(value: str) -> str | None:
    return _VISIBILITY_ALIASES.get(value.strip().casefold())


def knowledge_content_hash(*, title: str, content: str) -> str:
    normalized = f"{title.strip().casefold()}\n{content.strip().casefold()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def add_knowledge(
    session: Session,
    *,
    owner: Owner,
    visibility: str,
    title: str,
    content: str,
    item_type: str = "GENERAL",
    tags: list[str] | None = None,
    source: str = "OWNER_TELEGRAM",
    batch_id: int | None = None,
    version: int = 1,
    supersedes_id: int | None = None,
    valid_from: datetime | None = None,
    valid_until: datetime | None = None,
) -> KnowledgeItem:
    normalized_type = (item_type or "GENERAL").strip().upper()[:64]
    row = KnowledgeItem(
        owner_id=owner.id,
        type=normalized_type,
        title=title.strip(),
        content=content.strip(),
        visibility=visibility,
        status="ACTIVE",
        tags_json=list(tags or []),
        source=source,
        batch_id=batch_id,
        version=max(1, version),
        supersedes_id=supersedes_id,
        content_hash=knowledge_content_hash(title=title, content=content),
        valid_from=valid_from,
        valid_until=valid_until,
    )
    session.add(row)
    session.flush()
    return row


def list_knowledge(session: Session, *, owner_id: int, limit: int = 10) -> list[KnowledgeItem]:
    return list(
        session.scalars(
            select(KnowledgeItem)
            .where(KnowledgeItem.owner_id == owner_id, KnowledgeItem.status == "ACTIVE")
            .order_by(KnowledgeItem.id.desc())
            .limit(limit)
        )
    )


def delete_knowledge(session: Session, *, owner_id: int, knowledge_id: int) -> bool:
    row = session.get(KnowledgeItem, knowledge_id)
    if row is None or row.owner_id != owner_id:
        return False
    row.status = "DELETED"
    write_audit_log(
        session,
        owner_id=owner_id,
        actor="OWNER_TELEGRAM",
        action="KNOWLEDGE_DELETE",
        entity_type="KNOWLEDGE_ITEM",
        entity_id=row.id,
        metadata={"visibility": row.visibility, "version": row.version},
    )
    session.flush()
    return True


def supersede_knowledge(
    session: Session,
    *,
    owner_id: int,
    knowledge_id: int,
    title: str | None = None,
    content: str | None = None,
) -> KnowledgeItem | None:
    current = session.get(KnowledgeItem, knowledge_id)
    if current is None or current.owner_id != owner_id or current.status != "ACTIVE":
        return None
    next_title = (title if title is not None else current.title).strip()
    next_content = (content if content is not None else current.content).strip()
    if not next_title or not next_content:
        return None
    current.status = "SUPERSEDED"
    replacement = KnowledgeItem(
        owner_id=current.owner_id,
        type=current.type,
        title=next_title[:255],
        content=next_content,
        visibility=current.visibility,
        status="ACTIVE",
        tags_json=list(current.tags_json or []),
        source=current.source,
        batch_id=current.batch_id,
        version=max(1, current.version or 1) + 1,
        supersedes_id=current.id,
        content_hash=knowledge_content_hash(title=next_title, content=next_content),
        valid_from=current.valid_from,
        valid_until=current.valid_until,
    )
    session.add(replacement)
    session.flush()
    return replacement


def list_knowledge_batches(
    session: Session,
    *,
    owner_id: int,
    limit: int = 12,
) -> list[KnowledgeBatch]:
    return list(
        session.scalars(
            select(KnowledgeBatch)
            .where(KnowledgeBatch.owner_id == owner_id)
            .order_by(KnowledgeBatch.id.desc())
            .limit(max(1, limit))
        )
    )


def rollback_knowledge_batch(session: Session, *, owner_id: int, batch_id: int) -> int:
    batch = session.get(KnowledgeBatch, batch_id)
    if batch is None or batch.owner_id != owner_id or batch.status != "ACTIVE":
        return 0
    rows = list(
        session.scalars(
            select(KnowledgeItem).where(
                KnowledgeItem.owner_id == owner_id,
                KnowledgeItem.batch_id == batch_id,
                KnowledgeItem.status == "ACTIVE",
            )
        )
    )
    for row in rows:
        row.status = "ROLLED_BACK"
    batch.status = "ROLLED_BACK"
    batch.rolled_back_at = datetime.now(UTC)
    write_audit_log(
        session,
        owner_id=owner_id,
        actor="OWNER_TELEGRAM",
        action="KNOWLEDGE_BATCH_ROLLBACK",
        entity_type="KNOWLEDGE_BATCH",
        entity_id=batch.id,
        metadata={"affected_items": len(rows)},
    )
    session.flush()
    return len(rows)
