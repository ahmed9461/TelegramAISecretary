import pytest
from aiogram.exceptions import TelegramBadRequest

from app.telegram.callback_safety import is_expired_callback_error, safe_callback_answer


class FakeCallback:
    id = "callback-1"
    data = "knowledge:content:1"

    async def answer(self, text=None, show_alert=False):
        raise TelegramBadRequest(
            method=None,
            message="Bad Request: query is too old and response timeout expired or query ID is invalid",
        )


def test_expired_callback_error_is_detected() -> None:
    error = TelegramBadRequest(
        method=None,
        message="Bad Request: query is too old and response timeout expired or query ID is invalid",
    )
    assert is_expired_callback_error(error) is True


@pytest.mark.asyncio
async def test_expired_callback_is_ignored() -> None:
    callback = FakeCallback()
    assert await safe_callback_answer(callback) is False
