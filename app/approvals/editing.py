from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Approval, Conversation, Message


@dataclass(frozen=True, slots=True)
class EditableApproval:
    approval_id: int
    conversation_id: int
    owner_id: int
    candidate_response: str
    trigger_text: str
    source_snapshots: tuple[dict, ...] = ()


def get_editable_approval(session: Session, approval_id: int) -> EditableApproval | None:
    approval = session.get(Approval, approval_id)
    if approval is None or approval.status != "PENDING":
        return None
    conversation = session.get(Conversation, approval.conversation_id)
    if conversation is None:
        return None
    trigger_text = ""
    if approval.trigger_message_id is not None:
        trigger = session.get(Message, approval.trigger_message_id)
        if trigger is not None and not trigger.is_deleted:
            trigger_text = trigger.text or ""
    return EditableApproval(
        approval_id=approval.id,
        conversation_id=conversation.id,
        owner_id=conversation.owner_id,
        candidate_response=approval.candidate_response,
        trigger_text=trigger_text,
        source_snapshots=tuple(
            item
            for item in ((approval.context_json or {}).get("sources") or [])
            if isinstance(item, dict)
        ),
    )


def update_approval_candidate(session: Session, approval_id: int, *, text: str) -> bool:
    approval = session.get(Approval, approval_id)
    if approval is None or approval.status != "PENDING":
        return False
    value = text.strip()
    if not value:
        return False
    approval.candidate_response = value
    session.flush()
    return True
