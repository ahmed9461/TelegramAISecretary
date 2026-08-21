from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import get_settings
from app.db.models import KnowledgeItem
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.knowledge.admin import list_knowledge
from app.security.owner import OwnerGuard
from app.telegram.callback_safety import safe_callback_answer

router = Router(name="knowledge_manage_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class KnowledgeManageStates(StatesGroup):
    title = State()
    content = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _list_keyboard(rows: list[KnowledgeItem]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ إضافة معلومة", callback_data="brain:knowledge:add")]
    ]
    for row in rows[:12]:
        icon = {"PUBLIC": "🌍", "INTERNAL": "🏠", "PRIVATE": "🔒"}.get(row.visibility, "•")
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} #{row.id} {row.title[:30]}",
                    callback_data=f"knowledge:item:{row.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _item_keyboard(item_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ العنوان", callback_data=f"knowledge:title:{item_id}"),
                InlineKeyboardButton(text="📝 المحتوى", callback_data=f"knowledge:content:{item_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="🔁 مستوى الاستخدام",
                    callback_data=f"knowledge:visibility:{item_id}",
                )
            ],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"knowledge:delete:{item_id}")],
            [InlineKeyboardButton(text="⬅️ المعرفة", callback_data="brain:knowledge")],
        ]
    )


def _render_item(row: KnowledgeItem) -> str:
    visibility = {
        "PUBLIC": "🌍 عام — يمكن قوله للعميل",
        "INTERNAL": "🏠 داخلي — يوجّه السكرتير",
        "PRIVATE": "🔒 خاص — لا يدخل إلى AI",
    }.get(row.visibility, row.visibility)
    return (
        f"📚 المعلومة #{row.id}\n\n"
        f"النوع: {row.type}\n"
        f"الاستخدام: {visibility}\n"
        f"العنوان: {row.title}\n\n"
        f"المحتوى:\n{row.content[:2800]}"
    )


def _owned_item(session, item_id: int) -> KnowledgeItem | None:
    owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
    row = session.get(KnowledgeItem, item_id)
    if row is None or row.owner_id != owner.id or row.status != "ACTIVE":
        return None
    return row


@router.callback_query(F.data == "brain:knowledge")
async def knowledge_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_knowledge(session, owner_id=owner.id, limit=12)
    text = "📚 معرفة السكرتير\n\n"
    text += "اختر معلومة لعرضها أو تعديلها." if rows else "لا توجد معلومات محفوظة بعد."
    if callback.message:
        await callback.message.edit_text(text, reply_markup=_list_keyboard(rows))
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("knowledge:item:"))
async def knowledge_item(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "معرّف غير صالح", show_alert=True)
        return
    item_id = int(raw_id)
    await state.clear()
    with SessionLocal() as session:
        row = _owned_item(session, item_id)
        if row is None:
            await safe_callback_answer(callback, "لم أجد المعلومة", show_alert=True)
            return
        text = _render_item(row)
    if callback.message:
        await callback.message.edit_text(text[:4000], reply_markup=_item_keyboard(item_id))
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("knowledge:title:"))
async def knowledge_title_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(knowledge_item_id=int(raw_id))
    await state.set_state(KnowledgeManageStates.title)
    if callback.message:
        await callback.message.answer("✏️ أرسل العنوان الجديد:")
    await safe_callback_answer(callback)


@router.message(KnowledgeManageStates.title)
async def knowledge_title_save(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("العنوان لا يمكن أن يكون فارغًا.")
        return
    data = await state.get_data()
    item_id = int(data.get("knowledge_item_id") or 0)
    with SessionLocal() as session:
        row = _owned_item(session, item_id)
        if row is None:
            await state.clear()
            await message.answer("لم أجد المعلومة.")
            return
        row.title = title[:255]
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم تعديل العنوان.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ عرض المعلومة", callback_data=f"knowledge:item:{item_id}")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("knowledge:content:"))
async def knowledge_content_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(knowledge_item_id=int(raw_id))
    await state.set_state(KnowledgeManageStates.content)
    if callback.message:
        await callback.message.answer("📝 أرسل المحتوى الجديد كاملًا:")
    await safe_callback_answer(callback)


@router.message(KnowledgeManageStates.content)
async def knowledge_content_save(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    content = (message.text or "").strip()
    if not content:
        await message.answer("المحتوى لا يمكن أن يكون فارغًا.")
        return
    data = await state.get_data()
    item_id = int(data.get("knowledge_item_id") or 0)
    with SessionLocal() as session:
        row = _owned_item(session, item_id)
        if row is None:
            await state.clear()
            await message.answer("لم أجد المعلومة.")
            return
        row.content = content
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم تعديل المحتوى.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ عرض المعلومة", callback_data=f"knowledge:item:{item_id}")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("knowledge:visibility:"))
async def knowledge_visibility(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "معرّف غير صالح", show_alert=True)
        return
    item_id = int(raw_id)
    order = {"PUBLIC": "INTERNAL", "INTERNAL": "PRIVATE", "PRIVATE": "PUBLIC"}
    with SessionLocal() as session:
        row = _owned_item(session, item_id)
        if row is None:
            await safe_callback_answer(callback, "لم أجد المعلومة", show_alert=True)
            return
        row.visibility = order.get(row.visibility, "INTERNAL")
        new_visibility = row.visibility
        session.commit()
        text = _render_item(row)
    if callback.message:
        await callback.message.edit_text(text[:4000], reply_markup=_item_keyboard(item_id))
    await safe_callback_answer(callback, f"تم تغيير المستوى إلى {new_visibility}")


@router.callback_query(F.data.startswith("knowledge:delete:"))
async def knowledge_delete(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "معرّف غير صالح", show_alert=True)
        return
    item_id = int(raw_id)
    with SessionLocal() as session:
        row = _owned_item(session, item_id)
        if row is None:
            await safe_callback_answer(callback, "لم أجد المعلومة", show_alert=True)
            return
        row.status = "DELETED"
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            "🗑 تم حذف المعلومة.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ المعرفة", callback_data="brain:knowledge")]
                ]
            ),
        )
    await safe_callback_answer(callback, "تم الحذف")
