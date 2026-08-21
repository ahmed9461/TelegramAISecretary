import pytest

from app.ai.schemas import Confidence, Decision
from app.ai.text import TextPipeline
from app.db.enums import DecisionAction, RiskLevel


class FakeAI:
    async def classify_and_decide(self, *, text: str, context: dict) -> Decision:
        return Decision(
            intent="GREETING",
            risk=RiskLevel.LOW,
            action=DecisionAction.REQUIRE_APPROVAL,
            confidence=Confidence(intent=0.9, retrieval=0.0, answer=0.9, policy=0.9),
            reason_code="APPROVAL_POLICY",
        )

    async def generate_reply(self, *, text: str, context: dict, decision: Decision) -> str:
        return "أهلًا وسهلًا 👋"


@pytest.mark.asyncio
async def test_text_pipeline_creates_candidate_for_greeting() -> None:
    result = await TextPipeline(ai=FakeAI()).process_text(
        text="مرحبا",
        context={"state": "AI_APPROVAL", "has_grounding": False},
    )
    assert result.decision.action == DecisionAction.REQUIRE_APPROVAL
    assert "أهلًا" in result.candidate_reply
