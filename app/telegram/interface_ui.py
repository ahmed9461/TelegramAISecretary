from __future__ import annotations

import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import func, select

from app.config import get_settings
from app.db.enums import ConversationState, InterfaceMode
from app.db.models import MenuItem
from app.db.repositories import ConversationRepository, OwnerRepository
from app.db.session import SessionLocal
from app.interface.menus import MenuAction
from app.interface.service import get_owned_menu_item, list_menu_items
from app.security.owner import OwnerGuard
from app.telegram.adapter import AiogramTelegramAdapter
from app.telegram.callback_safety import safe_callback_answer

router = Router(name="interface_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class InterfaceStates(StatesGroup):
    button_label = State()
    button_payload = State()
    button_visibility = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _is_contextual(row: MenuItem) -> bool:
    rules = dict(row.visibility_rules_json or {})
    return str(rules.get("mode") or "ALWAYS").upper() == "CONTEXTUAL"


def _home_keyboard(profile_mode: str, rows: list[MenuItem]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                text=("✅ " if profile_mode == InterfaceMode.HYBRID.value else "") + "هجين",
                callback_data="interface:mode:HYBRID",
            ),
            InlineKeyboardButton(
                text=("✅ " if profile_mode == InterfaceMode.AI_ONLY.value else "") + "ذكاء فقط",
                callback_data="interface:mode:AI_ONLY",
            ),
        ],
        [
            InlineKeyboardButton(
                text=("✅ " if profile_mode == InterfaceMode.CUSTOM_MENU.value else "") + "أزرار فقط",
                callback_data="interface:mode:CUSTOM_MENU",
            )
        ],
        [
            InlineKeyboardButton(text="➕ رد ثابت", callback_data="interface:add:SEND_MESSAGE"),
            InlineKeyboardButton(text="➕ رابط", callback_data="interface:add:OPEN_URL"),
        ],
        [InlineKeyboardButton(text="➕ تحويل لي", callback_data="interface:add:HANDOFF")],
    ]
    for row in rows[:12]:
        icon = {
            MenuAction.SEND_MESSAGE.value: "💬",
            MenuAction.OPEN_URL.value: "🔗",
            MenuAction.HANDOFF.value: "👤",
        }.get(row.action_type, "🔘")
        visibility = "🎯" if _is_contextual(row) else "🌐"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {visibility} {icon} {row.emoji or ''} {row.label}".strip(),
                    callback_data=f"interface:delete:{row.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ القائمة الرئيسية", callback_data="brain:main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _render_home(profile_mode: str, rows: list[MenuItem]) -> str:
    mode_label = {
        InterfaceMode.HYBRID.value: "هجين — ذكاء + أزرار",
        InterfaceMode.AI_ONLY.value: "ذكاء فقط",
        InterfaceMode.CUSTOM_MENU.value: "أزرار فقط",
    }.get(profile_mode, profile_mode)
    lines = [
        "🧩 الواجهة والأزرار",
        "",
        f"الوضع: {mode_label}",
        f"الأزرار الفعالة: {sum(1 for row in rows if row.enabled)}",
        "",
        "🌐 الزر الدائم يظهر مع كل رد.",
        "🎯 الزر السياقي يظهر فقط عندما تطابق رسالة العميل أو رد السكرتير الكلمات التي تحددها.",
    ]
    if rows:
        lines.append("\nالأزرار الحالية:")
        for row in rows[:12]:
            visibility = "🎯 سياقي" if _is_contextual(row) else "🌐 دائم"
            lines.append(
                f"• {row.emoji or ''} {row.label} — {row.action_type} — {visibility}".strip()
            )
    return "\n".join(lines)[:4000]


@router.callback_query(F.data == "interface:home")
async def interface_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile, rows = list_menu_items(session, owner_id=owner.id)
        session.commit()
        mode = profile.mode
    if callback.message:
        await callback.message.edit_text(
            _render_home(mode, rows),
            reply_markup=_home_keyboard(mode, rows),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("interface:mode:"))
