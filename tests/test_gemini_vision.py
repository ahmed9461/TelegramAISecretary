import json

import httpx
import pytest

from app.vision.gemini import GeminiVisionProvider


@pytest.mark.asyncio
async def test_gemini_vision_returns_structured_observation() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-goog-api-key"] == "gem-test"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert body["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/jpeg"
        output = {
            "summary": "Screenshot of a subscription page",
            "extracted_text": "Premium - $10",
            "visible_elements": ["price card", "button"],
            "relevant_details": ["The visible price is $10"],
            "uncertainty": [],
            "detected_language": "English",
            "confidence": 0.98,
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(output)}]}}
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiVisionProvider(api_key="gem-test", client=client)
    result = await provider.analyze_image(
        image_bytes=b"fake-jpeg",
        mime_type="image/jpeg",
        user_text="كم السعر؟",
    )
    await client.aclose()

    assert result.extracted_text == "Premium - $10"
    assert result.confidence == 0.98
    assert "price card" in result.visible_elements
