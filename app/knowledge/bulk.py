from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import KnowledgeBatch, Owner
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


@dataclass(frozen=True, slots=True)
class BulkSaveResult:
    batch_id: int
    item_ids: tuple[int, ...]
    duplicate_of_batch_id: int | None = None


def source_content_hash(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class KnowledgeExtractor(Protocol):
    async def extract_knowledge(self, *, text: str, max_items: int = 60) -> list[dict]: ...


def normalize_candidates(
    raw_items: list[dict], *, max_items: int = 120
) -> list[KnowledgeCandidate]:
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
        collected.extend(
            await extractor.extract_knowledge(text=chunk, max_items=min(60, remaining))
        )
    return normalize_candidates(collected, max_items=max_items)


def save_bulk_candidates(
    session: Session,
    *,
    owner: Owner,
    candidates: list[KnowledgeCandidate],
    visibility: str,
    source: str = "OWNER_BULK_IMPORT",
    source_hash: str,
    source_name: str,
) -> BulkSaveResult:
    existing = session.scalar(
        select(KnowledgeBatch).where(
            KnowledgeBatch.owner_id == owner.id,
            KnowledgeBatch.content_hash == source_hash,
            KnowledgeBatch.status == "ACTIVE",
        )
    )
    if existing is not None:
        return BulkSaveResult(
            batch_id=existing.id,
            item_ids=(),
            duplicate_of_batch_id=existing.id,
        )

    batch = KnowledgeBatch(
        owner_id=owner.id,
        source_name=source_name[:255],
        source_kind="OWNER_BULK",
        visibility=visibility,
        content_hash=source_hash,
        item_count=len(candidates),
        status="ACTIVE",
        metadata_json={},
    )
    session.add(batch)
    session.flush()
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
            batch_id=batch.id,
        )
        ids.append(row.id)
    session.flush()
    return BulkSaveResult(batch_id=batch.id, item_ids=tuple(ids))
