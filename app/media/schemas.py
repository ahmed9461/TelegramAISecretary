from pydantic import BaseModel, Field


class MediaObservation(BaseModel):
    """Grounded extraction from contact-provided audio or a document."""

    summary: str = Field(max_length=2000)
    transcript: str = Field(default="", max_length=6000)
    extracted_text: str = Field(default="", max_length=6000)
    uncertainty: list[str] = Field(default_factory=list, max_length=20)
    detected_language: str | None = Field(default=None, max_length=64)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
