from __future__ import annotations

import logging
from time import perf_counter
from uuid import uuid4

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import BusinessConnection, BusinessMessagesDeleted, CallbackQuery, Message
from sqlalchemy import select

from app.ai.factory import build_multimodal_pipeline, build_text_pipeline
from app.approvals.service import (
    attach_owner_message,
    claim_for_send,
    create_approval,
    format_approval_reason,
    mark_sent,
    mark_uncertain,
    preview_claim,
    reject,
)
from app.config import get_settings
from app.conversations.context import build_ai_context
from app.conversations.ingest import ingest_message
from app.conversations.search import search_messages
from app.db.enums import ConversationState, DecisionAction
from app.db.models import Contact, Conversation
from app.db.models import Message as DBMessage
from app.db.repositories import (
    ApprovalRepository,
    BusinessConnectionRepository,
    ConversationRepository,
    OwnerRepository,
)
from app.db.session import SessionLocal
from app.feedback.service import should_prompt_feedback
from app.knowledge.admin import (
    add_knowledge,
    delete_knowledge,
    list_knowledge,
    normalize_visibility,
)
from app.observability.metrics import record_ai_run
from app.security.owner import OwnerGuard
from app.telegram.adapter import AiogramTelegramAdapter
from app.telegram.contracts import IncomingBusinessMessage
from app.telegram.debounce import DebounceRegistry
from app.telegram.owner_ui import approval_keyboard, main_admin_keyboard
from app.telegram.professional_copy import decision_reason_text

logger = logging.getLogger(__name__)
router = Router(name="secretary")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)
debouncer = DebounceRegistry()


def _knowledge_reference_ids(context: dict) -> list[int]:
    references: list[int] = []
    for item in context.get("trusted_knowledge") or []:
        if isinstance(item, dict) and isinstance(item.get("id"), int):
            references.append(item["id"])
    return references


def _persist_ai_telemetry(
    *,
    owner_id: int,
    conversation_id: int,
    trigger_message_id: int,
    trace_id: str,
    operation: str,
    provider: str,
    model: str,
    status: str,
    latency_ms: int,
    context: dict,
    result=None,
    error_code: str = "",
) -> None:
    decision = getattr(result, "decision", None)
    with SessionLocal() as session:
        record_ai_run(
            session,
            owner_id=owner_id,
            conversation_id=conversation_id,
            trigger_message_id=trigger_message_id,
            trace_id=trace_id,
            operation=operation,
            provider=provider,
            model=model,
            intent=getattr(decision, "intent", ""),
            risk=getattr(getattr(decision, "risk", None), "value", ""),
            action=getattr(getattr(decision, "action", None), "value", ""),
            confidence=(
                decision.confidence.model_dump(mode="json") if decision is not None else {}
            ),
            knowledge_refs=_knowledge_reference_ids(context),
            latency_ms=latency_ms,
            token_usage=getattr(result, "token_usage", {}),
            status=status,
            error_code=error_code,
        )
        try:
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "ai_telemetry_commit_failed",
                extra={"trace_id": trace_id, "operation": operation},
            )


def _rights_json(connection: BusinessConnection) -> dict:
    return connection.rights.model_dump(mode="json") if connection.rights else {}


def _can_reply(connection: BusinessConnection) -> bool:
    return bool(connection.is_enabled and connection.rights and connection.rights.can_reply)


def _content_type(message: Message) -> str:
    if message.text:
        return "TEXT"
    if message.voice:
        return "VOICE"
    if message.photo:
        return "PHOTO"
    if message.document:
        return "DOCUMENT"
    if message.video:
        return "VIDEO"
    if message.audio:
        return "AUDIO"
    return "OTHER"


def _persist_business_connection(connection: BusinessConnection) -> bool:
    """Persist only the configured owner's connection."""
    if connection.user.id != settings.owner_telegram_id:
        logger.warning(
            "business_connection_ignored unexpected_owner=%s connection=%s",
            connection.user.id,
            connection.id,
        )
        return False
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(
            session,
            settings.owner_telegram_id,
            display_name=connection.user.full_name,
        )
        BusinessConnectionRepository.upsert(
            session,
            owner_id=owner.id,
            telegram_connection_id=connection.id,
            telegram_user_chat_id=connection.user_chat_id,
            is_enabled=connection.is_enabled,
            rights_json=_rights_json(connection),
        )
        session.commit()
    return True


