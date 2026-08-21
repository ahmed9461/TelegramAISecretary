import re


_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{6}\b"),  # common OTP shape
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),  # payment-card-like digit sequence
]


def should_reject_long_term_memory(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return True
    return any(pattern.search(normalized) for pattern in _SENSITIVE_PATTERNS)
