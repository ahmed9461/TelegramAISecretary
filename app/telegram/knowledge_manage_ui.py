from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.audit.service import write_audit_log
from app.config import get_settings
from app.db.models import KnowledgeBatch, KnowledgeItem
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.knowledge.admin import (
    list_knowledge,
    list_knowledge_batches,
    rollback_knowledge_batch,
    supersede_knowledge,
)
from app.security.owner import OwnerGuard
from app.telegram.callback_safety import safe_callback_answer
from app.telegram.professional_copy import (
    knowledge_source_text,
    knowledge_type_text,
    knowledge_visibility_text,
)

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
        [InlineKeyboardButton(text="➕ إضافة معلومة", callback_data="brain:knowledge:add")],
        [InlineKeyboardButton(text="📦 دفعات المصادر", callback_data="knowledge:batches")],
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
                InlineKeyboardButton(
                    text="📝 المحتوى", callback_data=f"knowledge:content:{item_id}"
                ),
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
    visibility = knowledge_visibility_text(row.visibility)
    return (
        f"📚 المعلومة #{row.id}\n\n"
        f"النوع: {knowledge_type_text(row.type)}\n"
        f"الاستخدام: {visibility}\n"
        f"النسخة: {row.version or 1}\n"
        f"المصدر: {knowledge_source_text(row.source)}\n"
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
        replacement = supersede_knowledge(
            session,
            owner_id=row.owner_id,
            knowledge_id=row.id,
            title=title[:255],
        )
        if replacement is None:
            await state.clear()
            await message.answer("تعذر حفظ النسخة الجديدة من المعلومة.")
            return
        new_item_id = replacement.id
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم حفظ العنوان كنسخة جديدة مع الاحتفاظ بسجل النسخة السابقة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ عرض المعلومة",
                        callback_data=f"knowledge:item:{new_item_id}",
                    )
                ]
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
        replacement = supersede_knowledge(
            session,
            owner_id=row.owner_id,
            knowledge_id=row.id,
            content=content,
        )
        if replacement is None:
            await state.clear()
            await message.answer("تعذر حفظ النسخة الجديدة من المعلومة.")
            return
        new_item_id = replacement.id
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم حفظ المحتوى كنسخة جديدة مع الاحتفاظ بسجل النسخة السابقة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ عرض المعلومة",
                        callback_data=f"knowledge:item:{new_item_id}",
                    )
                ]
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
    label = {"PUBLIC": "عام", "INTERNAL": "داخلي", "PRIVATE": "خاص"}.get(
        new_visibility,
        "المستوى المحدد",
    )
    await safe_callback_answer(callback, f"تم تغيير مستوى الاستخدام إلى: {label}")


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
        write_audit_log(
            session,
            owner_id=row.owner_id,
            actor="OWNER_TELEGRAM",
            action="KNOWLEDGE_DELETE",
            entity_type="KNOWLEDGE_ITEM",
            entity_id=row.id,
            metadata={"visibility": row.visibility, "version": row.version},
        )
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


def _batch_keyboard(rows: list[KnowledgeBatch]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        status = "✅" if row.status == "ACTIVE" else "↩️"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{status} #{row.id} {row.source_name[:28]}",
                    callback_data=f"knowledge:batch:{row.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ المعرفة", callback_data="brain:knowledge")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "knowledge:batches")
async def knowledge_batches(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_knowledge_batches(session, owner_id=owner.id)
    text = (
        "📦 دفعات المصادر\n\nاختر دفعة لمراجعتها أو التراجع عنها بالكامل."
        if rows
        else "📦 دفعات المصادر\n\nلا توجد دفعات جماعية محفوظة بعد."
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=_batch_keyboard(rows))
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("knowledge:batch:"))
async def knowledge_batch(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتمكن من تحديد الدفعة.", show_alert=True)
        return
    batch_id = int(raw_id)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = session.get(KnowledgeBatch, batch_id)
        if row is None or row.owner_id != owner.id:
            await safe_callback_answer(callback, "لم أجد هذه الدفعة.", show_alert=True)
            return
        active = row.status == "ACTIVE"
        text = (
            f"📦 دفعة المصدر #{row.id}\n\n"
            f"المصدر: {row.source_name}\n"
            f"عدد المعلومات: {row.item_count}\n"
            f"مستوى الاستخدام: {knowledge_visibility_text(row.visibility)}\n"
            f"الحالة: {'فعالة' if active else 'تم التراجع عنها'}"
        )
    buttons = []
    if active:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="↩️ التراجع عن الدفعة",
                    callback_data=f"knowledge:batch_rollback:{batch_id}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text="⬅️ الدفعات", callback_data="knowledge:batches")])
    if callback.message:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("knowledge:batch_rollback:"))
async def knowledge_batch_rollback(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتمكن من تحديد الدفعة.", show_alert=True)
        return
    batch_id = int(raw_id)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        removed = rollback_knowledge_batch(session, owner_id=owner.id, batch_id=batch_id)
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            f"↩️ تم التراجع عن الدفعة وإيقاف {removed} من المعلومات. لم تُحذف الدفعات الأخرى.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ الدفعات", callback_data="knowledge:batches")]
                ]
            ),
        )
    await safe_callback_answer(callback, "تم التراجع عن الدفعة")
