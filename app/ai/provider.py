from typing import Protocol

from app.ai.schemas import Decision


class AIProvider(Protocol):
    async def classify_and_decide(self, *, text: str, context: dict) -> Decision: ...

    async def generate_reply(self, *, text: str, context: dict, decision: Decision) -> str: ...
