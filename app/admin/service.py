from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.conversations.state_machine import transition
from app.db.enums import ConversationState
from app.db.models import Approval, Contact, Conversation, Message
from app.db.repositories import ApprovalRepository, utcnow
from app.flows.service import cancel_active_flow
from app.memory.privacy import redact_sensitive_summary_text


@dataclass(frozen=True, slots=True)
class ConversationRow:
    conversation: Conversation
    contact: Contact
    pending_count: int


@dataclass(frozen=True, slots=True)
class ContactRow:
    contact: Contact
    conversation: Conversation | None


def list_owner_conversations(
    session: Session,
    *,
    owner_id: int,
    offset: int = 0,
    limit: int = 10,
) -> tuple[list[ConversationRow], int]:
    total = int(
        session.scalar(
            select(func.count()).select_from(Conversation).where(Conversation.owner_id == owner_id)
        )
        or 0
    )
    pairs = list(
        session.execute(
            select(Conversation, Contact)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(Conversation.owner_id == owner_id)
            .order_by(
                Conversation.last_message_at.desc().nullslast(),
                Conversation.id.desc(),
            )
            .offset(max(0, offset))
            .limit(max(1, min(limit, 20)))
        )
    )
    rows: list[ConversationRow] = []
    for conversation, contact in pairs:
        pending = int(
            session.scalar(
                select(func.count())
                .select_from(Approval)
                .where(
                    Approval.conversation_id == conversation.id,
                    Approval.status == "PENDING",
                    Approval.expires_at > utcnow(),
                )
            )
            or 0
        )
        rows.append(ConversationRow(conversation, contact, pending))
    return rows, total


def get_owned_conversation(
    session: Session, *, owner_id: int, conversation_id: int
) -> tuple[Conversation, Contact] | None:
    row = session.execute(
        select(Conversation, Contact)
        .join(Contact, Contact.id == Conversation.contact_id)
        .where(Conversation.id == conversation_id, Conversation.owner_id == owner_id)
    ).first()
    return (row[0], row[1]) if row is not None else None


def list_owner_contacts(
    session: Session,
    *,
    owner_id: int,
    offset: int = 0,
    limit: int = 10,
) -> tuple[list[ContactRow], int]:
    total = int(
        session.scalar(
            select(func.count()).select_from(Contact).where(Contact.owner_id == owner_id)
        )
        or 0
    )
    contacts = list(
        session.scalars(
            select(Contact)
            .where(Contact.owner_id == owner_id)
            .order_by(Contact.updated_at.desc(), Contact.id.desc())
            .offset(max(0, offset))
            .limit(max(1, min(limit, 20)))
        )
    )
    rows: list[ContactRow] = []
    for contact in contacts:
        conversation = session.scalar(
            select(Conversation)
            .where(Conversation.owner_id == owner_id, Conversation.contact_id == contact.id)
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
            .limit(1)
        )
        rows.append(ContactRow(contact, conversation))
    return rows, total


def get_owned_contact(session: Session, *, owner_id: int, contact_id: int) -> Contact | None:
    return session.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.owner_id == owner_id)
    )


def refresh_conversation_summary(
    session: Session, *, conversation: Conversation, limit: int = 8
) -> str:
    messages = list(
        session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.is_deleted.is_(False),
                Message.text.is_not(None),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(max(1, min(limit, 20)))
        )
    )
    lines: list[str] = []
    for row in reversed(messages):
        text = redact_sensitive_summary_text(" ".join((row.text or "").split()))
        if not text:
            continue
        role = "العميل" if row.direction == "IN" else "المالك/السكرتير"
        lines.append(f"{role}: {text[:240]}")
    conversation.summary = "\n".join(lines)[-1800:]
    session.flush()
    return conversation.summary


def set_conversation_state(
    session: Session,
    *,
    owner_id: int,
    conversation_id: int,
    target: ConversationState,
) -> Conversation | None:
    pair = get_owned_conversation(
        session, owner_id=owner_id, conversation_id=conversation_id
    )
    if pair is None:
        return None
    conversation, contact = pair
    current = ConversationState(conversation.state)
    explicit_unexclude = current == ConversationState.EXCLUDED
    new_state = transition(current, target, explicit_unexclude=explicit_unexclude)
    if new_state == current:
        return conversation

    if new_state in {
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.PAUSED,
        ConversationState.EXCLUDED,
        ConversationState.OBSERVE_ONLY,
    }:
        ApprovalRepository.invalidate_pending(session, conversation.id, status="STALE")
        cancel_active_flow(session, conversation_id=conversation.id)
    if new_state in {ConversationState.AI_APPROVAL, ConversationState.AI_AUTO}:
        refresh_conversation_summary(session, conversation=conversation)

    contact.is_excluded = new_state == ConversationState.EXCLUDED
    if new_state == ConversationState.EXCLUDED:
        contact.ai_allowed = False
    elif explicit_unexclude:
        contact.ai_allowed = True
    conversation.state = new_state.value
    conversation.revision += 1
    write_audit_log(
        session,
        owner_id=owner_id,
        actor="OWNER_TELEGRAM",
        action="CONVERSATION_STATE_CHANGED",
        entity_type="CONVERSATION",
        entity_id=conversation.id,
        metadata={"from_state": current.value, "to_state": new_state.value},
    )
    session.flush()
    return conversation


def set_contact_permission(
    session: Session,
    *,
    owner_id: int,
    contact_id: int,
    permission: str,
    enabled: bool,
) -> Contact | None:
    contact = get_owned_contact(session, owner_id=owner_id, contact_id=contact_id)
    if contact is None:
        return None
    if permission == "AI":
        contact.ai_allowed = enabled
    elif permission == "MEMORY":
        contact.memory_allowed = enabled
    else:
        raise ValueError("unsupported contact permission")
    write_audit_log(
        session,
        owner_id=owner_id,
        actor="OWNER_TELEGRAM",
        action="CONTACT_PERMISSION_CHANGED",
        entity_type="CONTACT",
        entity_id=contact.id,
        metadata={"permission": permission, "enabled": enabled},
    )
    session.flush()
    return contact


def list_pending_approvals(
    session: Session, *, owner_id: int, limit: int = 20
) -> list[tuple[Approval, Conversation, Contact]]:
    return list(
        session.execute(
            select(Approval, Conversation, Contact)
            .join(Conversation, Conversation.id == Approval.conversation_id)
            .join(Contact, Contact.id == Conversation.contact_id)
            .where(
                Conversation.owner_id == owner_id,
                Approval.status == "PENDING",
                Approval.expires_at > utcnow(),
            )
            .order_by(Approval.created_at.desc(), Approval.id.desc())
            .limit(max(1, min(limit, 50)))
        )
    )
