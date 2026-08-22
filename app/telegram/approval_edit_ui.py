from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.approvals.editing import get_editable_approval, update_approval_candidate
from app.config import get_settings
from app.conversations.context import build_ai_context
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.knowledge.admin import add_knowledge
from app.security.owner import OwnerGuard
from app.telegram.owner_ui import approval_keyboard
from app.telegram.professional_copy import knowledge_source_text, relevance_text

router = Router(name="approval_edit_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class ApprovalEditStates(StatesGroup):
    waiting_text = State()
    review = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _learn_confirm_keyboard(approval_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ حفظ كتوجيه داخلي",
                    callback_data=f"approval_edit:learn_confirm:{approval_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="إلغاء",
                    callback_data=f"approval_edit:learn_cancel:{approval_id}",
                )
            ],
        ]
    )


@router.callback_query(F.data.startswith("approval_edit:start:"))
async def approval_edit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    approval_id = int(raw_id)
    with SessionLocal() as session:
        draft = get_editable_approval(session, approval_id)
    if draft is None:
        await callback.answer("الرد لم يعد قابلًا للتعديل", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        approval_id=approval_id,
        trigger_text=draft.trigger_text,
        original_text=draft.candidate_response,
    )
    await state.set_state(ApprovalEditStates.waiting_text)
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await callback.message.answer(
            "✏️ أرسل الآن الرد المعدل كاملًا.\n\nلن يُرسل للعميل حتى تضغط «إرسال الرد» بعد المراجعة."
        )
    await callback.answer()


@router.message(ApprovalEditStates.waiting_text)
async def approval_edit_receive(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("أرسل ردًا نصيًا غير فارغ.")
        return
    data = await state.get_data()
    approval_id = int(data.get("approval_id") or 0)
    if approval_id <= 0:
        await state.clear()
        await message.answer("انتهت جلسة التعديل. افتح بطاقة الرد وحاول مجددًا.")
        return

    with SessionLocal() as session:
        ok = update_approval_candidate(session, approval_id, text=text)
        if ok:
            session.commit()
    if not ok:
        await state.clear()
        await message.answer("الرد لم يعد قابلًا للتعديل أو انتهت صلاحيته.")
        return

    await state.update_data(edited_text=text)
    await state.set_state(ApprovalEditStates.review)
    await message.answer(
        "✅ تم تحديث الرد المقترح.\n\n"
        f"{text[:3200]}\n\n"
        "يمكنك إرساله، مراجعة مصادره، أو حفظ صياغتك كتوجيه داخلي بعد تأكيدك.",
        reply_markup=approval_keyboard(approval_id),
    )


@router.callback_query(F.data.startswith("approval_meta:sources:"))
async def approval_sources(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    approval_id = int(raw_id)
    with SessionLocal() as session:
        draft = get_editable_approval(session, approval_id)
        if draft is None:
            await callback.answer("الرد لم يعد قيد المراجعة", show_alert=True)
            return
        if draft.source_snapshots:
            sources = list(draft.source_snapshots)
        elif not draft.trigger_text.strip():
            sources = []
        else:
            built = build_ai_context(
                session,
                conversation_id=draft.conversation_id,
                query=draft.trigger_text,
                message_limit=settings.context_message_limit,
                knowledge_top_k=settings.knowledge_top_k,
            )
            sources = [
                {
                    "id": hit.id,
                    "title": hit.title,
                    "visibility": hit.visibility,
                    "score": hit.score,
                    "source": hit.source,
                    "version": hit.version,
                    "conflict_ids": list(hit.conflict_ids),
                }
                for hit in built.knowledge_hits
            ]

    if not sources:
        text = "📚 المصادر المستخدمة\n\nلا توجد معرفة مالك مطابقة لهذا الرد."
    else:
        lines = ["📚 المصادر المستخدمة", ""]
        for source in sources:
            icon = "🌍" if source.get("visibility") == "PUBLIC" else "🏠"
            conflict = " — توجد معلومة أخرى متعارضة" if source.get("conflict_ids") else ""
            lines.append(f"{icon} #{source.get('id')} — {source.get('title')}")
            lines.append(
                f"   {relevance_text(float(source.get('score') or 0.0))} · "
                f"{knowledge_source_text(source.get('source'))}"
                f" · النسخة {int(source.get('version') or 1)}{conflict}"
            )
        text = "\n".join(lines)
    if callback.message:
        await callback.message.answer(text[:4000])
    await callback.answer()


@router.callback_query(F.data.startswith("approval_edit:learn:"))
async def approval_learn(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    approval_id = int(raw_id)
    data = await state.get_data()
    edited_text = str(data.get("edited_text") or "").strip()
    state_approval_id = int(data.get("approval_id") or 0)
    if state_approval_id != approval_id or not edited_text:
        await callback.answer(
            "التعلّم متاح بعد أن تعدّل الرد بنفسك في هذه الجلسة.",
            show_alert=True,
        )
        return

    if callback.message:
        await callback.message.answer(
            "🧠 تعلّم من تعديلك؟\n\n"
            "سيُحفظ الرد الذي كتبته أنت كتوجيه داخلي فقط. "
            "لن يصبح معلومة عامة أو سعرًا معتمدًا، ولن يُحفظ شيء دون تأكيدك.\n\n"
            f"الرد:\n{edited_text[:2500]}",
            reply_markup=_learn_confirm_keyboard(approval_id),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("approval_edit:learn_confirm:"))
async def approval_learn_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("طلب غير صالح", show_alert=True)
        return
    approval_id = int(raw_id)
    data = await state.get_data()
    edited_text = str(data.get("edited_text") or "").strip()
    if int(data.get("approval_id") or 0) != approval_id or not edited_text:
        await callback.answer("انتهت جلسة التعلّم", show_alert=True)
        return

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = add_knowledge(
            session,
            owner=owner,
            visibility="INTERNAL",
            title=f"مثال رد معتمد من المالك #{approval_id}",
            content=edited_text,
            item_type="EXAMPLE",
        )
        session.commit()
        knowledge_id = row.id

    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            f"✅ تم حفظ صياغتك كتوجيه داخلي #{knowledge_id}.\n"
            "لن تُعرض للعميل كمعلومة عامة، لكنها قد تساعد السكرتير في أسلوب الرد."
        )
    await callback.answer("تم الحفظ")


@router.callback_query(F.data.startswith("approval_edit:learn_cancel:"))
async def approval_learn_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    if callback.message:
        await callback.message.edit_text("تم إلغاء التعلّم، ولم يتم حفظ شيء.")
    await callback.answer()
