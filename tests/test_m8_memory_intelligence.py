from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.brain.models import ContactMemory
from app.brain.service import memory_for_ai
from app.db.base import Base
from app.db.models import Approval, Contact, Conversation, Feedback, Owner
from app.feedback.service import (
    feedback_summary,
    record_contact_feedback,
    should_prompt_feedback,
)
from app.memory.service import (
    MemoryProposal,
    approve_memory_suggestion,
    create_memory_suggestion,
    export_contact_memory,
    reject_memory_suggestion,
    sanitize_memory_proposal,
)
from app.telegram.feedback_ui import append_feedback_row
from app.telegram.memory_ui import _parse_mapping


def make_session() -> tuple[Session, Owner, Contact, Conversation]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    owner = Owner(telegram_user_id=8101, display_name="Owner")
    session.add(owner)
    session.flush()
    contact = Contact(
        owner_id=owner.id,
        telegram_user_id=8102,
        display_name="Customer",
    )
    session.add(contact)
    session.flush()
    conversation = Conversation(
        owner_id=owner.id,
        contact_id=contact.id,
        telegram_chat_id=8102,
    )
    session.add(conversation)
    session.flush()
    return session, owner, contact, conversation


def test_sensitive_values_are_removed_from_memory_proposal() -> None:
    proposal = sanitize_memory_proposal(
        {
            "summary": "عميل يفضل التواصل مساءً",
            "facts": {
                "المدينة": "الرياض",
                "كلمة المرور": "secret-123",
                "رمز التحقق": "123456",
                "البطاقة": "4111 1111 1111 1111",
            },
            "preferences": {
                "communication_time": "المساء",
                "response_style": "مختصر",
                "الردود القصيرة": True,
            },
            "confidence": 4,
            "rationale": "التشخيص: خاص",
        }
    )

    assert proposal.summary == "عميل يفضل التواصل مساءً"
    assert proposal.facts == {"المدينة": "الرياض"}
    assert proposal.preferences == {
        "وقت التواصل": "المساء",
        "أسلوب الرد": "مختصر",
        "الردود القصيرة": "نعم",
    }
    assert proposal.confidence == 1.0
    assert proposal.rationale == ""


def test_suggestion_does_not_mutate_memory_before_owner_approval() -> None:
    session, owner, contact, conversation = make_session()
    suggestion = create_memory_suggestion(
        session,
        owner_id=owner.id,
        contact_id=contact.id,
        conversation_id=conversation.id,
        source_message_ids=[10, 11],
        proposal=MemoryProposal(
            summary="عميل دائم",
            facts={"المدينة": "جدة"},
            preferences={"التواصل": "كتابي"},
            confidence=0.9,
            rationale="ذكرها العميل صراحة",
        ),
        ttl_hours=72,
    )

    assert suggestion.status == "PENDING"
    assert session.scalar(select(ContactMemory)) is None


def test_memory_suggestion_rejects_cross_owner_contact() -> None:
    session, _, contact, conversation = make_session()
    other_owner = Owner(telegram_user_id=9101, display_name="Other")
    session.add(other_owner)
    session.flush()

    with pytest.raises(ValueError, match="ownership mismatch"):
        create_memory_suggestion(
            session,
            owner_id=other_owner.id,
            contact_id=contact.id,
            conversation_id=conversation.id,
            source_message_ids=[10],
            proposal=MemoryProposal(
                summary="لا يجب حفظه",
                facts={},
                preferences={},
                confidence=0.9,
                rationale="اختبار عزل",
            ),
            ttl_hours=24,
        )


def test_owner_approval_merges_memory_and_records_provenance() -> None:
    session, owner, contact, conversation = make_session()
    existing = ContactMemory(
        owner_id=owner.id,
        contact_id=contact.id,
        facts_json={"اللغة": "العربية"},
        preferences_json={},
    )
    session.add(existing)
    session.flush()
    suggestion = create_memory_suggestion(
        session,
        owner_id=owner.id,
        contact_id=contact.id,
        conversation_id=conversation.id,
        source_message_ids=[31],
        proposal=MemoryProposal(
            summary="عميل يفضل الرد المختصر",
            facts={"المدينة": "الدمام"},
            preferences={"أسلوب الرد": "مختصر"},
            confidence=0.86,
            rationale="طلب ذلك صراحة",
        ),
        ttl_hours=24,
    )

    memory = approve_memory_suggestion(
        session,
        owner_id=owner.id,
        suggestion_id=suggestion.id,
        retention_days=180,
    )

    assert memory is not None
    assert memory.facts_json == {"اللغة": "العربية", "المدينة": "الدمام"}
    assert memory.preferences_json == {"أسلوب الرد": "مختصر"}
    assert memory.provenance_json["facts"]["المدينة"]["suggestion_id"] == suggestion.id
    assert memory.confidence_json["preferences"]["أسلوب الرد"] == 0.86
    assert memory.retention_until is not None
    assert suggestion.status == "APPROVED"
    assert memory_for_ai(memory, contact_memory_allowed=True)["summary"] == memory.summary


