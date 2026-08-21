import asyncio

from aiogram import Bot

from app.config import get_settings
from app.observability.logging import configure_logging
from app.telegram.bootstrap import build_dispatcher
from app.telegram.brain_ui import router as brain_router


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_configured:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID are required")
    bot = Bot(settings.telegram_bot_token)
    dp = build_dispatcher()
    dp.include_router(brain_router)
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
