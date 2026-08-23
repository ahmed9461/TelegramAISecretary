from __future__ import annotations

from dataclasses import dataclass

from app.ai.provider import AIProvider
from app.ai.schemas import Decision
from app.db.enums import DecisionAction
from app.media.provider import MediaProvider
from app.media.schemas import MediaObservation
from app.security.untrusted import wrap_untrusted


@dataclass(frozen=True, slots=True)
class MediaResult:
    observation: MediaObservation
    decision: Decision
    candidate_reply: str
    token_usage: dict[str, int]


class MediaPipeline:
    """Gemini extraction/transcription followed by DeepSeek policy reasoning."""

    def __init__(self, *, media: MediaProvider, ai: AIProvider) -> None:
        self.media = media
        self.ai = ai

    async def process_media(
        self,
        *,
        media_bytes: bytes,
        mime_type: str,
        media_kind: str,
        user_text: str | None,
        context: dict,
    ) -> MediaResult:
        observation = await self.media.analyze_media(
            media_bytes=media_bytes,
            mime_type=mime_type,
            media_kind=media_kind,
            user_text=user_text,
        )
        media_payload = observation.model_dump(mode="json")
        for key in ("summary", "transcript", "extracted_text", "detected_language"):
            value = media_payload.get(key)
            if isinstance(value, str):
                media_payload[key] = wrap_untrusted(value)
        media_payload["uncertainty"] = [
            wrap_untrusted(value) if isinstance(value, str) else value
            for value in media_payload.get("uncertainty") or []
        ]
        enriched_context = dict(context)
        enriched_context["media"] = media_payload
        enriched_context["has_grounding"] = True
        reasoning_text = (
            (user_text or "").strip()
            or observation.transcript.strip()
            or observation.extracted_text.strip()
            or observation.summary.strip()
            or "أرسل المستخدم ملفًا دون وصف إضافي."
        )[:6000]
        decision = await self.ai.classify_and_decide(
            text=reasoning_text, context=enriched_context
        )
        if decision.action in {DecisionAction.SILENT, DecisionAction.ESCALATE}:
            candidate = ""
        else:
            candidate = await self.ai.generate_reply(
                text=reasoning_text,
                context=enriched_context,
                decision=decision,
            )
        usage: dict[str, int] = {}
        for provider in (self.media, self.ai):
            provider_usage = getattr(provider, "token_usage", {})
            if not isinstance(provider_usage, dict):
                continue
            for key, value in provider_usage.items():
                if isinstance(value, int | float):
                    usage[key] = usage.get(key, 0) + int(value)
        return MediaResult(observation, decision, candidate, usage)
