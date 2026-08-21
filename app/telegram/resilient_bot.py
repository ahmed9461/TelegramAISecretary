from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError

logger = logging.getLogger(__name__)


def is_owner_bound_method(method, *, owner_chat_id: int) -> bool:
    """Only owner/admin Bot API requests are safe enough for automatic retry.

    Customer sends deliberately keep the existing fail-closed behavior because retrying an
    uncertain customer send could duplicate a business reply. Owner approval cards may be
    duplicated in the rare case Telegram accepted the first request but the response was lost;
    duplicate cards still reference the same approval ID, so only one can actually be sent.
    """
    chat_id = getattr(method, "chat_id", None)
    return chat_id is not None and str(chat_id) == str(owner_chat_id)


class ResilientOwnerBot(Bot):
    def __init__(
        self,
        token: str,
        *,
        owner_chat_id: int,
        owner_request_retries: int = 2,
        retry_base_seconds: float = 0.8,
        **kwargs,
    ) -> None:
        super().__init__(token, **kwargs)
        self._owner_chat_id = owner_chat_id
        self._owner_request_retries = max(0, owner_request_retries)
        self._retry_base_seconds = max(0.0, retry_base_seconds)

    async def __call__(self, method, request_timeout=None):
        retries = self._owner_request_retries if is_owner_bound_method(
            method,
            owner_chat_id=self._owner_chat_id,
        ) else 0

        for attempt in range(retries + 1):
            try:
                return await super().__call__(method, request_timeout=request_timeout)
            except TelegramNetworkError:
                if attempt >= retries:
                    raise
                delay = self._retry_base_seconds * (2**attempt)
                logger.warning(
                    "telegram_owner_request_retry method=%s attempt=%s delay=%.2f",
                    type(method).__name__,
                    attempt + 1,
                    delay,
                )
                await asyncio.sleep(delay)

        raise RuntimeError("unreachable")
