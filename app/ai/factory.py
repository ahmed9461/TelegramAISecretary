from app.ai.deepseek import DeepSeekAIProvider
from app.ai.multimodal import MultimodalPipeline
from app.ai.text import TextPipeline
from app.config import Settings
from app.vision.gemini import GeminiVisionProvider


def build_ai_provider(settings: Settings) -> DeepSeekAIProvider:
    if settings.ai_provider != "deepseek":
        raise ValueError("AI_PROVIDER must be deepseek for this milestone")
    return DeepSeekAIProvider(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        timeout_seconds=settings.ai_request_timeout_seconds,
        thinking_enabled=settings.deepseek_thinking_enabled,
        max_retries=settings.ai_max_retries,
        retry_base_seconds=settings.ai_retry_base_seconds,
    )


def build_text_pipeline(settings: Settings) -> TextPipeline:
    return TextPipeline(ai=build_ai_provider(settings))


def build_multimodal_pipeline(settings: Settings) -> MultimodalPipeline:
    if settings.vision_provider != "gemini":
        raise ValueError("Multimodal image pipeline currently requires VISION_PROVIDER=gemini")

    ai = build_ai_provider(settings)
    vision = GeminiVisionProvider(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
        fallback_models=settings.gemini_fallback_model_list,
        max_retries=settings.gemini_max_retries,
        retry_base_seconds=settings.gemini_retry_base_seconds,
        base_url=settings.gemini_base_url,
        timeout_seconds=settings.ai_request_timeout_seconds,
    )
    return MultimodalPipeline(vision=vision, ai=ai)
