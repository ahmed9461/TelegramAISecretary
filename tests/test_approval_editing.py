from app.approvals.editing import get_editable_approval, update_approval_candidate
from app.db.models import Approval, Conversation, Message
from app.telegram.owner_ui import approval_keyboard


class FakeSession:
    def __init__(self, rows: dict[tuple[type, int], object]) -> None:
        self.rows = rows
        self.flushed = False

    def get(self, model, row_id):
        return self.rows.get((model, row_id))

    def flush(self) -> None:
        self.flushed = True


def test_pending_approval_can_be_edited_without_sending() -> None:
    approval = Approval(
        id=7,
        conversation_id=3,
        trigger_message_id=9,
        conversation_revision=2,
        candidate_response="رد آلي",
        status="PENDING",
        context_json={
            "sources": [
                {
                    "id": 12,
                    "title": "السعر المعتمد",
                    "visibility": "PUBLIC",
                    "score": 0.9,
                }
            ]
        },
    )
    conversation = Conversation(
        id=3,
        owner_id=1,
        contact_id=2,
        telegram_chat_id=100,
        state="AI_APPROVAL",
    )
    trigger = Message(
        id=9,
        conversation_id=3,
        telegram_message_id=55,
        direction="IN",
        sender_type="CONTACT",
        content_type="TEXT",
        text="كم السعر؟",
        is_deleted=False,
    )
    session = FakeSession(
        {
            (Approval, 7): approval,
            (Conversation, 3): conversation,
            (Message, 9): trigger,
        }
    )

    draft = get_editable_approval(session, 7)
    assert draft is not None
    assert draft.trigger_text == "كم السعر؟"
    assert draft.source_snapshots[0]["id"] == 12
    assert update_approval_candidate(session, 7, text="السعر المعتمد هو 10 دولارات")
    assert approval.candidate_response == "السعر المعتمد هو 10 دولارات"
    assert session.flushed is True


def test_non_pending_approval_cannot_be_edited() -> None:
    approval = Approval(
        id=7,
        conversation_id=3,
        conversation_revision=2,
        candidate_response="تم",
        status="SENT",
    )
    session = FakeSession({(Approval, 7): approval})
    assert get_editable_approval(session, 7) is None
    assert update_approval_candidate(session, 7, text="تعديل") is False


def test_approval_keyboard_exposes_review_controls() -> None:
    markup = approval_keyboard(42)
    callbacks = {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    }
    assert "approval:send:42" in callbacks
    assert "approval_edit:start:42" in callbacks
    assert "approval_meta:sources:42" in callbacks
    assert "approval_edit:learn:42" in callbacks
    assert "approval:reject:42" in callbacks
