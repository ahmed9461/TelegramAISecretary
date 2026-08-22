from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brain.models import BusinessProfile, ContactMemory, ResponsePolicy
from app.db.models import Contact

PROFILE_FIELDS = {
    "display_name",
    "activity_description",
    "industry",
    "reply_style",
    "language",
    "tone",
    "custom_instructions",
    "extras_json",
    "is_active",
}


def get_or_create_profile(session: Session, *, owner_id: int) -> BusinessProfile:
    row = session.scalar(select(BusinessProfile).where(BusinessProfile.owner_id == owner_id))
    if row is not None:
        return row
    row = BusinessProfile(owner_id=owner_id)
    session.add(row)
    session.flush()
    return row


def update_profile(session: Session, *, owner_id: int, **changes: object) -> BusinessProfile:
    row = get_or_create_profile(session, owner_id=owner_id)
    for key, value in changes.items():
        if key not in PROFILE_FIELDS:
            raise ValueError(f"unsupported profile field: {key}")
        setattr(row, key, value)
    session.flush()
    return row


def get_contact_memory(session: Session, *, contact_id: int) -> ContactMemory | None:
    return session.scalar(select(ContactMemory).where(ContactMemory.contact_id == contact_id))


def upsert_contact_memory(
    session: Session,
    *,
    owner_id: int,
    contact_id: int,
    summary: str | None = None,
    facts_json: dict | None = None,
    preferences_json: dict | None = None,
    private_notes: str | None = None,
    share_with_ai: bool | None = None,
    provenance_json: dict | None = None,
    confidence_json: dict | None = None,
    retention_until: datetime | None = None,
    last_reviewed_at: datetime | None = None,
) -> ContactMemory:
    row = get_contact_memory(session, contact_id=contact_id)
    if row is None:
        row = ContactMemory(owner_id=owner_id, contact_id=contact_id)
        session.add(row)
    elif row.owner_id != owner_id:
        raise ValueError("contact memory owner mismatch")

    if summary is not None:
        row.summary = summary.strip()
    if facts_json is not None:
        row.facts_json = dict(facts_json)
    if preferences_json is not None:
        row.preferences_json = dict(preferences_json)
    if private_notes is not None:
        row.private_notes = private_notes.strip()
    if share_with_ai is not None:
        row.share_with_ai = bool(share_with_ai)
    if provenance_json is not None:
        row.provenance_json = dict(provenance_json)
    if confidence_json is not None:
        row.confidence_json = dict(confidence_json)
    if retention_until is not None:
        row.retention_until = retention_until
    if last_reviewed_at is not None:
        row.last_reviewed_at = last_reviewed_at
    session.flush()
    return row


def list_response_policies(
    session: Session,
    *,
    owner_id: int,
    enabled_only: bool = True,
) -> list[ResponsePolicy]:
    query = select(ResponsePolicy).where(ResponsePolicy.owner_id == owner_id)
    if enabled_only:
        query = query.where(ResponsePolicy.enabled.is_(True))
    query = query.order_by(ResponsePolicy.priority.asc(), ResponsePolicy.id.asc())
    return list(session.scalars(query))


def add_response_policy(
    session: Session,
    *,
    owner_id: int,
    name: str,
    description: str,
    action: str = "REQUIRE_APPROVAL",
    scope: str = "GLOBAL",
    priority: int = 100,
    conditions_json: dict | None = None,
    constraints_json: dict | None = None,
) -> ResponsePolicy:
    row = ResponsePolicy(
        owner_id=owner_id,
        name=name.strip(),
        description=description.strip(),
        action=action.strip().upper(),
        scope=scope.strip().upper(),
        priority=priority,
        conditions_json=dict(conditions_json or {}),
        constraints_json=dict(constraints_json or {}),
        enabled=True,
    )
    session.add(row)
    session.flush()
    return row


def profile_for_ai(profile: BusinessProfile | None) -> dict:
    if profile is None or not profile.is_active:
        return {}
    return {
        "display_name": profile.display_name,
        "activity_description": profile.activity_description,
        "industry": profile.industry,
        "reply_style": profile.reply_style,
        "language": profile.language,
        "tone": profile.tone,
        "custom_instructions": profile.custom_instructions,
        "extras": dict(profile.extras_json or {}),
    }


def memory_for_ai(memory: ContactMemory | None, *, contact_memory_allowed: bool) -> dict:
    if memory is None or not memory.share_with_ai or not contact_memory_allowed:
        return {}
    if memory.retention_until is not None:
        retention_until = memory.retention_until
        if retention_until.tzinfo is None:
            retention_until = retention_until.replace(tzinfo=UTC)
        if retention_until <= datetime.now(UTC):
            return {}
    # private_notes is deliberately excluded from the returned structure.
    return {
        "summary": memory.summary,
        "facts": dict(memory.facts_json or {}),
        "preferences": dict(memory.preferences_json or {}),
    }


def policies_for_ai(policies: Iterable[ResponsePolicy]) -> list[dict]:
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "scope": row.scope,
            "action": row.action,
            "priority": row.priority,
            "conditions": dict(row.conditions_json or {}),
            "constraints": dict(row.constraints_json or {}),
        }
        for row in policies
        if row.enabled
    ]


def build_brain_context(
    session: Session,
    *,
    owner_id: int,
    contact_id: int,
) -> dict:
    profile = session.scalar(select(BusinessProfile).where(BusinessProfile.owner_id == owner_id))
    contact = session.get(Contact, contact_id)
    memory = get_contact_memory(session, contact_id=contact_id)
    policies = list_response_policies(session, owner_id=owner_id, enabled_only=True)
    return {
        "business_profile": profile_for_ai(profile),
        "contact_memory": memory_for_ai(
            memory,
            contact_memory_allowed=bool(contact and contact.memory_allowed),
        ),
        "response_policies": policies_for_ai(policies),
    }


def brain_counts(session: Session, *, owner_id: int) -> dict[str, int]:
    memory_count = session.scalar(
        select(func.count(ContactMemory.id)).where(ContactMemory.owner_id == owner_id)
    )
    policy_count = session.scalar(
        select(func.count(ResponsePolicy.id)).where(
            ResponsePolicy.owner_id == owner_id,
            ResponsePolicy.enabled.is_(True),
        )
    )
    return {
        "memories": int(memory_count or 0),
        "policies": int(policy_count or 0),
    }