async def _ensure_business_connection(bot: Bot, connection_id: str) -> bool:
    """Recover connection state if Telegram's connection update was missed."""
    with SessionLocal() as session:
        cached = BusinessConnectionRepository.get(session, connection_id)
        if cached is not None:
            return bool(cached.is_enabled)

    try:
        connection = await bot.get_business_connection(business_connection_id=connection_id)
    except Exception:
        logger.exception("business_connection_recovery_failed connection=%s", connection_id)
        return False
    ok = _persist_business_connection(connection)
    if ok:
        logger.info("business_connection_recovered connection=%s", connection_id)
    return bool(ok and connection.is_enabled)


async def _set_card_status(callback: CallbackQuery, status_text: str) -> None:
    message = callback.message
    if message is None or not getattr(message, "text", None):
        return
    text = str(message.text)
    if "\n\n—\n" in text:
        text = text.split("\n\n—\n", 1)[0]
    text = text[:3700] + f"\n\n—\n{status_text}"
    try:
        await message.edit_text(text, reply_markup=None)
    except Exception:
        logger.debug("owner_card_edit_failed", exc_info=True)


@router.message(CommandStart())
async def owner_start(message: Message) -> None:
    if not guard.is_owner(message.from_user.id if message.from_user else None):
        return
    image_service = "🟢 جاهزة" if settings.multimodal_configured else "⚪ غير مهيأة"
    reply_service = "🟢 جاهزة" if settings.text_ai_configured else "⚪ غير مهيأة"
    await message.answer(
        "🧑‍💼 السكرتير\n\n"
        "الحالة: 🟢 يعمل\n"
        "الوضع: 🟡 موافقة قبل الإرسال\n"
        f"صياغة الردود: {reply_service}\n"
        f"فهم الصور: {image_service}\n\n"
        "يمكنك إدارة الهوية والمعرفة والسياسات من الأزرار أدناه.",
        reply_markup=main_admin_keyboard(),
    )


@router.message(Command("learn"))
async def owner_learn(message: Message) -> None:
    if not guard.is_owner(message.from_user.id if message.from_user else None):
        return
    raw = (message.text or "").split(maxsplit=1)
    if len(raw) != 2:
        await message.answer("الاستخدام: /learn عام | العنوان | المعلومة")
        return
    parts = [part.strip() for part in raw[1].split("|", 2)]
    if len(parts) != 3:
        await message.answer("الاستخدام: /learn عام | العنوان | المعلومة")
        return
    visibility = normalize_visibility(parts[0])
    if visibility is None or not parts[1] or not parts[2]:
        await message.answer("النوع يكون: عام أو داخلي. ويجب كتابة عنوان ومعلومة.")
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = add_knowledge(
            session,
            owner=owner,
            visibility=visibility,
            title=parts[1],
            content=parts[2],
        )
        session.commit()
        item_id = row.id
    await message.answer(f"✅ تم حفظ المعلومة #{item_id} في عقل السكرتير.")


@router.message(Command("knowledge"))
async def owner_knowledge(message: Message) -> None:
    if not guard.is_owner(message.from_user.id if message.from_user else None):
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_knowledge(session, owner_id=owner.id, limit=10)
    if not rows:
        await message.answer("🧠 لا توجد معلومات محفوظة حتى الآن.")
        return
    lines = ["🧠 آخر معلومات السكرتير:"]
    for row in rows:
        lines.append(f"#{row.id} [{row.visibility}] {row.title}")
    lines.append("\nللحذف: /forgetknowledge ID")
    await message.answer("\n".join(lines))


@router.message(Command("search"))
async def owner_search(message: Message) -> None:
    if not guard.is_owner(message.from_user.id if message.from_user else None):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        await message.answer("الاستخدام: /search كلمة أو جملة")
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        hits = search_messages(session, owner_id=owner.id, query=parts[1], limit=10)
    if not hits:
        await message.answer("لم أجد رسائل مطابقة في الأرشيف.")
        return
    lines = ["🔎 نتائج البحث في المحادثات:"]
    for hit in hits:
        arrow = "⬅️" if hit.direction == "IN" else "➡️"
        preview = hit.text.replace("\n", " ")[:180]
        lines.append(f"{arrow} {hit.contact_name} — {preview}")
    await message.answer("\n".join(lines)[:4000])


