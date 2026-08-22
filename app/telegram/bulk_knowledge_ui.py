from __future__ import annotations

import logging
from io import BytesIO

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.ai.factory import build_ai_provider
from app.config import get_settings
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.knowledge.bulk import (
    KnowledgeCandidate,
    extract_bulk_candidates,
    save_bulk_candidates,
    source_content_hash,
)
from app.security.owner import OwnerGuard
from app.telegram.callback_safety import safe_callback_answer
from app.telegram.professional_copy import knowledge_type_text

router = Router(name="bulk_knowledge_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)
logger = logging.getLogger(__name__)

_ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml"}
_MAX_FILE_BYTES = 4 * 1024 * 1024
_MAX_SOURCE_CHARS = 160_000


class BulkKnowledgeStates(StatesGroup):
    source = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 معلومات عامة", callback_data="bulk:start:PUBLIC"),
                InlineKeyboardButton(text="🏠 معلومات داخلية", callback_data="bulk:start:INTERNAL"),
            ],
            [InlineKeyboardButton(text="🔒 معلومات خاصة", callback_data="bulk:start:PRIVATE")],
            [InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")],
        ]
    )


def _preview_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ اعتماد الكل", callback_data="bulk:commit")],
            [InlineKeyboardButton(text="❌ إلغاء", callback_data="bulk:cancel")],
        ]
    )


def _back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ تغذية العقل", callback_data="brain:ingest")]]
    )


def _preview_text(candidates: list[KnowledgeCandidate], visibility: str, source_name: str) -> str:
    visibility_label = {
        "PUBLIC": "🌍 عام",
        "INTERNAL": "🏠 داخلي",
        "PRIVATE": "🔒 خاص",
    }.get(visibility, visibility)
    lines = [
        "📥 معاينة تغذية العقل",
        "",
        f"المصدر: {source_name}",
        f"مستوى الاستخدام: {visibility_label}",
        f"المعلومات المستخرجة: {len(candidates)}",
        "",
    ]
    for index, item in enumerate(candidates[:24], start=1):
        lines.append(f"{index}. {knowledge_type_text(item.type)} — {item.title}")
    if len(candidates) > 24:
        lines.append(f"… و{len(candidates) - 24} معلومة إضافية")
    lines.extend(
        [
            "",
            "لم يتم حفظ شيء بعد. راجع العدد والعناوين ثم اختر اعتماد الكل أو إلغاء.",
        ]
    )
    return "\n".join(lines)[:4000]


async def _document_text(message: Message, bot: Bot) -> tuple[str, str]:
    document = message.document
    if document is None:
        raise ValueError("أرسل نصًا أو ملفًا مدعومًا.")
    file_name = document.file_name or "uploaded.txt"
    lower = file_name.casefold()
    extension = next((ext for ext in _ALLOWED_EXTENSIONS if lower.endswith(ext)), None)
    if extension is None:
        raise ValueError("الملفات المدعومة حاليًا: TXT, MD, CSV, JSON, YAML.")
    if document.file_size and document.file_size > _MAX_FILE_BYTES:
        raise ValueError("حجم الملف كبير جدًا. الحد الحالي 4 MB لكل عملية تغذية.")

    telegram_file = await bot.get_file(document.file_id)
    if not telegram_file.file_path:
        raise ValueError("Telegram لم يُرجع مسار الملف.")
    target = BytesIO()
    await bot.download_file(telegram_file.file_path, destination=target)
    data = target.getvalue()
    if len(data) > _MAX_FILE_BYTES:
        raise ValueError("حجم الملف كبير جدًا. الحد الحالي 4 MB لكل عملية تغذية.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    return text, file_name


@router.callback_query(F.data == "brain:ingest")
async def bulk_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    text = (
        "📥 تغذية العقل\n\n"
        "بدل إضافة كل معلومة يدويًا، أرسل كتلة كبيرة من بيانات نشاطك مرة واحدة: الخدمات، "
        "الأسعار، الباقات، السياسات، الأسئلة الشائعة، الشروط وغيرها.\n\n"
        "يمكنك لصق نص طويل أو رفع TXT / MD / CSV / JSON / YAML. سيحلله السكرتير ويعرض "
        "معاينة قبل الحفظ.\n\n"
        "اختر مستوى استخدام البيانات التي سترسلها:"
    )
    if callback.message:
        await callback.message.edit_text(text, reply_markup=_home_keyboard())
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("bulk:start:"))
async def bulk_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    visibility = (callback.data or "").rsplit(":", 1)[-1].upper()
    if visibility not in {"PUBLIC", "INTERNAL", "PRIVATE"}:
        await safe_callback_answer(callback, "مستوى غير صالح", show_alert=True)
        return
    await state.clear()
    await state.update_data(bulk_visibility=visibility)
    await state.set_state(BulkKnowledgeStates.source)
    if callback.message:
        await callback.message.answer(
            "أرسل الآن كل البيانات في رسالة واحدة، أو ارفع ملفًا.\n\n"
            "مثال: تعريف النشاط + الخدمات + الباقات + الأسعار + المدد + طرق الدفع + السياسات + "
            "الأسئلة الشائعة. لا تحتاج تقسيمها يدويًا.",
            reply_markup=_back_keyboard(),
        )
    await safe_callback_answer(callback)


