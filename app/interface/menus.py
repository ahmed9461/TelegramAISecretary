from dataclasses import dataclass, field
from enum import StrEnum

from app.db.enums import InterfaceMode


class MenuAction(StrEnum):
    SEND_MESSAGE = "SEND_MESSAGE"
    OPEN_SUBMENU = "OPEN_SUBMENU"
    START_FLOW = "START_FLOW"
    TRIGGER_INTENT = "TRIGGER_INTENT"
    SHOW_KNOWLEDGE = "SHOW_KNOWLEDGE"
    HANDOFF = "HANDOFF"
    OPEN_URL = "OPEN_URL"
    COLLECT_DATA = "COLLECT_DATA"
    START_PAYMENT = "START_PAYMENT"


@dataclass(frozen=True, slots=True)
class MenuButton:
    id: str
    label: str
    action: MenuAction
    emoji: str | None = None
    config: dict = field(default_factory=dict)
    enabled: bool = True
    row: int = 0
    order: int = 0


@dataclass(frozen=True, slots=True)
class MenuDefinition:
    mode: InterfaceMode
    buttons: tuple[MenuButton, ...] = ()

    def visible_rows(self) -> list[list[MenuButton]]:
        if self.mode == InterfaceMode.AI_ONLY:
            return []
        active = [button for button in self.buttons if button.enabled]
        rows: dict[int, list[MenuButton]] = {}
        for button in sorted(active, key=lambda b: (b.row, b.order, b.id)):
            rows.setdefault(button.row, []).append(button)
        return [rows[key] for key in sorted(rows)]