@router.message(Command("forgetknowledge"))
async def owner_forget_knowledge(message: Message) -> None:
    if not guard.is_owner(message.from_user.id if message.from_user else None):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("الاستخدام: /forgetknowledge 12")
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        ok = delete_knowledge(session, owner_id=owner.id, knowledge_id=int(parts[1]))
        session.commit()
    await message.answer("✅ تم حذف المعلومة." if ok else "لم أجد هذه المعلومة.")


@router.callback_query(F.data.startswith("approval:"))
async def approval_callbacks(callback: CallbackQuery, bot: Bot) -> None:
    if not guard.is_owner(callback.from_user.id):
        await callback.answer()
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    action, approval_id = parts[1], int(parts[2])

    if action == "reject":
        with SessionLocal() as session:
            ok = reject(session, approval_id)
        await callback.answer("تم رفض الرد" if ok else "تم التعامل مع هذا الرد مسبقًا")
        if ok:
            await _set_card_status(callback, "❌ تم رفض الرد")
        return

    if action != "send":
        await callback.answer("إجراء غير معروف", show_alert=True)
        return

    with SessionLocal() as session:
        preview = preview_claim(session, approval_id)
    if preview is None:
        await callback.answer("الرد قديم أو تم التعامل معه مسبقًا", show_alert=True)
        await _set_card_status(callback, "⏭ هذا الرد لم يعد صالحًا")
        return

    # Fail closed: verify the current Telegram connection and reply right before sending.
    try:
        live_connection = await bot.get_business_connection(
            business_connection_id=preview.business_connection_id
        )
    except Exception:
        logger.exception("approval_connection_check_failed approval=%s", approval_id)
        await callback.answer("تعذر التحقق من صلاحية الاتصال. لم يتم الإرسال.", show_alert=True)
        return
    if live_connection.user.id != settings.owner_telegram_id or not _can_reply(live_connection):
        _persist_business_connection(live_connection)
        await callback.answer("صلاحية الرد غير متاحة حاليًا في Telegram.", show_alert=True)
        return
    _persist_business_connection(live_connection)

    with SessionLocal() as session:
        claim = claim_for_send(session, approval_id)
    if claim is None:
        await callback.answer("الرد انتهت صلاحيته أو تغير سياق المحادثة", show_alert=True)
        await _set_card_status(callback, "⏭ انتهت صلاحية هذا الرد أو تغيرت المحادثة")
        return

    adapter = AiogramTelegramAdapter(bot)
    with SessionLocal() as session:
        request_feedback = settings.feedback_buttons_enabled and should_prompt_feedback(
            session,
            conversation_id=claim.conversation_id,
            interval=settings.feedback_prompt_every_n_responses,
        )
    try:
        sent_message_id = await adapter.send_text(
            business_connection_id=claim.business_connection_id,
            chat_id=claim.chat_id,
            text=claim.text,
            intent=claim.intent,
            feedback_approval_id=approval_id if request_feedback else None,
        )
    except Exception:
        logger.exception("approval_send_uncertain approval=%s", approval_id)
        with SessionLocal() as session:
            mark_uncertain(session, approval_id)
        await callback.answer("تعذر تأكيد الإرسال؛ لن أعيد المحاولة تلقائيًا", show_alert=True)
        await _set_card_status(callback, "⚠️ حالة الإرسال غير مؤكدة — لا إعادة تلقائية")
        return

    with SessionLocal() as session:
        mark_sent(session, approval_id, telegram_message_id=sent_message_id)
    await callback.answer("تم إرسال الرد")
    await _set_card_status(callback, "✅ تم الإرسال")


@router.callback_query(
    F.data.in_(
        {
            "a:conversations",
            "a:pending",
            "a:contacts",
            "a:schedules",
            "a:security",
            "a:pause",
        }
    )
)
async def owner_callbacks(callback: CallbackQuery) -> None:
    if not guard.is_owner(callback.from_user.id):
        await callback.answer()
        return
    action = (callback.data or "").split(":", 1)[-1]
    await callback.answer(f"{action}: القسم قيد استكمال الواجهة")


