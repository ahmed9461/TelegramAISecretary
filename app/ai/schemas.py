from pydantic import BaseModel, Field

from app.db.enums import DecisionAction, RiskLevel


class Confidence(BaseModel):
    intent: float = Field(ge=0, le=1)
    retrieval: float = Field(ge=0, le=1)
    answer: float = Field(ge=0, le=1)
    policy: float = Field(ge=0, le=1)


class Decision(BaseModel):
    intent: str
    risk: RiskLevel
    action: DecisionAction
    confidence: Confidence
    needs_owner: bool = False
    needs_more_info: bool = False
    allowed_to_answer: bool = True
    reason_code: str
    knowledge_ids: list[str] = []
    reply_constraints: list[str] = []
