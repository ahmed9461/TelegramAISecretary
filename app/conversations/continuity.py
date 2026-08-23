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
    r"(?:[؟?]|\b(?:كم|اختر|اختار|حدد|ارسل|أرسل|اذكر|هل|ماهي|ما\s+هي|what|which|how\s+many)\b)",
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


def _looks_like_short_answer(value: str) -> bool:
    clean = " ".join(value.strip().split())
    if not clean or "؟" in clean or "?" in clean:
        return False
    if _SHORT_NUMBER.fullmatch(clean) or clean.casefold() in _NORMALIZED_SHORT_ANSWERS:
        return True
    # One or two words can be a direct choice such as "الباقة السنوية". Longer free text is
    # left untouched so this helper does not reinterpret a new topic as an answer.
    return len(clean) <= 32 and len(clean.split()) <= 2


def resolve_conversation_continuity(
    text: str,
    messages: list[ConversationMessage],
) -> ConversationContinuity:
    """Resolve compact replies against the latest secretary question without changing storage.

    Incoming messages remain stored exactly as sent. The resolved form is transient AI/retrieval
    context only; it is never learned or promoted to knowledge.
    """

    outgoing = [row for row in messages if row.direction == "OUT" and (row.text or "").strip()]
    last_outgoing = (outgoing[-1].text or "").strip() if outgoing else ""
    is_contextual = bool(
        last_outgoing and _QUESTION_CUES.search(last_outgoing) and _looks_like_short_answer(text)
    )
    resolved = (
        f"السؤال السابق من السكرتير: {last_outgoing}\nإجابة العميل: {text.strip()}"
        if is_contextual
        else text
    )
    return ConversationContinuity(
        original_text=text,
        resolved_text=resolved,
        has_prior_outgoing=bool(outgoing),
        prior_outgoing_count=len(outgoing),
        contextual_short_reply=is_contextual,
        last_outgoing_question=last_outgoing if is_contextual else "",
    )
