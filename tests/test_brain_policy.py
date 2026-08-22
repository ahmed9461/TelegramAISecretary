from app.ai.policy import choose_action
from app.ai.schemas import Confidence
from app.db.enums import ConversationState, DecisionAction, RiskLevel

HIGH_CONF = Confidence(intent=0.95, retrieval=0.95, answer=0.95, policy=0.95)


def test_internal_only_grounding_cannot_auto_send_business_fact() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=HIGH_CONF,
        has_grounding=True,
        has_public_grounding=False,
    )
    assert decision.action == DecisionAction.REQUIRE_APPROVAL
    assert decision.reason_code == "NON_PUBLIC_GROUNDING"


def test_public_grounding_can_reach_auto_path_when_safe() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=HIGH_CONF,
        has_grounding=True,
        has_public_grounding=True,
    )
    assert decision.action == DecisionAction.AUTO_REPLY


def test_greeting_does_not_require_business_knowledge() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="GREETING",
        risk=RiskLevel.LOW,
        confidence=HIGH_CONF,
        has_grounding=False,
        has_public_grounding=False,
    )
    assert decision.action == DecisionAction.AUTO_REPLY
