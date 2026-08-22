from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai.policy import choose_action
from app.ai.schemas import Confidence
from app.ai.text import TextResult
from app.config import Settings
from app.conversations.ingest import ingest_message
from app.db.base import Base
from app.db.enums import (
    ConversationState,
    DecisionAction,
    FlowSessionStatus,
    FlowStatus,
    RiskLevel,
)
from app.db.models import (
    Approval,
    AuditLog,
    Contact,
    Conversation,
    CustomIntent,
    Flow,
    FlowSession,
    FlowStep,
    KnowledgeItem,
    Message,
    Owner,
)
from app.flows.service import FlowAutomationBlockedError, start_flow, submit_flow_value
from app.intents.service import match_custom_intent, normalize_utterance, utterance_similarity
from app.schedules.service import (
    claim_due_reminders,
    create_reminder,
    local_time_to_utc,
    mark_reminder_delivered,
    release_reminder_claim,
    validate_timezone,
)
from app.telegram.contracts import IncomingBusinessMessage


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _owner_conversation(
    db: Session,
    *,
    owner_tg: int = 1,
    chat_id: int = 100,
) -> tuple[Owner, Conversation]:
    owner = Owner(telegram_user_id=owner_tg, display_name="المالك", timezone="Asia/Riyadh")
    db.add(owner)
    db.flush()
    contact = Contact(
        owner_id=owner.id,
        telegram_user_id=owner_tg + 10,
        display_name="عميل",
    )
    db.add(contact)
    db.flush()
    conversation = Conversation(
        owner_id=owner.id,
        contact_id=contact.id,
        telegram_chat_id=chat_id,
        business_connection_id="business-test",
        state=ConversationState.AI_APPROVAL.value,
    )
    db.add(conversation)
    db.flush()
    return owner, conversation


def _published_flow(db: Session, *, owner_id: int, name: str = "طلب خدمة") -> Flow:
    flow = Flow(
        owner_id=owner_id,
        name=name,
        description="يجمع نوع الخدمة ووسيلة التواصل",
        version=1,
        status=FlowStatus.PUBLISHED.value,
        entry_step_key="kind",
        completion_action_json={"message": "وصل طلبك وسيتابعه المسؤول."},
    )
    db.add(flow)
    db.flush()
    db.add_all(
        [
            FlowStep(
                flow_id=flow.id,
                step_key="kind",
                step_type="ASK_CHOICE",
                config_json={"prompt": "اختر نوع الخدمة", "choices": ["تصميم", "استشارة"]},
                next_step_rules_json={"next_key": "contact"},
                sort_order=1,
            ),
            FlowStep(
                flow_id=flow.id,
                step_key="contact",
                step_type="ASK_TEXT",
                config_json={"prompt": "ما وسيلة التواصل المناسبة؟"},
                next_step_rules_json={"next_key": "complete"},
                sort_order=2,
            ),
            FlowStep(
                flow_id=flow.id,
                step_key="complete",
                step_type="COMPLETE",
                config_json={},
                next_step_rules_json={},
                sort_order=3,
            ),
        ]
    )
    db.flush()
    return flow


def test_arabic_intent_normalization_and_similarity_are_data_driven() -> None:
    assert normalize_utterance("أُرِيدُ حجزًا!") == "اريد حجزا"
    assert utterance_similarity("أريد حجز موعد لو سمحت", "حجز موعد") >= 0.86
    assert utterance_similarity("أريد معرفة الأسعار", "مشكلة تسجيل الدخول") < 0.82


