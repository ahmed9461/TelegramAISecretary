from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

logger = logging.getLogger(__name__)

_EXPIRED_MARKERS = (
    "query is too old",
    "response timeout expired",
    "query id is invalid",
)


def is_expired_callback_error(error: TelegramBadRequest) -> bool:
    message = str(error).lower()
    return any(marker in message for marker in _EXPIRED_MARKERS)


async def safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> bool:
    """Answer a callback without turning an expired Telegram query into a handler crash.

    Telegram callback-query IDs are short-lived. Old inline buttons, polling backlog,
    or a bot restart can make a callback expire even when the requested action itself
    completed successfully. Those expected expiration errors are logged and ignored;
    every other TelegramBadRequest is still raised normally.
    """

    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as error:
        if not is_expired_callback_error(error):
            raise
        logger.info(
            "callback_query_expired callback_id=%s data=%r",
            callback.id,
            callback.data,
        )
        return False
    return True
