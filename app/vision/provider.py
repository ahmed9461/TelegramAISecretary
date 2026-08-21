from typing import Protocol

from app.vision.schemas import VisionObservation


class VisionProvider(Protocol):
    async def analyze_image(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        user_text: str | None = None,
    ) -> VisionObservation: ...
