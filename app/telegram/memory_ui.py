from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select, update

from app.ai.factory import build_ai_provider
from app.brain.models import ContactMemory, MemorySuggestion
from app.brain.service import get_contact_memory, memory_for_ai, upsert_contact_memory
from app.config import get_settings
from app.db.models import Contact, Conversation
from app.db.models import Message as DBMessage
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.memory.privacy import should_reject_long_term_memory
from app.memory.service import (
    approve_memory_suggestion,
    create_memory_suggestion,
    export_contact_memory,
    propose_memory_update,
    reject_memory_suggestion,
)
from app.security.owner import OwnerGuard

logger = logging.getLogger(__name__)
router = Router(name="memory_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class MemoryStates(StatesGroup):
    summary = State()
    facts = State()
    preferences = State()
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
    share_label = (
        "🟢 مشاركة الملخص مع السكرتير" if share_with_ai else "⚪ عدم مشاركة الملخص مع السكرتير"
    )
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
                    text="📌 حقائق مؤكدة",
                    callback_data=f"memory:facts:{contact_id}",
                ),
                InlineKeyboardButton(
                    text="💬 تفضيلات التواصل",
                    callback_data=f"memory:preferences:{contact_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✨ اقتراح من المحادثة",
                    callback_data=f"memory:suggest:{contact_id}",
                ),
                InlineKeyboardButton(
                    text="📤 تصدير الذاكرة",
                    callback_data=f"memory:export:{contact_id}",
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
                    callback_data=f"memory:clear:request:{contact_id}",
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
    facts = _format_mapping(memory.facts_json if memory else {})
    preferences = _format_mapping(memory.preferences_json if memory else {})
    retention = "—"
    if memory and memory.retention_until:
        retention = memory.retention_until.strftime("%Y-%m-%d")
    return (
        "👤 ذاكرة الشخص\n\n"
        f"الاسم: {contact.display_name or '—'}\n"
        f"المعرف: {username}\n"
        f"رقم الحساب في Telegram: {contact.telegram_user_id}\n\n"
        f"🧠 الملخص: {summary[:1200]}\n\n"
        f"📌 حقائق مؤكدة:\n{facts}\n\n"
        f"💬 تفضيلات التواصل:\n{preferences}\n\n"
        f"🔒 ملاحظة خاصة: {private_notes[:800]}\n\n"
        f"مشاركة الملخص مع السكرتير: {'نعم' if shared and allowed else 'لا'}\n\n"
        f"مراجعة الذاكرة حتى: {retention}\n\n"
        "الملاحظة الخاصة لا تدخل إلى خدمة الصياغة مطلقًا، ولا تُضاف معلومات من "
        "المحادثات دون موافقتك الصريحة."
    )


def _format_mapping(value: dict | None) -> str:
    rows = [f"• {key}: {item}" for key, item in (value or {}).items()]
    return "\n".join(rows) if rows else "—"


def _parse_mapping(text: str) -> dict[str, str]:
    if text.strip() == "—":
        return {}
    parsed: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        key = key.strip()[:80]
        value = value.strip()[:500]
        if not separator or not key or not value:
            continue
        if should_reject_long_term_memory(f"{key}: {value}"):
            continue
        parsed[key] = value
        if len(parsed) >= 12:
            break
    return parsed


def _suggestion_preview(suggestion: MemorySuggestion) -> str:
    confidence = round(max(0.0, min(1.0, suggestion.confidence)) * 100)
    return (
        "✨ اقتراح ذاكرة بانتظار مراجعتك\n\n"
        f"الملخص: {suggestion.summary or '—'}\n\n"
        f"الحقائق:\n{_format_mapping(suggestion.facts_json)}\n\n"
        f"التفضيلات:\n{_format_mapping(suggestion.preferences_json)}\n\n"
        f"درجة الثقة: {confidence}%\n"
        "سبب الاقتراح: معلومات دائمة ذُكرت صراحة في المحادثة وتحتاج مراجعتك.\n\n"
        "لن تُحفظ هذه المعلومات في ذاكرة الشخص إلا بعد الضغط على اعتماد."
    )


def _suggestion_keyboard(suggestion_id: int, contact_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ اعتماد الذاكرة",
                    callback_data=f"memory:suggestion:approve:{suggestion_id}",
                ),
                InlineKeyboardButton(
                    text="❌ رفض الاقتراح",
                    callback_data=f"memory:suggestion:reject:{suggestion_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ ذاكرة الشخص",
                    callback_data=f"memory:contact:{contact_id}",
                )
            ],
        ]
    )


