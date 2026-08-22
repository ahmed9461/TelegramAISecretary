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


def polish_candidate_reply(text: str) -> str:
    """Apply deterministic customer-facing copy safeguards after model drafting."""
    value = _ARABIC_TODAY_HELP.sub("كيف أقدر أساعدك؟", text)
    value = _ENGLISH_TODAY_HELP.sub("How can I help?", value)
    value = _INTERNAL_CODE_LINE.sub("", value)
    value = "\n".join(line.rstrip() for line in value.strip().splitlines()).strip()
    return re.sub(r"\n{3,}", "\n\n", value)
