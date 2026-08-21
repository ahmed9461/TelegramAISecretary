from app.config import Settings


def test_multimodal_requires_both_provider_keys() -> None:
    configured = Settings(
        _env_file=None,
        ai_provider="deepseek",
        deepseek_api_key="ds",
        vision_provider="gemini",
        gemini_api_key="gm",
    )
    assert configured.multimodal_configured is True

    missing = Settings(_env_file=None, ai_provider="deepseek", deepseek_api_key="ds", vision_provider="gemini")
    assert missing.multimodal_configured is False
