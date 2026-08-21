import json

import httpx
import pytest

from app.ai.deepseek import DeepSeekAIProvider


@pytest.mark.asyncio
async def test_deepseek_bulk_extraction_requires_structured_items() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        source = json.loads(body["messages"][1]["content"])["source"]
        assert "10 دولار" in source
        content = json.dumps(
            {
                "items": [
                    {
                        "type": "PRICE",
                        "title": "الاشتراك الشهري",
                        "content": "السعر 10 دولار.",
                        "tags": ["اشتراك"],
                    }
                ]
            },
            ensure_ascii=False,
        )
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = DeepSeekAIProvider(api_key="ds-test", client=client)
    items = await provider.extract_knowledge(text="الاشتراك الشهري سعره 10 دولار")
    await client.aclose()

    assert items[0]["type"] == "PRICE"
    assert items[0]["title"] == "الاشتراك الشهري"
