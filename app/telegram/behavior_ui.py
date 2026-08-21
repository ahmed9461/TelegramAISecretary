from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from app.config import get_settings
from app.db.enums import GlobalMode
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.security.owner import OwnerGuard

router = Router(name="behavior_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


_MODE_LABELS = {
    GlobalMode.AUTO.value: "🟢 تلقائي",
    GlobalMode.APPROVAL.value: "🟡 موافقة قبل الإرسال",
    GlobalMode.OBSERVE.value: "👁 مراقبة فقط",
    GlobalMode.OFF.value: "⛔ متوقف",
}


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _keyboard(current: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    options = [
        (GlobalMode.AUTO.value, "🟢 تلقائي"),
        (GlobalMode.APPROVAL.value, "🟡 موافقة"),
        (GlobalMode.OBSERVE.value, "👁 مراقبة"),
        (GlobalMode.OFF.value, "⛔ إيقاف"),
    ]
    for index in range(0, len(options), 2):
        row: list[InlineKeyboardButton] = []
        for value, label in options[index : index + 2]:
            marker = "✓ " if value == current else ""
            row.append(
                InlineKeyboardButton(
                    text=f"{marker}{label}",
                    callback_data=f"behavior:set:{value}",
                )
            )
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ القائمة الرئيسية", callback_data="brain:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _text(mode: str) -> str:
    return (
        "⚙️ سلوك السكرتير\n\n"
        f"الوضع العام الحالي: {_MODE_LABELS.get(mode, mode)}\n\n"
        "🟢 تلقائي: يسمح بالرد التلقائي فقط عندما تسمح حالة المحادثة والأمان والثقة.\n"
        "🟡 موافقة: يمنع الإرسال التلقائي ويجعل الردود تمر عليك أولًا.\n"
        "👁 مراقبة: يحفظ ويفهم السياق دون إرسال ردود.\n"
        "⛔ متوقف: يمنع ردود الذكاء الاصطناعي بالكامل.\n\n"
        "الوضع العام يعمل كسقف أمان: اختيار «تلقائي» لا يلغي حالة أكثر تشددًا "
        "لمحادثة محددة مثل تدخل بشري أو استبعاد."
    )


@router.callback_query(F.data == "behavior:home")
async def behavior_home(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        mode = owner.default_mode
    if callback.message:
        await callback.message.edit_text(_text(mode), reply_markup=_keyboard(mode))
    await callback.answer()


@router.callback_query(F.data.startswith("behavior:set:"))
async def behavior_set(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    mode = (callback.data or "").rsplit(":", 1)[-1].upper()
    allowed = {item.value for item in GlobalMode}
    if mode not in allowed:
        await callback.answer("وضع غير صالح", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        owner.default_mode = mode
        session.commit()
    if callback.message:
        await callback.message.edit_text(_text(mode), reply_markup=_keyboard(mode))
    await callback.answer(f"تم تغيير الوضع إلى {_MODE_LABELS.get(mode, mode)}")
