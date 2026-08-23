from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_token: str = Field(default="", repr=False)
    metrics_window_days: int = 30
    readiness_require_telegram: bool = True
    readiness_require_ai: bool = True
    backup_retention_days: int = 30

    telegram_bot_token: str = Field(default="", repr=False)
    owner_telegram_id: int = 0
    telegram_polling: bool = True

    database_url: str = Field(default="sqlite+pysqlite:///./secretary.sqlite3")

    ai_provider: str = "disabled"
    ai_request_timeout_seconds: float = 60.0
    ai_max_retries: int = 2
    ai_retry_base_seconds: float = 1.0

    approval_ttl_hours: int = 24
    message_debounce_seconds: float = 1.5
    context_message_limit: int = 12
    knowledge_top_k: int = 6
    memory_retention_days: int = 365
    memory_suggestion_ttl_hours: int = 72
    feedback_buttons_enabled: bool = True
    feedback_prompt_every_n_responses: int = 3
    custom_intent_default_threshold: float = 0.82
    schedule_poll_seconds: float = 30.0
    schedule_batch_size: int = 20
    schedule_claim_timeout_seconds: int = 300

    deepseek_api_key: str = Field(default="", repr=False)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_thinking_enabled: bool = False

    vision_provider: str = "disabled"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_base_url: str = "https://generativelanguage.googleapis.com"
    gemini_model: str = "gemini-3.7-flash"
    gemini_fallback_models: str = "gemini-3.6-flash,gemini-3.5-flash"
    gemini_max_retries: int = 2
    gemini_retry_base_seconds: float = 1.0
    max_image_bytes: int = 10_000_000
    max_media_bytes: int = 18_000_000

    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = ""

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.owner_telegram_id)

    @property
    def text_ai_configured(self) -> bool:
        return bool(self.ai_provider == "deepseek" and self.deepseek_api_key)

    @property
    def gemini_fallback_model_list(self) -> tuple[str, ...]:
        return tuple(
            model.strip()
            for model in self.gemini_fallback_models.split(",")
            if model.strip() and model.strip() != self.gemini_model
        )

    @property
    def multimodal_configured(self) -> bool:
        return bool(
            self.ai_provider == "deepseek"
            and self.deepseek_api_key
            and self.vision_provider == "gemini"
            and self.gemini_api_key
        )

    @property
    def bounded_custom_intent_threshold(self) -> float:
        return max(0.5, min(1.0, self.custom_intent_default_threshold))


@lru_cache
def get_settings() -> Settings:
    return Settings()
