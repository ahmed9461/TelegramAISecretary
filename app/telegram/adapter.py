from __future__ import annotations

from io import BytesIO

from aiogram import Bot
from aiogram.enums import ChatAction


class AiogramTelegramAdapter:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send_text(
        self,
        *,
        business_connection_id: str,
        chat_id: int,
        text: str,
        reply_markup=None,
    ) -> int:
        message = await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            business_connection_id=business_connection_id,
            reply_markup=reply_markup,
        )
        return message.message_id

    async def send_typing(self, *, business_connection_id: str, chat_id: int) -> None:
        await self.bot.send_chat_action(
            chat_id=chat_id,
            action=ChatAction.TYPING,
            business_connection_id=business_connection_id,
        )

    async def download_file_bytes(self, *, file_id: str, max_bytes: int) -> bytes:
        file = await self.bot.get_file(file_id)
        if not file.file_path:
            raise ValueError("Telegram returned no file_path")
        destination = BytesIO()
        await self.bot.download_file(file.file_path, destination=destination)
        data = destination.getvalue()
        if len(data) > max_bytes:
            raise ValueError(f"Telegram media exceeds configured limit ({max_bytes} bytes)")
        return data
