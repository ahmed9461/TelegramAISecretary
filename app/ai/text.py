from __future__ import annotations

from dataclasses import dataclass

from app.ai.copy import polish_candidate_reply
from app.ai.provider import AIProvider
from app.ai.schemas import Decision
from app.db.enums import DecisionAction


@dataclass(frozen=True, slots=True)
class TextResult:
    decision: Decision
    candidate_reply: str
    token_usage: dict[str, int]


class TextPipeline:
    """DeepSeek classification/decision -> candidate reply behind local policy."""

    def __init__(self, *, ai: AIProvider) -> None:
        self.ai = ai

    async def process_text(self, *, text: str, context: dict) -> TextResult:
        decision = await self.ai.classify_and_decide(text=text, context=context)
        if decision.action in {DecisionAction.SILENT, DecisionAction.ESCALATE}:
            candidate = ""
        else:
            candidate = await self.ai.generate_reply(text=text, context=context, decision=decision)
            candidate = polish_candidate_reply(
                candidate,
                allow_greeting=not bool(context.get("conversation_has_prior_reply")),
            )
        usage = getattr(self.ai, "token_usage", {})
        return TextResult(
            decision=decision,
            candidate_reply=candidate,
            token_usage=dict(usage) if isinstance(usage, dict) else {},
        )