@router.business_connection()
async def on_business_connection(connection: BusinessConnection) -> None:
    if not _persist_business_connection(connection):
        return
    logger.info(
        "business_connection_changed id=%s enabled=%s owner=%s can_reply=%s",
        connection.id,
        connection.is_enabled,
        connection.user.id,
        bool(connection.rights and connection.rights.can_reply),
    )


def _load_text_work(conversation_id: int, trigger_message_id: int) -> tuple[str, dict, int] | None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        db_message = session.get(DBMessage, trigger_message_id)
        if (
            conversation is None
            or db_message is None
            or db_message.is_deleted
            or not db_message.text
        ):
            return None
        contact = session.get(Contact, conversation.contact_id)
        built = build_ai_context(
            session,
            conversation_id=conversation_id,
            query=db_message.text,
            message_limit=settings.context_message_limit,
            knowledge_top_k=settings.knowledge_top_k,
        )
        context = dict(built.payload)
        context["contact_name"] = contact.display_name if contact else ""
        return db_message.text, context, conversation.revision


def _conversation_is_current(conversation_id: int, expected_revision: int) -> Conversation | None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None or conversation.revision != expected_revision:
            return None
        # Return a detached snapshot sufficient for create_approval; caller re-queries before write.
        session.expunge(conversation)
        return conversation


def _approval_context(*, intent: str, context: dict) -> dict:
    sources: list[dict] = []
    for item in context.get("trusted_knowledge") or []:
        if not isinstance(item, dict):
            continue
        sources.append(
            {
                key: item.get(key)
                for key in (
                    "id",
                    "type",
                    "title",
                    "visibility",
                    "score",
                    "source",
                    "version",
                    "valid_until",
                    "conflict_ids",
                )
            }
        )
    return {
        "intent": intent.strip().upper(),
        "sources": sources,
        "has_conflicting_grounding": bool(context.get("has_conflicting_grounding")),
    }


async def _send_approval_card(bot: Bot, *, approval_id: int, text: str) -> None:
    owner_message = await bot.send_message(
        chat_id=settings.owner_telegram_id,
        text=text,
        reply_markup=approval_keyboard(approval_id),
    )
    with SessionLocal() as session:
        attach_owner_message(
            session,
            approval_id,
            owner_chat_id=settings.owner_telegram_id,
            owner_message_id=owner_message.message_id,
        )


