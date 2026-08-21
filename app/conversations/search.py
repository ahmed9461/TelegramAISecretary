from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Contact, Conversation, Message


@dataclass(frozen=True, slots=True)
class SearchHit:
    message_id: int
    conversation_id: int
    chat_id: int
    contact_name: str
    direction: str
    text: str


def search_messages(
    session: Session,
    *,
    owner_id: int,
    query: str,
    limit: int = 20,
) -> list[SearchHit]:
    term = query.strip()
    if not term:
        return []
    pattern = f"%{term}%"
    rows = session.execute(
        select(Message, Conversation, Contact)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(
            Conversation.owner_id == owner_id,
            Message.is_deleted.is_(False),
            Message.text.is_not(None),
            or_(Message.text.ilike(pattern), Contact.display_name.ilike(pattern)),
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(max(1, limit))
    ).all()
    return [
        SearchHit(
            message_id=message.id,
            conversation_id=conversation.id,
            chat_id=conversation.telegram_chat_id,
            contact_name=contact.display_name,
            direction=message.direction,
            text=message.text or "",
        )
        for message, conversation, contact in rows
    ]
