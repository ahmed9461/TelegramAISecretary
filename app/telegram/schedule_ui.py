from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.audit.service import write_audit_log
from app.config import get_settings
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.schedules.service import (
    create_reminder,
    list_reminders,
    local_time_to_utc,
    validate_timezone,
)
from app.security.owner import OwnerGuard
from app.telegram.callback_safety import safe_callback_answer

router = Router(name="schedule_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class ScheduleStates(StatesGroup):
    timezone = State()
    reminder_text = State()
    reminder_time = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _parse_run_at(row) -> datetime | None:
    raw = str((row.config_json or {}).get("run_at") or "")
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)


def _render_home(timezone: str, rows: list) -> str:
    lines = [
        "⏰ الأوقات والتذكيرات",
        "",
        f"منطقتك الزمنية: {timezone}",
        "يمكنك إنشاء تذكير خاص بك؛ لا يرسل السكرتير رسائل متابعة للعملاء من تلقاء نفسه.",
    ]
    if rows:
        lines.append("\nالتذكيرات القادمة:")
        zone = ZoneInfo(timezone)
        for row in rows[:12]:
            run_at = _parse_run_at(row)
            local = run_at.astimezone(zone).strftime("%Y-%m-%d %H:%M") if run_at else "وقت غير صالح"
            text = str((row.config_json or {}).get("text") or "").replace("\n", " ")[:80]
            lines.append(f"• {local} — {text}")
    else:
        lines.append("\nلا توجد تذكيرات قادمة.")
    return "\n".join(lines)[:4000]


def _keyboard(rows: list) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="➕ تذكير", callback_data="schedule:add"),
            InlineKeyboardButton(text="🌍 المنطقة الزمنية", callback_data="schedule:timezone"),
        ]
    ]
    for row in rows[:10]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 حذف تذكير {row.id}",
                    callback_data=f"schedule:delete:{row.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ القائمة الرئيسية", callback_data="brain:main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _show_home(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_reminders(session, owner_id=owner.id)
        timezone = owner.timezone
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            _render_home(timezone, rows),
            reply_markup=_keyboard(rows),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.in_({"schedule:home", "a:schedules"}))
async def schedule_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await _show_home(callback, state)


@router.callback_query(F.data == "schedule:timezone")
async def set_timezone(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    await state.set_state(ScheduleStates.timezone)
    if callback.message:
        await callback.message.answer(
            "اكتب اسم منطقتك الزمنية، مثل Asia/Riyadh أو Europe/London."
        )
    await safe_callback_answer(callback)


@router.message(ScheduleStates.timezone)
async def timezone_value(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    try:
        timezone = validate_timezone(message.text or "")
    except ValueError:
        await message.answer("لم أتعرف على المنطقة الزمنية. مثال صحيح: Asia/Riyadh")
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        owner.timezone = timezone
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="OWNER_TIMEZONE_UPDATED",
            entity_type="OWNER",
            entity_id=owner.id,
            metadata={"timezone": timezone},
        )
        session.commit()
    await state.clear()
    await message.answer(f"✅ تم ضبط المنطقة الزمنية على {timezone}.")


@router.callback_query(F.data == "schedule:add")
async def add_reminder(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    await state.set_state(ScheduleStates.reminder_text)
    if callback.message:
        await callback.message.answer("بماذا تريد أن أذكّرك؟")
    await safe_callback_answer(callback)


@router.message(ScheduleStates.reminder_text)
async def reminder_text(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("اكتب نص التذكير.")
        return
    await state.update_data(reminder_text=value[:2000])
    await state.set_state(ScheduleStates.reminder_time)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        timezone = owner.timezone
    await message.answer(
        "متى أذكّرك؟ أرسل التاريخ والوقت بهذا الشكل:\n"
        "2026-08-25 14:30\n\n"
        f"سيُحسب الوقت حسب {timezone}."
    )


@router.message(ScheduleStates.reminder_time)
async def reminder_time(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    data = await state.get_data()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        try:
            run_at = local_time_to_utc(value=message.text or "", timezone=owner.timezone)
            row = create_reminder(
                session,
                owner_id=owner.id,
                timezone=owner.timezone,
                text=str(data.get("reminder_text") or ""),
                run_at=run_at,
            )
        except ValueError:
            await message.answer(
                "لم أتمكن من حفظ الموعد. تأكد أنه في المستقبل وبالصيغة 2026-08-25 14:30."
            )
            return
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="REMINDER_CREATED",
            entity_type="SCHEDULE",
            entity_id=row.id,
        )
        session.commit()
        local = run_at.astimezone(ZoneInfo(owner.timezone)).strftime("%Y-%m-%d %H:%M")
        timezone = owner.timezone
    await state.clear()
    await message.answer(f"✅ سأذكّرك في {local} حسب {timezone}.")


@router.callback_query(F.data.startswith("schedule:delete:"))
async def delete_reminder(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتعرف على التذكير.", show_alert=True)
        return
    from app.db.models import Schedule

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = session.get(Schedule, int(raw_id))
        if row is None or row.owner_id != owner.id:
            await safe_callback_answer(callback, "لم أجد هذا التذكير.", show_alert=True)
            return
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="REMINDER_DELETED",
            entity_type="SCHEDULE",
            entity_id=row.id,
        )
        session.delete(row)
        session.commit()
    await safe_callback_answer(callback, "تم حذف التذكير")