async def _process_text_for_approval(
    *,
    bot: Bot,
    connection_id: str,
    conversation_id: int,
    trigger_message_id: int,
) -> None:
    if not settings.text_ai_configured:
        return
    loaded = _load_text_work(conversation_id, trigger_message_id)
    if loaded is None:
        return
    text, context, expected_revision = loaded
    if context.get("state") in {
        ConversationState.HUMAN_TAKEOVER.value,
        ConversationState.EXCLUDED.value,
        ConversationState.PAUSED.value,
        ConversationState.OBSERVE_ONLY.value,
    }:
        return

    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return
        owner_id = conversation.owner_id
        chat_id = conversation.telegram_chat_id
        contact = session.get(Contact, conversation.contact_id)
        contact_name = contact.display_name if contact else "غير معروف"

    adapter = AiogramTelegramAdapter(bot)
    await adapter.send_typing(business_connection_id=connection_id, chat_id=chat_id)
    trace_id = uuid4().hex
    started = perf_counter()
    try:
        result = await build_text_pipeline(settings).process_text(text=text, context=context)
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000)
        _persist_ai_telemetry(
            owner_id=owner_id,
            conversation_id=conversation_id,
            trigger_message_id=trigger_message_id,
            trace_id=trace_id,
            operation="TEXT_RESPONSE",
            provider=settings.ai_provider,
            model=settings.deepseek_model,
            status="ERROR",
            latency_ms=latency_ms,
            context=context,
            error_code=type(exc).__name__,
        )
        logger.exception(
            "text_ai_failed chat=%s trigger=%s",
            chat_id,
            trigger_message_id,
            extra={"trace_id": trace_id, "operation": "TEXT_RESPONSE"},
        )
        await bot.send_message(
            chat_id=settings.owner_telegram_id,
            text=(
                "⚠️ تعذر تحليل رسالة نصية بالذكاء الاصطناعي.\n"
                f"المحادثة: {chat_id}\n"
                "لم يتم إرسال أي رد للمستخدم."
            ),
        )
        return

    # A newer incoming/edit/delete event invalidates the AI result before it becomes a draft.
    if _conversation_is_current(conversation_id, expected_revision) is None:
        _persist_ai_telemetry(
            owner_id=owner_id,
            conversation_id=conversation_id,
            trigger_message_id=trigger_message_id,
            trace_id=trace_id,
            operation="TEXT_RESPONSE",
            provider=settings.ai_provider,
            model=settings.deepseek_model,
            status="DISCARDED",
            latency_ms=round((perf_counter() - started) * 1000),
            context=context,
            result=result,
        )
        logger.info(
            "ai_result_discarded_stale conversation=%s",
            conversation_id,
            extra={"trace_id": trace_id, "operation": "TEXT_RESPONSE"},
        )
        return

    _persist_ai_telemetry(
        owner_id=owner_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_message_id,
        trace_id=trace_id,
        operation="TEXT_RESPONSE",
        provider=settings.ai_provider,
        model=settings.deepseek_model,
        status="SUCCESS",
        latency_ms=round((perf_counter() - started) * 1000),
        context=context,
        result=result,
    )

    if result.decision.action == DecisionAction.SILENT:
        return
    if result.decision.action == DecisionAction.ESCALATE or not result.candidate_reply:
        await bot.send_message(
            chat_id=settings.owner_telegram_id,
            text=(
                "💬 رسالة تحتاج تدخلك\n\n"
                f"من: {contact_name}\n"
                f"الرسالة: {text[:1000]}\n"
                f"سبب التحويل: {decision_reason_text(result.decision.reason_code)}\n\n"
                "لم يتم إرسال رد تلقائي."
            ),
        )
        return

    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None or conversation.revision != expected_revision:
            return
        approval = create_approval(
            session,
            conversation=conversation,
            trigger_message_id=trigger_message_id,
            candidate_response=result.candidate_reply,
            reason=format_approval_reason(
                source="TEXT",
                reason_code=result.decision.reason_code,
                intent=result.decision.intent,
            ),
            context=_approval_context(intent=result.decision.intent, context=context),
            ttl_hours=settings.approval_ttl_hours,
        )

    await _send_approval_card(
        bot,
        approval_id=approval.id,
        text=(
            "💬 رد مقترح على رسالة\n\n"
            f"👤 {contact_name}\n"
            f"📝 الرسالة: {text[:1000]}\n\n"
            f"✍️ رد السكرتير المقترح:\n{result.candidate_reply}\n\n"
            f"⏳ صالح للموافقة لمدة {settings.approval_ttl_hours} ساعة"
        ),
    )


