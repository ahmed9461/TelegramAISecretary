from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.repositories import ConversationRepository, IngestResult, OwnerRepository
from app.telegram.contracts import IncomingBusinessMessage


def ingest_message(
    session: Session,
    *,
    owner_telegram_id: int,
    incoming: IncomingBusinessMessage,
    username: str | None = None,
) -> IngestResult:
    if incoming.sender_user_id is None:
        raise ValueError(
            "business message sender_user_id is required for private contact ingestion"
        )

    owner = OwnerRepository.get_or_create(session, owner_telegram_id)
    result = ConversationRepository.ingest_business_message(
        session,
        owner=owner,
        business_connection_id=incoming.business_connection_id,
        chat_id=incoming.chat_id,
        telegram_message_id=incoming.message_id,
        sender_user_id=incoming.sender_user_id,
        sender_name=incoming.sender_name,
        username=username,
        text=incoming.text,
        content_type=incoming.content_type,
        reply_to_message_id=incoming.reply_to_message_id,
    )
    session.commit()
    return result