@router.message(BulkKnowledgeStates.source)
async def bulk_receive(message: Message, state: FSMContext, bot: Bot) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    data = await state.get_data()
    visibility = str(data.get("bulk_visibility") or "INTERNAL")

    try:
        if message.text:
            source_text = message.text
            source_name = "نص ملصق"
        elif message.document:
            source_text, source_name = await _document_text(message, bot)
        else:
            await message.answer("أرسل نصًا أو ملفًا مدعومًا.")
            return
        source_text = source_text.strip()
        if not source_text:
            await message.answer("المصدر فارغ.")
            return
        if len(source_text) > _MAX_SOURCE_CHARS:
            await message.answer(
                "المصدر كبير جدًا لهذه العملية. قسّمه إلى جزأين أو أكثر؛ الحد الحالي 160 ألف حرف."
            )
            return
        if not settings.text_ai_configured:
            await message.answer(
                "خدمة تنظيم المعرفة غير مهيأة حاليًا، لذلك لا يمكن تحليل التغذية الجماعية."
            )
            return

        wait = await message.answer("🧠 جارٍ تحليل البيانات وتقسيمها إلى معرفة منظمة…")
        provider = build_ai_provider(settings)
        candidates = await extract_bulk_candidates(provider, text=source_text, max_items=120)
        if not candidates:
            await wait.edit_text("لم أستطع استخراج معلومات واضحة من هذا المصدر.")
            return
        await state.update_data(
            bulk_candidates=[item.to_dict() for item in candidates],
            bulk_source_name=source_name,
            bulk_source_hash=source_content_hash(source_text),
        )
        await state.set_state(None)
        await wait.edit_text(
            _preview_text(candidates, visibility, source_name),
            reply_markup=_preview_keyboard(),
        )
    except Exception:
        logger.exception("bulk_knowledge_analysis_failed source=%s", source_name)
        await state.clear()
        await message.answer(
            "تعذر تحليل المصدر حاليًا. لم تُحفظ أي معلومة؛ يمكنك المحاولة مرة أخرى.",
            reply_markup=_back_keyboard(),
        )


@router.callback_query(F.data == "bulk:commit")
async def bulk_commit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    data = await state.get_data()
    raw_candidates = data.get("bulk_candidates") or []
    visibility = str(data.get("bulk_visibility") or "INTERNAL")
    source_name = str(data.get("bulk_source_name") or "bulk")[:120]
    source_hash = str(data.get("bulk_source_hash") or "")
    candidates = [
        KnowledgeCandidate(
            type=str(item.get("type") or "GENERAL"),
            title=str(item.get("title") or ""),
            content=str(item.get("content") or ""),
            tags=tuple(str(tag) for tag in (item.get("tags") or [])),
        )
        for item in raw_candidates
        if isinstance(item, dict) and item.get("title") and item.get("content")
    ]
    if not candidates:
        await safe_callback_answer(callback, "انتهت المعاينة. أعد التغذية.", show_alert=True)
        return

    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        saved = save_bulk_candidates(
            session,
            owner=owner,
            candidates=candidates,
            visibility=visibility,
            source=f"OWNER_BULK:{source_name}",
            source_hash=source_hash,
            source_name=source_name,
        )
        session.commit()
    await state.clear()
    if saved.duplicate_of_batch_id is not None:
        if callback.message:
            await callback.message.edit_text(
                "ℹ️ هذا المصدر محفوظ مسبقًا، لذلك لم أضف نسخة مكررة.",
                reply_markup=_back_keyboard(),
            )
        await safe_callback_answer(callback, "المصدر موجود مسبقًا")
        return
    if callback.message:
        await callback.message.edit_text(
            f"✅ تم حفظ {len(saved.item_ids)} من المعلومات ضمن الدفعة #{saved.batch_id}.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📚 عرض المعرفة", callback_data="brain:knowledge")],
                    [InlineKeyboardButton(text="📥 تغذية أخرى", callback_data="brain:ingest")],
                ]
            ),
        )
    await safe_callback_answer(callback, "تم الحفظ")


@router.callback_query(F.data == "bulk:cancel")
async def bulk_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            "❌ ألغيت العملية ولم يتم حفظ أي معلومة.",
            reply_markup=_back_keyboard(),
        )
    await safe_callback_answer(callback, "تم الإلغاء")