async def _process_photo_for_approval(
    *,
    message: Message,
    bot: Bot,
    connection_id: str,
    conversation_id: int,
    trigger_message_id: int,
) -> None:
    if not settings.multimodal_configured or not message.photo:
        return

    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return
        owner_id = conversation.owner_id
        expected_revision = conversation.revision
        contact = session.get(Contact, conversation.contact_id)
        contact_name = contact.display_name if contact else "غير معروف"
        built = build_ai_context(
            session,
            conversation_id=conversation_id,
            query=message.caption or "صورة",
            message_limit=settings.context_message_limit,
            knowledge_top_k=settings.knowledge_top_k,
        )
        context = dict(built.payload)
        context["contact_name"] = contact_name
        chat_id = conversation.telegram_chat_id

    if context.get("state") in {
        ConversationState.HUMAN_TAKEOVER.value,
        ConversationState.EXCLUDED.value,
        ConversationState.PAUSED.value,
        ConversationState.OBSERVE_ONLY.value,
    }:
        return

    adapter = AiogramTelegramAdapter(bot)
    await adapter.send_typing(business_connection_id=connection_id, chat_id=chat_id)
    trace_id = uuid4().hex
    started = perf_counter()
    try:
        image_bytes = await adapter.download_file_bytes(
            file_id=message.photo[-1].file_id,
            max_bytes=settings.max_image_bytes,
        )
        result = await build_multimodal_pipeline(settings).process_image(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            user_text=message.caption,
            context=context,
        )
    except Exception as exc:
        latency_ms = round((perf_counter() - started) * 1000)
        _persist_ai_telemetry(
            owner_id=owner_id,
            conversation_id=conversation_id,
            trigger_message_id=trigger_message_id,
            trace_id=trace_id,
            operation="IMAGE_RESPONSE",
            provider="gemini+deepseek",
            model=f"{settings.gemini_model}+{settings.deepseek_model}",
            status="ERROR",
            latency_ms=latency_ms,
            context=context,
            error_code=type(exc).__name__,
        )
        logger.exception(
            "multimodal_image_failed chat=%s message=%s",
            chat_id,
            message.message_id,
            extra={"trace_id": trace_id, "operation": "IMAGE_RESPONSE"},
        )
        await bot.send_message(
            chat_id=settings.owner_telegram_id,
            text=(
                "⚠️ تعذر فهم صورة واردة بعد المحاولة الآمنة.\n"
                f"المحادثة: {chat_id}\n"
                "لم يتم إرسال أي رد للمستخدم."
            ),
        )
        return

    if _conversation_is_current(conversation_id, expected_revision) is None:
        _persist_ai_telemetry(
            owner_id=owner_id,
            conversation_id=conversation_id,
            trigger_message_id=trigger_message_id,
            trace_id=trace_id,
            operation="IMAGE_RESPONSE",
            provider="gemini+deepseek",
            model=f"{settings.gemini_model}+{settings.deepseek_model}",
            status="DISCARDED",
            latency_ms=round((perf_counter() - started) * 1000),
            context=context,
            result=result,
        )
        logger.info(
            "image_ai_result_discarded_stale conversation=%s",
            conversation_id,
            extra={"trace_id": trace_id, "operation": "IMAGE_RESPONSE"},
        )
        return

    _persist_ai_telemetry(
        owner_id=owner_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_message_id,
        trace_id=trace_id,
        operation="IMAGE_RESPONSE",
        provider="gemini+deepseek",
        model=f"{settings.gemini_model}+{settings.deepseek_model}",
        status="SUCCESS",
        latency_ms=round((perf_counter() - started) * 1000),
        context=context,
        result=result,
    )

    if (
        result.decision.action in {DecisionAction.SILENT, DecisionAction.ESCALATE}
        or not result.candidate_reply
    ):
        await bot.send_message(
            chat_id=settings.owner_telegram_id,
            text=(
                "🖼 صورة تحتاج تدخلك\n\n"
                f"من: {contact_name}\n"
                f"فهم الصورة: {result.vision.summary}\n"
                f"سبب التحويل: {decision_reason_text(result.decision.reason_code)}\n\n"
                "لم يتم إنشاء رد قابل للإرسال تلقائيًا."
            ),
        )
        return

    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None or conversation.revision != expected_revision:
            return
        approval = create_approval(
            session,
            conversation=conversation,
            trigger_message_id=trigger_message_id,
            candidate_response=result.candidate_reply,
            reason=format_approval_reason(
                source="IMAGE",
                reason_code=result.decision.reason_code,
                intent=result.decision.intent,
            ),
            context=_approval_context(intent=result.decision.intent, context=context),
            ttl_hours=settings.approval_ttl_hours,
        )

    extracted = result.vision.extracted_text.strip()
    extracted_preview = extracted[:500] + ("…" if len(extracted) > 500 else "")
    card = f"🖼 رد مقترح على صورة\n\n👤 {contact_name}\n🔎 فهم الصورة: {result.vision.summary}\n"
    if extracted_preview:
        card += f"📝 النص المقروء: {extracted_preview}\n"
    card += (
        f"\n✍️ رد السكرتير المقترح:\n{result.candidate_reply}\n\n"
        f"⏳ صالح للموافقة لمدة {settings.approval_ttl_hours} ساعة"
    )
    await _send_approval_card(bot, approval_id=approval.id, text=card)


