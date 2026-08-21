from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.brain.models import ContactMemory
from app.brain.service import get_contact_memory, upsert_contact_memory
from app.config import get_settings
from app.db.models import Contact
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.security.owner import OwnerGuard

router = Router(name="memory_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class MemoryStates(StatesGroup):
    summary = State()
    private_notes = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _home_keyboard(contacts: list[Contact]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for contact in contacts[:12]:
        label = contact.display_name or contact.username or str(contact.telegram_user_id)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"👤 {label[:32]}",
                    callback_data=f"memory:contact:{contact.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _contact_keyboard(contact_id: int, *, share_with_ai: bool) -> InlineKeyboardMarkup:
    share_label = "🟢 مشاركة الذاكرة مع AI" if share_with_ai else "⚪ عدم مشاركة الذاكرة"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ ملخص الذاكرة",
                    callback_data=f"memory:summary:{contact_id}",
                ),
                InlineKeyboardButton(
                    text="🔒 ملاحظة خاصة",
                    callback_data=f"memory:private:{contact_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=share_label,
                    callback_data=f"memory:toggle:{contact_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 مسح ذاكرة الشخص",
                    callback_data=f"memory:clear:{contact_id}",
                )
            ],
            [InlineKeyboardButton(text="⬅️ الأشخاص", callback_data="brain:memory")],
        ]
    )


def _format_memory(contact: Contact, memory: ContactMemory | None) -> str:
    summary = memory.summary if memory and memory.summary else "—"
    private_notes = memory.private_notes if memory and memory.private_notes else "—"
    shared = bool(memory.share_with_ai) if memory else True
    allowed = bool(contact.memory_allowed)
    username = f"@{contact.username}" if contact.username else "—"
    return (
        "👤 ذاكرة الشخص\n\n"
        f"الاسم: {contact.display_name or '—'}\n"
        f"المعرف: {username}\n"
        f"Telegram ID: {contact.telegram_user_id}\n\n"
        f"🧠 الملخص: {summary[:1200]}\n\n"
        f"🔒 ملاحظة خاصة: {private_notes[:800]}\n\n"
        f"مشاركة الذاكرة مع AI: {'نعم' if shared and allowed else 'لا'}\n\n"
        "الملاحظة الخاصة لا تدخل إلى نموذج الذكاء الاصطناعي مطلقًا."
    )


@router.callback_query(F.data == "brain:memory")
async def memory_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        contacts = list(
            session.scalars(
                select(Contact)
                .where(Contact.owner_id == owner.id)
                .order_by(Contact.updated_at.desc(), Contact.id.desc())
                .limit(12)
            )
        )
    text = "👥 ذاكرة الأشخاص\n\n"
    if contacts:
        text += "اختر شخصًا لعرض ذاكرته أو تعديلها."
    else:
        text += "لا توجد محادثات محفوظة بعد. ستظهر الأشخاص هنا بعد وصول رسائلهم."
    if callback.message:
        await callback.message.edit_text(text, reply_markup=_home_keyboard(contacts))
    await callback.answer()


@router.callback_query(F.data.startswith("memory:contact:"))
async def memory_contact(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    contact_id = int(raw_id)
    await state.clear()
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        if contact is None:
            await callback.answer("لم أجد الشخص", show_alert=True)
            return
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact.owner_id != owner.id:
            await callback.answer("غير مسموح", show_alert=True)
            return
        memory = get_contact_memory(session, contact_id=contact.id)
        text = _format_memory(contact, memory)
        shared = bool(memory.share_with_ai) if memory else True
    if callback.message:
        await callback.message.edit_text(
            text[:4000],
            reply_markup=_contact_keyboard(contact_id, share_with_ai=shared),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("memory:summary:"))
async def memory_summary_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(contact_id=int(raw_id))
    await state.set_state(MemoryStates.summary)
    if callback.message:
        await callback.message.answer(
            "🧠 اكتب ملخصًا قصيرًا مفيدًا عن هذا الشخص.\n"
            "اكتب — لمسح الملخص الحالي."
        )
    await callback.answer()


@router.message(MemoryStates.summary)
async def memory_summary_save(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    data = await state.get_data()
    contact_id = int(data.get("contact_id") or 0)
    value = (message.text or "").strip()
    if value == "—":
        value = ""
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact is None or contact.owner_id != owner.id:
            await state.clear()
            await message.answer("لم أجد الشخص.")
            return
        upsert_contact_memory(
            session,
            owner_id=owner.id,
            contact_id=contact.id,
            summary=value,
        )
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم تحديث ملخص الذاكرة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ ذاكرة الشخص", callback_data=f"memory:contact:{contact_id}")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("memory:private:"))
async def memory_private_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(contact_id=int(raw_id))
    await state.set_state(MemoryStates.private_notes)
    if callback.message:
        await callback.message.answer(
            "🔒 اكتب ملاحظتك الخاصة. هذه الملاحظة لك فقط ولا تدخل إلى AI.\n"
            "اكتب — لمسحها."
        )
    await callback.answer()


@router.message(MemoryStates.private_notes)
async def memory_private_save(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    data = await state.get_data()
    contact_id = int(data.get("contact_id") or 0)
    value = (message.text or "").strip()
    if value == "—":
        value = ""
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact is None or contact.owner_id != owner.id:
            await state.clear()
            await message.answer("لم أجد الشخص.")
            return
        upsert_contact_memory(
            session,
            owner_id=owner.id,
            contact_id=contact.id,
            private_notes=value,
        )
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم حفظ الملاحظة الخاصة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ ذاكرة الشخص", callback_data=f"memory:contact:{contact_id}")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("memory:toggle:"))
async def memory_toggle(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    contact_id = int(raw_id)
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact is None or contact.owner_id != owner.id:
            await callback.answer("لم أجد الشخص", show_alert=True)
            return
        memory = get_contact_memory(session, contact_id=contact.id)
        current = bool(memory.share_with_ai) if memory else True
        memory = upsert_contact_memory(
            session,
            owner_id=owner.id,
            contact_id=contact.id,
            share_with_ai=not current,
        )
        session.commit()
        text = _format_memory(contact, memory)
        shared = bool(memory.share_with_ai)
    if callback.message:
        await callback.message.edit_text(
            text[:4000],
            reply_markup=_contact_keyboard(contact_id, share_with_ai=shared),
        )
    await callback.answer("تم تحديث مشاركة الذاكرة")


@router.callback_query(F.data.startswith("memory:clear:"))
async def memory_clear(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    contact_id = int(raw_id)
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact is None or contact.owner_id != owner.id:
            await callback.answer("لم أجد الشخص", show_alert=True)
            return
        memory = get_contact_memory(session, contact_id=contact.id)
        if memory is not None:
            session.delete(memory)
            session.commit()
    if callback.message:
        await callback.message.edit_text(
            "🗑 تم مسح ذاكرة هذا الشخص.\nلن يؤثر ذلك على سجل المحادثة نفسه.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ الأشخاص", callback_data="brain:memory")]
                ]
            ),
        )
    await callback.answer("تم مسح الذاكرة")
