from __future__ import annotations

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from app.telegram import resilient_bot as resilient_bot_module
from app.telegram.resilient_bot import ResilientOwnerBot

VALID_TEST_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"


@pytest.mark.asyncio
async def test_owner_request_retries_network_errors_then_succeeds(monkeypatch) -> None:
    attempts: list[tuple[SendMessage, int | None]] = []
    sleeps: list[float] = []
    expected_result = object()

    async def flaky_call(self, method, request_timeout=None):
        attempts.append((method, request_timeout))
        if len(attempts) < 3:
            raise TelegramNetworkError(method, "simulated disconnect")
        return expected_result

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(Bot, "__call__", flaky_call)
    monkeypatch.setattr(resilient_bot_module.asyncio, "sleep", record_sleep)

    bot = ResilientOwnerBot(
        VALID_TEST_TOKEN,
        owner_chat_id=123,
        owner_request_retries=2,
        retry_base_seconds=0.25,
    )
    try:
        result = await bot(SendMessage(chat_id=123, text="owner card"), request_timeout=9)
    finally:
        await bot.session.close()

    assert result is expected_result
    assert len(attempts) == 3
    assert [timeout for _, timeout in attempts] == [9, 9, 9]
    assert sleeps == [0.25, 0.5]


@pytest.mark.asyncio
async def test_customer_request_is_not_retried_after_uncertain_network_failure(
    monkeypatch,
) -> None:
    attempts: list[SendMessage] = []
    sleeps: list[float] = []

    async def failed_call(self, method, request_timeout=None):
        attempts.append(method)
        raise TelegramNetworkError(method, "simulated uncertain customer send")

    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(Bot, "__call__", failed_call)
    monkeypatch.setattr(resilient_bot_module.asyncio, "sleep", record_sleep)

    bot = ResilientOwnerBot(
        VALID_TEST_TOKEN,
        owner_chat_id=123,
        owner_request_retries=2,
        retry_base_seconds=0.25,
    )
    method = SendMessage(chat_id=456, text="customer reply")
    try:
        with pytest.raises(TelegramNetworkError, match="uncertain customer send"):
            await bot(method)
    finally:
        await bot.session.close()

    assert attempts == [method]
    assert sleeps == []
