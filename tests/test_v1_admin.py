from __future__ import annotations

from datetime import timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.admin.service import (
    get_owned_conversation,
    list_owner_contacts,
    list_owner_conversations,
    list_pending_approvals,
    refresh_conversation_summary,
    set_contact_permission,
    set_conversation_state,
)
from app.db.base import Base
from app.db.enums import ConversationState
from app.db.models import Approval, AuditLog, Contact, Conversation, Message, Owner
from app.db.repositories import utcnow


def _database() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _conversation(session: Session) -> tuple[Owner, Contact, Conversation]:
    owner = Owner(telegram_user_id=100, display_name="المالك")
    session.add(owner)
    session.flush()
    contact = Contact(
        owner_id=owner.id,
        telegram_user_id=200,
        display_name="عميل الاختبار",
    )
    session.add(contact)
    session.flush()
    conversation = Conversation(
        owner_id=owner.id,
        contact_id=contact.id,
        telegram_chat_id=200,
        business_connection_id="bc-test",
        state=ConversationState.AI_APPROVAL.value,
        revision=3,
        last_message_at=utcnow(),
    )
    session.add(conversation)
    session.flush()
    return owner, contact, conversation


def test_owner_lists_are_isolated_and_show_pending_count() -> None:
    with _database() as session:
        owner, contact, conversation = _conversation(session)
        approval = Approval(
            conversation_id=conversation.id,
            conversation_revision=conversation.revision,
            candidate_response="رد مقترح",
            status="PENDING",
            expires_at=utcnow() + timedelta(hours=1),
        )
        session.add(approval)
        session.commit()

        conversations, total = list_owner_conversations(session, owner_id=owner.id)
        contacts, contact_total = list_owner_contacts(session, owner_id=owner.id)
        pending = list_pending_approvals(session, owner_id=owner.id)

        assert total == 1 and conversations[0].pending_count == 1
        assert contact_total == 1 and contacts[0].contact.id == contact.id
        assert len(pending) == 1 and pending[0][0].id == approval.id
        assert list_owner_conversations(session, owner_id=999)[1] == 0
        assert list_pending_approvals(session, owner_id=999) == []


def test_human_takeover_invalidates_pending_and_return_refreshes_summary() -> None:
    with _database() as session:
        owner, _, conversation = _conversation(session)
        session.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    telegram_message_id=1,
                    direction="IN",
                    sender_type="CONTACT",
                    content_type="TEXT",
                    text="أحتاج معرفة شروط الخدمة",
                ),
                Message(
                    conversation_id=conversation.id,
                    telegram_message_id=2,
                    direction="OUT",
                    sender_type="OWNER_VIA_BOT",
                    content_type="TEXT",
                    text="سأراجع طلبك",
                ),
                Approval(
                    conversation_id=conversation.id,
                    conversation_revision=conversation.revision,
                    candidate_response="رد قديم",
                    status="PENDING",
                    expires_at=utcnow() + timedelta(hours=1),
                ),
            ]
        )
        session.commit()

        updated = set_conversation_state(
            session,
            owner_id=owner.id,
            conversation_id=conversation.id,
            target=ConversationState.HUMAN_TAKEOVER,
        )
        session.commit()
        assert updated is not None and updated.state == ConversationState.HUMAN_TAKEOVER.value
        assert session.scalar(select(Approval)).status == "STALE"

        updated = set_conversation_state(
            session,
            owner_id=owner.id,
            conversation_id=conversation.id,
            target=ConversationState.AI_APPROVAL,
        )
        session.commit()
        assert updated is not None and "شروط الخدمة" in updated.summary
        actions = list(session.scalars(select(AuditLog.action)))
        assert actions.count("CONVERSATION_STATE_CHANGED") == 2


def test_exclusion_requires_explicit_owner_return_and_permissions_are_audited() -> None:
    with _database() as session:
        owner, contact, conversation = _conversation(session)
        session.commit()

        set_conversation_state(
            session,
            owner_id=owner.id,
            conversation_id=conversation.id,
            target=ConversationState.EXCLUDED,
        )
        session.commit()
        assert contact.is_excluded is True and contact.ai_allowed is False

        set_conversation_state(
            session,
            owner_id=owner.id,
            conversation_id=conversation.id,
            target=ConversationState.AI_APPROVAL,
        )
        set_contact_permission(
            session,
            owner_id=owner.id,
            contact_id=contact.id,
            permission="MEMORY",
            enabled=False,
        )
        session.commit()

        pair = get_owned_conversation(
            session, owner_id=owner.id, conversation_id=conversation.id
        )
        assert pair is not None
        assert pair[1].is_excluded is False and pair[1].ai_allowed is True
        assert pair[1].memory_allowed is False
        assert session.scalar(
            select(AuditLog).where(AuditLog.action == "CONTACT_PERMISSION_CHANGED")
        )


def test_summary_omits_deleted_messages() -> None:
    with _database() as session:
        _, _, conversation = _conversation(session)
        session.add_all(
            [
                Message(
                    conversation_id=conversation.id,
                    telegram_message_id=1,
                    direction="IN",
                    sender_type="CONTACT",
                    content_type="TEXT",
                    text="رسالة ظاهرة",
                ),
                Message(
                    conversation_id=conversation.id,
                    telegram_message_id=2,
                    direction="IN",
                    sender_type="CONTACT",
                    content_type="TEXT",
                    text="رسالة محذوفة",
                    is_deleted=True,
                ),
                Message(
                    conversation_id=conversation.id,
                    telegram_message_id=3,
                    direction="IN",
                    sender_type="CONTACT",
                    content_type="TEXT",
                    text="رمز التحقق 482731 وكلمة المرور: live-secret",
                ),
            ]
        )
        session.commit()
        summary = refresh_conversation_summary(session, conversation=conversation)
        assert "رسالة ظاهرة" in summary
        assert "رسالة محذوفة" not in summary
        assert "482731" not in summary and "live-secret" not in summary
        assert "بيانات حساسة محجوبة" in summary
