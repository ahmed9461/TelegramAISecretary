from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.admin.service import (
    get_owned_contact,
    get_owned_conversation,
    list_owner_contacts,
    list_owner_conversations,
    list_pending_approvals,
    refresh_conversation_summary,
    set_contact_permission,
    set_conversation_state,
)
from app.approvals.service import preview_claim
from app.audit.service import write_audit_log
from app.config import get_settings
from app.db.enums import ConversationState, GlobalMode
from app.db.models import BusinessConnection, Contact, Conversation
from app.db.models import Message as DBMessage
from app.db.repositories import ApprovalRepository, ConversationRepository, OwnerRepository
from app.db.session import SessionLocal
from app.security.owner import OwnerGuard
from app.telegram.adapter import AiogramTelegramAdapter
from app.telegram.callback_safety import safe_callback_answer
from app.telegram.owner_ui import approval_keyboard, main_admin_keyboard

logger = logging.getLogger(__name__)
router = Router(name="admin_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)

_PAGE_SIZE = 8
_STATE_LABELS = {
    ConversationState.AI_AUTO.value: "🟢 تلقائي",
    ConversationState.AI_APPROVAL.value: "🟡 بموافقتك",
    ConversationState.OBSERVE_ONLY.value: "👁 مراقبة فقط",
    ConversationState.HUMAN_TAKEOVER.value: "👤 متابعة بشرية",
    ConversationState.ESCALATED.value: "🔔 تحتاج تدخلك",
    ConversationState.PAUSED.value: "⏸ متوقفة",
    ConversationState.EXCLUDED.value: "🚫 مستبعدة",
}


class AdminStates(StatesGroup):
    one_time_reply = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _back_main() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="⬅️ القائمة الرئيسية", callback_data="brain:main")]


def _name(contact: Contact) -> str:
    return (contact.display_name or contact.username or "شخص بلا اسم")[:60]


def _pagination(prefix: str, offset: int, total: int) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if offset > 0:
        row.append(
            InlineKeyboardButton(
                text="السابق",
                callback_data=f"{prefix}:{max(0, offset - _PAGE_SIZE)}",
            )
        )
    if offset + _PAGE_SIZE < total:
        row.append(
            InlineKeyboardButton(
                text="التالي",
                callback_data=f"{prefix}:{offset + _PAGE_SIZE}",
            )
        )
    return row


def _offset(data: str | None, prefix: str) -> int:
    parts = (data or "").split(":")
    if len(parts) == 3 and f"{parts[0]}:{parts[1]}" == prefix and parts[2].isdigit():
        return int(parts[2])
    return 0


@router.callback_query(F.data.startswith("a:conversations"))
async def conversations_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    offset = _offset(callback.data, "a:conversations")
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows, total = list_owner_conversations(
            session, owner_id=owner.id, offset=offset, limit=_PAGE_SIZE
        )
    keyboard: list[list[InlineKeyboardButton]] = []
    for row in rows:
        badge = f" • {row.pending_count} بانتظارك" if row.pending_count else ""
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{_name(row.contact)} — "
                        f"{_STATE_LABELS.get(row.conversation.state, 'حالة خاصة')}{badge}"
                    )[:64],
                    callback_data=f"admin:conv:{row.conversation.id}",
                )
            ]
        )
    page = _pagination("a:conversations", offset, total)
    if page:
        keyboard.append(page)
    keyboard.append(_back_main())
    text = (
        "💬 المحادثات\n\n"
        f"العدد: {total}\n"
        "اختر محادثة لعرض آخر السياق أو التدخل أو إعادة السكرتير."
        if total
        else "💬 المحادثات\n\nلا توجد محادثات مسجلة حتى الآن."
    )
    if callback.message:
        await callback.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    await safe_callback_answer(callback)