def test_custom_intent_respects_owner_threshold_and_enabled_state(db: Session) -> None:
    owner, _ = _owner_conversation(db)
    row = CustomIntent(
        owner_id=owner.id,
        name="حجز موعد",
        description="",
        examples_json=["أريد حجز موعد", "موعد جديد"],
        linked_action_type="NONE",
        linked_action_config_json={},
        confidence_threshold=0.82,
        enabled=True,
    )
    db.add(row)
    db.commit()

    match = match_custom_intent(db, owner_id=owner.id, text="أريد حجز موعد لو سمحت")
    assert match is not None
    assert match.name == "حجز موعد"
    row.enabled = False
    db.commit()
    assert match_custom_intent(db, owner_id=owner.id, text="أريد حجز موعد") is None
    assert match_custom_intent(db, owner_id=999, text="أريد حجز موعد") is None


def test_flow_session_is_isolated_and_keeps_published_version_snapshot(db: Session) -> None:
    owner, conversation = _owner_conversation(db)
    flow = _published_flow(db, owner_id=owner.id)
    db.commit()

    turn = start_flow(db, conversation=conversation, flow_id=flow.id)
    db.commit()
    assert turn.prompt == "اختر نوع الخدمة"
    assert turn.choices == ("تصميم", "استشارة")

    with pytest.raises(ValueError, match="invalid_choice"):
        submit_flow_value(db, conversation=conversation, value="خيار غير معتمد")
    db.rollback()

    turn = submit_flow_value(db, conversation=conversation, value="تصميم")
    db.commit()
    assert turn is not None
    assert turn.prompt == "ما وسيلة التواصل المناسبة؟"

    # Publishing/editing a later definition cannot mutate the active session snapshot.
    flow.version = 2
    current_step = db.scalar(
        select(FlowStep).where(FlowStep.flow_id == flow.id, FlowStep.step_key == "contact")
    )
    assert current_step is not None
    current_step.config_json = {"prompt": "سؤال جديد لا يجب أن يصل للجلسة الجارية"}
    db.commit()

    turn = submit_flow_value(db, conversation=conversation, value="تيليجرام")
    db.commit()
    assert turn is not None and turn.completed
    assert turn.prompt == "وصل طلبك وسيتابعه المسؤول."
    assert turn.collected_data == {"kind": "تصميم", "contact": "تيليجرام"}
    stored = db.scalar(select(FlowSession).where(FlowSession.id == turn.session_id))
    assert stored is not None
    assert stored.flow_version == 1
    assert stored.status == FlowSessionStatus.COMPLETED.value
    assert stored.definition_json["version"] == 1


def test_flow_cannot_cross_owner_or_start_twice(db: Session) -> None:
    owner, conversation = _owner_conversation(db)
    flow = _published_flow(db, owner_id=owner.id)
    other_owner, other_conversation = _owner_conversation(db, owner_tg=2, chat_id=200)
    db.commit()

    with pytest.raises(ValueError, match="not published"):
        start_flow(db, conversation=other_conversation, flow_id=flow.id)
    db.rollback()
    start_flow(db, conversation=conversation, flow_id=flow.id)
    db.commit()
    with pytest.raises(ValueError, match="already has an active flow"):
        start_flow(db, conversation=conversation, flow_id=flow.id)
    assert other_owner.id != owner.id


def test_archived_flow_cannot_start(db: Session) -> None:
    owner, conversation = _owner_conversation(db)
    flow = _published_flow(db, owner_id=owner.id)
    flow.status = FlowStatus.ARCHIVED.value
    db.commit()
    with pytest.raises(ValueError, match="not published"):
        start_flow(db, conversation=conversation, flow_id=flow.id)


def test_human_takeover_cancels_an_active_flow(db: Session) -> None:
    owner, conversation = _owner_conversation(db)
    flow = _published_flow(db, owner_id=owner.id)
    db.commit()
    turn = start_flow(db, conversation=conversation, flow_id=flow.id)
    db.commit()

    conversation.state = ConversationState.HUMAN_TAKEOVER.value
    with pytest.raises(FlowAutomationBlockedError):
        submit_flow_value(db, conversation=conversation, value="تصميم")
    db.commit()

    stored = db.get(FlowSession, turn.session_id)
    assert stored is not None
    assert stored.status == FlowSessionStatus.CANCELLED.value