@router.business_message()
async def on_business_message(message: Message, bot: Bot) -> None:
    connection_id = message.business_connection_id
    if not connection_id or message.sender_business_bot is not None or message.from_user is None:
        return
    if not await _ensure_business_connection(bot, connection_id):
        return

    # Messages written manually by the owner are context, not new requests for the AI.
    # Persist them when the conversation is known and invalidate any pending draft.
    if message.from_user.id == settings.owner_telegram_id:
        with SessionLocal() as session:
            owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
            conversation = ConversationRepository.get_by_chat(
                session, owner_id=owner.id, chat_id=message.chat.id
            )
            if conversation is not None:
                ApprovalRepository.invalidate_pending(session, conversation.id, status="SUPERSEDED")
                ConversationRepository.append_outgoing(
                    session,
                    conversation=conversation,
                    telegram_message_id=message.message_id,
                    text=message.text or message.caption or "",
                )
                session.commit()
        debouncer.cancel((connection_id, message.chat.id))
        logger.info(
            "owner_manual_message_recorded chat=%s message=%s",
            message.chat.id,
            message.message_id,
        )
        return

    incoming = IncomingBusinessMessage(
        business_connection_id=connection_id,
        chat_id=message.chat.id,
        message_id=message.message_id,
        sender_user_id=message.from_user.id,
        sender_name=message.from_user.full_name,
        text=message.text or message.caption,
        content_type=_content_type(message),
        reply_to_message_id=(
            message.reply_to_message.message_id if message.reply_to_message else None
        ),
    )
    with SessionLocal() as session:
        result = ingest_message(
            session,
            owner_telegram_id=settings.owner_telegram_id,
            incoming=incoming,
            username=message.from_user.username,
        )
    if result.duplicate:
        return

    logger.info(
        "business_message_ingested connection=%s chat=%s message=%s conversation=%s revision=%s",
        connection_id,
        message.chat.id,
        message.message_id,
        result.conversation.id,
        result.conversation.revision,
    )

    key = (connection_id, message.chat.id)
    if message.photo:
        debouncer.schedule(
            key,
            delay_seconds=settings.message_debounce_seconds,
            factory=lambda: _process_photo_for_approval(
                message=message,
                bot=bot,
                connection_id=connection_id,
                conversation_id=result.conversation.id,
                trigger_message_id=result.message.id,
            ),
        )
    elif message.text:
        debouncer.schedule(
            key,
            delay_seconds=settings.message_debounce_seconds,
            factory=lambda: _process_text_for_approval(
                bot=bot,
                connection_id=connection_id,
                conversation_id=result.conversation.id,
                trigger_message_id=result.message.id,
            ),
        )


@router.edited_business_message()
async def on_edited_business_message(message: Message, bot: Bot) -> None:
    connection_id = message.business_connection_id
    if not connection_id or message.from_user is None or message.sender_business_bot is not None:
        return
    if not await _ensure_business_connection(bot, connection_id):
        return

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        conversation = ConversationRepository.mark_edited(
            session,
            owner_id=owner.id,
            chat_id=message.chat.id,
            telegram_message_id=message.message_id,
            new_text=message.text or message.caption,
        )
        internal_message = None
        if conversation is not None:
            internal_message = session.scalar(
                select(DBMessage).where(
                    DBMessage.conversation_id == conversation.id,
                    DBMessage.telegram_message_id == message.message_id,
                )
            )
        session.commit()
        conversation_id = conversation.id if conversation else None
        internal_id = internal_message.id if internal_message else None

    key = (connection_id, message.chat.id)
    debouncer.cancel(key)
    if message.from_user.id == settings.owner_telegram_id:
        logger.info(
            "owner_manual_message_edited chat=%s message=%s", message.chat.id, message.message_id
        )
        return
    if conversation_id and internal_id and message.text:
        debouncer.schedule(
            key,
            delay_seconds=settings.message_debounce_seconds,
            factory=lambda: _process_text_for_approval(
                bot=bot,
                connection_id=connection_id,
                conversation_id=conversation_id,
                trigger_message_id=internal_id,
            ),
        )
    logger.info("business_message_edited chat=%s message=%s", message.chat.id, message.message_id)


@router.deleted_business_messages()
async def on_deleted_business_messages(event: BusinessMessagesDeleted, bot: Bot) -> None:
    if not await _ensure_business_connection(bot, event.business_connection_id):
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        ConversationRepository.mark_deleted(
            session,
            owner_id=owner.id,
            chat_id=event.chat.id,
            telegram_message_ids=list(event.message_ids),
        )
        session.commit()
    debouncer.cancel((event.business_connection_id, event.chat.id))
    logger.info("business_messages_deleted chat=%s count=%s", event.chat.id, len(event.message_ids))


async def _shutdown() -> None:
    await debouncer.shutdown()


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(router)
    dp.shutdown.register(_shutdown)
    return dp
