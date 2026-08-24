from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.admin.service import clear_conversation_state_override, set_conversation_state
from app.conversations.context import build_ai_context
from app.db.base import Base
from app.db.enums import ConversationState, GlobalMode
from app.db.models import Contact, Conversation, Message, Owner
from app.observability.metrics import record_ai_run
from scripts.evaluate_smart_secretary import _load_dataset, _offline_scores


def _session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def _conversation(session: Session) -> tuple[Owner, Contact, Conversation]:
    owner = Owner(telegram_user_id=90001, default_mode=GlobalMode.AUTO.value)
    session.add(owner)
    session.flush()
    contact = Contact(owner_id=owner.id, telegram_user_id=90002, display_name="Eval Contact")
    session.add(contact)
    session.flush()
    conversation = Conversation(
        owner_id=owner.id,
        contact_id=contact.id,
        telegram_chat_id=90003,
        state=ConversationState.AI_APPROVAL.value,
        state_is_explicit=False,
    )
    session.add(conversation)
    session.flush()
    return owner, contact, conversation


def test_repeatable_smart_secretary_eval_gate() -> None:
    scores = _offline_scores(_load_dataset())
    failures = {
        name: score.failures for name, score in scores.items() if score.passed != score.total
    }
    assert not failures, failures


def test_inherited_state_follows_global_auto_and_explicit_override_is_preserved() -> None:
    session = _session()
    owner, _, conversation = _conversation(session)
    session.add(
        Message(
            conversation_id=conversation.id,
            telegram_message_id=1,
            direction="IN",
            text="مرحبًا",
        )
    )
    session.commit()

    inherited = build_ai_context(session, conversation_id=conversation.id, query="مرحبًا")
    assert inherited.payload["state"] == ConversationState.AI_AUTO.value
    assert inherited.payload["state_source"] == "INHERITED"

    updated = set_conversation_state(
        session,
        owner_id=owner.id,
        conversation_id=conversation.id,
        target=ConversationState.AI_APPROVAL,
    )
    session.commit()
    assert updated is not None and updated.state_is_explicit is True
    explicit = build_ai_context(session, conversation_id=conversation.id, query="مرحبًا")
    assert explicit.payload["state"] == ConversationState.AI_APPROVAL.value
    assert explicit.payload["state_source"] == "EXPLICIT"

    cleared = clear_conversation_state_override(
        session,
        owner_id=owner.id,
        conversation_id=conversation.id,
    )
    session.commit()
    assert cleared is not None and cleared.state_is_explicit is False
    assert cleared.state == ConversationState.AI_AUTO.value


def test_ai_run_stores_only_bounded_decision_context_metadata() -> None:
    session = _session()
    owner, _, conversation = _conversation(session)
    run = record_ai_run(
        session,
        owner_id=owner.id,
        conversation_id=conversation.id,
        trace_id="smart-eval",
        operation="TEXT_RESPONSE",
        provider="provider",
        model="model",
        status="SUCCESS",
        intent="REFUND_AUTHORIZATION",
        risk="HIGH",
        action="ESCALATE",
        decision_context={
            "reason_code": "REFUND_DECISION",
            "effective_state": "AI_AUTO",
            "global_mode": "AUTO",
            "state_source": "INHERITED",
            "public_grounding": True,
        },
    )
    session.commit()
    assert run is not None
    assert run.decision_context_json["reason_code"] == "REFUND_DECISION"
    serialized = str(run.decision_context_json)
    assert "message" not in serialized.casefold()
    assert "prompt" not in serialized.casefold()
