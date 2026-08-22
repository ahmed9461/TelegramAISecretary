from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brain.models import ContactMemory, MemorySuggestion
from app.brain.service import get_contact_memory, upsert_contact_memory
from app.db.models import Contact, Conversation
from app.memory.privacy import should_reject_long_term_memory

_MEMORY_KEY_LABELS = {
    "city": "المدينة",
    "location": "الموقع",
    "language": "اللغة",
    "preferred_language": "اللغة المفضلة",
    "communication_time": "وقت التواصل",
    "preferred_contact_time": "وقت التواصل المفضل",
    "contact_method": "وسيلة التواصل",
    "preferred_contact_method": "وسيلة التواصل المفضلة",
    "response_style": "أسلوب الرد",
    "name": "الاسم",
}


class MemorySuggestionProvider(Protocol):
    async def extract_memory_suggestion(
        self,
        *,
        transcript: list[dict],
        current_memory: dict,
    ) -> dict: ...


@dataclass(frozen=True, slots=True)
class MemoryProposal:
    summary: str
    facts: dict[str, str]
    preferences: dict[str, str]
    confidence: float
    rationale: str

    @property
    def is_empty(self) -> bool:
        return not (self.summary or self.facts or self.preferences)


def _clean_mapping(value: object, *, max_items: int = 12) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    cleaned: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()[:80]
        key = _MEMORY_KEY_LABELS.get(key.casefold(), key.replace("_", " "))
        if isinstance(raw_value, bool):
            item = "نعم" if raw_value else "لا"
        else:
            item = str(raw_value).strip()[:500]
        if not key or not item or should_reject_long_term_memory(f"{key}: {item}"):
            continue
        cleaned[key] = item
        if len(cleaned) >= max_items:
            break
    return cleaned


