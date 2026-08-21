from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IncomingBusinessMessage:
    business_connection_id: str
    chat_id: int
    message_id: int
    sender_user_id: int | None
    sender_name: str
    text: str | None
    content_type: str = "TEXT"
    reply_to_message_id: int | None = None
    metadata: dict = field(default_factory=dict)


class MessagingAdapter(Protocol):
    async def send_text(
        self,
        *,
        business_connection_id: str,
        chat_id: int,
        text: str,
        reply_markup: object | None = None,
    ) -> int: ...

    async def send_typing(self, *, business_connection_id: str, chat_id: int) -> None: ...
