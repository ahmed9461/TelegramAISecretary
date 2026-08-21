from __future__ import annotations

OPEN_MARKER = "<<<UNTRUSTED_USER_CONTENT>>>"
CLOSE_MARKER = "<<<END_UNTRUSTED_USER_CONTENT>>>"


def sanitize_untrusted(value: str) -> str:
    """Prevent user text from forging our trust-boundary markers."""
    return value.replace("<<<", "‹‹‹").replace(">>>", "›››")


def wrap_untrusted(value: str | None) -> str:
    text = sanitize_untrusted(value or "")
    return f"{OPEN_MARKER}\n{text}\n{CLOSE_MARKER}"
