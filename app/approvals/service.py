from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Approval, Conversation
from app.db.repositories import ApprovalRepository, ConversationRepository

_INTENT_MARKER = "|INTENT="


@dataclass(frozen=True, slots=True)
class ApprovalClaim:
    approval_id: int
    conversation_id: int
    chat_id: int
    business_connection_id: str
    text: str
    intent: str = ""


def format_approval_reason(*, source: str, reason_code: str, intent: str) -> str:
    """Keep the classified intent with the approval without changing the M6 schema."""
    base = f"{source.strip().upper()}_{reason_code.strip().upper()}"
    normalized_intent = intent.strip().upper().replace("|", " ")[:64].strip()
    if not normalized_intent:
        return base[:255]
    suffix = f"{_INTENT_MARKER}{normalized_intent}"
    return f"{base[: 255 - len(suffix)]}{suffix}"


def approval_intent(reason: str) -> str:
    _, marker, intent = reason.rpartition(_INTENT_MARKER)
    return intent.strip().upper() if marker else ""


def create_approval(
    session: Session,
    *,
    conversation: Conversation,
    trigger_message_id: int | None,
    candidate_response: str,
    reason: str,
    context: dict | None = None,
    ttl_hours: int = 24,
) -> Approval:
    approval = ApprovalRepository.create(
        session,
        conversation=conversation,
        trigger_message_id=trigger_message_id,
        candidate_response=candidate_response,
        reason=reason,
        context=context,
        ttl_hours=ttl_hours,
    )
    session.commit()
    return approval


def attach_owner_message(
    session: Session,
    approval_id: int,
    *,
    owner_chat_id: int,
    owner_message_id: int,
) -> bool:
    ok = ApprovalRepository.attach_owner_message(
        session,
        approval_id,
        owner_chat_id=owner_chat_id,
        owner_message_id=owner_message_id,
    )
    session.commit()
    return ok


def preview_claim(session: Session, approval_id: int) -> ApprovalClaim | None:
    approval = session.get(Approval, approval_id)
    if approval is None or approval.status != "PENDING":
        return None
    conversation = session.get(Conversation, approval.conversation_id)
    if conversation is None or not conversation.business_connection_id:
        return None
    return ApprovalClaim(
        approval_id=approval.id,
        conversation_id=conversation.id,
        chat_id=conversation.telegram_chat_id,
        business_connection_id=conversation.business_connection_id,
        text=approval.candidate_response,
        intent=str((approval.context_json or {}).get("intent") or approval_intent(approval.reason)),
    )


def claim_for_send(session: Session, approval_id: int) -> ApprovalClaim | None:
    approval = ApprovalRepository.claim_for_send(session, approval_id)
    if approval is None:
        session.commit()
        return None
    conversation = session.get(Conversation, approval.conversation_id)
    if conversation is None or not conversation.business_connection_id:
        approval.status = "FAILED"
        session.commit()
        return None
    claim = ApprovalClaim(
        approval_id=approval.id,
        conversation_id=conversation.id,
        chat_id=conversation.telegram_chat_id,
        business_connection_id=conversation.business_connection_id,
        text=approval.candidate_response,
        intent=str((approval.context_json or {}).get("intent") or approval_intent(approval.reason)),
    )
    session.commit()
    return claim


def mark_sent(
    session: Session, approval_id: int, *, telegram_message_id: int | None = None
) -> None:
    approval = session.get(Approval, approval_id)
    if approval is None:
        return
    conversation = session.get(Conversation, approval.conversation_id)
    ApprovalRepository.mark_sent(
        session,
        approval_id,
        telegram_message_id=telegram_message_id,
    )
    if conversation is not None and telegram_message_id is not None:
        ConversationRepository.append_outgoing(
            session,
            conversation=conversation,
            telegram_message_id=telegram_message_id,
            text=approval.candidate_response,
        )
    session.commit()


def mark_uncertain(session: Session, approval_id: int) -> None:
    ApprovalRepository.mark_uncertain(session, approval_id)
    session.commit()


def reject(session: Session, approval_id: int) -> bool:
    rejected = ApprovalRepository.reject(session, approval_id)
    session.commit()
    return rejected