def _manual_metadata(
    memory: ContactMemory | None,
    *,
    section: str,
    values: dict[str, str] | None = None,
    has_summary: bool | None = None,
) -> tuple[dict, dict]:
    provenance = dict(memory.provenance_json or {}) if memory else {}
    confidence = dict(memory.confidence_json or {}) if memory else {}
    reviewed_at = datetime.now(UTC).isoformat()
    if section == "summary":
        if has_summary:
            provenance["summary"] = {"source": "OWNER_MANUAL", "reviewed_at": reviewed_at}
            confidence["summary"] = 1.0
        else:
            provenance.pop("summary", None)
            confidence.pop("summary", None)
    else:
        provenance[section] = {
            key: {"source": "OWNER_MANUAL", "reviewed_at": reviewed_at} for key in (values or {})
        }
        confidence[section] = {key: 1.0 for key in (values or {})}
    return provenance, confidence


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
            "🧠 اكتب ملخصًا قصيرًا مفيدًا عن هذا الشخص.\nاكتب — لمسح الملخص الحالي."
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
    if value and should_reject_long_term_memory(value):
        await message.answer(
            "حفاظًا على الخصوصية، لا يمكن وضع كلمات مرور أو رموز تحقق أو بيانات دفع "
            "في الذاكرة المشتركة. يمكنك وضع ملاحظة خاصة بدلًا من ذلك عند الحاجة."
        )
        return
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact is None or contact.owner_id != owner.id:
            await state.clear()
            await message.answer("لم أجد الشخص.")
            return
        memory = get_contact_memory(session, contact_id=contact.id)
        provenance, confidence = _manual_metadata(
            memory,
            section="summary",
            has_summary=bool(value),
        )
        upsert_contact_memory(
            session,
            owner_id=owner.id,
            contact_id=contact.id,
            summary=value,
            provenance_json=provenance,
            confidence_json=confidence,
            retention_until=datetime.now(UTC)
            + timedelta(days=max(1, settings.memory_retention_days)),
            last_reviewed_at=datetime.now(UTC),
        )
        session.commit()
    await state.clear()
    await message.answer(
        "✅ تم تحديث ملخص الذاكرة.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ ذاكرة الشخص", callback_data=f"memory:contact:{contact_id}"
                    )
                ]
            ]
        ),
    )


async def _mapping_start(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    target_state: State,
    prompt: str,
) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(contact_id=int(raw_id))
    await state.set_state(target_state)
    if callback.message:
        await callback.message.answer(prompt)
    await callback.answer()


@router.callback_query(F.data.startswith("memory:facts:"))
async def memory_facts_start(callback: CallbackQuery, state: FSMContext) -> None:
    await _mapping_start(
        callback,
        state,
        target_state=MemoryStates.facts,
        prompt=(
            "📌 اكتب الحقائق المؤكدة، كل حقيقة في سطر بهذا الشكل:\n"
            "المدينة: الرياض\nاللغة المفضلة: العربية\n\n"
            "اكتب — لمسح الحقائق الحالية. لن تُحفظ البيانات الحساسة هنا."
        ),
    )


@router.callback_query(F.data.startswith("memory:preferences:"))
async def memory_preferences_start(callback: CallbackQuery, state: FSMContext) -> None:
    await _mapping_start(
        callback,
        state,
        target_state=MemoryStates.preferences,
        prompt=(
            "💬 اكتب تفضيلات التواصل، كل تفضيل في سطر بهذا الشكل:\n"
            "وقت التواصل: المساء\nأسلوب الرد: مختصر\n\n"
            "اكتب — لمسح التفضيلات الحالية."
        ),
    )


