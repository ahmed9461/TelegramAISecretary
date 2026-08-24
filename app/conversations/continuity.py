from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


class ConversationMessage(Protocol):
    direction: str
    text: str | None


_SHORT_NUMBER = re.compile(
    r"^[0-9٠-٩۰-۹]+(?:[.,،][0-9٠-٩۰-۹]+)?"
    r"(?:\s*(?:مجموعة|مجموعات|شهر|أشهر|اشهر|نجمة|نجوم|ريال|دولار|عميل|عملاء))?$",
    re.IGNORECASE,
)
_SHORT_ANSWERS = {
    "نعم",
    "اي",
    "ايوه",
    "أيوه",
    "اجل",
    "أجل",
    "لا",
    "موافق",
    "موافقة",
    "تمام",
    "اوكي",
    "أوكي",
    "سنوي",
    "شهري",
    "yes",
    "no",
    "ok",
}
_NORMALIZED_SHORT_ANSWERS = {item.casefold() for item in _SHORT_ANSWERS}
_QUESTION_CUES = re.compile(
    r"(?:[؟?]|\b(?:كم|اختر|اختار|حدد|ارسل|أرسل|اذكر|هل|ماهي|ما\s+هي|"
    r"what|which|how\s+many)\b)",
    re.IGNORECASE,
)
_NEW_TOPIC_CUES = re.compile(
    r"^(?:طيب\s+)?(?:وش|ايش|إيش|ما|ماذا|متى|وين|أين|كيف|كم|هل|ليش|لماذا|"
    r"ابي|أبي|ابغى|أبغى|اريد|أريد|what|when|where|why|how|can\s+i|i\s+need)\b",
    re.IGNORECASE,
)
_OUTCOME_CUES = re.compile(
    r"^(?:ما\s+)?(?:نفع|ضبط|اشتغل|عمل|تغير)|^(?:لسه|مازال|ما\s+زال)|^still\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class ConversationContinuity:
    original_text: str
    resolved_text: str
    has_prior_outgoing: bool
    prior_outgoing_count: int
    contextual_short_reply: bool
    last_outgoing_question: str
    last_outgoing_message: str
    conversation_focus: str


def _looks_like_short_answer(value: str) -> bool:
    clean = " ".join(value.strip().split())
    if not clean or "؟" in clean or "?" in clean:
        return False
    if _SHORT_NUMBER.fullmatch(clean) or clean.casefold() in _NORMALIZED_SHORT_ANSWERS:
        return True
    # Compact outcomes and social continuations can be several words. Clear questions/requests
    # are excluded separately so a topic change is not attached to the preceding turn.
    return len(clean) <= 80 and len(clean.split()) <= 8


def _same_message_text(left: str, right: str) -> bool:
    return " ".join(left.strip().casefold().split()) == " ".join(right.strip().casefold().split())


def resolve_conversation_continuity(
    text: str,
    messages: list[ConversationMessage],
) -> ConversationContinuity:
    """Resolve compact replies against the latest secretary question without changing storage.

    Incoming messages remain stored exactly as sent. The resolved form is transient AI/retrieval
    context only; it is never learned or promoted to knowledge.
    """

    meaningful = [row for row in messages if (row.text or "").strip()]
    outgoing = [row for row in meaningful if row.direction == "OUT"]
    prior = meaningful
    if prior and prior[-1].direction == "IN" and _same_message_text(prior[-1].text or "", text):
        prior = prior[:-1]
    immediately_previous = prior[-1] if prior else None
    last_outgoing = (
        (immediately_previous.text or "").strip()
        if immediately_previous is not None and immediately_previous.direction == "OUT"
        else ""
    )
    prior_contact = ""
    if last_outgoing:
        for row in reversed(prior[:-1]):
            if row.direction == "IN" and (row.text or "").strip():
                prior_contact = (row.text or "").strip()
                break
    clean_text = " ".join(text.strip().split())
    is_contextual = bool(
        last_outgoing
        and _looks_like_short_answer(clean_text)
        and not _QUESTION_CUES.search(clean_text)
        and (not _NEW_TOPIC_CUES.search(clean_text) or _OUTCOME_CUES.search(clean_text))
    )
    if is_contextual:
        parts = []
        if prior_contact:
            parts.append(f"موضوع العميل السابق: {prior_contact[:500]}")
        if _QUESTION_CUES.search(last_outgoing):
            parts.append(f"السؤال السابق من السكرتير: {last_outgoing[:700]}")
            parts.append(f"إجابة العميل: {clean_text}")
        else:
            parts.append(f"آخر رد من السكرتير: {last_outgoing[:700]}")
            parts.append(f"رد العميل الحالي: {clean_text}")
        resolved = "\n".join(parts)
    else:
        resolved = text
    return ConversationContinuity(
        original_text=text,
        resolved_text=resolved,
        has_prior_outgoing=bool(outgoing),
        prior_outgoing_count=len(outgoing),
        contextual_short_reply=is_contextual,
        last_outgoing_question=(
            last_outgoing if is_contextual and _QUESTION_CUES.search(last_outgoing) else ""
        ),
        last_outgoing_message=last_outgoing if is_contextual else "",
        conversation_focus=prior_contact if is_contextual else "",
    )
