from app.ai.intents import (
    BUSINESS_FACT_INTENTS,
    SAFE_CLARIFICATION_INTENTS,
    SENSITIVE_INTENTS,
    SOCIAL_INTENTS,
    canonicalize_intent,
)
from app.ai.schemas import Confidence, Decision
from app.db.enums import ConversationState, DecisionAction, RiskLevel


def choose_action(
    *,
    state: ConversationState,
    intent: str,
    risk: RiskLevel,
    confidence: Confidence,
    has_grounding: bool,
    has_public_grounding: bool | None = None,
    has_conflicting_grounding: bool = False,
    needs_more_info: bool = False,
) -> Decision:
    """Apply local safety policy after model classification.

    ``has_public_grounding`` is optional for backward compatibility. When supplied, automatic
    replies require PUBLIC knowledge for business-specific facts. INTERNAL knowledge may still
    guide a draft, but it cannot be enough to bypass owner approval.
    """
    public_grounding = has_grounding if has_public_grounding is None else has_public_grounding
    intent = canonicalize_intent(intent)

    if state in {
        ConversationState.EXCLUDED,
        ConversationState.HUMAN_TAKEOVER,
        ConversationState.PAUSED,
        ConversationState.OBSERVE_ONLY,
    }:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.SILENT,
            confidence=confidence,
            allowed_to_answer=False,
            reason_code=f"STATE_{state.value}",
        )

    if intent == "REQUEST_OWNER":
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.ESCALATE,
            confidence=confidence,
            needs_owner=True,
            allowed_to_answer=False,
            reason_code="OWNER_REQUESTED",
        )

    if risk == RiskLevel.HIGH or intent in SENSITIVE_INTENTS:
        sensitive_reasons = {
            "REFUND_AUTHORIZATION": "REFUND_DECISION",
            "DISCOUNT_REQUEST": "UNAPPROVED_DISCOUNT",
            "PRIVATE_DATA_REQUEST": "PRIVATE_DATA_REQUEST",
            "BINDING_COMMITMENT": "BINDING_COMMITMENT",
            "SENSITIVE_ACTION": "SENSITIVE_ACTION",
        }
        return Decision(
            intent=intent,
            risk=RiskLevel.HIGH,
            action=DecisionAction.ESCALATE,
            confidence=confidence,
            needs_owner=True,
            allowed_to_answer=False,
            reason_code=sensitive_reasons.get(intent, "HIGH_RISK"),
        )

    if has_conflicting_grounding:
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.REQUIRE_APPROVAL,
            confidence=confidence,
            needs_owner=True,
            reason_code="KNOWLEDGE_CONFLICT",
        )

    if not has_grounding and intent in SOCIAL_INTENTS:
        if state == ConversationState.AI_APPROVAL:
            return Decision(
                intent=intent,
                risk=risk,
                action=DecisionAction.REQUIRE_APPROVAL,
                confidence=confidence,
                needs_owner=True,
                reason_code="APPROVAL_POLICY",
            )
        if min(confidence.intent, confidence.policy) >= 0.55:
            return Decision(
                intent=intent,
                risk=risk,
                action=DecisionAction.AUTO_REPLY,
                confidence=confidence,
                reason_code="SAFE_SOCIAL_REPLY",
                reply_constraints=["NO_BUSINESS_FACTS"],
            )

    if (
        not has_grounding
        and needs_more_info
        and intent in SAFE_CLARIFICATION_INTENTS
        and min(confidence.intent, confidence.policy) >= 0.6
    ):
        action = (
            DecisionAction.REQUIRE_APPROVAL
            if state == ConversationState.AI_APPROVAL
            else DecisionAction.ASK_FOLLOWUP
        )
        return Decision(
            intent=intent,
            risk=risk,
            action=action,
            confidence=confidence,
            needs_owner=action == DecisionAction.REQUIRE_APPROVAL,
            needs_more_info=True,
            reason_code="APPROVAL_POLICY"
            if action == DecisionAction.REQUIRE_APPROVAL
            else "SAFE_CLARIFICATION",
            reply_constraints=["ASK_ONE_CLARIFYING_QUESTION", "NO_BUSINESS_FACTS"],
        )

    if not has_grounding and intent in BUSINESS_FACT_INTENTS | {"UNCLEAR"}:
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

    if (
        state == ConversationState.AI_AUTO
        and intent in BUSINESS_FACT_INTENTS
        and has_grounding
        and not public_grounding
    ):
        return Decision(
            intent=intent,
            risk=risk,
            action=DecisionAction.REQUIRE_APPROVAL,
            confidence=confidence,
            needs_owner=True,
            reason_code="NON_PUBLIC_GROUNDING",
        )

    return Decision(
        intent=intent,
        risk=risk,
        action=DecisionAction.AUTO_REPLY,
        confidence=confidence,
        reason_code="SAFE_AUTO",
    )