async def interface_mode(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    mode = (callback.data or "").rsplit(":", 1)[-1].upper()
    if mode not in {item.value for item in InterfaceMode}:
        await safe_callback_answer(callback, "وضع غير صالح", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile, rows = list_menu_items(session, owner_id=owner.id)
        profile.mode = mode
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            _render_home(mode, rows),
            reply_markup=_home_keyboard(mode, rows),
        )
    await safe_callback_answer(callback, "تم تغيير وضع الواجهة")


@router.callback_query(F.data.startswith("interface:add:"))
async def interface_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    action = (callback.data or "").rsplit(":", 1)[-1].upper()
    if action not in {
        MenuAction.SEND_MESSAGE.value,
        MenuAction.OPEN_URL.value,
        MenuAction.HANDOFF.value,
    }:
        await safe_callback_answer(callback, "نوع زر غير مدعوم", show_alert=True)
        return
    await state.clear()
    await state.update_data(interface_action=action)
    await state.set_state(InterfaceStates.button_label)
    if callback.message:
        await callback.message.answer("اكتب اسم الزر كما سيظهر للعميل، ويمكنك بدء الاسم بإيموجي:")
    await safe_callback_answer(callback)


@router.message(InterfaceStates.button_label)
async def interface_label(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    label = (message.text or "").strip()
    if not label:
        await message.answer("اسم الزر لا يمكن أن يكون فارغًا.")
        return
    data = await state.get_data()
    action = str(data.get("interface_action") or "")
    await state.update_data(interface_label=label[:128])
    if action == MenuAction.HANDOFF.value:
        await state.update_data(interface_payload={})
        await _ask_visibility(message, state)
        return
    await state.set_state(InterfaceStates.button_payload)
    if action == MenuAction.OPEN_URL.value:
        await message.answer("أرسل رابط الزر ويجب أن يبدأ بـ https:// أو http://")
    else:
        await message.answer("أرسل النص الذي تريد أن يرسله هذا الزر للعميل:")


@router.message(InterfaceStates.button_payload)
async def interface_payload(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("القيمة لا يمكن أن تكون فارغة.")
        return
    data = await state.get_data()
    action = str(data.get("interface_action") or "")
    if action == MenuAction.OPEN_URL.value:
        if not value.startswith(("https://", "http://")):
            await message.answer("الرابط يجب أن يبدأ بـ https:// أو http://")
            return
        payload = {"url": value}
    else:
        payload = {"text": value}
    await state.update_data(interface_payload=payload)
    await _ask_visibility(message, state)


async def _ask_visibility(message: Message, state: FSMContext) -> None:
    await state.set_state(InterfaceStates.button_visibility)
    await message.answer(
        "🎯 متى يظهر هذا الزر؟\n\n"
        "إذا تريده سياقيًا، اكتب الكلمات أو العبارات التي تدل على ظهوره مفصولة بفواصل.\n"
        "مثال لزر طرق الدفع: دفع، سداد، تحويل، كريبتو، نجوم\n\n"
        "أرسل — فقط إذا تريده زرًا دائمًا مع كل رد."
    )


def _split_keywords(raw: str) -> list[str]:
    values = re.split(r"[,،|\n]+", raw)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        key = item.casefold()
        if not item or key in seen:
            continue
        seen.add(key)
        result.append(item[:80])
        if len(result) >= 24:
            break
    return result


@router.message(InterfaceStates.button_visibility)
async def interface_visibility(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    raw = (message.text or "").strip()
    if raw.casefold() in {"—", "-", "دائم", "always"}:
        rules = {"mode": "ALWAYS"}
    else:
        keywords = _split_keywords(raw)
        if not keywords:
            await message.answer("اكتب كلمة واحدة على الأقل، أو أرسل — ليظهر الزر دائمًا.")
            return
        rules = {"mode": "CONTEXTUAL", "keywords": keywords}
    await _save_button(message, state, visibility_rules=rules)


async def _save_button(
    message: Message,
    state: FSMContext,
    *,
    visibility_rules: dict,
) -> None:
    data = await state.get_data()
    action = str(data.get("interface_action") or MenuAction.SEND_MESSAGE.value)
    raw_label = str(data.get("interface_label") or "زر").strip()
    payload = dict(data.get("interface_payload") or {})
    parts = raw_label.split(maxsplit=1)
    emoji = None
    label = raw_label
    if len(parts) == 2 and len(parts[0]) <= 4 and not parts[0].isalnum():
        emoji, label = parts[0], parts[1]

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile, _ = list_menu_items(session, owner_id=owner.id)
        active_count = int(
            session.scalar(
                select(func.count(MenuItem.id)).where(MenuItem.menu_profile_id == profile.id)
            )
            or 0
        )
        row = MenuItem(
            menu_profile_id=profile.id,
            parent_item_id=None,
            label=label[:128],
            emoji=emoji,
            action_type=action,
            action_config_json=payload,
            row_index=active_count // 2,
            sort_order=active_count,
            visibility_rules_json=visibility_rules,
            enabled=True,
        )
        session.add(row)
        session.commit()
        item_id = row.id
    await state.clear()
    visibility = (
        "🎯 سياقي" if visibility_rules.get("mode") == "CONTEXTUAL" else "🌐 دائم"
    )
    await message.answer(
        f"✅ تم إنشاء الزر #{item_id} — {visibility}.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ الواجهة والأزرار", callback_data="interface:home")]
            ]
        ),
    )


