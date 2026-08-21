from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import Visibility
from app.db.models import KnowledgeItem, Owner


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
    session.flush()
    return True