def test_reminder_timezone_claim_delivery_and_retry_are_idempotent(db: Session) -> None:
    owner, _ = _owner_conversation(db)
    now = datetime.now(UTC)
    row = create_reminder(
        db,
        owner_id=owner.id,
        timezone="Asia/Riyadh",
        text="راجع الطلبات الجديدة",
        run_at=now + timedelta(minutes=1),
    )
    db.commit()

    assert claim_due_reminders(db, now=now) == []
    claims = claim_due_reminders(db, now=now + timedelta(minutes=2))
    db.commit()
    assert [claim.schedule_id for claim in claims] == [row.id]
    assert claim_due_reminders(db, now=now + timedelta(minutes=3)) == []

    # A crashed worker cannot strand a due reminder forever; the claim is a lease.
    stale_claims = claim_due_reminders(db, now=now + timedelta(minutes=8))
    db.commit()
    assert [claim.schedule_id for claim in stale_claims] == [row.id]

    release_reminder_claim(db, row.id)
    db.commit()
    assert len(claim_due_reminders(db, now=now + timedelta(minutes=4))) == 1
    mark_reminder_delivered(db, row.id)
    db.commit()
    assert claim_due_reminders(db, now=now + timedelta(minutes=5)) == []


def test_timezone_parser_uses_owner_zone_and_rejects_invalid_values() -> None:
    assert validate_timezone("Asia/Riyadh") == "Asia/Riyadh"
    utc = local_time_to_utc(value="2026-08-25 14:30", timezone="Asia/Riyadh")
    assert utc.isoformat().startswith("2026-08-25T11:30:00")
    with pytest.raises(ValueError, match="unknown timezone"):
        validate_timezone("Mars/Base")
    with pytest.raises(ValueError, match="invalid reminder time"):
        local_time_to_utc(value="غدًا", timezone="Asia/Riyadh")


@pytest.mark.parametrize(
    ("state", "risk", "confidence", "grounded", "public", "expected"),
    [
        (
            ConversationState.AI_AUTO,
            RiskLevel.LOW,
            Confidence(intent=0.94, retrieval=0.9, answer=0.92, policy=0.96),
            True,
            True,
            DecisionAction.AUTO_REPLY,
        ),
        (
            ConversationState.AI_APPROVAL,
            RiskLevel.LOW,
            Confidence(intent=0.94, retrieval=0.9, answer=0.92, policy=0.96),
            True,
            True,
            DecisionAction.REQUIRE_APPROVAL,
        ),
        (
            ConversationState.AI_AUTO,
            RiskLevel.HIGH,
            Confidence(intent=0.99, retrieval=1, answer=0.99, policy=0.99),
            True,
            True,
            DecisionAction.ESCALATE,
        ),
        (
            ConversationState.AI_AUTO,
            RiskLevel.LOW,
            Confidence(intent=0.95, retrieval=0.9, answer=0.95, policy=0.95),
            True,
            False,
            DecisionAction.REQUIRE_APPROVAL,
        ),
    ],
)
def test_confidence_auto_eval_matrix(
    state: ConversationState,
    risk: RiskLevel,
    confidence: Confidence,
    grounded: bool,
    public: bool,
    expected: DecisionAction,
) -> None:
    decision = choose_action(
        state=state,
        intent="QUESTION",
        risk=risk,
        confidence=confidence,
        has_grounding=grounded,
        has_public_grounding=public,
    )
    assert decision.action == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("can_reply", [True, False])
