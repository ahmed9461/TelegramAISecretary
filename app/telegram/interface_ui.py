from __future__ import annotations

import logging
import re

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
)
from sqlalchemy import func, select

from app.audit.service import write_audit_log
from app.config import get_settings
from app.db.enums import ConversationState, FlowStatus, InterfaceMode, PaymentStatus
from app.db.models import Contact, Flow, MenuItem, PaymentOrder
from app.db.repositories import ConversationRepository, OwnerRepository
from app.db.session import SessionLocal
from app.flows.service import start_flow
from app.interface.menus import MenuAction
from app.interface.service import get_owned_menu_item, list_menu_items, publish_menu_draft
from app.payments.service import create_stars_order
from app.security.owner import OwnerGuard
from app.telegram.adapter import AiogramTelegramAdapter
from app.telegram.callback_safety import safe_callback_answer
from app.telegram.professional_copy import menu_action_text

router = Router(name="interface_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)
logger = logging.getLogger(__name__)


class InterfaceStates(StatesGroup):
    button_label = State()
    button_payload = State()
    button_visibility = State()
    payment_price = State()
    payment_description = State()
    payment_success = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _is_contextual(row: MenuItem) -> bool:
    rules = dict(row.visibility_rules_json or {})
    return str(rules.get("mode") or "ALWAYS").upper() == "CONTEXTUAL"


def _home_keyboard(profile_mode: str, rows: list[MenuItem]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="👁 معاينة المسودة", callback_data="interface:preview"),
            InlineKeyboardButton(text="✅ نشر المسودة", callback_data="interface:publish"),
        ],
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
                text=("✅ " if profile_mode == InterfaceMode.CUSTOM_MENU.value else "")
                + "أزرار فقط",
                callback_data="interface:mode:CUSTOM_MENU",
            )
        ],
        [
            InlineKeyboardButton(text="➕ رد ثابت", callback_data="interface:add:SEND_MESSAGE"),
            InlineKeyboardButton(
                text="➕ رابط / بوابة خارجية",
                callback_data="interface:add:OPEN_URL",
            ),
        ],
        [
            InlineKeyboardButton(text="➕ إجراء", callback_data="interface:add-flow"),
            InlineKeyboardButton(text="➕ تحويل لي", callback_data="interface:add:HANDOFF"),
        ],
        [
            InlineKeyboardButton(
                text="⭐ دفع بنجوم Telegram",
                callback_data="interface:add:START_PAYMENT",
            )
        ],
    ]
    for row in rows[:12]:
        icon = {
            MenuAction.SEND_MESSAGE.value: "💬",
            MenuAction.OPEN_URL.value: "🔗",
            MenuAction.HANDOFF.value: "👤",
            MenuAction.START_PAYMENT.value: "⭐",
        }.get(row.action_type, "🔘")
        visibility = "🎯" if _is_contextual(row) else "🌐"
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ {visibility} {icon} {row.emoji or ''} {row.label}".strip(),
                    callback_data=f"interface:edit:{row.id}",
                ),
                InlineKeyboardButton(
                    text="⬆️",
                    callback_data=f"interface:move:{row.id}:up",
                ),
                InlineKeyboardButton(
                    text="⬇️",
                    callback_data=f"interface:move:{row.id}:down",
                ),
                InlineKeyboardButton(
                    text="🗑",
                    callback_data=f"interface:delete:{row.id}",
                ),
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
        "الحالة: مسودة خاصة بك — لن يراها العملاء حتى تنشرها.",
        f"الوضع: {mode_label}",
        f"أزرار المسودة: {sum(1 for row in rows if row.enabled)}",
        "",
        "🌐 الزر الدائم يظهر مع كل رد.",
        "🎯 الزر السياقي يظهر فقط عندما تطابق رسالة العميل أو رد السكرتير الكلمات التي تحددها.",
    ]
    if rows:
        lines.append("\nالأزرار الحالية:")
        for row in rows[:12]:
            visibility = "🎯 سياقي" if _is_contextual(row) else "🌐 دائم"
            lines.append(
                f"• {row.emoji or ''} {row.label} — {menu_action_text(row.action_type)} — "
                f"{visibility}".strip()
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


def _preview_keyboard(rows: list[MenuItem]) -> InlineKeyboardMarkup:
    grouped: dict[int, list[InlineKeyboardButton]] = {}
    for row in rows:
        if not row.enabled:
            continue
        grouped.setdefault(row.row_index, []).append(
            InlineKeyboardButton(
                text=f"{row.emoji or ''} {row.label}".strip(),
                callback_data=f"interface:preview-action:{row.id}",
            )
        )
    keyboard = [grouped[index] for index in sorted(grouped)]
    keyboard.append([InlineKeyboardButton(text="⬅️ رجوع للمسودة", callback_data="interface:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@router.callback_query(F.data == "interface:preview")
async def interface_preview(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile, rows = list_menu_items(session, owner_id=owner.id)
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            "👁 معاينة آمنة\n\n"
            "هذه هي الأزرار كما ستظهر للعميل بعد النشر. الضغط هنا يشرح الإجراء فقط "
            "ولا يرسل ردًا أو يفتح رابطًا أو يبدأ إجراءً.",
            reply_markup=_preview_keyboard(rows),
        )
    await safe_callback_answer(callback, f"معاينة وضع {profile.mode}")


@router.callback_query(F.data.startswith("interface:preview-action:"))
async def interface_preview_action(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = (
            get_owned_menu_item(
                session,
                owner_id=owner.id,
                item_id=int(raw_id),
                required_scope="DRAFT",
            )
            if raw_id.isdigit()
            else None
        )
    if pair is None:
        await safe_callback_answer(callback, "هذا الزر لم يعد في المسودة.", show_alert=True)
        return
    _, row = pair
    await safe_callback_answer(
        callback,
        f"عند النشر: {menu_action_text(row.action_type)}",
        show_alert=True,
    )


@router.callback_query(F.data == "interface:publish")
async def interface_publish_request(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    if callback.message:
        await callback.message.answer(
            "هل تريد نشر هذه المسودة للعملاء الآن؟\n"
            "سيبقى الإصدار السابق محفوظًا في قاعدة البيانات للتدقيق.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ نعم، نشر الآن",
                            callback_data="interface:publish:confirm",
                        ),
                        InlineKeyboardButton(text="إلغاء", callback_data="interface:home"),
                    ]
                ]
            ),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data == "interface:publish:confirm")
async def interface_publish_confirm(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        try:
            published = publish_menu_draft(session, owner_id=owner.id)
        except ValueError:
            await safe_callback_answer(callback, "لا توجد مسودة جاهزة للنشر.", show_alert=True)
            return
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="INTERFACE_MENU_PUBLISHED",
            entity_type="MENU_PROFILE",
            entity_id=published.id,
        )
        session.commit()
        profile, rows = list_menu_items(session, owner_id=owner.id)
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            "✅ تم نشر الواجهة للعملاء، وأنشأت لك نسخة مسودة جديدة للتعديلات القادمة.\n\n"
            + _render_home(profile.mode, rows),
            reply_markup=_home_keyboard(profile.mode, rows),
        )
    await safe_callback_answer(callback, "تم النشر")


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
        MenuAction.START_PAYMENT.value,
    }:
        await safe_callback_answer(callback, "نوع زر غير مدعوم", show_alert=True)
        return
    await state.clear()
    await state.update_data(interface_action=action)
    await state.set_state(InterfaceStates.button_label)
    if callback.message:
        await callback.message.answer("اكتب اسم الزر كما سيظهر للعميل، ويمكنك بدء الاسم بإيموجي:")
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("interface:edit:"))
async def interface_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = (
            get_owned_menu_item(
                session,
                owner_id=owner.id,
                item_id=int(raw_id),
                required_scope="DRAFT",
            )
            if raw_id.isdigit()
            else None
        )
    if pair is None:
        await safe_callback_answer(callback, "لم أجد الزر في المسودة.", show_alert=True)
        return
    _, row = pair
    await state.clear()
    await state.update_data(
        interface_edit_id=row.id,
        interface_action=row.action_type,
        interface_payload=dict(row.action_config_json or {}),
    )
    await state.set_state(InterfaceStates.button_label)
    if callback.message:
        await callback.message.answer(
            f"الاسم الحالي: {row.emoji or ''} {row.label}\n\n"
            "أرسل الاسم الجديد كما سيظهر للعميل."
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("interface:move:"))
async def interface_move(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or not parts[2].isdigit() or parts[3] not in {"up", "down"}:
        await safe_callback_answer(callback, "اختيار غير صالح.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile, rows = list_menu_items(session, owner_id=owner.id)
        index = next((i for i, row in enumerate(rows) if row.id == int(parts[2])), None)
        if index is None:
            await safe_callback_answer(callback, "لم أجد الزر في المسودة.", show_alert=True)
            return
        target = index - 1 if parts[3] == "up" else index + 1
        if target < 0 or target >= len(rows):
            await safe_callback_answer(callback, "الزر في نهاية هذا الاتجاه.")
            return
        rows[index], rows[target] = rows[target], rows[index]
        for order, row in enumerate(rows):
            row.sort_order = order
            row.row_index = order // 2
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="INTERFACE_BUTTON_REORDERED",
            entity_type="MENU_ITEM",
            entity_id=int(parts[2]),
        )
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            _render_home(profile.mode, rows),
            reply_markup=_home_keyboard(profile.mode, rows),
        )
    await safe_callback_answer(callback, "تم ترتيب المسودة")


