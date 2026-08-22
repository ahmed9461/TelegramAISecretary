import json

import httpx
import pytest

from app.ai.deepseek import DeepSeekAIProvider
from app.db.enums import ConversationState, DecisionAction, RiskLevel


@pytest.mark.asyncio
async def test_deepseek_classification_is_filtered_by_local_policy() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-flash"
        assert body["thinking"] == {"type": "disabled"}
        if calls == 1:
            assert body["response_format"] == {"type": "json_object"}
            content = json.dumps(
                {
                    "intent": "QUESTION",
                    "risk": "LOW",
                    "intent_confidence": 0.95,
                    "answer_confidence": 0.93,
                    "policy_confidence": 0.96,
                    "needs_more_info": False,
                }
            )
        else:
            content = "السعر الظاهر في الصورة هو 10 دولارات."
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DeepSeekAIProvider(api_key="ds-test", client=client)
    decision = await provider.classify_and_decide(
        text="كم السعر؟",
        context={
            "state": ConversationState.AI_APPROVAL.value,
            "has_grounding": True,
            "vision": {"extracted_text": "Premium - $10"},
        },
    )

    assert decision.risk == RiskLevel.LOW
    # Even high model confidence cannot bypass the owner's APPROVAL state.
    assert decision.action == DecisionAction.REQUIRE_APPROVAL

    reply = await provider.generate_reply(
        text="كم السعر؟",
        context={"vision": {"extracted_text": "Premium - $10"}},
        decision=decision,
    )
    await client.aclose()
    assert "10" in reply
    assert provider.token_usage == {
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "total_tokens": 30,
    }
