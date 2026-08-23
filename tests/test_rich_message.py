from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendRichMessage

from app.telegram.adapter import AiogramTelegramAdapter
from app.telegram.rich_message import render_input_rich_message


class RichBot:
    def __init__(self, *, rich_error: Exception | None = None) -> None:
        self.rich_error = rich_error
        self.rich_calls: list[dict] = []
        self.plain_calls: list[dict] = []

    async def send_rich_message(self, **kwargs):
        self.rich_calls.append(kwargs)
        if self.rich_error is not None:
            raise self.rich_error
        return SimpleNamespace(message_id=41)

    async def send_message(self, **kwargs):
        self.plain_calls.append(kwargs)
        return SimpleNamespace(message_id=42)


def _structured_reply() -> str:
    return "الباقات المتاحة\n\n• الباقة الأساسية\n• الباقة الاحترافية"


def test_renderer_uses_native_heading_and_list_only_for_structured_reply() -> None:
    rich = render_input_rich_message(_structured_reply())
    assert rich is not None
    assert [block.type for block in rich.blocks or []] == ["heading", "list"]
    assert render_input_rich_message("كيف أقدر أساعدك؟") is None


@pytest.mark.asyncio
async def test_adapter_sends_rich_message_without_plain_duplicate(monkeypatch) -> None:
    bot = RichBot()
    adapter = AiogramTelegramAdapter(bot)  # type: ignore[arg-type]
    monkeypatch.setattr(adapter, "_default_reply_markup", lambda **kwargs: None)

    message_id = await adapter.send_text(
        business_connection_id="business",
        chat_id=100,
        text=_structured_reply(),
    )

    assert message_id == 41
    assert len(bot.rich_calls) == 1
    assert bot.plain_calls == []


@pytest.mark.asyncio
async def test_confirmed_rich_rejection_falls_back_once(monkeypatch) -> None:
    method = SendRichMessage(
        chat_id=100,
        rich_message=render_input_rich_message(_structured_reply()),
    )
    bot = RichBot(rich_error=TelegramBadRequest(method=method, message="rich unsupported"))
    adapter = AiogramTelegramAdapter(bot)  # type: ignore[arg-type]
    monkeypatch.setattr(adapter, "_default_reply_markup", lambda **kwargs: None)

    message_id = await adapter.send_text(
        business_connection_id="business",
        chat_id=100,
        text=_structured_reply(),
    )

    assert message_id == 42
    assert len(bot.rich_calls) == 1
    assert len(bot.plain_calls) == 1


@pytest.mark.asyncio
async def test_uncertain_rich_failure_never_sends_plain_duplicate(monkeypatch) -> None:
    bot = RichBot(rich_error=RuntimeError("uncertain transport failure"))
    adapter = AiogramTelegramAdapter(bot)  # type: ignore[arg-type]
    monkeypatch.setattr(adapter, "_default_reply_markup", lambda **kwargs: None)

    with pytest.raises(RuntimeError, match="uncertain transport"):
        await adapter.send_text(
            business_connection_id="business",
            chat_id=100,
            text=_structured_reply(),
        )

    assert len(bot.rich_calls) == 1
    assert bot.plain_calls == []