async def _mapping_save(
    message: Message,
    state: FSMContext,
    *,
    section: str,
    success_text: str,
) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    data = await state.get_data()
    contact_id = int(data.get("contact_id") or 0)
    source = message.text or ""
    values = _parse_mapping(source)
    if source.strip() != "—" and not values:
        await message.answer(
            "لم أجد أسطرًا صالحة. استخدم الصيغة «العنوان: القيمة»، وتجنب البيانات الحساسة."
        )
        return
    with SessionLocal() as session:
        contact = session.get(Contact, contact_id)
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        if contact is None or contact.owner_id != owner.id:
            await state.clear()
            await message.answer("لم أجد الشخص.")
            return
        memory = get_contact_memory(session, contact_id=contact.id)
        provenance, confidence = _manual_metadata(
            memory,
            section=section,
            values=values,
        )
        kwargs = {f"{section}_json": values}
        upsert_contact_memory(
            session,
            owner_id=owner.id,
            contact_id=contact.id,
            provenance_json=provenance,
            confidence_json=confidence,
            retention_until=datetime.now(UTC)
            + timedelta(days=max(1, settings.memory_retention_days)),
            last_reviewed_at=datetime.now(UTC),
            **kwargs,
        )
        session.commit()
    await state.clear()
    await message.answer(
        success_text,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⬅️ ذاكرة الشخص",
                        callback_data=f"memory:contact:{contact_id}",
                    )
                ]
            ]
        ),
    )


@router.message(MemoryStates.facts)
async def memory_facts_save(message: Message, state: FSMContext) -> None:
    await _mapping_save(
        message,
        state,
        section="facts",
        success_text="✅ تم تحديث الحقائق المؤكدة.",
    )


@router.message(MemoryStates.preferences)
async def memory_preferences_save(message: Message, state: FSMContext) -> None:
    await _mapping_save(
        message,
        state,
        section="preferences",
        success_text="✅ تم تحديث تفضيلات التواصل.",
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
            "🔒 اكتب ملاحظتك الخاصة. هذه الملاحظة لك فقط ولا تدخل إلى خدمة الصياغة.\nاكتب — لمسحها."
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
                [
                    InlineKeyboardButton(
                        text="⬅️ ذاكرة الشخص", callback_data=f"memory:contact:{contact_id}"
                    )
                ]
            ]
        ),
    )


@router.callback_query(F.data.startswith("memory:suggest:"))
async def memory_suggest(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    contact_id = int(raw_id)
    if not settings.text_ai_configured:
        await callback.answer("خدمة الصياغة غير مهيأة حاليًا.", show_alert=True)
        return
    await callback.answer("أراجع آخر المحادثة لإعداد اقتراح…")
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        contact = session.get(Contact, contact_id)
        if contact is None or contact.owner_id != owner.id:
            if callback.message:
                await callback.message.answer("لم أجد الشخص.")
            return
        if not contact.memory_allowed:
            if callback.message:
                await callback.message.answer(
                    "حفظ الذاكرة معطل لهذا الشخص. فعّله أولًا قبل إنشاء اقتراح."
                )
            return
        conversation = session.scalar(
            select(Conversation)
            .where(
                Conversation.owner_id == owner.id,
                Conversation.contact_id == contact.id,
            )
            .order_by(Conversation.id.desc())
            .limit(1)
        )
        if conversation is None:
            if callback.message:
                await callback.message.answer("لا توجد محادثة يمكن مراجعتها بعد.")
            return
        rows = list(
            session.scalars(
                select(DBMessage)
                .where(
                    DBMessage.conversation_id == conversation.id,
                    DBMessage.is_deleted.is_(False),
                    DBMessage.text.is_not(None),
                )
                .order_by(DBMessage.id.desc())
                .limit(max(1, settings.context_message_limit))
            )
        )
        rows.reverse()
        transcript = [
            {
                "role": "contact" if row.direction == "IN" else "secretary",
                "text": row.text or "",
            }
            for row in rows
            if (row.text or "").strip()
        ]
        source_message_ids = [row.id for row in rows]
        memory = get_contact_memory(session, contact_id=contact.id)
        current_memory = memory_for_ai(
            memory,
            contact_memory_allowed=contact.memory_allowed,
        )
        owner_id = owner.id
        conversation_id = conversation.id
    if not transcript:
        if callback.message:
            await callback.message.answer("لا توجد رسائل نصية كافية لإعداد اقتراح.")
        return
    try:
        proposal = await propose_memory_update(
            build_ai_provider(settings),
            transcript=transcript,
            current_memory=current_memory,
        )
    except Exception:
        logger.exception("memory_suggestion_generation_failed contact=%s", contact_id)
        if callback.message:
            await callback.message.answer("تعذر إعداد اقتراح الذاكرة الآن. لم يتم حفظ أي معلومة.")
        return
    if proposal.is_empty:
        if callback.message:
            await callback.message.answer(
                "لم أجد في المحادثة معلومات دائمة مناسبة للحفظ. لم يتم تغيير الذاكرة."
            )
        return
    with SessionLocal() as session:
        suggestion = create_memory_suggestion(
            session,
            owner_id=owner_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            source_message_ids=source_message_ids,
            proposal=proposal,
            ttl_hours=settings.memory_suggestion_ttl_hours,
        )
        session.commit()
        preview = _suggestion_preview(suggestion)
        suggestion_id = suggestion.id
    if callback.message:
        await callback.message.answer(
            preview[:4000],
            reply_markup=_suggestion_keyboard(suggestion_id, contact_id),
        )


def _suggestion_action(callback_data: str | None) -> tuple[str, int] | None:
    parts = (callback_data or "").split(":")
    if len(parts) != 4 or parts[2] not in {"approve", "reject"} or not parts[3].isdigit():
        return None
    return parts[2], int(parts[3])


@router.callback_query(F.data.startswith("memory:suggestion:"))
async def memory_suggestion_resolve(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    parsed = _suggestion_action(callback.data)
    if parsed is None:
        await callback.answer("تعذر قراءة الإجراء.", show_alert=True)
        return
    action, suggestion_id = parsed
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        suggestion = session.get(MemorySuggestion, suggestion_id)
        contact_id = suggestion.contact_id if suggestion else 0
        if action == "approve":
            memory = approve_memory_suggestion(
                session,
                owner_id=owner.id,
                suggestion_id=suggestion_id,
                retention_days=settings.memory_retention_days,
            )
            ok = memory is not None
        else:
            ok = reject_memory_suggestion(
                session,
                owner_id=owner.id,
                suggestion_id=suggestion_id,
            )
        session.commit()
    if not ok:
        await callback.answer("تم التعامل مع هذا الاقتراح مسبقًا أو انتهت صلاحيته.", show_alert=True)
        return
    if callback.message:
        status = (
            "✅ تم اعتماد الاقتراح وحفظ الذاكرة."
            if action == "approve"
            else "❌ تم رفض الاقتراح دون تغيير الذاكرة."
        )
        await callback.message.edit_text(
            status,
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⬅️ ذاكرة الشخص",
                            callback_data=f"memory:contact:{contact_id}",
                        )
                    ]
                ]
            ),
        )
    await callback.answer("تم اعتماد الذاكرة" if action == "approve" else "تم رفض الاقتراح")


