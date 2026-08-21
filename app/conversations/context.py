from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brain.service import build_brain_context
from app.db.enums import Visibility
from app.db.models import Conversation, Message
from app.knowledge.retrieval import KnowledgeHit, retrieve_knowledge
from app.security.untrusted import wrap_untrusted


@dataclass(frozen=True, slots=True)
class BuiltContext:
    payload: dict
    knowledge_hits: tuple[KnowledgeHit, ...]


def build_ai_context(
    session: Session,
    *,
    conversation_id: int,
    query: str,
    message_limit: int = 12,
    knowledge_top_k: int = 6,
) -> BuiltContext:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise ValueError("conversation not found")

    rows = list(
        session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.is_deleted.is_(False))
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(max(1, message_limit))
        )
    )
    rows.reverse()

    recent_messages = [
        {
            "role": "contact" if row.direction == "IN" else "owner",
            "content_type": row.content_type,
            "text": wrap_untrusted(row.text or ""),
            "edited": bool(row.is_edited),
        }
        for row in rows
        if row.text
    ]

    hits = retrieve_knowledge(
        session,
        owner_id=conversation.owner_id,
        query=query,
        limit=knowledge_top_k,
    )
    trusted_knowledge = [
        {
            "id": hit.id,
            "title": hit.title,
            "content": hit.content,
            "visibility": hit.visibility,
            "score": round(hit.score, 4),
        }
        for hit in hits
    ]
    confidence = hits[0].score if hits else 0.0
    has_public_grounding = any(hit.visibility == Visibility.PUBLIC.value for hit in hits)
    brain_context = build_brain_context(
        session,
        owner_id=conversation.owner_id,
        contact_id=conversation.contact_id,
    )

    return BuiltContext(
        payload={
            "state": conversation.state,
            "conversation_summary": conversation.summary,
            "recent_messages": recent_messages,
            "trusted_knowledge": trusted_knowledge,
            "has_grounding": bool(hits),
            "has_public_grounding": has_public_grounding,
            "retrieval_confidence": min(1.0, confidence),
            **brain_context,
        },
        knowledge_hits=tuple(hits),
    )
