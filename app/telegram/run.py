import asyncio

from aiogram import Bot

from app.config import get_settings
from app.observability.logging import configure_logging
from app.telegram.approval_edit_ui import router as approval_edit_router
from app.telegram.behavior_ui import router as behavior_router
from app.telegram.bootstrap import build_dispatcher
from app.telegram.brain_ui import router as brain_router
from app.telegram.bulk_knowledge_ui import router as bulk_knowledge_router
from app.telegram.interface_ui import router as interface_router
from app.telegram.knowledge_manage_ui import router as knowledge_manage_router
from app.telegram.memory_ui import router as memory_router
from app.telegram.policy_manage_ui import router as policy_manage_router


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.telegram_configured:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID are required")
    bot = Bot(settings.telegram_bot_token)
    dp = build_dispatcher()
    # Specialized M6 routers are registered before the generic brain router so they can
    # provide richer management screens for callbacks that existed as simple M5 placeholders.
    dp.include_router(approval_edit_router)
    dp.include_router(behavior_router)
    dp.include_router(memory_router)
    dp.include_router(knowledge_manage_router)
    dp.include_router(policy_manage_router)
    dp.include_router(bulk_knowledge_router)
    dp.include_router(interface_router)
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
