from __future__ import annotations

from dataclasses import dataclass

from app.ai.provider import AIProvider
from app.ai.schemas import Decision
from app.db.enums import DecisionAction
from app.security.untrusted import wrap_untrusted
from app.vision.provider import VisionProvider
from app.vision.schemas import VisionObservation


@dataclass(frozen=True, slots=True)
class MultimodalResult:
    vision: VisionObservation
    decision: Decision
    candidate_reply: str
    token_usage: dict[str, int]


class MultimodalPipeline:
    """Gemini vision -> normalized evidence -> DeepSeek reasoning/reply."""

    def __init__(self, *, vision: VisionProvider, ai: AIProvider) -> None:
        self.vision = vision
        self.ai = ai

    async def process_image(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        user_text: str | None,
        context: dict,
    ) -> MultimodalResult:
        observation = await self.vision.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
            user_text=user_text,
        )
        enriched_context = dict(context)
        vision_payload = observation.model_dump(mode="json")
        for key in ("summary", "extracted_text", "detected_language"):
            if isinstance(vision_payload.get(key), str):
                vision_payload[key] = wrap_untrusted(vision_payload[key])
        for key in ("visible_elements", "relevant_details", "uncertainty"):
            values = vision_payload.get(key)
            if isinstance(values, list):
                vision_payload[key] = [
                    wrap_untrusted(value) if isinstance(value, str) else value for value in values
                ]
        enriched_context["vision"] = vision_payload
        # The image itself can ground visual claims. It does not automatically ground
        # unrelated facts about the owner, so callers may still add knowledge separately.
        enriched_context["has_grounding"] = True
        reasoning_text = user_text or "المستخدم أرسل صورة بدون نص إضافي."
        decision = await self.ai.classify_and_decide(text=reasoning_text, context=enriched_context)
        if decision.action in {DecisionAction.SILENT, DecisionAction.ESCALATE}:
            candidate = ""
        else:
            candidate = await self.ai.generate_reply(
                text=reasoning_text,
                context=enriched_context,
                decision=decision,
            )
        usage: dict[str, int] = {}
        for provider in (self.vision, self.ai):
            provider_usage = getattr(provider, "token_usage", {})
            if not isinstance(provider_usage, dict):
                continue
            for key, value in provider_usage.items():
                if isinstance(value, int | float):
                    usage[key] = usage.get(key, 0) + int(value)
        return MultimodalResult(
            vision=observation,
            decision=decision,
            candidate_reply=candidate,
            token_usage=usage,
        )
