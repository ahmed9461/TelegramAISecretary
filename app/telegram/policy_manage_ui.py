from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.brain.models import ResponsePolicy
from app.brain.service import list_response_policies
from app.config import get_settings
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.security.owner import OwnerGuard

router = Router(name="policy_manage_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class PolicyManageStates(StatesGroup):
    name = State()
    description = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _list_keyboard(rows: list[ResponsePolicy]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ إضافة قاعدة", callback_data="brain:policy:add")]
    ]
    for row in rows[:12]:
        icon = "🟢" if row.enabled else "⚪"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"{icon} #{row.id} {row.name[:30]}",
                    callback_data=f"policy:item:{row.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _item_keyboard(policy_id: int, *, enabled: bool) -> InlineKeyboardMarkup:
    toggle = "⏸ تعطيل" if enabled else "▶️ تفعيل"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ الاسم", callback_data=f"policy:name:{policy_id}"),
                InlineKeyboardButton(
                    text="📝 الوصف",
                    callback_data=f"policy:description:{policy_id}",
                ),
            ],
            [InlineKeyboardButton(text=toggle, callback_data=f"policy:toggle:{policy_id}")],
            [InlineKeyboardButton(text="🗑 حذف", callback_data=f"policy:delete:{policy_id}")],
            [InlineKeyboardButton(text="⬅️ قواعد الرد", callback_data="brain:policies")],
        ]
    )


def _owned_policy(session, policy_id: int) -> ResponsePolicy | None:
    owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
    row = session.get(ResponsePolicy, policy_id)
    if row is None or row.owner_id != owner.id:
        return None
    return row


def _render(row: ResponsePolicy) -> str:
    return (
        f"🎛️ قاعدة الرد #{row.id}\n\n"
        f"الاسم: {row.name}\n"
        f"الحالة: {'🟢 مفعلة' if row.enabled else '⚪ معطلة'}\n"
        f"الإجراء: {row.action}\n"
        f"النطاق: {row.scope}\n"
        f"الأولوية: {row.priority}\n\n"
        f"الوصف:\n{row.description[:2500]}\n\n"
        "هذه القاعدة لا تستطيع تجاوز قيود الأمان الأساسية."
    )


@router.callback_query(F.data == "brain:policies")
async def policy_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_response_policies(session, owner_id=owner.id, enabled_only=False)
    text = "🎛️ قواعد الرد\n\n"
    text += "اختر قاعدة لعرضها أو تعديلها." if rows else "لا توجد قواعد مخصصة بعد."
    if callback.message:
        await callback.message.edit_text(text, reply_markup=_list_keyboard(rows))
    await callback.answer()


@router.callback_query(F.data.startswith("policy:item:"))
async def policy_item(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    policy_id = int(raw_id)
    await state.clear()
    with SessionLocal() as session:
        row = _owned_policy(session, policy_id)
        if row is None:
            await callback.answer("لم أجد القاعدة", show_alert=True)
            return
        text = _render(row)
        enabled = bool(row.enabled)
    if callback.message:
        await callback.message.edit_text(
            text[:4000],
            reply_markup=_item_keyboard(policy_id, enabled=enabled),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("policy:name:"))
async def policy_name_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(policy_id=int(raw_id))
    await state.set_state(PolicyManageStates.name)
    if callback.message:
        await callback.message.answer("✏️ أرسل الاسم الجديد للقاعدة:")
    await callback.answer()


@router.message(PolicyManageStates.name)
async def policy_name_save(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("الاسم لا يمكن أن يكون فارغًا.")
        return
    data = await state.get_data()
    policy_id = int(data.get("policy_id") or 0)
    with SessionLocal() as session:
        row = _owned_policy(session, policy_id)
        if row is None:
            await state.clear()
            await message.answer("لم أجد القاعدة.")
            return
        row.name = value[:255]
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم تعديل اسم القاعدة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ عرض القاعدة", callback_data=f"policy:item:{policy_id}")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("policy:description:"))
async def policy_description_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(policy_id=int(raw_id))
    await state.set_state(PolicyManageStates.description)
    if callback.message:
        await callback.message.answer("📝 أرسل الوصف الجديد للقاعدة:")
    await callback.answer()


@router.message(PolicyManageStates.description)
async def policy_description_save(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("الوصف لا يمكن أن يكون فارغًا.")
        return
    data = await state.get_data()
    policy_id = int(data.get("policy_id") or 0)
    with SessionLocal() as session:
        row = _owned_policy(session, policy_id)
        if row is None:
            await state.clear()
            await message.answer("لم أجد القاعدة.")
            return
        row.description = value
        row.conditions_json = {"natural_language": value}
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم تعديل وصف القاعدة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ عرض القاعدة", callback_data=f"policy:item:{policy_id}")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("policy:toggle:"))
async def policy_toggle(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    policy_id = int(raw_id)
    with SessionLocal() as session:
        row = _owned_policy(session, policy_id)
        if row is None:
            await callback.answer("لم أجد القاعدة", show_alert=True)
            return
        row.enabled = not bool(row.enabled)
        enabled = bool(row.enabled)
        session.commit()
        text = _render(row)
    if callback.message:
        await callback.message.edit_text(
            text[:4000],
            reply_markup=_item_keyboard(policy_id, enabled=enabled),
        )
    await callback.answer("تم تحديث حالة القاعدة")


@router.callback_query(F.data.startswith("policy:delete:"))
async def policy_delete(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    policy_id = int(raw_id)
    with SessionLocal() as session:
        row = _owned_policy(session, policy_id)
        if row is None:
            await callback.answer("لم أجد القاعدة", show_alert=True)
            return
        session.delete(row)
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            "🗑 تم حذف القاعدة.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ قواعد الرد", callback_data="brain:policies")]
                ]
            ),
        )
    await callback.answer("تم الحذف")
