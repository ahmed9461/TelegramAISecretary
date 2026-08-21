import pytest

from app.ai.multimodal import MultimodalPipeline
from app.ai.schemas import Confidence, Decision
from app.db.enums import DecisionAction, RiskLevel
from app.vision.schemas import VisionObservation


class FakeVision:
    async def analyze_image(self, *, image_bytes: bytes, mime_type: str, user_text: str | None = None):
        assert image_bytes == b"img"
        assert mime_type == "image/jpeg"
        return VisionObservation(
            summary="A login error screenshot",
            extracted_text="Invalid password",
            visible_elements=["error dialog"],
            relevant_details=["Login failed"],
            uncertainty=[],
            detected_language="English",
            confidence=0.99,
        )


class FakeAI:
    def __init__(self) -> None:
        self.context_seen = None

    async def classify_and_decide(self, *, text: str, context: dict):
        self.context_seen = context
        return Decision(
            intent="SUPPORT",
            risk=RiskLevel.LOW,
            action=DecisionAction.REQUIRE_APPROVAL,
            confidence=Confidence(intent=0.9, retrieval=1, answer=0.9, policy=0.9),
            needs_owner=True,
            reason_code="APPROVAL_POLICY",
        )

    async def generate_reply(self, *, text: str, context: dict, decision: Decision):
        assert "Invalid password" in context["vision"]["extracted_text"]
        assert "UNTRUSTED_USER_CONTENT" in context["vision"]["extracted_text"]
        return "يظهر في الصورة خطأ في كلمة المرور."


@pytest.mark.asyncio
async def test_pipeline_routes_gemini_evidence_into_deepseek_context() -> None:
    ai = FakeAI()
    pipeline = MultimodalPipeline(vision=FakeVision(), ai=ai)
    result = await pipeline.process_image(
        image_bytes=b"img",
        mime_type="image/jpeg",
        user_text="وش المشكلة؟",
        context={"state": "AI_APPROVAL", "has_grounding": False},
    )
    assert ai.context_seen["has_grounding"] is True
    assert "A login error screenshot" in ai.context_seen["vision"]["summary"]
    assert "UNTRUSTED_USER_CONTENT" in ai.context_seen["vision"]["summary"]
    assert "كلمة المرور" in result.candidate_reply