@router.callback_query(F.data == "interface:add-flow")
async def interface_add_flow(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flows = list(
            session.scalars(
                select(Flow).where(
                    Flow.owner_id == owner.id,
                    Flow.status == FlowStatus.PUBLISHED.value,
                )
            )
        )
    if callback.message:
        if not flows:
            await callback.message.answer(
                "لا توجد إجراءات منشورة بعد. أنشئ الإجراء واختبره وانشره من قسم الأتمتة أولًا."
            )
        else:
            await callback.message.answer(
                "اختر الإجراء الذي تريد إظهاره كزر للعميل:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=flow.name[:60],
                                callback_data=f"interface:add-flow:{flow.id}",
                            )
                        ]
                        for flow in flows[:20]
                    ]
                ),
            )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("interface:add-flow:"))
async def interface_add_flow_value(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "اختيار غير صالح.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flow = session.scalar(
            select(Flow).where(
                Flow.id == int(raw_id),
                Flow.owner_id == owner.id,
                Flow.status == FlowStatus.PUBLISHED.value,
            )
        )
        if flow is None:
            await safe_callback_answer(callback, "الإجراء غير متاح.", show_alert=True)
            return
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
            label=flow.name[:128],
            emoji="🧭",
            action_type=MenuAction.START_FLOW.value,
            action_config_json={"flow_id": flow.id},
            row_index=active_count // 2,
            sort_order=active_count,
            visibility_rules_json={"mode": "ALWAYS"},
            enabled=True,
        )
        session.add(row)
        session.commit()
    await safe_callback_answer(callback, "تمت إضافة زر الإجراء")


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
    if action == MenuAction.START_PAYMENT.value:
        await state.set_state(InterfaceStates.payment_price)
        await message.answer("كم نجمة سعر هذا المنتج أو الخدمة؟ أرسل رقمًا صحيحًا أكبر من صفر.")
        return
    if action == MenuAction.HANDOFF.value:
        await state.update_data(interface_payload={})
        await _ask_visibility(message, state)
        return
    if action == MenuAction.START_FLOW.value and data.get("interface_edit_id"):
        await _ask_visibility(message, state)
        return
    await state.set_state(InterfaceStates.button_payload)
    if action == MenuAction.OPEN_URL.value:
        await message.answer("أرسل رابط الزر ويجب أن يبدأ بـ https:// أو http://")
    else:
        await message.answer("أرسل النص الذي تريد أن يرسله هذا الزر للعميل:")


