from dataclasses import dataclass
from datetime import UTC, datetime

from app.db.enums import Visibility


@dataclass(frozen=True, slots=True)
class KnowledgeRecord:
    id: str
    title: str
    content: str
    visibility: Visibility
    valid_from: datetime | None = None
    valid_until: datetime | None = None

    def usable_now(self, at: datetime | None = None) -> bool:
        at = at or datetime.now(UTC)
        if self.valid_from and at < self.valid_from:
            return False
        if self.valid_until and at > self.valid_until:
            return False
        return True

    def can_quote_to_contact(self) -> bool:
        return self.visibility == Visibility.PUBLIC and self.usable_now()