def sanitize_memory_proposal(payload: object) -> MemoryProposal:
    raw = payload if isinstance(payload, Mapping) else {}
    summary = str(raw.get("summary") or "").strip()[:1200]
    if summary and should_reject_long_term_memory(summary):
        summary = ""
    try:
        confidence = float(raw.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    rationale = str(raw.get("rationale") or "").strip()[:600]
    if rationale and should_reject_long_term_memory(rationale):
        rationale = ""
    return MemoryProposal(
        summary=summary,
        facts=_clean_mapping(raw.get("facts")),
        preferences=_clean_mapping(raw.get("preferences")),
        confidence=max(0.0, min(1.0, confidence)),
        rationale=rationale,
    )


async def propose_memory_update(
    provider: MemorySuggestionProvider,
    *,
    transcript: list[dict],
    current_memory: dict,
) -> MemoryProposal:
    raw = await provider.extract_memory_suggestion(
        transcript=transcript,
        current_memory=current_memory,
    )
    return sanitize_memory_proposal(raw)


def create_memory_suggestion(
    session: Session,
    *,
    owner_id: int,
    contact_id: int,
    conversation_id: int,
    source_message_ids: Sequence[int],
    proposal: MemoryProposal,
    ttl_hours: int,
) -> MemorySuggestion:
    if proposal.is_empty:
        raise ValueError("empty memory proposal")
    contact = session.get(Contact, contact_id)
    conversation = session.get(Conversation, conversation_id)
    if (
        contact is None
        or contact.owner_id != owner_id
        or conversation is None
        or conversation.owner_id != owner_id
        or conversation.contact_id != contact_id
    ):
        raise ValueError("memory suggestion ownership mismatch")
    pending = list(
        session.scalars(
            select(MemorySuggestion).where(
                MemorySuggestion.owner_id == owner_id,
                MemorySuggestion.contact_id == contact_id,
                MemorySuggestion.status == "PENDING",
            )
        )
    )
    now = datetime.now(UTC)
    for row in pending:
        row.status = "SUPERSEDED"
        row.resolved_at = now
    suggestion = MemorySuggestion(
        owner_id=owner_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        source_message_ids_json=[int(item) for item in source_message_ids][-24:],
        summary=proposal.summary,
        facts_json=dict(proposal.facts),
        preferences_json=dict(proposal.preferences),
        confidence=proposal.confidence,
        rationale=proposal.rationale,
        status="PENDING",
        expires_at=now + timedelta(hours=max(1, ttl_hours)),
    )
    session.add(suggestion)
    session.flush()
    return suggestion


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def approve_memory_suggestion(
    session: Session,
    *,
    owner_id: int,
    suggestion_id: int,
    retention_days: int,
) -> ContactMemory | None:
    suggestion = session.get(MemorySuggestion, suggestion_id)
    if suggestion is None or suggestion.owner_id != owner_id or suggestion.status != "PENDING":
        return None
    now = datetime.now(UTC)
    if _aware(suggestion.expires_at) <= now:
        suggestion.status = "EXPIRED"
        suggestion.resolved_at = now
        session.flush()
        return None

    contact = session.get(Contact, suggestion.contact_id)
    conversation = session.get(Conversation, suggestion.conversation_id)
    if (
        contact is None
        or contact.owner_id != owner_id
        or conversation is None
        or conversation.owner_id != owner_id
        or conversation.contact_id != contact.id
    ):
        return None

    memory = get_contact_memory(session, contact_id=suggestion.contact_id)
    if memory is not None and memory.owner_id != owner_id:
        return None
    current_facts = dict(memory.facts_json or {}) if memory else {}
    current_preferences = dict(memory.preferences_json or {}) if memory else {}
    current_facts.update(dict(suggestion.facts_json or {}))
    current_preferences.update(dict(suggestion.preferences_json or {}))
    provenance = dict(memory.provenance_json or {}) if memory else {}
    confidence = dict(memory.confidence_json or {}) if memory else {}
    source_entry = {
        "suggestion_id": suggestion.id,
        "conversation_id": suggestion.conversation_id,
        "source_message_ids": list(suggestion.source_message_ids_json or []),
        "approved_at": now.isoformat(),
    }
    if suggestion.summary:
        provenance["summary"] = source_entry
        confidence["summary"] = suggestion.confidence
    fact_sources = dict(provenance.get("facts") or {})
    fact_confidence = dict(confidence.get("facts") or {})
    for key in suggestion.facts_json or {}:
        fact_sources[str(key)] = source_entry
        fact_confidence[str(key)] = suggestion.confidence
    provenance["facts"] = fact_sources
    confidence["facts"] = fact_confidence
    preference_sources = dict(provenance.get("preferences") or {})
    preference_confidence = dict(confidence.get("preferences") or {})
    for key in suggestion.preferences_json or {}:
        preference_sources[str(key)] = source_entry
        preference_confidence[str(key)] = suggestion.confidence
    provenance["preferences"] = preference_sources
    confidence["preferences"] = preference_confidence

    memory = upsert_contact_memory(
        session,
        owner_id=owner_id,
        contact_id=suggestion.contact_id,
        summary=suggestion.summary or (memory.summary if memory else ""),
        facts_json=current_facts,
        preferences_json=current_preferences,
        provenance_json=provenance,
        confidence_json=confidence,
        retention_until=now + timedelta(days=max(1, retention_days)),
        last_reviewed_at=now,
    )
    suggestion.status = "APPROVED"
    suggestion.resolved_at = now
    session.flush()
    return memory


def reject_memory_suggestion(
    session: Session,
    *,
    owner_id: int,
    suggestion_id: int,
) -> bool:
    suggestion = session.get(MemorySuggestion, suggestion_id)
    if suggestion is None or suggestion.owner_id != owner_id or suggestion.status != "PENDING":
        return False
    suggestion.status = "REJECTED"
    suggestion.resolved_at = datetime.now(UTC)
    session.flush()
    return True


def export_contact_memory(memory: ContactMemory) -> dict:
    return {
        "contact_id": memory.contact_id,
        "summary": memory.summary,
        "facts": dict(memory.facts_json or {}),
        "preferences": dict(memory.preferences_json or {}),
        "private_notes": memory.private_notes,
        "shared_with_secretary": bool(memory.share_with_ai),
        "provenance": dict(memory.provenance_json or {}),
        "confidence": dict(memory.confidence_json or {}),
        "retention_until": (memory.retention_until.isoformat() if memory.retention_until else None),
        "last_reviewed_at": (
            memory.last_reviewed_at.isoformat() if memory.last_reviewed_at else None
        ),
        "exported_at": datetime.now(UTC).isoformat(),
    }
