from app.ai.policy import choose_action
from app.ai.schemas import Confidence
from app.db.enums import ConversationState, DecisionAction, RiskLevel

HIGH_CONF = Confidence(intent=0.95, retrieval=0.95, answer=0.95, policy=0.95)


def test_high_risk_always_escalates() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="PRICE_COMMITMENT",
        risk=RiskLevel.HIGH,
        confidence=HIGH_CONF,
        has_grounding=True,
    )
    assert decision.action == DecisionAction.ESCALATE


def test_unknown_without_grounding_does_not_hallucinate() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=HIGH_CONF,
        has_grounding=False,
    )
    assert decision.action == DecisionAction.ESCALATE
    assert decision.allowed_to_answer is False


def test_low_risk_grounded_can_auto_reply() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=HIGH_CONF,
        has_grounding=True,
    )
    assert decision.action == DecisionAction.AUTO_REPLY


def test_conflicting_grounding_requires_owner_review() -> None:
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=HIGH_CONF,
        has_grounding=True,
        has_public_grounding=True,
        has_conflicting_grounding=True,
    )
    assert decision.action == DecisionAction.REQUIRE_APPROVAL
    assert decision.reason_code == "KNOWLEDGE_CONFLICT"

    low_confidence = Confidence(intent=0.5, retrieval=0.8, answer=0.5, policy=0.8)
    decision = choose_action(
        state=ConversationState.AI_AUTO,
        intent="QUESTION",
        risk=RiskLevel.LOW,
        confidence=low_confidence,
        has_grounding=True,
        has_public_grounding=True,
        has_conflicting_grounding=True,
    )
    assert decision.reason_code == "KNOWLEDGE_CONFLICT"
