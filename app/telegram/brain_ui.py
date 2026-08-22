from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.brain.service import (
    add_response_policy,
    brain_counts,
    get_or_create_profile,
    list_response_policies,
    update_profile,
)
from app.config import get_settings
from app.db.models import KnowledgeItem
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.knowledge.admin import add_knowledge, delete_knowledge, list_knowledge
from app.security.owner import OwnerGuard
from app.telegram.owner_ui import main_admin_keyboard
from app.telegram.professional_copy import knowledge_type_text, policy_action_text

router = Router(name="secretary_brain_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class BrainStates(StatesGroup):
    profile_name = State()
    profile_activity = State()
    profile_style = State()
    profile_instructions = State()
    knowledge_title = State()
    knowledge_content = State()
    policy_name = State()
    policy_description = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _brain_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏢 الهوية", callback_data="brain:profile"),
                InlineKeyboardButton(text="📚 المعرفة", callback_data="brain:knowledge"),
            ],
            [
                InlineKeyboardButton(text="👥 ذاكرة الأشخاص", callback_data="brain:memory"),
                InlineKeyboardButton(text="🎛️ قواعد الرد", callback_data="brain:policies"),
            ],
            [InlineKeyboardButton(text="⬅️ القائمة الرئيسية", callback_data="brain:main")],
        ]
    )


def _back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")]]
    )


def _profile_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ تعديل الهوية", callback_data="brain:profile:edit")],
            [InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")],
        ]
    )


def _knowledge_keyboard(rows: list[KnowledgeItem]) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ إضافة معلومة", callback_data="brain:knowledge:add")]
    ]
    for row in rows[:8]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 #{row.id} {row.title[:24]}",
                    callback_data=f"brain:knowledge:delete:{row.id}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _knowledge_categories_keyboard() -> InlineKeyboardMarkup:
    values = [
        ("🧾 عام", "GENERAL"),
        ("🛠️ خدمة", "SERVICE"),
        ("📦 منتج", "PRODUCT"),
        ("💰 سعر", "PRICE"),
        ("❓ سؤال شائع", "FAQ"),
        ("📜 سياسة", "POLICY"),
        ("🧩 مخصص", "CUSTOM"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for index in range(0, len(values), 2):
        rows.append(
            [
                InlineKeyboardButton(text=label, callback_data=f"brain:knowledge:cat:{value}")
                for label, value in values[index : index + 2]
            ]
        )
    rows.append([InlineKeyboardButton(text="إلغاء", callback_data="brain:knowledge")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _visibility_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌍 عام", callback_data="brain:knowledge:vis:PUBLIC"),
                InlineKeyboardButton(text="🏠 داخلي", callback_data="brain:knowledge:vis:INTERNAL"),
            ],
            [InlineKeyboardButton(text="🔒 خاص", callback_data="brain:knowledge:vis:PRIVATE")],
            [InlineKeyboardButton(text="إلغاء", callback_data="brain:knowledge")],
        ]
    )


def _policy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ إضافة قاعدة", callback_data="brain:policy:add")],
            [InlineKeyboardButton(text="⬅️ عقل السكرتير", callback_data="brain:home")],
        ]
    )


def _policy_action_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🟡 تتطلب موافقة", callback_data="brain:policy:action:REQUIRE_APPROVAL"
                ),
                InlineKeyboardButton(
                    text="🔴 تصعيد لي", callback_data="brain:policy:action:ESCALATE"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="ℹ️ توجيه فقط", callback_data="brain:policy:action:GUIDE_ONLY"
                )
            ],
            [InlineKeyboardButton(text="إلغاء", callback_data="brain:policies")],
        ]
    )


