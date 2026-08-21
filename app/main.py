from fastapi import FastAPI

from app.config import get_settings
from app.observability.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Telegram AI Secretary", version="0.4.0")


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "environment": settings.app_env,
        "telegram_configured": settings.telegram_configured,
        "ai_provider": settings.ai_provider,
    }


@app.get("/ready", tags=["system"])
def ready() -> dict:
    return {"ready": True}
