from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brain.service import build_brain_context
from app.db.enums import ConversationState, GlobalMode, Visibility
from app.db.models import Conversation, Message, Owner
from app.knowledge.retrieval import KnowledgeHit, retrieve_knowledge
from app.security.untrusted import wrap_untrusted


@dataclass(frozen=True, slots=True)
class BuiltContext:
    payload: dict
    knowledge_hits: tuple[KnowledgeHit, ...]


def effective_state_for_global_mode(*, conversation_state: str, global_mode: str) -> str:
    """Apply the owner's global mode as a safety ceiling.

    Global APPROVAL can make an AI_AUTO conversation stricter, but AUTO never loosens an
    explicitly stricter per-conversation state. OBSERVE and OFF always suppress AI replies.
    """
    if global_mode == GlobalMode.OFF.value:
        return ConversationState.PAUSED.value
    if global_mode == GlobalMode.OBSERVE.value:
        return ConversationState.OBSERVE_ONLY.value
    if (
        global_mode == GlobalMode.APPROVAL.value
        and conversation_state == ConversationState.AI_AUTO.value
    ):
        return ConversationState.AI_APPROVAL.value
    return conversation_state


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
    owner = session.get(Owner, conversation.owner_id)
    global_mode = owner.default_mode if owner else GlobalMode.APPROVAL.value
    effective_state = effective_state_for_global_mode(
        conversation_state=conversation.state,
        global_mode=global_mode,
    )

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
            "state": effective_state,
            "conversation_state": conversation.state,
            "global_mode": global_mode,
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