@router.message(InterfaceStates.payment_price)
async def interface_payment_price(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    raw = (message.text or "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 1_000_000:
        await message.answer("أرسل عددًا صحيحًا من 1 إلى 1,000,000 نجمة.")
        return
    await state.update_data(payment_stars=int(raw))
    await state.set_state(InterfaceStates.payment_description)
    await message.answer(
        "اكتب وصفًا واضحًا لما سيحصل عليه العميل بعد الدفع (حتى 255 حرفًا)."
    )


@router.message(InterfaceStates.payment_description)
async def interface_payment_description(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    description = (message.text or "").strip()
    if not description:
        await message.answer("وصف المنتج أو الخدمة مطلوب قبل إنشاء زر الدفع.")
        return
    await state.update_data(payment_description=description[:255])
    await state.set_state(InterfaceStates.payment_success)
    await message.answer(
        "اكتب الرسالة التي تصل للعميل بعد تأكيد Telegram نجاح الدفع. "
        "لا تُرسل هذه الرسالة عند فتح الفاتورة أو مرحلة ما قبل الدفع."
    )


@router.message(InterfaceStates.payment_success)
async def interface_payment_success(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    success = (message.text or "").strip()
    if not success:
        await message.answer("اكتب رسالة تأكيد واضحة للعميل بعد نجاح الدفع.")
        return
    data = await state.get_data()
    await state.update_data(
        interface_payload={
            "title": str(data.get("interface_label") or "دفع")[:32],
            "description": str(data.get("payment_description") or "")[:255],
            "stars": int(data.get("payment_stars") or 0),
            "success_message": success[:4000],
        }
    )
    await _ask_visibility(message, state)


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
        edit_id = data.get("interface_edit_id")
        pair = (
            get_owned_menu_item(
                session,
                owner_id=owner.id,
                item_id=int(edit_id),
                required_scope="DRAFT",
            )
            if edit_id
            else None
        )
        if edit_id and pair is None:
            await state.clear()
            await message.answer("لم يعد الزر موجودًا في المسودة. افتح الواجهة وحاول مرة أخرى.")
            return
        row = pair[1] if pair is not None else MenuItem(menu_profile_id=profile.id)
        row.parent_item_id = None
        row.label = label[:128]
        row.emoji = emoji
        row.action_type = action
        row.action_config_json = payload
        if pair is None:
            row.row_index = active_count // 2
            row.sort_order = active_count
        row.visibility_rules_json = visibility_rules
        row.enabled = True
        if pair is None:
            session.add(row)
        session.flush()
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="INTERFACE_BUTTON_UPDATED" if edit_id else "INTERFACE_BUTTON_DRAFTED",
            entity_type="MENU_ITEM",
            entity_id=row.id,
        )
        session.commit()
        item_id = row.id
    await state.clear()
    visibility = "🎯 سياقي" if visibility_rules.get("mode") == "CONTEXTUAL" else "🌐 دائم"
    await message.answer(
        f"✅ تم حفظ الزر #{item_id} في المسودة — {visibility}.\n"
        "عاينه ثم اضغط «نشر المسودة» عندما يصبح جاهزًا.",
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
        pair = get_owned_menu_item(
            session,
            owner_id=owner.id,
            item_id=int(raw_id),
            required_scope="DRAFT",
        )
        if pair is None:
            await safe_callback_answer(callback, "لم أجد الزر", show_alert=True)
            return
        _, row = pair
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="INTERFACE_BUTTON_DELETE",
            entity_type="MENU_ITEM",
            entity_id=row.id,
        )
        session.delete(row)
        session.commit()
        profile, rows = list_menu_items(session, owner_id=owner.id)
        mode = profile.mode
    if callback.message:
        await callback.message.edit_text(
            _render_home(mode, rows),
            reply_markup=_home_keyboard(mode, rows),
        )
    await safe_callback_answer(callback, "تم حذف الزر من المسودة")


@router.callback_query(F.data.startswith("m:"))
async def customer_menu_action(callback: CallbackQuery, bot: Bot) -> None:
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit() or callback.message is None:
        await safe_callback_answer(callback)
        return

    business_connection_id = getattr(callback.message, "business_connection_id", None)
    chat = getattr(callback.message, "chat", None)
    if not business_connection_id or chat is None:
        await safe_callback_answer(callback, "تعذر ربط الزر بهذه المحادثة.", show_alert=True)
        return

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_menu_item(
            session,
            owner_id=owner.id,
            item_id=int(raw_id),
            required_scope="DEFAULT",
        )
        session.commit()
    if pair is None:
        await safe_callback_answer(callback, "هذا الزر لم يعد متاحًا.", show_alert=True)
        return
    _, item = pair
    if not item.enabled:
        await safe_callback_answer(callback, "هذا الزر متوقف حاليًا.", show_alert=True)
        return

    adapter = AiogramTelegramAdapter(bot)
    config = dict(item.action_config_json or {})
    if item.action_type == MenuAction.SEND_MESSAGE.value:
        await safe_callback_answer(callback, "تم استلام اختيارك")
        text = str(config.get("text") or "").strip()
        if text:
            await adapter.send_text(
                business_connection_id=business_connection_id,
                chat_id=chat.id,
                text=text,
            )
        return

    if item.action_type == MenuAction.HANDOFF.value:
        await safe_callback_answer(callback, "تم تحويل طلبك")
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
        return

    if item.action_type == MenuAction.START_FLOW.value:
        await safe_callback_answer(callback, "جارٍ بدء الإجراء")
        raw_flow_id = config.get("flow_id")
        if not isinstance(raw_flow_id, int) and not str(raw_flow_id).isdigit():
            return
        with SessionLocal() as session:
            owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
            conversation = ConversationRepository.get_by_chat(
                session,
                owner_id=owner.id,
                chat_id=chat.id,
            )
            if conversation is None:
                return
            try:
                turn = start_flow(
                    session,
                    conversation=conversation,
                    flow_id=int(raw_flow_id),
                )
            except ValueError:
                await adapter.send_text(
                    business_connection_id=business_connection_id,
                    chat_id=chat.id,
                    text="هذا الإجراء غير متاح حاليًا. اكتب طلبك وسيتابعك السكرتير.",
                    attach_default_menu=False,
                )
                return
            session.commit()
            conversation_id = conversation.id
        from app.telegram.bootstrap import _send_flow_turn

        await _send_flow_turn(
            bot,
            connection_id=business_connection_id,
            conversation_id=conversation_id,
            turn=turn,
        )
        return

    if item.action_type == MenuAction.START_PAYMENT.value:
        await safe_callback_answer(callback, "جارٍ تجهيز رابط الدفع")
        title = str(config.get("title") or item.label).strip()[:32]
        description = str(config.get("description") or "").strip()[:255]
        success_message = str(config.get("success_message") or "").strip()[:4000]
        raw_stars = config.get("stars")
        if not str(raw_stars).isdigit() or not title or not description or not success_message:
            await adapter.send_text(
                business_connection_id=business_connection_id,
                chat_id=chat.id,
                text="إعداد الدفع لهذا الخيار غير مكتمل. تم تنبيه المسؤول ولم تُنشأ فاتورة.",
                attach_default_menu=False,
            )
            await bot.send_message(
                chat_id=settings.owner_telegram_id,
                text=f"⚠️ زر الدفع «{item.label}» يحتاج مراجعة إعداداته قبل استخدامه.",
            )
            return
        with SessionLocal() as session:
            owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
            conversation = ConversationRepository.get_by_chat(
                session,
                owner_id=owner.id,
                chat_id=chat.id,
            )
            if conversation is None:
                return
            contact = session.get(Contact, conversation.contact_id)
            if contact is None or contact.telegram_user_id != callback.from_user.id:
                return
            order = create_stars_order(
                session,
                conversation=conversation,
                telegram_user_id=callback.from_user.id,
                menu_item_id=item.id,
                title=title,
                description=description,
                amount=int(raw_stars),
                success_message=success_message,
            )
            session.commit()
            order_id = order.id
            invoice_payload = order.invoice_payload
        try:
            invoice_url = await bot.create_invoice_link(
                title=title,
                description=description,
                payload=invoice_payload,
                currency="XTR",
                prices=[LabeledPrice(label=title, amount=int(raw_stars))],
                business_connection_id=business_connection_id,
                provider_token=None,
            )
            terms_note = settings.payment_terms_text.strip()
            checkout_text = (
                f"⭐ {title}\n\n{description}\n\n"
                f"القيمة: {int(raw_stars)} نجمة\n"
                f"الشروط: {terms_note}"
            )
            buttons = [
                [
                    InlineKeyboardButton(
                        text=f"الدفع بـ {int(raw_stars)} نجمة ⭐",
                        url=invoice_url,
                    )
                ]
            ]
            if settings.payment_terms_url.startswith(("https://", "http://")):
                buttons.append(
                    [InlineKeyboardButton(text="شروط الخدمة", url=settings.payment_terms_url)]
                )
            await adapter.send_text(
                business_connection_id=business_connection_id,
                chat_id=chat.id,
                text=checkout_text[:4000],
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                attach_default_menu=False,
                native_rich=False,
            )
        except Exception:
            with SessionLocal() as session:
                failed = session.get(PaymentOrder, order_id)
                if failed is not None and failed.status == PaymentStatus.CREATED.value:
                    failed.status = PaymentStatus.FAILED.value
                    session.commit()
            await bot.send_message(
                chat_id=settings.owner_telegram_id,
                text=(
                    f"⚠️ تعذر تجهيز رابط الدفع للطلب #{order_id}. "
                    "لم أعد المحاولة تلقائيًا."
                ),
            )
            logger.exception("stars_invoice_link_or_delivery_failed order=%s", order_id)
        return

    await safe_callback_answer(callback, "هذا الإجراء غير مدعوم حاليًا.", show_alert=True)