async def _edit(callback: CallbackQuery, text: str, markup: InlineKeyboardMarkup) -> None:
    if callback.message:
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "brain:main")
async def brain_main(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await _edit(
        callback,
        "🧑‍💼 السكرتير\n\nاختر القسم الذي تريد إدارته:",
        main_admin_keyboard(),
    )


@router.callback_query(F.data == "brain:home")
async def brain_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile = get_or_create_profile(session, owner_id=owner.id)
        counts = brain_counts(session, owner_id=owner.id)
        knowledge_count = sum(1 for _ in list_knowledge(session, owner_id=owner.id, limit=1000))
        session.commit()
        profile_ready = bool(profile.activity_description.strip() or profile.display_name.strip())
    await _edit(
        callback,
        "🧠 عقل السكرتير\n\n"
        f"الهوية: {'✅ مهيأة' if profile_ready else '⚪ تحتاج إعداد'}\n"
        f"المعرفة: {knowledge_count}\n"
        f"ذاكرة الأشخاص: {counts['memories']}\n"
        f"قواعد الرد: {counts['policies']}\n\n"
        "كل هذه البيانات قابلة للتغيير بدون تعديل الكود، لذلك تستطيع تغيير نشاطك أو "
        "خدماتك لاحقًا بحرية.",
        _brain_home_keyboard(),
    )


@router.callback_query(F.data == "brain:profile")
async def brain_profile(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        profile = get_or_create_profile(session, owner_id=owner.id)
        session.commit()
        language_label = (
            profile.language if profile.language and profile.language != "AUTO" else "تلقائية"
        )
        text = (
            "🏢 هوية السكرتير\n\n"
            f"الاسم/العلامة: {profile.display_name or '—'}\n"
            f"النشاط: {profile.activity_description or '—'}\n"
            f"المجال: {profile.industry or '—'}\n"
            f"أسلوب الرد: {profile.reply_style or '—'}\n"
            f"اللغة: {language_label}\n"
            f"النبرة: {profile.tone or '—'}\n"
            f"تعليمات خاصة: {profile.custom_instructions or '—'}"
        )
    await _edit(callback, text[:4000], _profile_keyboard())


@router.callback_query(F.data == "brain:profile:edit")
async def brain_profile_edit(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(BrainStates.profile_name)
    await callback.answer()
    if callback.message:
        await callback.message.answer("🏢 اكتب اسمك أو اسم النشاط/العلامة الذي سيمثله السكرتير:")


@router.message(BrainStates.profile_name)
async def brain_profile_name(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    await state.update_data(profile_name=(message.text or "").strip())
    await state.set_state(BrainStates.profile_activity)
    await message.answer("📝 صف نشاطك الحالي وما الذي تقدمه للعملاء. يمكنك تغييره لاحقًا بالكامل:")


@router.message(BrainStates.profile_activity)
async def brain_profile_activity(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    await state.update_data(profile_activity=(message.text or "").strip())
    await state.set_state(BrainStates.profile_style)
    await message.answer("💬 كيف تريد أسلوب الرد؟ مثال: مختصر، احترافي وودود، بدون مبالغة:")


@router.message(BrainStates.profile_style)
async def brain_profile_style(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    await state.update_data(profile_style=(message.text or "").strip())
    await state.set_state(BrainStates.profile_instructions)
    await message.answer(
        "🎛️ اكتب أي تعليمات ثابتة للسكرتير. مثال: لا تعطِ سعرًا نهائيًا دون معلومات معتمدة.\n"
        "أرسل — إذا لا تريد إضافة تعليمات الآن."
    )


@router.message(BrainStates.profile_instructions)
async def brain_profile_instructions(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    data = await state.get_data()
    instructions = (message.text or "").strip()
    if instructions == "—":
        instructions = ""
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        update_profile(
            session,
            owner_id=owner.id,
            display_name=str(data.get("profile_name") or ""),
            activity_description=str(data.get("profile_activity") or ""),
            reply_style=str(data.get("profile_style") or "احترافي وودود"),
            custom_instructions=instructions,
        )
        session.commit()
    await state.clear()
    await message.answer("✅ تم تحديث هوية السكرتير.", reply_markup=_back_home_keyboard())


@router.callback_query(F.data == "brain:knowledge")
async def brain_knowledge(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_knowledge(session, owner_id=owner.id, limit=10)
    lines = ["📚 معرفة السكرتير", ""]
    if not rows:
        lines.append("لا توجد معلومات محفوظة بعد.")
    else:
        for row in rows:
            visibility = {"PUBLIC": "🌍", "INTERNAL": "🏠", "PRIVATE": "🔒"}.get(
                row.visibility, "•"
            )
            lines.append(f"{visibility} #{row.id} {knowledge_type_text(row.type)} — {row.title}")
    lines.append("\n🔒 المعلومات الخاصة لا تُشارك مع خدمة الصياغة.")
    await _edit(callback, "\n".join(lines)[:4000], _knowledge_keyboard(rows))


@router.callback_query(F.data == "brain:knowledge:add")
async def brain_knowledge_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await _edit(
        callback,
        "اختر نوع المعلومة. الأنواع مجرد تنظيم ويمكن تغيير نشاطك لاحقًا:",
        _knowledge_categories_keyboard(),
    )


@router.callback_query(F.data.startswith("brain:knowledge:cat:"))
async def brain_knowledge_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    category = (callback.data or "").rsplit(":", 1)[-1].upper()
    await state.update_data(knowledge_category=category)
    await _edit(
        callback,
        "اختر مستوى استخدام المعلومة:\n\n"
        "🌍 عام: يمكن قوله للعميل\n"
        "🏠 داخلي: يوجّه السكرتير ولا يُكشف كسياسة داخلية\n"
        "🔒 خاص: لك فقط ولا يُشارك مع خدمة الصياغة",
        _visibility_keyboard(),
    )


@router.callback_query(F.data.startswith("brain:knowledge:vis:"))
async def brain_knowledge_visibility(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    visibility = (callback.data or "").rsplit(":", 1)[-1].upper()
    if visibility not in {"PUBLIC", "INTERNAL", "PRIVATE"}:
        await callback.answer("قيمة غير صالحة", show_alert=True)
        return
    await state.update_data(knowledge_visibility=visibility)
    await state.set_state(BrainStates.knowledge_title)
    await callback.answer()
    if callback.message:
        await callback.message.answer("✏️ اكتب عنوانًا مختصرًا للمعلومة:")


@router.message(BrainStates.knowledge_title)
async def brain_knowledge_title(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("اكتب عنوانًا غير فارغ.")
        return
    await state.update_data(knowledge_title=title)
    await state.set_state(BrainStates.knowledge_content)
    await message.answer("📝 اكتب المعلومة نفسها بالتفصيل الذي تريد أن يعتمد عليه السكرتير:")


@router.message(BrainStates.knowledge_content)
async def brain_knowledge_content(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    content = (message.text or "").strip()
    if not content:
        await message.answer("اكتب محتوى غير فارغ.")
        return
    data = await state.get_data()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = add_knowledge(
            session,
            owner=owner,
            visibility=str(data.get("knowledge_visibility") or "INTERNAL"),
            title=str(data.get("knowledge_title") or "معلومة"),
            content=content,
            item_type=str(data.get("knowledge_category") or "GENERAL"),
        )
        session.commit()
        item_id = row.id
    await state.clear()
    await message.answer(f"✅ تم حفظ المعلومة #{item_id}.", reply_markup=_back_home_keyboard())


@router.callback_query(F.data.startswith("brain:knowledge:delete:"))
async def brain_knowledge_delete(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await callback.answer("معرّف غير صالح", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        ok = delete_knowledge(session, owner_id=owner.id, knowledge_id=int(raw_id))
        session.commit()
    await callback.answer("تم الحذف" if ok else "لم أجد المعلومة", show_alert=True)
    if callback.message:
        await callback.message.delete()
        await callback.message.answer("📚 تم تحديث المعرفة.", reply_markup=_back_home_keyboard())


@router.callback_query(F.data == "brain:memory")
async def brain_memory(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        counts = brain_counts(session, owner_id=owner.id)
    await _edit(
        callback,
        "👥 ذاكرة الأشخاص\n\n"
        f"الذواكر المحفوظة: {counts['memories']}\n\n"
        "كل شخص له ذاكرة منفصلة. الملاحظات الخاصة لا تُشارك مع خدمة الصياغة، ويمكن "
        "تعطيل مشاركة الذاكرة لكل شخص. واجهة تحرير الأشخاص التفصيلية مستقلة حتى لا "
        "تختلط بقاعدة المعرفة العامة.",
        _back_home_keyboard(),
    )


@router.callback_query(F.data == "brain:policies")
async def brain_policies(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        rows = list_response_policies(session, owner_id=owner.id, enabled_only=True)
    lines = ["🎛️ قواعد الرد", ""]
    if not rows:
        lines.append("لا توجد قواعد مخصصة بعد. سيظل نظام الأمان الافتراضي هو الحاكم.")
    else:
        for row in rows[:12]:
            lines.append(
                f"#{row.id} — {row.name} — {policy_action_text(row.action)}\n"
                f"{row.description[:160]}"
            )
    lines.append("\nالقواعد المخصصة لا تستطيع تجاوز قيود الأمان الأساسية مثل المخاطر العالية.")
    await _edit(callback, "\n".join(lines)[:4000], _policy_keyboard())


@router.callback_query(F.data == "brain:policy:add")
async def brain_policy_add(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(BrainStates.policy_name)
    await callback.answer()
    if callback.message:
        await callback.message.answer("✏️ اكتب اسم القاعدة. مثال: طلبات الخصم الكبيرة")


@router.message(BrainStates.policy_name)
async def brain_policy_name(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    name = (message.text or "").strip()
    if not name:
        await message.answer("اكتب اسمًا غير فارغ.")
        return
    await state.update_data(policy_name=name)
    await state.set_state(BrainStates.policy_description)
    await message.answer("📝 صف متى تنطبق القاعدة وما الذي تريد من السكرتير مراعاته:")


@router.message(BrainStates.policy_description)
async def brain_policy_description(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    description = (message.text or "").strip()
    if not description:
        await message.answer("اكتب وصفًا غير فارغ.")
        return
    await state.update_data(policy_description=description)
    await state.set_state(None)
    await message.answer(
        "اختر الإجراء الافتراضي لهذه القاعدة:", reply_markup=_policy_action_keyboard()
    )


@router.callback_query(F.data.startswith("brain:policy:action:"))
async def brain_policy_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await callback.answer()
        return
    action = (callback.data or "").rsplit(":", 1)[-1].upper()
    if action not in {"REQUIRE_APPROVAL", "ESCALATE", "GUIDE_ONLY"}:
        await callback.answer("إجراء غير صالح", show_alert=True)
        return
    data = await state.get_data()
    name = str(data.get("policy_name") or "").strip()
    description = str(data.get("policy_description") or "").strip()
    if not name or not description:
        await state.clear()
        await callback.answer("انتهت جلسة إضافة القاعدة. حاول مجددًا.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = add_response_policy(
            session,
            owner_id=owner.id,
            name=name,
            description=description,
            action=action,
            conditions_json={"natural_language": description},
        )
        session.commit()
        policy_id = row.id
    await state.clear()
    await callback.answer("تم الحفظ")
    if callback.message:
        await callback.message.answer(
            f"✅ تم حفظ قاعدة الرد #{policy_id}.",
            reply_markup=_back_home_keyboard(),
        )
