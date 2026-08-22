from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import ConversationState, FlowSessionStatus, FlowStatus
from app.db.models import Conversation, Flow, FlowSession, FlowStep
from app.flows.engine import FlowDefinition, FlowRuntime, FlowStepDef, StepType

_MAX_STEPS = 40


class FlowAutomationBlockedError(ValueError):
    """Raised when human ownership or a pause forbids flow automation."""


@dataclass(frozen=True, slots=True)
class FlowTurn:
    session_id: int
    flow_id: int
    flow_name: str
    prompt: str
    choices: tuple[str, ...] = ()
    completed: bool = False
    handoff: bool = False
    collected_data: dict | None = None


def _step_from_row(row: FlowStep) -> FlowStepDef:
    config = dict(row.config_json or {})
    rules = dict(row.next_step_rules_json or {})
    return FlowStepDef(
        key=row.step_key,
        type=StepType(row.step_type),
        prompt=str(config.get("prompt") or "").strip(),
        next_key=str(rules.get("next_key") or "").strip() or None,
        choices=tuple(
            str(item).strip() for item in config.get("choices") or [] if str(item).strip()
        ),
        required=bool(config.get("required", True)),
    )


def definition_from_rows(flow: Flow, rows: list[FlowStep]) -> FlowDefinition:
    if len(rows) > _MAX_STEPS:
        raise ValueError("flow has too many steps")
    definition = FlowDefinition(
        id=str(flow.id),
        version=flow.version,
        entry_key=str(flow.entry_step_key or ""),
        steps={row.step_key: _step_from_row(row) for row in rows},
    )
    definition.validate()
    return definition


def serialize_definition(definition: FlowDefinition) -> dict:
    return {
        "id": definition.id,
        "version": definition.version,
        "entry_key": definition.entry_key,
        "steps": [
            {
                "key": step.key,
                "type": step.type.value,
                "prompt": step.prompt,
                "next_key": step.next_key,
                "choices": list(step.choices),
                "required": step.required,
            }
            for step in definition.steps.values()
        ],
    }


def deserialize_definition(payload: dict) -> FlowDefinition:
    steps = {
        str(item["key"]): FlowStepDef(
            key=str(item["key"]),
            type=StepType(str(item["type"])),
            prompt=str(item.get("prompt") or ""),
            next_key=str(item.get("next_key") or "") or None,
            choices=tuple(str(value) for value in item.get("choices") or []),
            required=bool(item.get("required", True)),
        )
        for item in payload.get("steps") or []
    }
    definition = FlowDefinition(
        id=str(payload.get("id") or ""),
        version=int(payload.get("version") or 1),
        entry_key=str(payload.get("entry_key") or ""),
        steps=steps,
    )
    definition.validate()
    return definition


def load_flow_definition(session: Session, *, flow_id: int) -> tuple[Flow, FlowDefinition] | None:
    flow = session.get(Flow, flow_id)
    if flow is None:
        return None
    rows = list(
        session.scalars(
            select(FlowStep)
            .where(FlowStep.flow_id == flow.id)
            .order_by(FlowStep.sort_order, FlowStep.id)
        )
    )
    return flow, definition_from_rows(flow, rows)


def active_flow_session(session: Session, *, conversation_id: int) -> FlowSession | None:
    return session.scalar(
        select(FlowSession)
        .where(
            FlowSession.conversation_id == conversation_id,
            FlowSession.status == FlowSessionStatus.ACTIVE.value,
        )
        .order_by(FlowSession.started_at.desc(), FlowSession.id.desc())
        .limit(1)
    )


def _runtime_for_session(row: FlowSession) -> FlowRuntime:
    definition = deserialize_definition(dict(row.definition_json or {}))
    return FlowRuntime(
        definition=definition,
        current_key=row.current_step_key,
        data=dict(row.collected_data_json or {}),
    )


def _completion_message(flow: Flow) -> str:
    configured = str((flow.completion_action_json or {}).get("message") or "").strip()
    return configured or "شكرًا، اكتملت المعلومات المطلوبة وسيتابعها المسؤول."


