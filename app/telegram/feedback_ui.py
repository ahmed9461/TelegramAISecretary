from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import get_settings
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.feedback.service import feedback_summary, record_contact_feedback
from app.security.owner import OwnerGuard
from app.telegram.owner_ui import main_admin_keyboard

router = Router(name="feedback_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


def append_feedback_row(
    markup: InlineKeyboardMarkup | None,
    *,
    approval_id: int,
) -> InlineKeyboardMarkup:
    rows = [list(row) for row in markup.inline_keyboard] if markup is not None else []
    rows.append(
        [
            InlineKeyboardButton(
                text=f"{rating}⭐",
                callback_data=f"feedback:rate:{approval_id}:{rating}",
            )
            for rating in range(1, 6)
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("feedback:rate:"))
async def rate_response(callback: CallbackQuery) -> None:
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or not parts[2].isdigit() or not parts[3].isdigit():
        await callback.answer("تعذر قراءة التقييم.", show_alert=True)
        return
    with SessionLocal() as session:
        row = record_contact_feedback(
            session,
            approval_id=int(parts[2]),
            telegram_user_id=callback.from_user.id,
            rating=int(parts[3]),
        )
        if row is not None:
            session.commit()
    if row is None:
        await callback.answer("هذا التقييم غير متاح لهذه المحادثة.", show_alert=True)
        return
    await callback.answer("شكرًا لك، تم تسجيل تقييمك ⭐")


@router.callback_query(F.data == "a:stats")
async def owner_feedback_stats(callback: CallbackQuery) -> None:
    if not guard.is_owner(callback.from_user.id):
        await callback.answer()
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        summary = feedback_summary(session, owner_id=owner.id)
        session.commit()
    if summary.average is None:
        text = (
            "📊 رضا العملاء\n\n"
            "لا توجد تقييمات بعد. سيظهر سؤال تقييم مختصر للعملاء دوريًا حسب إعداداتك."
        )
    else:
        bars = "\n".join(
            f"{rating}⭐: {summary.distribution[rating]}" for rating in range(5, 0, -1)
        )
        text = (
            "📊 رضا العملاء\n\n"
            f"متوسط التقييم: {summary.average:.1f} من 5\n"
            f"عدد التقييمات: {summary.total}\n\n{bars}"
        )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=main_admin_keyboard())
    await callback.answer()
