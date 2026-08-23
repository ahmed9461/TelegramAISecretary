from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import PaymentStatus
from app.db.models import Conversation, PaymentOrder


@dataclass(frozen=True, slots=True)
class PaymentCheck:
    ok: bool
    order: PaymentOrder | None
    error_message: str = ""


def create_stars_order(
    session: Session,
    *,
    conversation: Conversation,
    telegram_user_id: int,
    menu_item_id: int | None,
    title: str,
    description: str,
    amount: int,
    success_message: str,
) -> PaymentOrder:
    if not 1 <= amount <= 1_000_000:
        raise ValueError("invalid_stars_amount")
    public_id = uuid4().hex
    order = PaymentOrder(
        public_id=public_id,
        owner_id=conversation.owner_id,
        conversation_id=conversation.id,
        contact_id=conversation.contact_id,
        menu_item_id=menu_item_id,
        telegram_user_id=telegram_user_id,
        title=title.strip()[:32],
        description=description.strip()[:255],
        currency="XTR",
        amount=amount,
        invoice_payload=f"stars:{public_id}",
        status=PaymentStatus.CREATED.value,
        success_message=success_message.strip()[:4000],
    )
    if not order.title or not order.description:
        raise ValueError("invalid_product_copy")
    session.add(order)
    session.flush()
    return order


def validate_pre_checkout(
    session: Session,
    *,
    payload: str,
    telegram_user_id: int,
    currency: str,
    total_amount: int,
    ttl_minutes: int = 30,
) -> PaymentCheck:
    order = session.scalar(
        select(PaymentOrder).where(PaymentOrder.invoice_payload == payload).with_for_update()
    )
    if order is None:
        return PaymentCheck(False, None, "لم أجد طلب الدفع. افتح رابطًا جديدًا من المحادثة.")
    now = datetime.now(UTC)
    created_at = order.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if now - created_at > timedelta(minutes=max(5, ttl_minutes)):
        if order.status != PaymentStatus.PAID.value:
            order.status = PaymentStatus.EXPIRED.value
        return PaymentCheck(False, order, "انتهت صلاحية طلب الدفع. أنشئ طلبًا جديدًا.")
    if order.status not in {PaymentStatus.CREATED.value, PaymentStatus.PRECHECKOUT.value}:
        return PaymentCheck(False, order, "طلب الدفع لم يعد متاحًا.")
    if (
        order.telegram_user_id != telegram_user_id
        or currency != "XTR"
        or order.currency != currency
        or order.amount != total_amount
    ):
        return PaymentCheck(False, order, "تعذر مطابقة تفاصيل الطلب بأمان.")
    order.status = PaymentStatus.PRECHECKOUT.value
    return PaymentCheck(True, order)


def record_successful_payment(
    session: Session,
    *,
    payload: str,
    telegram_user_id: int,
    currency: str,
    total_amount: int,
    telegram_charge_id: str,
    provider_charge_id: str,
) -> tuple[PaymentOrder, bool]:
    order = session.scalar(
        select(PaymentOrder).where(PaymentOrder.invoice_payload == payload).with_for_update()
    )
    if order is None:
        raise ValueError("payment_order_not_found")
    if order.status == PaymentStatus.PAID.value:
        if order.telegram_payment_charge_id == telegram_charge_id:
            return order, False
        raise ValueError("payment_order_already_paid")
    if (
        order.telegram_user_id != telegram_user_id
        or currency != "XTR"
        or order.currency != currency
        or order.amount != total_amount
        or not telegram_charge_id
    ):
        raise ValueError("payment_mismatch")
    order.status = PaymentStatus.PAID.value
    order.telegram_payment_charge_id = telegram_charge_id
    order.provider_payment_charge_id = provider_charge_id or None
    order.paid_at = datetime.now(UTC)
    return order, True
