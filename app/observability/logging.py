from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(authorization|api[_-]?key|token|password|secret)"
    r"(\s*[:=]\s*)(bearer\s+)?([^\s,;]+)"
)
_EXTRA_FIELDS = (
    "trace_id",
    "conversation_id",
    "telegram_update_id",
    "ai_run_id",
    "operation",
)


def redact_log_value(value: object) -> str:
    text = str(value)
    return _SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        text,
    )


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_log_value(record.getMessage()),
        }
        for field in _EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value not in (None, ""):
                payload[field] = redact_log_value(value)
        if record.exc_info:
            payload["exception"] = redact_log_value(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO", format_name: str = "json") -> None:
    handler = logging.StreamHandler()
    if format_name.strip().lower() == "json":
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