@router.callback_query(F.data.startswith("interface:delete:"))
async def interface_delete(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "معرّف غير صالح", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_menu_item(session, owner_id=owner.id, item_id=int(raw_id))
        if pair is None:
            await safe_callback_answer(callback, "لم أجد الزر", show_alert=True)
            return
        _, row = pair
        session.delete(row)
        session.commit()
        profile, rows = list_menu_items(session, owner_id=owner.id)
        mode = profile.mode
    if callback.message:
        await callback.message.edit_text(
            _render_home(mode, rows),
            reply_markup=_home_keyboard(mode, rows),
        )
    await safe_callback_answer(callback, "تم حذف الزر")


@router.callback_query(F.data.startswith("m:"))
async def customer_menu_action(callback: CallbackQuery, bot: Bot) -> None:
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit() or callback.message is None:
        await safe_callback_answer(callback)
        return

    await safe_callback_answer(callback)
    business_connection_id = getattr(callback.message, "business_connection_id", None)
    chat = getattr(callback.message, "chat", None)
    if not business_connection_id or chat is None:
        return

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_menu_item(session, owner_id=owner.id, item_id=int(raw_id))
        session.commit()
    if pair is None:
        return
    _, item = pair
    if not item.enabled:
        return

    adapter = AiogramTelegramAdapter(bot)
    config = dict(item.action_config_json or {})
    if item.action_type == MenuAction.SEND_MESSAGE.value:
        text = str(config.get("text") or "").strip()
        if text:
            await adapter.send_text(
                business_connection_id=business_connection_id,
                chat_id=chat.id,
                text=text,
            )
        return

    if item.action_type == MenuAction.HANDOFF.value:
        with SessionLocal() as session:
            owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
            conversation = ConversationRepository.get_by_chat(
                session,
                owner_id=owner.id,
                chat_id=chat.id,
            )
            if conversation is not None:
                conversation.state = ConversationState.HUMAN_TAKEOVER.value
                conversation.revision += 1
                session.commit()
        await adapter.send_text(
            business_connection_id=business_connection_id,
            chat_id=chat.id,
            text=str(config.get("text") or "تم تحويل المحادثة للمتابعة البشرية."),
            attach_default_menu=False,
        )
        await bot.send_message(
            chat_id=settings.owner_telegram_id,
            text=f"👤 طلب العميل متابعة بشرية\nالمحادثة: {chat.id}",
        )