def test_rejection_and_expiry_do_not_expose_memory_to_ai() -> None:
    session, owner, contact, conversation = make_session()
    suggestion = create_memory_suggestion(
        session,
        owner_id=owner.id,
        contact_id=contact.id,
        conversation_id=conversation.id,
        source_message_ids=[41],
        proposal=MemoryProposal(
            summary="معلومة قابلة للمراجعة",
            facts={},
            preferences={},
            confidence=0.8,
            rationale="اختبار",
        ),
        ttl_hours=24,
    )

    assert reject_memory_suggestion(
        session,
        owner_id=owner.id,
        suggestion_id=suggestion.id,
    )
    assert session.scalar(select(ContactMemory)) is None

    expired = ContactMemory(
        owner_id=owner.id,
        contact_id=contact.id,
        summary="ذاكرة منتهية",
        retention_until=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(expired)
    session.flush()
    assert memory_for_ai(expired, contact_memory_allowed=True) == {}


def test_memory_export_contains_review_metadata_and_private_note() -> None:
    memory = ContactMemory(
        owner_id=1,
        contact_id=2,
        summary="ملخص",
        facts_json={"المدينة": "أبها"},
        preferences_json={"التواصل": "مساءً"},
        private_notes="ملاحظة للمالك فقط",
        provenance_json={"summary": {"suggestion_id": 7}},
        confidence_json={"summary": 0.91},
        retention_until=datetime(2027, 1, 1, tzinfo=UTC),
        last_reviewed_at=datetime(2026, 8, 22, tzinfo=UTC),
    )

    exported = export_contact_memory(memory)

    assert exported["private_notes"] == "ملاحظة للمالك فقط"
    assert exported["provenance"]["summary"]["suggestion_id"] == 7
    assert exported["retention_until"] == "2027-01-01T00:00:00+00:00"


def _approval(session: Session, conversation: Conversation, *, status: str) -> Approval:
    row = Approval(
        conversation_id=conversation.id,
        conversation_revision=conversation.revision,
        candidate_response="رد مهني",
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def test_feedback_prompt_interval_is_configurable() -> None:
    session, _, _, conversation = make_session()

    assert not should_prompt_feedback(session, conversation_id=conversation.id, interval=3)
    assert should_prompt_feedback(session, conversation_id=conversation.id, interval=1)
    _approval(session, conversation, status="SENT")
    _approval(session, conversation, status="SENT")

    assert should_prompt_feedback(session, conversation_id=conversation.id, interval=3)
    assert not should_prompt_feedback(session, conversation_id=conversation.id, interval=0)


def test_only_the_recipient_can_rate_and_can_update_rating() -> None:
    session, _, contact, conversation = make_session()
    approval = _approval(session, conversation, status="SENT")

    assert (
        record_contact_feedback(
            session,
            approval_id=approval.id,
            telegram_user_id=999999,
            rating=5,
        )
        is None
    )
    first = record_contact_feedback(
        session,
        approval_id=approval.id,
        telegram_user_id=contact.telegram_user_id,
        rating=4,
    )
    updated = record_contact_feedback(
        session,
        approval_id=approval.id,
        telegram_user_id=contact.telegram_user_id,
        rating=5,
    )

    assert first is not None and updated is not None
    assert first.id == updated.id
    assert updated.rating == 5
    assert len(session.scalars(select(Feedback)).all()) == 1


def test_owner_feedback_summary_has_average_and_distribution() -> None:
    session, owner, contact, conversation = make_session()
    first = _approval(session, conversation, status="SENT")
    second = _approval(session, conversation, status="SENT")
    record_contact_feedback(
        session,
        approval_id=first.id,
        telegram_user_id=contact.telegram_user_id,
        rating=5,
    )
    record_contact_feedback(
        session,
        approval_id=second.id,
        telegram_user_id=contact.telegram_user_id,
        rating=3,
    )

    summary = feedback_summary(session, owner_id=owner.id)

    assert summary.total == 2
    assert summary.average == 4.0
    assert summary.distribution[5] == 1
    assert summary.distribution[3] == 1


def test_memory_editor_parser_ignores_sensitive_and_malformed_lines() -> None:
    parsed = _parse_mapping(
        "المدينة: الرياض\nسطر بلا فاصل\nرمز التحقق: 123456\nوقت التواصل: المساء"
    )

    assert parsed == {"المدينة": "الرياض", "وقت التواصل": "المساء"}


def test_feedback_keyboard_preserves_menu_and_adds_five_clear_choices() -> None:
    markup = append_feedback_row(None, approval_id=91)

    assert [button.text for button in markup.inline_keyboard[-1]] == [
        "1⭐",
        "2⭐",
        "3⭐",
        "4⭐",
        "5⭐",
    ]
    assert markup.inline_keyboard[-1][-1].callback_data == "feedback:rate:91:5"
