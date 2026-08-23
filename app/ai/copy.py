from __future__ import annotations

import re

_ARABIC_TODAY_HELP = re.compile(
    r"كيف\s+(?:أ|ا)قدر\s+(?:أ|ا)ساعدك\s+اليوم\s*([؟?]?)",
    re.IGNORECASE,
)
_ENGLISH_TODAY_HELP = re.compile(r"how can i help you today\s*([?]?)", re.IGNORECASE)
_INTERNAL_CODE_LINE = re.compile(
    r"(?im)^.*\b(?:HIGH_RISK|NO_GROUNDING|LOW_CONFIDENCE|APPROVAL_POLICY|"
    r"NON_PUBLIC_GROUNDING|SAFE_AUTO|KNOWLEDGE_CONFLICT|REQUIRE_APPROVAL|"
    r"AUTO_REPLY|ESCALATE|SILENT|STATE_[A-Z_]+)\b.*$"
)
_OPENING_GREETING = re.compile(
    r"^\s*(?:(?:السلام\s+عليكم(?:\s+ورحمة\s+الله(?:\s+وبركاته)?)?)|"
    r"(?:وعليكم\s+السلام(?:\s+ورحمة\s+الله(?:\s+وبركاته)?)?)|"
    r"(?:(?:أهلا|اهلا)(?:ً)?(?:\s+وسهلا(?:ً)?)?)|(?:هلا(?:\s+والله)?)|"
    r"(?:مرحبا(?:ً)?(?:\s+بك)?)|(?:حياك\s+الله)|(?:hello|hi|welcome))"
    r"\s*[!,.،؛;:\-–—]*\s*",
    re.IGNORECASE,
)
_PAIRED_MARKDOWN = re.compile(r"(?:\*\*|__)(.+?)(?:\*\*|__)", re.DOTALL)
_INLINE_BACKTICKS = re.compile(r"`([^`]+)`")
_MARKDOWN_HEADING = re.compile(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+")
_MARKDOWN_BULLET = re.compile(r"(?m)^[ \t]*[-*][ \t]+")


def polish_candidate_reply(text: str, *, allow_greeting: bool = True) -> str:
    """Apply deterministic customer-facing copy safeguards after model drafting."""
    value = _ARABIC_TODAY_HELP.sub("كيف أقدر أساعدك؟", text)
    value = _ENGLISH_TODAY_HELP.sub("How can I help?", value)
    value = _INTERNAL_CODE_LINE.sub("", value)
    value = _PAIRED_MARKDOWN.sub(r"\1", value)
    value = _INLINE_BACKTICKS.sub(r"\1", value)
    value = _MARKDOWN_HEADING.sub("", value)
    value = _MARKDOWN_BULLET.sub("• ", value)
    if not allow_greeting:
        without_repeat = _OPENING_GREETING.sub("", value, count=1).lstrip()
        if without_repeat:
            value = without_repeat
    value = "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()
    return re.sub(r"\n{3,}", "\n\n", value)
