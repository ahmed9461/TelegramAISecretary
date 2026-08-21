from enum import StrEnum


class GlobalMode(StrEnum):
    AUTO = "AUTO"
    APPROVAL = "APPROVAL"
    OBSERVE = "OBSERVE"
    OFF = "OFF"


class ConversationState(StrEnum):
    AI_AUTO = "AI_AUTO"
    AI_APPROVAL = "AI_APPROVAL"
    OBSERVE_ONLY = "OBSERVE_ONLY"
    HUMAN_TAKEOVER = "HUMAN_TAKEOVER"
    ESCALATED = "ESCALATED"
    PAUSED = "PAUSED"
    EXCLUDED = "EXCLUDED"


class InterfaceMode(StrEnum):
    AI_ONLY = "AI_ONLY"
    CUSTOM_MENU = "CUSTOM_MENU"
    HYBRID = "HYBRID"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class DecisionAction(StrEnum):
    AUTO_REPLY = "AUTO_REPLY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"
    SILENT = "SILENT"
    ASK_FOLLOWUP = "ASK_FOLLOWUP"


class Visibility(StrEnum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    PRIVATE = "PRIVATE"


class FlowStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class FlowSessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