async def test_safe_auto_path_rechecks_rights_and_audits_result(monkeypatch, can_reply) -> None:
    from app.telegram import bootstrap

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def factory() -> Session:
        return Session(engine, expire_on_commit=False)

    with factory() as session:
        ingested = ingest_message(
            session,
            owner_telegram_id=100,
            incoming=IncomingBusinessMessage(
                business_connection_id="bc-auto",
                chat_id=200,
                message_id=1,
                sender_user_id=300,
                sender_name="عميل الاختبار",
                text="ما تفاصيل الخدمة؟",
            ),
        )
        ingested.owner.default_mode = "AUTO"
        ingested.conversation.state = ConversationState.AI_AUTO.value
        session.add(
            KnowledgeItem(
                owner_id=ingested.owner.id,
                title="تفاصيل الخدمة",
                content="الخدمة متاحة وفق الوصف المعتمد.",
                visibility="PUBLIC",
            )
        )
        session.commit()
        conversation_id = ingested.conversation.id
        trigger_message_id = ingested.message.id

    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=Confidence(intent=0.95, retrieval=0.9, answer=0.94, policy=0.96),
        has_grounding=True,
        has_public_grounding=True,
    )

    class FakePipeline:
        async def process_text(self, *, text: str, context: dict) -> TextResult:
            assert context["has_public_grounding"] is True
            return TextResult(
                decision=decision,
                candidate_reply="أهلًا بك، الخدمة متاحة وفق المعلومات المعتمدة. كيف أقدر أساعدك؟",
                token_usage={"total_tokens": 20},
            )

    sent: list[dict] = []
    owner_notices: list[dict] = []

    class FakeAdapter:
        def __init__(self, bot) -> None:
            self.bot = bot

        async def send_typing(self, **kwargs) -> None:
            return None

        async def send_text(self, **kwargs) -> int:
            sent.append(kwargs)
            return 900

    class FakeRights:
        def __init__(self, allowed: bool) -> None:
            self.can_reply = allowed

        def model_dump(self, *, mode: str) -> dict:
            assert mode == "json"
            return {"can_reply": self.can_reply}

    class FakeUser:
        id = 100
        full_name = "المالك"

    class FakeConnection:
        id = "bc-auto"
        user = FakeUser()
        user_chat_id = 100
        is_enabled = True
        rights = FakeRights(can_reply)

    class FakeBot:
        async def get_business_connection(self, **kwargs):
            assert kwargs == {"business_connection_id": "bc-auto"}
            return FakeConnection()

        async def send_message(self, **kwargs):
            owner_notices.append(kwargs)

    monkeypatch.setattr(bootstrap, "SessionLocal", factory)
    monkeypatch.setattr(bootstrap, "build_text_pipeline", lambda settings: FakePipeline())
    monkeypatch.setattr(bootstrap, "AiogramTelegramAdapter", FakeAdapter)
    monkeypatch.setattr(
        bootstrap,
        "settings",
        Settings(
            _env_file=None,
            owner_telegram_id=100,
            ai_provider="deepseek",
            deepseek_api_key="test",
            feedback_prompt_every_n_responses=3,
        ),
    )

    await bootstrap._process_text_for_approval(
        bot=FakeBot(),
        connection_id="bc-auto",
        conversation_id=conversation_id,
        trigger_message_id=trigger_message_id,
    )

    with factory() as session:
        approval = session.scalar(select(Approval))
        assert approval is not None
        if can_reply:
            assert len(sent) == 1
            assert owner_notices == []
            assert "اليوم" not in sent[0]["text"]
            assert approval.status == "SENT"
            outgoing = session.scalar(select(Message).where(Message.direction == "OUT"))
            assert outgoing is not None and outgoing.telegram_message_id == 900
            audit = session.scalar(
                select(AuditLog).where(AuditLog.action == "AUTOMATIC_RESPONSE_SENT")
            )
            assert audit is not None and audit.actor == "SYSTEM"
        else:
            assert sent == []
            assert len(owner_notices) == 1
            assert "صلاحية الرد" in owner_notices[0]["text"]
            assert approval.status == "FAILED"
            audit = session.scalar(
                select(AuditLog).where(AuditLog.action == "RESPONSE_SEND_BLOCKED")
            )
            assert audit is not None and audit.actor == "SYSTEM"
