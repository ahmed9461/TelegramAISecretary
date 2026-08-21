import pytest

from app.flows.engine import FlowDefinition, FlowRuntime, FlowStepDef, StepType


def subscription_flow() -> FlowDefinition:
    return FlowDefinition(
        id="subscription",
        version=1,
        entry_key="plan",
        steps={
            "plan": FlowStepDef("plan", StepType.ASK_CHOICE, "اختر الباقة", "email", ("شهر", "سنة")),
            "email": FlowStepDef("email", StepType.ASK_TEXT, "أرسل البريد", "done"),
            "done": FlowStepDef("done", StepType.COMPLETE),
        },
    )


def test_flow_is_generic_and_collects_data() -> None:
    runtime = FlowRuntime.start(subscription_flow())
    assert runtime.current.key == "plan"
    runtime.submit("سنة")
    assert runtime.current.key == "email"
    runtime.submit("user@example.com")
    assert runtime.completed
    assert runtime.data == {"plan": "سنة", "email": "user@example.com"}


def test_flow_rejects_invalid_choice() -> None:
    runtime = FlowRuntime.start(subscription_flow())
    with pytest.raises(ValueError, match="invalid_choice"):
        runtime.submit("أسبوع")
