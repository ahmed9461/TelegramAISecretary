from typing import Protocol

from app.media.schemas import MediaObservation


class MediaProvider(Protocol):
    async def analyze_media(
        self,
        *,
        media_bytes: bytes,
        mime_type: str,
        media_kind: str,
        user_text: str | None = None,
    ) -> MediaObservation: ...
