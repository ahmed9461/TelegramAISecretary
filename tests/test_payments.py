from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.enums import ConversationState, PaymentStatus
from app.db.models import Contact, Conversation, Owner
from app.payments.service import (
    create_stars_order,
    record_successful_payment,
    validate_pre_checkout,
)


def _session_and_conversation() -> tuple[Session, Conversation]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    owner = Owner(telegram_user_id=1, display_name="مالك")
    session.add(owner)
    session.flush()
    contact = Contact(owner_id=owner.id, telegram_user_id=2, display_name="عميل")
    session.add(contact)
    session.flush()
    conversation = Conversation(
        owner_id=owner.id,
        contact_id=contact.id,
        telegram_chat_id=20,
        business_connection_id="business",
        state=ConversationState.AI_APPROVAL.value,
    )
    session.add(conversation)
    session.flush()
    return session, conversation


def test_stars_order_checks_user_currency_amount_and_success_idempotency() -> None:
    session, conversation = _session_and_conversation()
    with session:
        order = create_stars_order(
            session,
            conversation=conversation,
            telegram_user_id=2,
            menu_item_id=None,
            title="اشتراك",
            description="اشتراك رقمي موصوف بوضوح",
            amount=75,
            success_message="تم تفعيل طلبك.",
        )
        session.commit()

        rejected = validate_pre_checkout(
            session,
            payload=order.invoice_payload,
            telegram_user_id=99,
            currency="XTR",
            total_amount=75,
        )
        assert rejected.ok is False
        assert order.status == PaymentStatus.CREATED.value

        accepted = validate_pre_checkout(
            session,
            payload=order.invoice_payload,
            telegram_user_id=2,
            currency="XTR",
            total_amount=75,
        )
        assert accepted.ok is True
        assert order.status == PaymentStatus.PRECHECKOUT.value
        session.commit()

        paid, first = record_successful_payment(
            session,
            payload=order.invoice_payload,
            telegram_user_id=2,
            currency="XTR",
            total_amount=75,
            telegram_charge_id="tg-charge-1",
            provider_charge_id="provider-1",
        )
        session.commit()
        assert first is True
        assert paid.status == PaymentStatus.PAID.value

        same, duplicate = record_successful_payment(
            session,
            payload=order.invoice_payload,
            telegram_user_id=2,
            currency="XTR",
            total_amount=75,
            telegram_charge_id="tg-charge-1",
            provider_charge_id="provider-1",
        )
        assert same.id == order.id
        assert duplicate is False


def test_expired_order_is_rejected_before_checkout() -> None:
    session, conversation = _session_and_conversation()
    with session:
        order = create_stars_order(
            session,
            conversation=conversation,
            telegram_user_id=2,
            menu_item_id=None,
            title="خدمة",
            description="وصف الخدمة",
            amount=20,
            success_message="تم الاستلام.",
        )
        order.created_at = datetime.now(UTC) - timedelta(hours=2)
        session.commit()

        result = validate_pre_checkout(
            session,
            payload=order.invoice_payload,
            telegram_user_id=2,
            currency="XTR",
            total_amount=20,
            ttl_minutes=30,
        )
        assert result.ok is False
        assert order.status == PaymentStatus.EXPIRED.value