def _turn_for_runtime(
    *,
    row: FlowSession,
    flow: Flow,
    runtime: FlowRuntime,
) -> FlowTurn:
    prefixes: list[str] = []
    while not runtime.completed and runtime.current.type == StepType.MESSAGE:
        if runtime.current.prompt:
            prefixes.append(runtime.current.prompt)
        runtime.submit()

    if runtime.completed or runtime.current.type == StepType.COMPLETE:
        row.status = FlowSessionStatus.COMPLETED.value
        row.completed_at = datetime.now(UTC)
        row.collected_data_json = dict(runtime.data)
        return FlowTurn(
            session_id=row.id,
            flow_id=flow.id,
            flow_name=flow.name,
            prompt="\n\n".join([*prefixes, _completion_message(flow)]),
            completed=True,
            collected_data=dict(runtime.data),
        )

    if runtime.current.type == StepType.HANDOFF:
        row.status = FlowSessionStatus.COMPLETED.value
        row.completed_at = datetime.now(UTC)
        row.collected_data_json = dict(runtime.data)
        return FlowTurn(
            session_id=row.id,
            flow_id=flow.id,
            flow_name=flow.name,
            prompt=runtime.current.prompt or "تم تحويل طلبك للمتابعة البشرية.",
            completed=True,
            handoff=True,
            collected_data=dict(runtime.data),
        )

    row.current_step_key = runtime.current_key
    row.collected_data_json = dict(runtime.data)
    prompt = "\n\n".join([*prefixes, runtime.current.prompt])
    return FlowTurn(
        session_id=row.id,
        flow_id=flow.id,
        flow_name=flow.name,
        prompt=prompt,
        choices=runtime.current.choices,
        collected_data=dict(runtime.data),
    )


def start_flow(
    session: Session,
    *,
    conversation: Conversation,
    flow_id: int,
) -> FlowTurn:
    if conversation.state in {
        ConversationState.EXCLUDED.value,
        ConversationState.HUMAN_TAKEOVER.value,
        ConversationState.PAUSED.value,
        ConversationState.OBSERVE_ONLY.value,
    }:
        raise ValueError("conversation does not allow automation")
    loaded = load_flow_definition(session, flow_id=flow_id)
    if loaded is None:
        raise ValueError("flow not found")
    flow, definition = loaded
    if flow.owner_id != conversation.owner_id or flow.status != FlowStatus.PUBLISHED.value:
        raise ValueError("flow is not published for this owner")
    existing = active_flow_session(session, conversation_id=conversation.id)
    if existing is not None:
        raise ValueError("conversation already has an active flow")

    runtime = FlowRuntime.start(definition)
    row = FlowSession(
        conversation_id=conversation.id,
        flow_id=flow.id,
        flow_version=flow.version,
        current_step_key=runtime.current_key,
        collected_data_json={},
        definition_json=serialize_definition(definition),
        status=FlowSessionStatus.ACTIVE.value,
    )
    session.add(row)
    session.flush()
    return _turn_for_runtime(row=row, flow=flow, runtime=runtime)


def submit_flow_value(
    session: Session,
    *,
    conversation: Conversation,
    value: object | None,
) -> FlowTurn | None:
    row = active_flow_session(session, conversation_id=conversation.id)
    if row is None:
        return None
    if conversation.state in {
        ConversationState.EXCLUDED.value,
        ConversationState.HUMAN_TAKEOVER.value,
        ConversationState.PAUSED.value,
        ConversationState.OBSERVE_ONLY.value,
    }:
        row.status = FlowSessionStatus.CANCELLED.value
        row.completed_at = datetime.now(UTC)
        session.flush()
        raise FlowAutomationBlockedError("conversation does not allow automation")
    flow = session.get(Flow, row.flow_id)
    if flow is None or flow.owner_id != conversation.owner_id:
        row.status = FlowSessionStatus.FAILED.value
        return None
    runtime = _runtime_for_session(row)
    runtime.submit(value)
    return _turn_for_runtime(row=row, flow=flow, runtime=runtime)


def cancel_active_flow(session: Session, *, conversation_id: int) -> bool:
    row = active_flow_session(session, conversation_id=conversation_id)
    if row is None:
        return False
    row.status = FlowSessionStatus.CANCELLED.value
    row.completed_at = datetime.now(UTC)
    session.flush()
    return True
