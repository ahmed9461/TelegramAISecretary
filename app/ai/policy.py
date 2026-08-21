from app.ai.schemas import Confidence, Decision
from app.db.enums import ConversationState, DecisionAction, RiskLevel


def choose_action(
    *,
    state: ConversationState,
    intent: str,
    risk: RiskLevel,
    confidence: Confidence,
    has_grounding: bool,
) -> Decision:
    if state in {ConversationState.EXCLUDED, ConversationState.HUMAN_TAKEOVER, ConversationState.PAUSED}:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.SILENT,
            confidence=confidence,
            allowed_to_answer=False,
            reason_code=f"STATE_{state.value}",
        )

    if risk == RiskLevel.HIGH:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.ESCALATE,
            confidence=confidence,
            needs_owner=True,
            allowed_to_answer=False,
            reason_code="HIGH_RISK",
        )

    if not has_grounding and intent not in {"GREETING", "REQUEST_OWNER"}:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.ESCALATE,
            confidence=confidence,
            needs_owner=True,
            allowed_to_answer=False,
            reason_code="NO_GROUNDING",
        )

    if min(confidence.intent, confidence.answer, confidence.policy) < 0.7:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.REQUIRE_APPROVAL,
            confidence=confidence,
            needs_owner=True,
            reason_code="LOW_CONFIDENCE",
        )

    if state == ConversationState.AI_APPROVAL or risk == RiskLevel.MEDIUM:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.REQUIRE_APPROVAL,
            confidence=confidence,
            needs_owner=True,
            reason_code="APPROVAL_POLICY",
        )

    if state == ConversationState.OBSERVE_ONLY:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.SILENT,
            confidence=confidence,
            allowed_to_answer=False,
            reason_code="OBSERVE_ONLY",
        )

    return Decision(
        intent=intent,
        risk=risk,
        action=DecisionAction.AUTO_REPLY,
        confidence=confidence,
        reason_code="SAFE_AUTO",
    )
