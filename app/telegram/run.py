import asyncio

from app.config import get_settings
from app.observability.logging import configure_logging
from app.schedules.runner import run_reminder_loop
from app.telegram.approval_edit_ui import router as approval_edit_router
from app.telegram.automation_ui import router as automation_router
from app.telegram.behavior_ui import router as behavior_router
from app.telegram.bootstrap import build_dispatcher
from app.telegram.brain_ui import router as brain_router
from app.telegram.bulk_knowledge_ui import router as bulk_knowledge_router
from app.telegram.feedback_ui import router as feedback_router
from app.telegram.interface_ui import router as interface_router
from app.telegram.knowledge_manage_ui import router as knowledge_manage_router
from app.telegram.memory_ui import router as memory_router
from app.telegram.policy_manage_ui import router as policy_manage_router
from app.telegram.resilient_bot import ResilientOwnerBot
from app.telegram.schedule_ui import router as schedule_router


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    if not settings.telegram_configured:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID are required")
    bot = ResilientOwnerBot(
        settings.telegram_bot_token,
        owner_chat_id=settings.owner_telegram_id,
    )
    dp = build_dispatcher()
    # Specialized routers are registered before the generic brain router so current management
    # screens handle their callbacks instead of older placeholders.
    dp.include_router(approval_edit_router)
    dp.include_router(feedback_router)
    dp.include_router(automation_router)
    dp.include_router(schedule_router)
    dp.include_router(behavior_router)
    dp.include_router(memory_router)
    dp.include_router(knowledge_manage_router)
    dp.include_router(policy_manage_router)
    dp.include_router(bulk_knowledge_router)
    dp.include_router(interface_router)
    dp.include_router(brain_router)
    stop_event = asyncio.Event()
    reminder_task = asyncio.create_task(run_reminder_loop(bot, stop_event))
    try:
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
    finally:
        stop_event.set()
        await reminder_task


if __name__ == "__main__":
    asyncio.run(main())
