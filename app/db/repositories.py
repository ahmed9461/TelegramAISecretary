from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.enums import ConversationState, GlobalMode
from app.db.models import Approval, BusinessConnection, Contact, Conversation, Message, Owner


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class IngestResult:
    owner: Owner
    contact: Contact
    conversation: Conversation
    message: Message
    duplicate: bool


class OwnerRepository:
    @staticmethod
    def get_or_create(session: Session, telegram_user_id: int, *, display_name: str = "Owner") -> Owner:
        owner = session.scalar(select(Owner).where(Owner.telegram_user_id == telegram_user_id))
        if owner:
            if display_name and display_name != "Owner":
                owner.display_name = display_name
            return owner
        owner = Owner(
            telegram_user_id=telegram_user_id,
            display_name=display_name,
            default_mode=GlobalMode.APPROVAL.value,
        )
        session.add(owner)
        session.flush()
        return owner


class BusinessConnectionRepository:
    @staticmethod
    def get(session: Session, telegram_connection_id: str) -> BusinessConnection | None:
        return session.scalar(
            select(BusinessConnection).where(
                BusinessConnection.telegram_connection_id == telegram_connection_id
            )
        )

    @staticmethod
    def upsert(
        session: Session,
        *,
        owner_id: int,
        telegram_connection_id: str,
        telegram_user_chat_id: int,
        is_enabled: bool,
        rights_json: dict,
    ) -> BusinessConnection:
        row = BusinessConnectionRepository.get(session, telegram_connection_id)
        if row is None:
            row = BusinessConnection(
                owner_id=owner_id,
                telegram_connection_id=telegram_connection_id,
                telegram_user_chat_id=telegram_user_chat_id,
            )
            session.add(row)
        row.owner_id = owner_id
        row.telegram_user_chat_id = telegram_user_chat_id
        row.is_enabled = is_enabled
        row.rights_json = rights_json
        row.last_seen_at = utcnow()
        session.flush()
        return row


class ConversationRepository:
    @staticmethod
    def get_by_id(session: Session, conversation_id: int) -> Conversation | None:
        return session.get(Conversation, conversation_id)

    @staticmethod
    def get_by_chat(session: Session, *, owner_id: int, chat_id: int) -> Conversation | None:
        return session.scalar(
            select(Conversation).where(
                Conversation.owner_id == owner_id,
                Conversation.telegram_chat_id == chat_id,
            )
        )

    @staticmethod
    def ingest_business_message(
        session: Session,
        *,
        owner: Owner,
        business_connection_id: str,
        chat_id: int,
        telegram_message_id: int,
        sender_user_id: int,
        sender_name: str,
        username: str | None,
        text: str | None,
        content_type: str,
        reply_to_message_id: int | None = None,
    ) -> IngestResult:
        contact = session.scalar(
            select(Contact).where(
                Contact.owner_id == owner.id,
                Contact.telegram_user_id == sender_user_id,
            )
        )
        if contact is None:
            contact = Contact(
                owner_id=owner.id,
                telegram_user_id=sender_user_id,
                display_name=sender_name,
                username=username,
            )
            session.add(contact)
            session.flush()
        else:
            contact.display_name = sender_name or contact.display_name
            contact.username = username

        conversation = ConversationRepository.get_by_chat(session, owner_id=owner.id, chat_id=chat_id)
        if conversation is None:
            default_state = (
                ConversationState.AI_AUTO.value
                if owner.default_mode == GlobalMode.AUTO.value
                else ConversationState.AI_APPROVAL.value
            )
            conversation = Conversation(
                owner_id=owner.id,
                contact_id=contact.id,
                telegram_chat_id=chat_id,
                business_connection_id=business_connection_id,
                state=default_state,
                revision=1,
            )
            session.add(conversation)
            session.flush()
        else:
            conversation.business_connection_id = business_connection_id

        existing = session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.telegram_message_id == telegram_message_id,
            )
        )
        if existing:
            return IngestResult(owner, contact, conversation, existing, True)

        message = Message(
            conversation_id=conversation.id,
            telegram_message_id=telegram_message_id,
            direction="IN",
            sender_type="CONTACT",
            content_type=content_type,
            text=text,
            reply_to_message_id=reply_to_message_id,
        )
        session.add(message)
        now = utcnow()
        conversation.last_message_at = now
        conversation.last_incoming_at = now
        conversation.revision += 1
        session.flush()
        return IngestResult(owner, contact, conversation, message, False)

    @staticmethod
    def mark_edited(
        session: Session,
        *,
        owner_id: int,
        chat_id: int,
        telegram_message_id: int,
        new_text: str | None,
    ) -> Conversation | None:
        conversation = ConversationRepository.get_by_chat(session, owner_id=owner_id, chat_id=chat_id)
        if conversation is None:
            return None
        row = session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.telegram_message_id == telegram_message_id,
            )
        )
        if row is None:
            return conversation
        row.text = new_text
        row.is_edited = True
        row.edited_at = utcnow()
        conversation.revision += 1
        conversation.last_message_at = utcnow()
        ApprovalRepository.invalidate_pending(session, conversation.id, status="STALE")
        session.flush()
        return conversation

    @staticmethod
    def mark_deleted(
        session: Session,
        *,
        owner_id: int,
        chat_id: int,
        telegram_message_ids: list[int],
    ) -> Conversation | None:
        conversation = ConversationRepository.get_by_chat(session, owner_id=owner_id, chat_id=chat_id)
        if conversation is None:
            return None
        rows = list(
            session.scalars(
                select(Message).where(
                    Message.conversation_id == conversation.id,
                    Message.telegram_message_id.in_(telegram_message_ids),
                )
            )
        )
        if not rows:
            return conversation
        now = utcnow()
        for row in rows:
            row.is_deleted = True
            row.deleted_at = now
        conversation.revision += 1
        conversation.last_message_at = now
        ApprovalRepository.invalidate_pending(session, conversation.id, status="STALE")
        session.flush()
        return conversation

    @staticmethod
    def append_outgoing(
        session: Session,
        *,
        conversation: Conversation,
        telegram_message_id: int,
        text: str,
    ) -> Message:
        existing = session.scalar(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.telegram_message_id == telegram_message_id,
            )
        )
        if existing:
            return existing
        row = Message(
            conversation_id=conversation.id,
            telegram_message_id=telegram_message_id,
            direction="OUT",
            sender_type="OWNER_VIA_BOT",
            content_type="TEXT",
            text=text,
        )
        session.add(row)
        conversation.revision += 1
        conversation.last_message_at = utcnow()
        session.flush()
        return row


