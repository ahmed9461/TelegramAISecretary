from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StepType(StrEnum):
    MESSAGE = "MESSAGE"
    ASK_TEXT = "ASK_TEXT"
    ASK_CHOICE = "ASK_CHOICE"
    ASK_NUMBER = "ASK_NUMBER"
    ASK_DATE = "ASK_DATE"
    ASK_FILE = "ASK_FILE"
    ASK_CONTACT_DATA = "ASK_CONTACT_DATA"
    SHOW_KNOWLEDGE = "SHOW_KNOWLEDGE"
    AI_STEP = "AI_STEP"
    HANDOFF = "HANDOFF"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class FlowStepDef:
    key: str
    type: StepType
    prompt: str = ""
    next_key: str | None = None
    choices: tuple[str, ...] = ()
    required: bool = True


@dataclass(frozen=True, slots=True)
class FlowDefinition:
    id: str
    version: int
    entry_key: str
    steps: dict[str, FlowStepDef]

    def validate(self) -> None:
        if not self.steps:
            raise ValueError("flow has no steps")
        if self.entry_key not in self.steps:
            raise ValueError("entry step does not exist")
        for step in self.steps.values():
            if step.next_key and step.next_key not in self.steps:
                raise ValueError(f"missing next step: {step.next_key}")
            if step.type == StepType.ASK_CHOICE and not step.choices:
                raise ValueError(f"choice step {step.key} has no choices")
            if step.type in {
                StepType.ASK_TEXT,
                StepType.ASK_CHOICE,
                StepType.ASK_NUMBER,
                StepType.ASK_DATE,
                StepType.ASK_FILE,
                StepType.ASK_CONTACT_DATA,
            } and not step.prompt.strip():
                raise ValueError(f"input step {step.key} has no prompt")


@dataclass(slots=True)
class FlowRuntime:
    definition: FlowDefinition
    current_key: str
    data: dict[str, object] = field(default_factory=dict)
    completed: bool = False

    @classmethod
    def start(cls, definition: FlowDefinition) -> FlowRuntime:
        definition.validate()
        return cls(definition=definition, current_key=definition.entry_key)

    @property
    def current(self) -> FlowStepDef:
        return self.definition.steps[self.current_key]

    def submit(self, value: object | None = None) -> FlowStepDef | None:
        step = self.current
        if step.type == StepType.COMPLETE:
            self.completed = True
            return None

        if step.type in {
            StepType.ASK_TEXT,
            StepType.ASK_NUMBER,
            StepType.ASK_DATE,
            StepType.ASK_FILE,
            StepType.ASK_CONTACT_DATA,
            StepType.ASK_CHOICE,
        }:
            if step.required and (value is None or value == ""):
                raise ValueError("value_required")
            if step.type == StepType.ASK_CHOICE and value not in step.choices:
                raise ValueError("invalid_choice")
            if step.type == StepType.ASK_NUMBER:
                try:
                    value = float(value)  # type: ignore[arg-type]
                except (TypeError, ValueError) as exc:
                    raise ValueError("invalid_number") from exc
            self.data[step.key] = value

        if not step.next_key:
            self.completed = True
            return None

        self.current_key = step.next_key
        if self.current.type == StepType.COMPLETE:
            self.completed = True
        return self.current
