import json

import httpx
import pytest

from app.vision.gemini import GeminiVisionProvider


@pytest.mark.asyncio
async def test_gemini_retries_503_then_succeeds() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": {"message": "busy"}})
        observation = {
            "summary": "صورة اختبار",
            "extracted_text": "hello",
            "visible_elements": ["text"],
            "relevant_details": [],
            "uncertainty": [],
            "detected_language": "en",
            "confidence": 0.9,
        }
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(observation)}]}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiVisionProvider(
        api_key="gm", client=client, max_retries=1, retry_base_seconds=0
    )
    result = await provider.analyze_image(image_bytes=b"abc", mime_type="image/jpeg")
    await client.aclose()
    assert calls == 2
    assert result.extracted_text == "hello"


@pytest.mark.asyncio
async def test_gemini_falls_back_after_transient_failures() -> None:
    seen_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        if "gemini-3.7-flash" in str(request.url):
            return httpx.Response(503, json={"error": {"message": "busy"}})
        observation = {
            "summary": "fallback ok",
            "extracted_text": "",
            "visible_elements": [],
            "relevant_details": [],
            "uncertainty": [],
            "detected_language": "unknown",
            "confidence": 0.8,
        }
        return httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(observation)}]}}]}
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = GeminiVisionProvider(
        api_key="gm",
        client=client,
        max_retries=0,
        retry_base_seconds=0,
        fallback_models=("gemini-3.6-flash",),
    )
    result = await provider.analyze_image(image_bytes=b"abc", mime_type="image/jpeg")
    await client.aclose()
    assert result.summary == "fallback ok"
    assert any("gemini-3.6-flash" in url for url in seen_urls)
