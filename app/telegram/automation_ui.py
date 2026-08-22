from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select

from app.audit.service import write_audit_log
from app.config import get_settings
from app.db.enums import FlowStatus
from app.db.models import CustomIntent, Flow, FlowStep
from app.db.repositories import OwnerRepository
from app.db.session import SessionLocal
from app.flows.service import load_flow_definition
from app.intents.service import list_custom_intents
from app.security.owner import OwnerGuard
from app.telegram.callback_safety import safe_callback_answer

router = Router(name="automation_ui")
settings = get_settings()
guard = OwnerGuard(settings.owner_telegram_id)


class AutomationStates(StatesGroup):
    flow_name = State()
    flow_description = State()
    flow_triggers = State()
    flow_questions = State()
    flow_completion = State()
    intent_name = State()
    intent_examples = State()
    intent_threshold = State()


def _is_owner(user_id: int | None) -> bool:
    return guard.is_owner(user_id)


def _split_values(raw: str, *, limit: int) -> list[str]:
    values = re.split(r"[,،|\n]+", raw)
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        key = cleaned.casefold()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        result.append(cleaned[:160])
        if len(result) >= limit:
            break
    return result


def _status_label(value: str) -> str:
    return {
        FlowStatus.DRAFT.value: "مسودة",
        FlowStatus.PUBLISHED.value: "منشور",
        FlowStatus.ARCHIVED.value: "مؤرشف",
    }.get(value, "غير معروف")


def _home_text(flows: list[Flow], intents: list[CustomIntent]) -> str:
    lines = [
        "🧭 الأتمتة الذكية",
        "",
        "أنشئ إجراءً منظمًا يجمع المعلومات خطوة بخطوة، واربطه بعبارات يفهمها السكرتير.",
        "كل إجراء يبقى مسودة حتى تنشره بنفسك، ولا تُعتمد اقتراحات أو نوايا بصمت.",
        "",
        f"الإجراءات: {len(flows)}",
        f"النوايا المخصصة: {len(intents)}",
    ]
    if flows:
        lines.append("\nالإجراءات الحالية:")
        for row in flows[:8]:
            lines.append(f"• {row.name} — {_status_label(row.status)} — النسخة {row.version}")
    if intents:
        lines.append("\nعبارات التوجيه:")
        for row in intents[:8]:
            state = "فعالة" if row.enabled else "متوقفة"
            lines.append(f"• {row.name} — {state} — ثقة {round(row.confidence_threshold * 100)}%")
    return "\n".join(lines)[:4000]