class ApprovalRepository:
    @staticmethod
    def invalidate_pending(session: Session, conversation_id: int, *, status: str) -> int:
        result = session.execute(
            update(Approval)
            .where(Approval.conversation_id == conversation_id, Approval.status == "PENDING")
            .values(status=status, resolved_at=utcnow())
        )
        return int(result.rowcount or 0)

    @staticmethod
    def create(
        session: Session,
        *,
        conversation: Conversation,
        trigger_message_id: int | None,
        candidate_response: str,
        reason: str,
        ttl_hours: int = 24,
    ) -> Approval:
        ApprovalRepository.invalidate_pending(session, conversation.id, status="SUPERSEDED")
        approval = Approval(
            conversation_id=conversation.id,
            trigger_message_id=trigger_message_id,
            conversation_revision=conversation.revision,
            candidate_response=candidate_response,
            reason=reason,
            status="PENDING",
            expires_at=utcnow() + timedelta(hours=max(1, ttl_hours)),
        )
        session.add(approval)
        session.flush()
        return approval

    @staticmethod
    def attach_owner_message(
        session: Session,
        approval_id: int,
        *,
        owner_chat_id: int,
        owner_message_id: int,
    ) -> bool:
        result = session.execute(
            update(Approval)
            .where(Approval.id == approval_id)
            .values(owner_chat_id=owner_chat_id, owner_message_id=owner_message_id)
        )
        return result.rowcount == 1

    @staticmethod
    def claim_for_send(session: Session, approval_id: int) -> Approval | None:
        approval = session.get(Approval, approval_id)
        if approval is None:
            return None
        conversation = session.get(Conversation, approval.conversation_id)
        if conversation is None:
            return None
        if approval.status != "PENDING":
            return None
        now = utcnow()
        if approval.expires_at and approval.expires_at <= now:
            approval.status = "EXPIRED"
            approval.resolved_at = now
            session.flush()
            return None
        if approval.conversation_revision != conversation.revision:
            approval.status = "STALE"
            approval.resolved_at = now
            session.flush()
            return None

        result = session.execute(
            update(Approval)
            .where(Approval.id == approval_id, Approval.status == "PENDING")
            .values(status="SENDING")
        )
        if result.rowcount != 1:
            return None
        session.flush()
        return session.get(Approval, approval_id)

    @staticmethod
    def mark_sent(session: Session, approval_id: int, *, telegram_message_id: int | None = None) -> None:
        session.execute(
            update(Approval)
            .where(Approval.id == approval_id, Approval.status == "SENDING")
            .values(
                status="SENT",
                sent_telegram_message_id=telegram_message_id,
                resolved_at=utcnow(),
            )
        )

    @staticmethod
    def mark_uncertain(session: Session, approval_id: int) -> None:
        session.execute(
            update(Approval)
            .where(Approval.id == approval_id, Approval.status == "SENDING")
            .values(status="UNCERTAIN", resolved_at=utcnow())
        )

    @staticmethod
    def reject(session: Session, approval_id: int) -> bool:
        result = session.execute(
            update(Approval)
            .where(Approval.id == approval_id, Approval.status == "PENDING")
            .values(status="REJECTED", resolved_at=utcnow())
        )
        return result.rowcount == 1
