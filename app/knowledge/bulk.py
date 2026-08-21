from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.db.models import Owner
from app.knowledge.admin import add_knowledge

_ALLOWED_TYPES = {
    "GENERAL",
    "SERVICE",
    "PRODUCT",
    "PRICE",
    "FAQ",
    "POLICY",
    "CUSTOM",
}


@dataclass(frozen=True, slots=True)
class KnowledgeCandidate:
    type: str
    title: str
    content: str
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tags"] = list(self.tags)
        return data


class KnowledgeExtractor(Protocol):
    async def extract_knowledge(self, *, text: str, max_items: int = 60) -> list[dict]: ...


def normalize_candidates(raw_items: list[dict], *, max_items: int = 120) -> list[KnowledgeCandidate]:
    """Normalize model output and aggressively reject empty/invented-looking shells.

    The extractor may return imperfect JSON. This layer keeps only self-contained records
    with both a title and source-backed content, normalizes the type, limits tag sizes, and
    deduplicates exact semantic duplicates before anything reaches the database.
    """

    normalized: list[KnowledgeCandidate] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        if not title or not content:
            continue
        item_type = str(item.get("type") or "GENERAL").strip().upper()
        if item_type not in _ALLOWED_TYPES:
            item_type = "CUSTOM"
        key = (title.casefold(), content.casefold())
        if key in seen:
            continue
        seen.add(key)
        tags_raw = item.get("tags") or []
        tags: list[str] = []
        if isinstance(tags_raw, list):
            for tag in tags_raw[:8]:
                clean = str(tag).strip()
                if clean and clean not in tags:
                    tags.append(clean[:64])
        normalized.append(
            KnowledgeCandidate(
                type=item_type,
                title=title[:255],
                content=content,
                tags=tuple(tags),
            )
        )
        if len(normalized) >= max(1, max_items):
            break
    return normalized


def _chunk_text(text: str, *, chunk_chars: int = 24000) -> list[str]:
    clean = text.strip()
    if not clean:
        return []
    if len(clean) <= chunk_chars:
        return [clean]

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for paragraph in clean.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        addition = len(paragraph) + (2 if current else 0)
        if current and current_size + addition > chunk_chars:
            chunks.append("\n\n".join(current))
            current = []
            current_size = 0
        if len(paragraph) > chunk_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_size = 0
            for start in range(0, len(paragraph), chunk_chars):
                chunks.append(paragraph[start : start + chunk_chars])
            continue
        current.append(paragraph)
        current_size += addition
    if current:
        chunks.append("\n\n".join(current))
    return chunks


async def extract_bulk_candidates(
    extractor: KnowledgeExtractor,
    *,
    text: str,
    max_items: int = 120,
) -> list[KnowledgeCandidate]:
    collected: list[dict] = []
    for chunk in _chunk_text(text):
        remaining = max_items - len(collected)
        if remaining <= 0:
            break
        collected.extend(await extractor.extract_knowledge(text=chunk, max_items=min(60, remaining)))
    return normalize_candidates(collected, max_items=max_items)


def save_bulk_candidates(
    session: Session,
    *,
    owner: Owner,
    candidates: list[KnowledgeCandidate],
    visibility: str,
    source: str = "OWNER_BULK_IMPORT",
) -> list[int]:
    ids: list[int] = []
    for candidate in candidates:
        row = add_knowledge(
            session,
            owner=owner,
            visibility=visibility,
            title=candidate.title,
            content=candidate.content,
            item_type=candidate.type,
            tags=list(candidate.tags),
            source=source,
        )
        ids.append(row.id)
    session.flush()
    return ids