def _home_keyboard(flows: list[Flow], intents: list[CustomIntent]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="➕ إجراء جديد", callback_data="automation:flow:new"),
            InlineKeyboardButton(text="➕ نية مخصصة", callback_data="automation:intent:new"),
        ]
    ]
    for flow in flows[:8]:
        if flow.status == FlowStatus.DRAFT.value:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"👁 تجربة {flow.name[:28]}",
                        callback_data=f"automation:flow:test:{flow.id}",
                    ),
                    InlineKeyboardButton(
                        text="✅ نشر", callback_data=f"automation:flow:publish:{flow.id}"
                    ),
                ]
            )
        elif flow.status == FlowStatus.PUBLISHED.value:
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"✏️ تعديل {flow.name[:20]}",
                        callback_data=f"automation:flow:revise:{flow.id}",
                    ),
                    InlineKeyboardButton(
                        text="📦 أرشفة",
                        callback_data=f"automation:flow:archive:{flow.id}",
                    )
                ]
            )
    for intent in intents[:8]:
        toggle = "⏸ إيقاف" if intent.enabled else "▶️ تشغيل"
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"✏️ {intent.name[:18]}",
                    callback_data=f"automation:intent:edit:{intent.id}",
                ),
                InlineKeyboardButton(
                    text=toggle,
                    callback_data=f"automation:intent:toggle:{intent.id}",
                ),
                InlineKeyboardButton(
                    text="🗑 حذف", callback_data=f"automation:intent:delete:{intent.id}"
                ),
            ]
        )
    rows.append([InlineKeyboardButton(text="⬅️ القائمة الرئيسية", callback_data="brain:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_home(callback: CallbackQuery, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flows = list(
            session.scalars(
                select(Flow)
                .where(Flow.owner_id == owner.id)
                .order_by(Flow.updated_at.desc(), Flow.id.desc())
            )
        )
        intents = list_custom_intents(session, owner_id=owner.id)
        session.commit()
    if callback.message:
        await callback.message.edit_text(
            _home_text(flows, intents),
            reply_markup=_home_keyboard(flows, intents),
        )
    await safe_callback_answer(callback)


@router.callback_query(F.data == "automation:home")
async def automation_home(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await _show_home(callback, state)


@router.callback_query(F.data == "automation:flow:new")
async def new_flow(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    await state.set_state(AutomationStates.flow_name)
    if callback.message:
        await callback.message.answer("ما اسم الإجراء كما سيظهر لك؟")
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("automation:flow:revise:"))
async def revise_flow(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتعرف على الإجراء.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flow = _owned_flow(session, owner_id=owner.id, flow_id=int(raw_id))
        if flow is None or flow.status != FlowStatus.PUBLISHED.value:
            await safe_callback_answer(callback, "الإجراء غير متاح للتعديل.", show_alert=True)
            return
        triggers = list((flow.completion_action_json or {}).get("trigger_phrases") or [])
        await state.clear()
        await state.update_data(
            flow_name=flow.name,
            flow_description=flow.description,
            flow_triggers=triggers,
            flow_version=flow.version + 1,
            supersedes_flow_id=flow.id,
        )
    await state.set_state(AutomationStates.flow_questions)
    if callback.message:
        await callback.message.answer(
            "اكتب أسئلة النسخة الجديدة، واجعل كل سؤال في سطر مستقل.\n\n"
            "ستبقى أي محادثة بدأت النسخة السابقة على خطواتها الأصلية دون تغيير."
        )
    await safe_callback_answer(callback)


@router.message(AutomationStates.flow_name)
async def flow_name(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("اكتب اسمًا واضحًا للإجراء.")
        return
    await state.update_data(flow_name=value[:255])
    await state.set_state(AutomationStates.flow_description)
    await message.answer("اكتب وصفًا قصيرًا للهدف من الإجراء، أو أرسل — للتخطي.")


@router.message(AutomationStates.flow_description)
async def flow_description(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    await state.update_data(flow_description="" if value in {"—", "-"} else value[:1000])
    await state.set_state(AutomationStates.flow_triggers)
    await message.answer(
        "ما العبارات التي تدل على هذا الطلب؟\n\n"
        "افصل بينها بفواصل. مثال: أريد حجزًا، حجز موعد، موعد جديد"
    )


@router.message(AutomationStates.flow_triggers)
async def flow_triggers(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    values = _split_values(message.text or "", limit=20)
    if not values:
        await message.answer("أضف عبارة واحدة على الأقل ليتمكن السكرتير من فهم الطلب.")
        return
    await state.update_data(flow_triggers=values)
    await state.set_state(AutomationStates.flow_questions)
    await message.answer(
        "اكتب المعلومات التي تريد جمعها، واجعل كل سؤال في سطر مستقل.\n\n"
        "مثال:\nما الاسم؟\nما وسيلة التواصل المناسبة؟\nاكتب تفاصيل الطلب."
    )


@router.message(AutomationStates.flow_questions)
async def flow_questions(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    questions = [line.strip()[:500] for line in (message.text or "").splitlines() if line.strip()]
    if not questions:
        await message.answer("اكتب سؤالًا واحدًا على الأقل.")
        return
    if len(questions) > 12:
        await message.answer("يمكن أن يحتوي الإجراء على 12 سؤالًا كحد أقصى من هذه الواجهة.")
        return
    await state.update_data(flow_questions=questions)
    await state.set_state(AutomationStates.flow_completion)
    await message.answer("ما الرسالة التي تظهر للعميل بعد اكتمال الإجراء؟")


@router.message(AutomationStates.flow_completion)
async def flow_completion(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    completion = (message.text or "").strip()
    if not completion:
        await message.answer("اكتب رسالة ختامية واضحة.")
        return
    data = await state.get_data()
    questions = list(data.get("flow_questions") or [])
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flow = Flow(
            owner_id=owner.id,
            name=str(data.get("flow_name") or "إجراء")[:255],
            description=str(data.get("flow_description") or "")[:2000],
            version=int(data.get("flow_version") or 1),
            status=FlowStatus.DRAFT.value,
            entry_step_key="question_1",
            completion_action_json={
                "message": completion[:2000],
                "trigger_phrases": list(data.get("flow_triggers") or []),
                "supersedes_flow_id": data.get("supersedes_flow_id"),
            },
        )
        session.add(flow)
        session.flush()
        for index, prompt in enumerate(questions, start=1):
            next_key = f"question_{index + 1}" if index < len(questions) else "complete"
            session.add(
                FlowStep(
                    flow_id=flow.id,
                    step_key=f"question_{index}",
                    step_type="ASK_TEXT",
                    config_json={"prompt": prompt, "required": True},
                    next_step_rules_json={"next_key": next_key},
                    sort_order=index,
                )
            )
        session.add(
            FlowStep(
                flow_id=flow.id,
                step_key="complete",
                step_type="COMPLETE",
                config_json={},
                next_step_rules_json={},
                sort_order=len(questions) + 1,
            )
        )
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="FLOW_DRAFT_CREATED",
            entity_type="FLOW",
            entity_id=flow.id,
        )
        session.commit()
        flow_id = flow.id
        name = flow.name
    await state.clear()
    await message.answer(
        f"🧪 أصبحت «{name}» مسودة جاهزة للمعاينة.\n\n"
        "لن تبدأ مع أي عميل حتى تختبرها ثم تضغط نشر.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="👁 معاينة التجربة",
                        callback_data=f"automation:flow:test:{flow_id}",
                    ),
                    InlineKeyboardButton(
                        text="✅ نشر", callback_data=f"automation:flow:publish:{flow_id}"
                    ),
                ],
                [InlineKeyboardButton(text="⬅️ الأتمتة", callback_data="automation:home")],
            ]
        ),
    )


def _owned_flow(session, *, owner_id: int, flow_id: int) -> Flow | None:
    return session.scalar(select(Flow).where(Flow.id == flow_id, Flow.owner_id == owner_id))


@router.callback_query(F.data.startswith("automation:flow:test:"))
async def test_flow(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتعرف على الإجراء.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        loaded = load_flow_definition(session, flow_id=int(raw_id))
        if loaded is None or loaded[0].owner_id != owner.id:
            await safe_callback_answer(callback, "لم أجد هذا الإجراء.", show_alert=True)
            return
        flow, definition = loaded
        prompts = [
            step.prompt
            for step in definition.steps.values()
            if step.prompt and step.type.value.startswith("ASK_")
        ]
        triggers = list((flow.completion_action_json or {}).get("trigger_phrases") or [])
    lines = [f"🧪 معاينة «{flow.name}»", "", "عبارات البدء:"]
    lines.extend(f"• {value}" for value in triggers)
    lines.append("\nالأسئلة بالترتيب:")
    lines.extend(f"{index}. {value}" for index, value in enumerate(prompts, start=1))
    lines.append(f"\nرسالة الإكمال:\n{(flow.completion_action_json or {}).get('message', '')}")
    if callback.message:
        await callback.message.answer("\n".join(lines)[:4000])
    await safe_callback_answer(callback, "اكتملت المعاينة")


@router.callback_query(F.data.startswith("automation:flow:publish:"))
async def publish_flow(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتعرف على الإجراء.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flow = _owned_flow(session, owner_id=owner.id, flow_id=int(raw_id))
        loaded = load_flow_definition(session, flow_id=int(raw_id)) if flow else None
        if flow is None or loaded is None:
            await safe_callback_answer(callback, "لم أجد هذا الإجراء.", show_alert=True)
            return
        if flow.status == FlowStatus.ARCHIVED.value:
            await safe_callback_answer(callback, "الإجراء مؤرشف ولا يمكن نشره.", show_alert=True)
            return
        loaded[1].validate()
        flow.status = FlowStatus.PUBLISHED.value
        triggers = list((flow.completion_action_json or {}).get("trigger_phrases") or [])
        supersedes_id = int(
            (flow.completion_action_json or {}).get("supersedes_flow_id") or 0
        )
        candidates = list(
            session.scalars(
                select(CustomIntent).where(
                    CustomIntent.owner_id == owner.id,
                    CustomIntent.linked_action_type == "START_FLOW",
                )
            )
        )
        linked = next(
            (
                row
                for row in candidates
                if int((row.linked_action_config_json or {}).get("flow_id") or 0)
                in {flow.id, supersedes_id}
            ),
            None,
        )
        if supersedes_id:
            superseded = _owned_flow(session, owner_id=owner.id, flow_id=supersedes_id)
            if superseded is not None:
                superseded.status = FlowStatus.ARCHIVED.value
        if linked is None:
            linked = CustomIntent(
                owner_id=owner.id,
                name=flow.name,
                description=flow.description,
                examples_json=triggers,
                linked_action_type="START_FLOW",
                linked_action_config_json={"flow_id": flow.id},
                confidence_threshold=settings.bounded_custom_intent_threshold,
                enabled=True,
            )
            session.add(linked)
        else:
            linked.name = flow.name
            linked.description = flow.description
            linked.examples_json = triggers
            linked.linked_action_config_json = {"flow_id": flow.id}
            linked.enabled = True
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="FLOW_PUBLISHED",
            entity_type="FLOW",
            entity_id=flow.id,
        )
        session.commit()
        name = flow.name
    await safe_callback_answer(callback, "تم نشر الإجراء")
    if callback.message:
        await callback.message.answer(
            f"✅ نُشر «{name}». سيتعرف السكرتير على عبارات البدء التي اعتمدتها، "
            "ويمكنك إيقافها من قسم الأتمتة."
        )


@router.callback_query(F.data.startswith("automation:flow:archive:"))
async def archive_flow(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        await safe_callback_answer(callback, "لم أتعرف على الإجراء.", show_alert=True)
        return
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        flow = _owned_flow(session, owner_id=owner.id, flow_id=int(raw_id))
        if flow is None:
            await safe_callback_answer(callback, "لم أجد هذا الإجراء.", show_alert=True)
            return
        flow.status = FlowStatus.ARCHIVED.value
        linked = list(
            session.scalars(
                select(CustomIntent).where(
                    CustomIntent.owner_id == owner.id,
                    CustomIntent.linked_action_type == "START_FLOW",
                )
            )
        )
        for intent in linked:
            if int((intent.linked_action_config_json or {}).get("flow_id") or 0) == flow.id:
                intent.enabled = False
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="FLOW_ARCHIVED",
            entity_type="FLOW",
            entity_id=flow.id,
        )
        session.commit()
    await safe_callback_answer(callback, "تمت أرشفة الإجراء وإيقاف عباراته")


@router.callback_query(F.data == "automation:intent:new")
async def new_intent(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    await state.clear()
    await state.set_state(AutomationStates.intent_name)
    if callback.message:
        await callback.message.answer("ما اسم الطلب الذي تريد أن يتعرف عليه السكرتير؟")
    await safe_callback_answer(callback)


@router.callback_query(F.data.startswith("automation:intent:edit:"))
async def edit_intent(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    intent_id = _intent_id(callback)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = session.scalar(
            select(CustomIntent).where(
                CustomIntent.id == intent_id,
                CustomIntent.owner_id == owner.id,
            )
        )
        if row is None:
            await safe_callback_answer(callback, "لم أجد هذا الطلب.", show_alert=True)
            return
    await state.clear()
    await state.update_data(intent_edit_id=intent_id)
    await state.set_state(AutomationStates.intent_name)
    if callback.message:
        await callback.message.answer(
            "اكتب الاسم الجديد للطلب. ستراجع بعده الأمثلة ودرجة التطابق والإجراء المرتبط."
        )
    await safe_callback_answer(callback)


@router.message(AutomationStates.intent_name)
async def intent_name(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    value = (message.text or "").strip()
    if not value:
        await message.answer("اكتب اسمًا واضحًا للطلب.")
        return
    await state.update_data(intent_name=value[:128])
    await state.set_state(AutomationStates.intent_examples)
    await message.answer("اكتب أمثلة لعبارات العميل وافصل بينها بفواصل.")


@router.message(AutomationStates.intent_examples)
async def intent_examples(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    values = _split_values(message.text or "", limit=20)
    if not values:
        await message.answer("أضف مثالًا واحدًا على الأقل.")
        return
    await state.update_data(intent_examples=values)
    await state.set_state(AutomationStates.intent_threshold)
    await message.answer(
        "ما درجة التطابق المطلوبة؟ أرسل رقمًا من 50 إلى 100.\n"
        f"المقترح الآمن: {round(settings.bounded_custom_intent_threshold * 100)}"
    )


@router.message(AutomationStates.intent_threshold)
async def intent_threshold(message: Message, state: FSMContext) -> None:
    if not _is_owner(message.from_user.id if message.from_user else None):
        return
    raw = (message.text or "").strip().replace("%", "")
    if not raw.isdigit() or not 50 <= int(raw) <= 100:
        await message.answer("أرسل رقمًا من 50 إلى 100.")
        return
    await state.update_data(intent_threshold=int(raw) / 100)
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
    rows = [
        [InlineKeyboardButton(text="توجيه فقط دون إجراء", callback_data="automation:intent:link:0")]
    ]
    rows.extend(
        [
            InlineKeyboardButton(
                text=f"بدء: {flow.name[:48]}",
                callback_data=f"automation:intent:link:{flow.id}",
            )
        ]
        for flow in flows[:20]
    )
    await message.answer(
        "اختر ما يحدث عند التعرف على الطلب. التوجيه وحده يساعد فهم الرد ولا يرسل شيئًا تلقائيًا.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("automation:intent:link:"))
async def link_intent(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    raw_flow_id = (callback.data or "").rsplit(":", 1)[-1]
    if not raw_flow_id.isdigit():
        await safe_callback_answer(callback, "اختيار غير صالح.", show_alert=True)
        return
    data = await state.get_data()
    if not data.get("intent_name") or not data.get("intent_examples"):
        await safe_callback_answer(callback, "انتهت جلسة الإعداد. ابدأ من جديد.", show_alert=True)
        return
    flow_id = int(raw_flow_id)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        action_type = "NONE"
        action_config: dict = {}
        if flow_id:
            flow = _owned_flow(session, owner_id=owner.id, flow_id=flow_id)
            if flow is None or flow.status != FlowStatus.PUBLISHED.value:
                await safe_callback_answer(callback, "الإجراء غير متاح.", show_alert=True)
                return
            action_type = "START_FLOW"
            action_config = {"flow_id": flow.id}
        edit_id = data.get("intent_edit_id")
        row = (
            session.scalar(
                select(CustomIntent).where(
                    CustomIntent.id == int(edit_id),
                    CustomIntent.owner_id == owner.id,
                )
            )
            if edit_id
            else None
        )
        if edit_id and row is None:
            await safe_callback_answer(callback, "لم أجد الطلب المراد تعديله.", show_alert=True)
            return
        if row is None:
            row = CustomIntent(owner_id=owner.id)
            session.add(row)
        row.name = str(data["intent_name"])[:128]
        row.description = row.description or ""
        row.examples_json = list(data["intent_examples"])
        row.linked_action_type = action_type
        row.linked_action_config_json = action_config
        row.confidence_threshold = float(data.get("intent_threshold") or 0.82)
        row.enabled = True
        session.flush()
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="CUSTOM_INTENT_UPDATED" if edit_id else "CUSTOM_INTENT_CREATED",
            entity_type="CUSTOM_INTENT",
            entity_id=row.id,
        )
        session.commit()
        name = row.name
    await state.clear()
    await safe_callback_answer(callback, "تم حفظ الطلب المخصص")
    if callback.message:
        await callback.message.answer(
            f"✅ أصبح «{name}» فعالًا بالعبارات ودرجة التطابق التي اعتمدتها."
        )


def _intent_id(callback: CallbackQuery) -> int | None:
    raw = (callback.data or "").rsplit(":", 1)[-1]
    return int(raw) if raw.isdigit() else None


@router.callback_query(F.data.startswith("automation:intent:toggle:"))
async def toggle_intent(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    intent_id = _intent_id(callback)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = session.scalar(
            select(CustomIntent).where(
                CustomIntent.id == intent_id,
                CustomIntent.owner_id == owner.id,
            )
        )
        if row is None:
            await safe_callback_answer(callback, "لم أجد هذا الطلب.", show_alert=True)
            return
        row.enabled = not row.enabled
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="CUSTOM_INTENT_TOGGLED",
            entity_type="CUSTOM_INTENT",
            entity_id=row.id,
            metadata={"enabled": row.enabled},
        )
        session.commit()
        enabled = row.enabled
    await safe_callback_answer(callback, "تم التشغيل" if enabled else "تم الإيقاف")


@router.callback_query(F.data.startswith("automation:intent:delete:"))
async def delete_intent(callback: CallbackQuery) -> None:
    if not _is_owner(callback.from_user.id):
        await safe_callback_answer(callback)
        return
    intent_id = _intent_id(callback)
    with SessionLocal() as session:
        owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
        row = session.scalar(
            select(CustomIntent).where(
                CustomIntent.id == intent_id,
                CustomIntent.owner_id == owner.id,
            )
        )
        if row is None:
            await safe_callback_answer(callback, "لم أجد هذا الطلب.", show_alert=True)
            return
        write_audit_log(
            session,
            owner_id=owner.id,
            actor="OWNER_TELEGRAM",
            action="CUSTOM_INTENT_DELETED",
            entity_type="CUSTOM_INTENT",
            entity_id=row.id,
        )
        session.delete(row)
        session.commit()
    await safe_callback_answer(callback, "تم حذف الطلب المخصص")