def _conversation_keyboard(conversation: Conversation, contact: Contact) -> InlineKeyboardMarkup:
    cid = conversation.id
    rows = [
        [
            InlineKeyboardButton(text="💬 رد مرة واحدة", callback_data=f"admin:reply:{cid}"),
            InlineKeyboardButton(text="📋 عرض الملخص", callback_data=f"admin:summary:{cid}"),
        ],
        [
            InlineKeyboardButton(text="🤖 تلقائي", callback_data=f"admin:state:{cid}:AI_AUTO"),
            InlineKeyboardButton(
                text="🟡 بموافقتي", callback_data=f"admin:state:{cid}:AI_APPROVAL"
            ),
        ],
        [
            InlineKeyboardButton(
                text="👤 أتولى المحادثة",
                callback_data=f"admin:state:{cid}:HUMAN_TAKEOVER",
            ),
            InlineKeyboardButton(
                text="👁 مراقبة", callback_data=f"admin:state:{cid}:OBSERVE_ONLY"
            ),
        ],
        [
            InlineKeyboardButton(text="⏸ إيقاف", callback_data=f"admin:state:{cid}:PAUSED"),
            InlineKeyboardButton(text="🚫 استبعاد", callback_data=f"admin:state:{cid}:EXCLUDED"),
        ],
        [
            InlineKeyboardButton(
                text="🧠 ذاكرة الشخص", callback_data=f"memory:contact:{contact.id}"
            )
        ],
        [InlineKeyboardButton(text="⬅️ المحادثات", callback_data="a:conversations")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _conversation_text(
    conversation: Conversation, contact: Contact, messages: list[DBMessage]
) -> str:
    lines = [
        f"💬 {_name(contact)}",
        "",
        f"الحالة: {_STATE_LABELS.get(conversation.state, 'حالة خاصة')}",
        f"الذكاء لهذا الشخص: {'مسموح' if contact.ai_allowed else 'متوقف'}",
        f"الذاكرة: {'مسموحة' if contact.memory_allowed else 'متوقفة'}",
    ]
    if contact.username:
        lines.append(f"المعرّف: @{contact.username}")
    if messages:
        lines.append("\nآخر السياق:")
        for row in reversed(messages):
            body = " ".join((row.text or "").split()) or f"[{row.content_type.lower()}]"
            arrow = "← العميل" if row.direction == "IN" else "→ المالك/السكرتير"
            lines.append(f"{arrow}: {body[:260]}")
    return "\n".join(lines)[:4000]


@router.callback_query(F.data.startswith("admin:conv:"))
async def conversation_detail(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "المحادثة غير صالحة.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_conversation(
            session, owner_id=owner.id, conversation_id=int(raw_id)
        )
        if pair is None:
            await safe_callback_answer(callback, "لم أجد المحادثة.", show_alert=True)
            return
        conversation, contact = pair
        messages = list(
            session.scalars(
                select(DBMessage)
                .where(
                    DBMessage.conversation_id == conversation.id,
                    DBMessage.is_deleted.is_(False),
                )
                .order_by(DBMessage.created_at.desc(), DBMessage.id.desc())
                .limit(6)
            )
        )
        text = _conversation_text(conversation, contact, messages)
        keyboard = _conversation_keyboard(conversation, contact)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin:state:"))
async def conversation_state(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    parts = (callback.data or "").split(":")
    if len(parts) != 4 or not parts[2].isdigit():
        await safe_callback_answer(callback, "الإجراء غير صالح.", show_alert=True)
        return
    try:
        target = ConversationState(parts[3])
    except ValueError:
        await safe_callback_answer(callback, "الحالة غير صالحة.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        try:
            updated = set_conversation_state(
                session,
                owner_id=owner.id,
                conversation_id=int(parts[2]),
                target=target,
            )
        except ValueError:
            updated = None
        if updated is not None:
            session.commit()
    if updated is None:
        await safe_callback_answer(callback, "تعذر تغيير حالة المحادثة.", show_alert=True)
        return
    await safe_callback_answer(
        callback, f"تم تحديث المحادثة إلى {_STATE_LABELS.get(updated.state, 'الحالة المختارة')}"
    )
    if callback.message:
        callback.data = f"admin:conv:{updated.id}"
        await conversation_detail(callback)


@router.callback_query(F.data.startswith("admin:summary:"))
async def conversation_summary(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_conversation(
            session, owner_id=owner.id, conversation_id=int(raw_id)
        )
        if pair is None:
            await safe_callback_answer(callback, "لم أجد المحادثة.", show_alert=True)
            return
        conversation, _ = pair
        summary = refresh_conversation_summary(session, conversation=conversation)
        session.commit()
    if callback.message:
        await callback.message.answer(
            f"📋 ملخص السياق الحالي\n\n{summary or 'لا يوجد نص كافٍ لبناء ملخص بعد.'}"
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin:reply:"))
async def one_time_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback)
        return
    await state.clear()
    await state.update_data(admin_conversation_id=int(raw_id))
    await state.set_state(AdminStates.one_time_reply)
    if callback.message:
        await callback.message.answer(
            "💬 اكتب الرد الذي تريد إرساله مرة واحدة. ستبقى حالة المحادثة كما هي.\n\n"
            "أرسل «إلغاء» للتراجع."
        )
    await safe_callback_answer(callback)


@router.message(AdminStates.one_time_reply)
async def one_time_reply_send(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    text = (message.text or "").strip()
    if text.casefold() in {"إلغاء", "الغاء", "cancel"}:
        await state.clear()
        await message.answer("تم إلغاء الرد.", reply_markup=main_admin_keyboard())
        return
    if not text:
        await message.answer("اكتب ردًا نصيًا واضحًا أو أرسل «إلغاء».")
        return
    data = await state.get_data()
    conversation_id = int(data.get("admin_conversation_id") or 0)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_conversation(
            session, owner_id=owner.id, conversation_id=conversation_id
        )
        if pair is None or not pair[0].business_connection_id:
            await state.clear()
            await message.answer("تعذر العثور على اتصال صالح لهذه المحادثة.")
            return
        conversation, _ = pair
        connection_id = conversation.business_connection_id
        chat_id = conversation.telegram_chat_id

    from app.telegram.bootstrap import _live_reply_permission

    can_send, _ = await _live_reply_permission(bot, connection_id)
    if not can_send:
        await message.answer("صلاحية الرد غير متاحة حاليًا في Telegram. لم يتم الإرسال.")
        return
    try:
        sent_id = await AiogramTelegramAdapter(bot).send_text(
            business_connection_id=connection_id,
            chat_id=chat_id,
            text=text[:4000],
            attach_default_menu=False,
        )
    except Exception:
        logger.exception("owner_one_time_reply_uncertain conversation=%s", conversation_id)
        await state.clear()
        await message.answer(
            "تعذر تأكيد الإرسال، لذلك لم أكرر المحاولة تلقائيًا حتى لا يصل الرد مرتين."
        )
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        pair = get_owned_conversation(
            session, owner_id=owner.id, conversation_id=conversation_id
        )
        if pair is not None:
            conversation, _ = pair
            ApprovalRepository.invalidate_pending(session, conversation.id, status="SUPERSEDED")
            ConversationRepository.append_outgoing(
                session,
                conversation=conversation,
                telegram_message_id=sent_id,
                text=text[:4000],
            )
            write_audit_log(
                session,
                owner_id=owner.id,
                actor="OWNER_TELEGRAM",
                action="ONE_TIME_REPLY_SENT",
                entity_type="CONVERSATION",
                entity_id=conversation.id,
            )
            session.commit()
    await state.clear()
    await message.answer("✅ تم إرسال الرد مرة واحدة، وبقي وضع المحادثة دون تغيير.")


@router.callback_query(F.data == "a:pending")
async def pending_home(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_pending_approvals(session, owner_id=owner.id)
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{_name(contact)} — رد #{approval.id}"[:64],
                callback_data=f"admin:approval:{approval.id}",
            )
        ]
        for approval, _, contact in rows
    ]
    keyboard.append(_back_main())
    text = (
        f"🔔 بانتظارك\n\nلديك {len(rows)} رد صالح للمراجعة."
        if rows
        else "🔔 بانتظارك\n\nلا توجد ردود معلقة حاليًا."
    )
    if callback.message:
        await callback.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin:approval:"))
async def pending_detail(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        preview = preview_claim(session, int(raw_id))
    if preview is None:
        await safe_callback_answer(callback, "انتهت صلاحية هذا الرد.", show_alert=True)
        return
    if callback.message:
        await callback.message.edit_text(
            f"🔔 رد بانتظارك #{raw_id}\n\n{preview.text[:3400]}",
            reply_markup=approval_keyboard(int(raw_id)),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("a:contacts"))
async def contacts_home(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    offset = _offset(callback.data, "a:contacts")
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows, total = list_owner_contacts(
            session, owner_id=owner.id, offset=offset, limit=_PAGE_SIZE
        )
    keyboard = [
        [
            InlineKeyboardButton(
                text=(
                    f"{'🚫 ' if row.contact.is_excluded else ''}{_name(row.contact)} — "
                    f"{'ذاكرة' if row.contact.memory_allowed else 'بلا ذاكرة'}"
                )[:64],
                callback_data=f"admin:contact:{row.contact.id}",
            )
        ]
        for row in rows
    ]
    page = _pagination("a:contacts", offset, total)
    if page:
        keyboard.append(page)
    keyboard.append(_back_main())
    text = (
        f"👥 الأشخاص\n\nالعدد: {total}\nاختر شخصًا لإدارة الذكاء والذاكرة والاستبعاد."
        if total
        else "👥 الأشخاص\n\nلا يوجد أشخاص مسجلون حتى الآن."
    )
    if callback.message:
        await callback.message.edit_text(
            text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    await safe_callback_answer(callback)


def _contact_keyboard(contact: Contact, conversation: Conversation | None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text="⛔ إيقاف الذكاء" if contact.ai_allowed else "✅ السماح للذكاء",
                callback_data=f"admin:contactperm:{contact.id}:AI:{int(not contact.ai_allowed)}",
            )
        ],
        [
            InlineKeyboardButton(
                text="⛔ منع الذاكرة" if contact.memory_allowed else "✅ السماح بالذاكرة",
                callback_data=(
                    f"admin:contactperm:{contact.id}:MEMORY:{int(not contact.memory_allowed)}"
                ),
            )
        ],
        [InlineKeyboardButton(text="🧠 عرض الذاكرة", callback_data=f"memory:contact:{contact.id}")],
    ]
    if conversation is not None:
        rows.append(
            [
                InlineKeyboardButton(
                    text="✅ إلغاء الاستبعاد" if contact.is_excluded else "🚫 استبعاد الشخص",
                    callback_data=(
                        f"admin:state:{conversation.id}:"
                        f"{'AI_APPROVAL' if contact.is_excluded else 'EXCLUDED'}"
                    ),
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="💬 فتح المحادثة", callback_data=f"admin:conv:{conversation.id}"
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ الأشخاص", callback_data="a:contacts")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("admin:contact:"))
async def contact_detail(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        contact = get_owned_contact(session, owner_id=owner.id, contact_id=int(raw_id))
        if contact is None:
            await safe_callback_answer(callback, "لم أجد الشخص.", show_alert=True)
            return
        conversation = session.scalar(
            select(Conversation)
            .where(Conversation.owner_id == owner.id, Conversation.contact_id == contact.id)
            .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
            .limit(1)
        )
        text = (
            f"👤 {_name(contact)}\n\n"
            f"الذكاء: {'مسموح' if contact.ai_allowed else 'متوقف'}\n"
            f"الذاكرة: {'مسموحة' if contact.memory_allowed else 'متوقفة'}\n"
            f"الاستبعاد: {'نعم' if contact.is_excluded else 'لا'}"
        )
        keyboard = _contact_keyboard(contact, conversation)
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin:contactperm:"))
async def contact_permission(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    parts = (callback.data or "").split(":")
    if (
        len(parts) != 5
        or not parts[2].isdigit()
        or parts[3] not in {"AI", "MEMORY"}
        or parts[4] not in {"0", "1"}
    ):
        await safe_callback_answer(callback, "الإجراء غير صالح.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        contact = set_contact_permission(
            session,
            owner_id=owner.id,
            contact_id=int(parts[2]),
            permission=parts[3],
            enabled=parts[4] == "1",
        )
        if contact is not None:
            session.commit()
    if contact is None:
        await safe_callback_answer(callback, "لم أجد الشخص.", show_alert=True)
        return
    await safe_callback_answer(callback, "تم حفظ الإعداد")
    callback.data = f"admin:contact:{contact.id}"
    await contact_detail(callback)


@router.callback_query(F.data == "a:security")
async def security_home(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        connections = list(
            session.scalars(
                select(BusinessConnection)
                .where(BusinessConnection.owner_id == owner.id)
                .order_by(BusinessConnection.updated_at.desc(), BusinessConnection.id.desc())
            )
        )
    lines = [
        "🛡️ الأمان والاتصال",
        "",
        "المعرفة الخاصة وملاحظات المالك لا تدخل ردود العملاء.",
        "كل إرسال تلقائي يعيد فحص صلاحية Telegram لحظة الإرسال.",
        "لا يوجد تعلم صامت؛ الذاكرة والمعرفة الدائمة تحتاج اعتمادك.",
    ]
    keyboard: list[list[InlineKeyboardButton]] = []
    if not connections:
        lines.append("\nلا يوجد اتصال Telegram Business مسجل بعد.")
    for row in connections:
        can_reply = bool((row.rights_json or {}).get("can_reply"))
        lines.append(
            f"\nالاتصال #{row.id}: {'فعال' if row.is_enabled else 'متوقف'} — "
            f"{'الرد مسموح' if can_reply else 'صلاحية الرد غير متاحة'}"
        )
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"🔄 فحص الاتصال #{row.id}",
                    callback_data=f"admin:connection:{row.id}",
                )
            ]
        )
    keyboard.append(_back_main())
    if callback.message:
        await callback.message.edit_text(
            "\n".join(lines)[:4000],
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin:connection:"))
async def security_refresh(callback: CallbackQuery, bot: Bot) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = session.scalar(
            select(BusinessConnection).where(
                BusinessConnection.id == int(raw_id), BusinessConnection.owner_id == owner.id
            )
        )
        connection_id = row.telegram_connection_id if row is not None else None
    if not connection_id:
        await safe_callback_answer(callback, "لم أجد الاتصال.", show_alert=True)
        return
    try:
        live = await bot.get_business_connection(business_connection_id=connection_id)
    except Exception:
        logger.exception("owner_connection_refresh_failed id=%s", raw_id)
        await safe_callback_answer(
            callback, "تعذر فحص Telegram الآن. لم تتغير الإعدادات.", show_alert=True
        )
        return
    from app.telegram.bootstrap import _persist_business_connection

    if not _persist_business_connection(live):
        await safe_callback_answer(callback, "اتصال غير مطابق للمالك.", show_alert=True)
        return
    await safe_callback_answer(callback, "تم تحديث حالة الاتصال")
    callback.data = "a:security"
    await security_home(callback)


@router.callback_query(F.data == "a:pause")
async def pause_home(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        mode = owner.default_mode
    text = (
        "⏸ التحكم السريع\n\n"
        "الحالة الحالية: "
        f"{'متوقف بالكامل' if mode == GlobalMode.OFF.value else 'يعمل حسب إعدادات السلوك'}"
        "\n\n"
        "الإيقاف يمنع ردود الذكاء الاصطناعي، لكنه لا يحذف المحادثات أو المعرفة أو الذاكرة."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⛔ إيقاف الآن", callback_data="admin:global:OFF")],
            [
                InlineKeyboardButton(
                    text="▶️ تشغيل بموافقتي", callback_data="admin:global:APPROVAL"
                )
            ],
            _back_main(),
        ]
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=keyboard)
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("admin:global:"))
async def set_global_mode(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    mode = (callback.data or "").rsplit(":", 1)[-1]
    if mode not in {GlobalMode.OFF.value, GlobalMode.APPROVAL.value}:
        await safe_callback_answer(callback, "الوضع غير صالح.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        previous = owner.default_mode
        owner.default_mode = mode
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="GLOBAL_MODE_CHANGED",
            entity_type="OWNER",
            entity_id=owner.id,
            metadata={"from_mode": previous, "to_mode": mode},
        )
        session.commit()
    await safe_callback_answer(
        callback, "تم إيقاف السكرتير" if mode == GlobalMode.OFF.value else "تم التشغيل بموافقتك"
    )
    callback.data = "a:pause"
    await pause_home(callback)
