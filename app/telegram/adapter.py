from __future__ import annotations

from io import BytesIO

from aiogram import Bot
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from app.config import get_settings
from app.db.models import Message
from app.db.repositories import ConversationRepository, OwnerRepository
from app.db.session import SessionLocal
from app.interface.service import load_menu_definition
from app.telegram.keyboards import to_aiogram_inline_keyboard
from app.telegram.rich_message import render_input_rich_message
from app.telegram.rich_text import render_native_rich


class AiogramTelegramAdapter:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    @staticmethod
    def _default_reply_markup(*, chat_id: int, reply_text: str, intent: str = ""):
        settings = get_settings()
        with SessionLocal() as session:
            owner = OwnerRepository.get_or_create(session, settings.owner_telegram_id)
            conversation = ConversationRepository.get_by_chat(
                session,
                owner_id=owner.id,
                chat_id=chat_id,
            )
            latest_user_text = ""
            if conversation is not None:
                latest = session.scalar(
                    select(Message)
                    .where(
                        Message.conversation_id == conversation.id,
                        Message.direction == "IN",
                        Message.is_deleted.is_(False),
                    )
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(1)
                )
                if latest is not None:
                    latest_user_text = latest.text or ""

            menu = load_menu_definition(
                session,
                owner_id=owner.id,
                context={
                    "user_text": latest_user_text,
                    "reply_text": reply_text,
                    "text": f"{latest_user_text}\n{reply_text}",
                    "intent": intent,
                },
            )
            session.commit()
        return to_aiogram_inline_keyboard(menu) if menu is not None else None

    async def send_text(
        self,
        *,
        business_connection_id: str,
        chat_id: int,
        text: str,
        reply_markup=None,
        attach_default_menu: bool = True,
        native_rich: bool = True,
        intent: str = "",
        feedback_approval_id: int | None = None,
    ) -> int:
        if reply_markup is None and attach_default_menu:
            reply_markup = self._default_reply_markup(
                chat_id=chat_id,
                reply_text=text,
                intent=intent,
            )
        if feedback_approval_id is not None:
            from app.telegram.feedback_ui import append_feedback_row

            reply_markup = append_feedback_row(
                reply_markup,
                approval_id=feedback_approval_id,
            )
        rendered = render_native_rich(text) if native_rich else None
        rich_message = render_input_rich_message(text) if native_rich else None
        if rich_message is not None:
            try:
                message = await self.bot.send_rich_message(
                    chat_id=chat_id,
                    rich_message=rich_message,
                    business_connection_id=business_connection_id,
                    reply_markup=reply_markup,
                )
                return message.message_id
            except TelegramBadRequest:
                # Telegram confirmed rejection, so a plain-message fallback cannot duplicate a
                # successfully accepted rich message. Network/timeout errors intentionally escape.
                pass
        message = await self.bot.send_message(
            chat_id=chat_id,
            text=rendered.text if rendered is not None else text,
            business_connection_id=business_connection_id,
            reply_markup=reply_markup,
            entities=list(rendered.entities) if rendered and rendered.entities else None,
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
