from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message, PreCheckoutQuery

from app.audit.service import write_audit_log
from app.config import get_settings
from app.db.session import SessionLocal
from app.payments.service import record_successful_payment, validate_pre_checkout

router = Router(name="payment_ui")
settings = get_settings()
logger = logging.getLogger(__name__)


@router.message(Command("terms"))
async def payment_terms(message: Message) -> None:
    text = settings.payment_terms_text.strip()
    if settings.payment_terms_url.startswith(("https://", "http://")):
        text = f"{text}\n\nالتفاصيل الكاملة: {settings.payment_terms_url}"
    await message.answer(f"📄 شروط الدفع\n\n{text}"[:4000])


@router.message(Command("paysupport"))
async def payment_support(message: Message) -> None:
    await message.answer(f"🧾 دعم المدفوعات\n\n{settings.payment_support_text.strip()}"[:4000])


@router.pre_checkout_query()
async def payment_pre_checkout(query: PreCheckoutQuery) -> None:
    try:
        with SessionLocal() as session:
            check = validate_pre_checkout(
                session,
                payload=query.invoice_payload,
                telegram_user_id=query.from_user.id,
                currency=query.currency,
                total_amount=query.total_amount,
                ttl_minutes=settings.payment_order_ttl_minutes,
            )
            session.commit()
    except Exception:
        logger.exception("payment_pre_checkout_failed")
        await query.answer(ok=False, error_message="تعذر التحقق من الطلب. حاول إنشاء طلب جديد.")
        return
    await query.answer(
        ok=check.ok,
        error_message=None if check.ok else check.error_message,
    )


@router.business_message(F.successful_payment)
@router.message(F.successful_payment)
async def payment_success(message: Message, bot: Bot) -> None:
    payment = message.successful_payment
    if payment is None or message.from_user is None:
        return
    try:
        with SessionLocal() as session:
            order, first_confirmation = record_successful_payment(
                session,
                payload=payment.invoice_payload,
                telegram_user_id=message.from_user.id,
                currency=payment.currency,
                total_amount=payment.total_amount,
                telegram_charge_id=payment.telegram_payment_charge_id,
                provider_charge_id=payment.provider_payment_charge_id,
            )
            if first_confirmation:
                write_audit_log(
                    session,
                    owner_id=order.owner_id,
                    actor="TELEGRAM_PAYMENT",
                    action="STARS_PAYMENT_CONFIRMED",
                    entity_type="PAYMENT_ORDER",
                    entity_id=order.id,
                    metadata={"currency": order.currency, "amount": order.amount},
                )
            session.commit()
            order_id = order.id
            title = order.title
            amount = order.amount
            success_message = order.success_message
    except ValueError:
        logger.exception("successful_payment_mismatch")
        await bot.send_message(
            chat_id=settings.owner_telegram_id,
            text="⚠️ وصل تأكيد دفع لم يطابق طلبًا صالحًا. لم تُنفذ أي خدمة تلقائيًا.",
        )
        return
    if not first_confirmation:
        return
    await message.answer(
        f"✅ تم تأكيد الدفع بنجاح\n\n{success_message}\n\nرقم الطلب: #{order_id}"[:4000]
    )
    await bot.send_message(
        chat_id=settings.owner_telegram_id,
        text=(
            "⭐ عملية دفع مؤكدة\n\n"
            f"الطلب: #{order_id}\n"
            f"العنصر: {title}\n"
            f"القيمة: {amount} نجمة\n\n"
            "تم التسليم وفق رسالة النجاح التي اعتمدتها."
        ),
    )