@router.callback_query(F.data.startswith("memory:export:"))
async def memory_export(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    contact_id = int(raw_id)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        contact = session.get(Contact, contact_id)
        memory = get_contact_memory(session, contact_id=contact_id)
        if contact is None or contact.owner_id != owner.id or memory is None:
            await callback.answer("لا توجد ذاكرة لتصديرها.", show_alert=True)
            return
        payload = export_contact_memory(memory)
        payload["contact"] = {
            "display_name": contact.display_name,
            "username": contact.username,
            "telegram_user_id": contact.telegram_user_id,
        }
    document = BufferedInputFile(
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        filename=f"contact-memory-{contact_id}.json",
    )
    if callback.message:
        await callback.message.answer_document(
            document,
            caption="📤 نسخة من ذاكرة الشخص وسجل مصدرها. الملف أُرسل لك وحدك.",
        )
    await callback.answer("تم تجهيز نسخة الذاكرة")


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


@router.callback_query(F.data.startswith("memory:clear:request:"))
async def memory_clear_request(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    contact_id = int(raw_id)
    if callback.message:
        await callback.message.edit_text(
            "🗑 هل تريد مسح ذاكرة هذا الشخص؟\n\n"
            "سيبقى سجل المحادثة كما هو، وستُلغى الاقتراحات المعلّقة لهذا الشخص.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="نعم، امسح الذاكرة",
                            callback_data=f"memory:clear:confirm:{contact_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="إلغاء",
                            callback_data=f"memory:contact:{contact_id}",
                        )
                    ],
                ]
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("memory:clear:confirm:"))
async def memory_clear_confirm(callback: CallbackQuery) -> None:
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
        session.execute(
            update(MemorySuggestion)
            .where(
                MemorySuggestion.owner_id == owner.id,
                MemorySuggestion.contact_id == contact.id,
                MemorySuggestion.status == "PENDING",
            )
            .values(status="REJECTED", resolved_at=datetime.now(UTC))
        )
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
