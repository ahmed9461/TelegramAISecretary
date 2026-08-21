from pydantic import BaseModel, Field


class VisionObservation(BaseModel):
    """Grounded visual evidence extracted from an image.

    This object is deliberately descriptive, not conversational: the vision model
    observes the image, while the text model remains responsible for reasoning and
    drafting the final reply.
    """

    summary: str
    extracted_text: str = ""
    visible_elements: list[str] = Field(default_factory=list)
    relevant_details: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    detected_language: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
