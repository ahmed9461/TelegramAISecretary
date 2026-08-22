from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from unicodedata import normalize

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CustomIntent

_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_NON_WORD = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class IntentMatch:
    intent_id: int
    name: str
    score: float
    action_type: str
    action_config: dict


def normalize_utterance(value: str) -> str:
    text = normalize("NFKC", value).casefold().replace("ـ", "")
    text = _ARABIC_DIACRITICS.sub("", text)
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"}))
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def utterance_similarity(message: str, example: str) -> float:
    left = normalize_utterance(message)
    right = normalize_utterance(example)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0

    left_tokens = set(left.split())
    right_tokens = set(right.split())
    overlap = len(left_tokens & right_tokens)
    token_score = (2 * overlap / (len(left_tokens) + len(right_tokens))) if overlap else 0.0
    sequence_score = SequenceMatcher(None, left, right).ratio()

    # An owner-provided phrase appearing intact inside a natural request is a strong signal.
    containment = 0.0
    shorter, longer = sorted((left, right), key=len)
    if len(shorter) >= 4 and shorter in longer:
        coverage = len(shorter) / len(longer)
        containment = min(0.97, 0.86 + (0.11 * coverage))
    return round(max(token_score, sequence_score, containment), 4)


def match_custom_intent(
    session: Session,
    *,
    owner_id: int,
    text: str,
) -> IntentMatch | None:
    rows = list(
        session.scalars(
            select(CustomIntent)
            .where(CustomIntent.owner_id == owner_id, CustomIntent.enabled.is_(True))
            .order_by(CustomIntent.id)
        )
    )
    best: IntentMatch | None = None
    for row in rows:
        examples = [str(value).strip() for value in (row.examples_json or []) if str(value).strip()]
        score = max((utterance_similarity(text, example) for example in examples), default=0.0)
        threshold = max(0.5, min(1.0, float(row.confidence_threshold)))
        if score < threshold:
            continue
        candidate = IntentMatch(
            intent_id=row.id,
            name=row.name,
            score=score,
            action_type=row.linked_action_type,
            action_config=dict(row.linked_action_config_json or {}),
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def list_custom_intents(session: Session, *, owner_id: int) -> list[CustomIntent]:
    return list(
        session.scalars(
            select(CustomIntent)
            .where(CustomIntent.owner_id == owner_id)
            .order_by(CustomIntent.enabled.desc(), CustomIntent.updated_at.desc(), CustomIntent.id)
        )
    )
