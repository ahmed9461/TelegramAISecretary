from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.approvals.service import claim_for_send, create_approval, format_approval_reason
from app.conversations.ingest import ingest_message
from app.db.base import Base
from app.db.models import Approval, Message
from app.telegram.contracts import IncomingBusinessMessage


def make_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def incoming(message_id: int, text: str = "hello") -> IncomingBusinessMessage:
    return IncomingBusinessMessage(
        business_connection_id="bc-1",
        chat_id=200,
        message_id=message_id,
        sender_user_id=300,
        sender_name="Contact",
        text=text,
    )


def test_ingest_is_idempotent() -> None:
    session = make_session()
    first = ingest_message(session, owner_telegram_id=100, incoming=incoming(1))
    second = ingest_message(session, owner_telegram_id=100, incoming=incoming(1))
    assert not first.duplicate
    assert second.duplicate
    assert len(session.scalars(select(Message)).all()) == 1


def test_approval_becomes_stale_when_context_changes() -> None:
    session = make_session()
    result = ingest_message(session, owner_telegram_id=100, incoming=incoming(1))
    approval = create_approval(
        session,
        conversation=result.conversation,
        trigger_message_id=result.message.id,
        candidate_response="candidate",
        reason="test",
    )

    ingest_message(session, owner_telegram_id=100, incoming=incoming(2, "new context"))
    claim = claim_for_send(session, approval.id)
    assert claim is None
    refreshed = session.get(Approval, approval.id)
    assert refreshed is not None
    assert refreshed.status == "STALE"


def test_approval_can_be_claimed_once() -> None:
    session = make_session()
    result = ingest_message(session, owner_telegram_id=100, incoming=incoming(1))
    approval = create_approval(
        session,
        conversation=result.conversation,
        trigger_message_id=result.message.id,
        candidate_response="candidate",
        reason="test",
    )
    claim = claim_for_send(session, approval.id)
    assert claim is not None
    assert claim.text == "candidate"
    assert claim_for_send(session, approval.id) is None


def test_approval_preserves_intent_for_contextual_menu() -> None:
    session = make_session()
    result = ingest_message(session, owner_telegram_id=100, incoming=incoming(1))
    approval = create_approval(
        session,
        conversation=result.conversation,
        trigger_message_id=result.message.id,
        candidate_response="candidate",
        reason=format_approval_reason(
            source="TEXT",
            reason_code="SAFE_AUTO",
            intent="payment_methods",
        ),
    )

    claim = claim_for_send(session, approval.id)

    assert claim is not None
    assert claim.intent == "PAYMENT_METHODS"
