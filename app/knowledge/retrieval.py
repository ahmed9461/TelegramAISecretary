from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import Visibility
from app.db.models import KnowledgeItem

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    id: int
    title: str
    content: str
    visibility: str
    score: float


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in _TOKEN_RE.findall(value) if len(token) >= 2}


def retrieve_knowledge(
    session: Session,
    *,
    owner_id: int,
    query: str,
    limit: int = 6,
    now: datetime | None = None,
) -> list[KnowledgeHit]:
    """Small-KB deterministic retriever.

    This intentionally keeps PostgreSQL as the source of truth and avoids a second vector
    database until the knowledge base is large enough to justify one. PRIVATE rows are never
    returned to the LLM. PUBLIC and INTERNAL rows may guide the model; INTERNAL is labelled so
    the model knows it must not disclose it verbatim.
    """
    now = now or datetime.now(timezone.utc)
    query_tokens = _tokens(query)
    if not query_tokens:
        return []

    rows = list(
        session.scalars(
            select(KnowledgeItem).where(
                KnowledgeItem.owner_id == owner_id,
                KnowledgeItem.status == "ACTIVE",
                KnowledgeItem.visibility.in_([Visibility.PUBLIC.value, Visibility.INTERNAL.value]),
            )
        )
    )

    scored: list[KnowledgeHit] = []
    for row in rows:
        if row.valid_from and row.valid_from > now:
            continue
        if row.valid_until and row.valid_until < now:
            continue
        title_tokens = _tokens(row.title)
        content_tokens = _tokens(row.content)
        overlap = len(query_tokens & content_tokens)
        title_overlap = len(query_tokens & title_tokens)
        if overlap == 0 and title_overlap == 0:
            continue
        # 0..1-ish deterministic score with a title match bonus.
        coverage = overlap / max(1, len(query_tokens))
        title_bonus = 0.25 * (title_overlap / max(1, len(query_tokens)))
        score = min(1.0, coverage + title_bonus)
        scored.append(
            KnowledgeHit(
                id=row.id,
                title=row.title,
                content=row.content,
                visibility=row.visibility,
                score=score,
            )
        )

    scored.sort(key=lambda item: (-item.score, item.id))
    return scored[: max(1, limit)]
