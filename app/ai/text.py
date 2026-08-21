from __future__ import annotations

from dataclasses import dataclass

from app.ai.provider import AIProvider
from app.ai.schemas import Decision
from app.db.enums import DecisionAction


@dataclass(frozen=True, slots=True)
class TextResult:
    decision: Decision
    candidate_reply: str


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
        return TextResult(decision=decision, candidate_reply=candidate)
