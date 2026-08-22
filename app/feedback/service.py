from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Approval, Contact, Conversation, Feedback


@dataclass(frozen=True, slots=True)
class FeedbackSummary:
    total: int
    average: float | None
    distribution: dict[int, int]


def should_prompt_feedback(
    session: Session,
    *,
    conversation_id: int,
    interval: int,
) -> bool:
    """Return whether the response being sent should carry a rating prompt."""
    if interval < 1:
        return False
    sent_count = int(
        session.scalar(
            select(func.count(Approval.id)).where(
                Approval.conversation_id == conversation_id,
                Approval.status == "SENT",
            )
        )
        or 0
    )
    return (sent_count + 1) % interval == 0


def record_contact_feedback(
    session: Session,
    *,
    approval_id: int,
    telegram_user_id: int,
    rating: int,
) -> Feedback | None:
    """Upsert a rating only when it comes from the contact who received the reply."""
    if rating not in {1, 2, 3, 4, 5}:
        return None
    approval = session.get(Approval, approval_id)
    if approval is None or approval.status not in {"SENDING", "SENT"}:
        return None
    conversation = session.get(Conversation, approval.conversation_id)
    if conversation is None:
        return None
    contact = session.get(Contact, conversation.contact_id)
    if contact is None or contact.telegram_user_id != telegram_user_id:
        return None
    row = session.scalar(select(Feedback).where(Feedback.approval_id == approval.id))
    if row is None:
        row = Feedback(
            owner_id=conversation.owner_id,
            contact_id=contact.id,
            conversation_id=conversation.id,
            approval_id=approval.id,
            rating=rating,
        )
        session.add(row)
    else:
        row.rating = rating
    session.flush()
    return row


def feedback_summary(session: Session, *, owner_id: int) -> FeedbackSummary:
    total, average = session.execute(
        select(func.count(Feedback.id), func.avg(Feedback.rating)).where(
            Feedback.owner_id == owner_id
        )
    ).one()
    rows = session.execute(
        select(Feedback.rating, func.count(Feedback.id))
        .where(Feedback.owner_id == owner_id)
        .group_by(Feedback.rating)
    )
    distribution = {rating: 0 for rating in range(1, 6)}
    for rating, count in rows:
        distribution[int(rating)] = int(count)
    return FeedbackSummary(
        total=int(total or 0),
        average=float(average) if average is not None else None,
        distribution=distribution,
    )
