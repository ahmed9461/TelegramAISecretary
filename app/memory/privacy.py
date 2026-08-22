import re

_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{6}\b"),  # common OTP shape
    re.compile(r"\b(?:\d[ -]*?){13,19}\b"),  # payment-card-like digit sequence
    re.compile(r"\bSA\d{22}\b", re.IGNORECASE),  # Saudi IBAN
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),  # common API-secret shape
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b"),  # bot-token-like secret
    re.compile(
        r"(?:كلمة\s*المرور|رمز\s*التحقق|password|passcode|api[_ -]?key|secret)"
        r"\s*[:=]?\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:تشخيص|مرض|دواء|حالة\s*صحية|diagnosis|medical|medication)\s*[:=]?\s*\S+",
        re.IGNORECASE,
    ),
]


def should_reject_long_term_memory(text: str) -> bool:
    normalized = text.strip()
    if not normalized:
        return True
    return any(pattern.search(normalized) for pattern in _SENSITIVE_PATTERNS)
