from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import Visibility
from app.db.models import KnowledgeItem

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)
_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_ARABIC_TRANSLATION = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي"})
_STOPWORDS = {
    "في",
    "من",
    "على",
    "الى",
    "عن",
    "هل",
    "ما",
    "ماذا",
    "كيف",
    "هو",
    "هي",
    "هذا",
    "هذه",
    "the",
    "a",
    "an",
    "is",
    "are",
    "of",
    "to",
}
_TYPE_HINTS = {
    "PRICE": {"سعر", "اسعار", "تكلفه", "رسوم", "price", "cost"},
    "POLICY": {"سياسه", "شروط", "استرجاع", "الغاء", "policy", "terms", "refund"},
    "FAQ": {"سوال", "اسئله", "faq"},
    "SERVICE": {"خدمه", "خدمات", "service", "services"},
    "PRODUCT": {"منتج", "منتجات", "product", "products"},
}
_CONCEPT_STEMS = {
    "PRESALES": {
        "اشتراك",
        "اشترك",
        "مشترك",
        "باقه",
        "باقات",
        "خطه",
        "خطط",
        "خيار",
        "خيارات",
        "ابدا",
        "ابدأ",
        "join",
        "subscribe",
        "plan",
        "package",
    },
    "ONBOARDING": {
        "تشغيل",
        "اشغل",
        "تفعيل",
        "فعلت",
        "تهيئه",
        "اعداد",
        "اربط",
        "ربط",
        "setup",
        "activate",
        "configure",
    },
    "SUPPORT": {
        "مشكله",
        "عطل",
        "تعذر",
        "دخول",
        "ادخل",
        "خطا",
        "دعم",
        "broken",
        "issue",
        "support",
        "login",
    },
    "REFUND": {"استرجاع", "استرداد", "الغاء", "refund", "cancel"},
    "PAYMENT": {"دفع", "سداد", "تحويل", "payment", "pay"},
    "PRICING": {"سعر", "اسعار", "تكلفه", "رسوم", "price", "cost"},
}
_NEGATION_STEMS = {"مو", "غير", "ليس", "لست", "ما", "not", "isnt", "isn't"}
_CONCEPT_TYPE_BONUS = {
    "PRESALES": {"PRICE": 0.2, "PRODUCT": 0.16, "SERVICE": 0.12, "FAQ": 0.08},
    "ONBOARDING": {"FAQ": 0.16, "SERVICE": 0.12, "PRODUCT": 0.08},
    "SUPPORT": {"FAQ": 0.16, "SERVICE": 0.1, "POLICY": 0.05},
    "REFUND": {"POLICY": 0.18, "FAQ": 0.08},
    "PAYMENT": {"FAQ": 0.16, "POLICY": 0.1},
    "PRICING": {"PRICE": 0.2, "PRODUCT": 0.1, "SERVICE": 0.08},
}


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    id: int
    type: str
    title: str
    content: str
    visibility: str
    score: float
    source: str | None = None
    tags: tuple[str, ...] = ()
    version: int = 1
    valid_until: datetime | None = None
    conflict_ids: tuple[int, ...] = ()

    @property
    def has_conflict(self) -> bool:
        return bool(self.conflict_ids)


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().translate(_ARABIC_TRANSLATION)
    normalized = _ARABIC_DIACRITICS_RE.sub("", normalized)
    return " ".join(normalized.split())


def _tokens(value: str) -> set[str]:
    normalized = normalize_search_text(value)
    tokens = {
        token
        for token in _TOKEN_RE.findall(normalized)
        if len(token) >= 2 and token not in _STOPWORDS
    }
    tokens.update(token[2:] for token in tuple(tokens) if token.startswith("ال") and len(token) > 4)
    tokens.update(token[1:] for token in tuple(tokens) if token.startswith("و") and len(token) > 4)
    return tokens


def _matches_stem(tokens: set[str], stems: set[str]) -> bool:
    return any(
        token.startswith(stem) or stem.startswith(token) for token in tokens for stem in stems
    )


def infer_retrieval_intents(value: str) -> frozenset[str]:
    """Infer a small generic lifecycle facet set for deterministic retrieval reranking."""
    tokens = _tokens(value)
    concepts = {
        concept for concept, stems in _CONCEPT_STEMS.items() if _matches_stem(tokens, stems)
    }
    has_onboarding = "ONBOARDING" in concepts
    has_subscription_language = _matches_stem(tokens, _CONCEPT_STEMS["PRESALES"])
    has_negation = _matches_stem(tokens, _NEGATION_STEMS)
    if has_onboarding:
        concepts.discard("PRESALES")
    elif has_subscription_language or (has_negation and "مشترك" in " ".join(tokens)):
        concepts.add("PRESALES")
    if "رد" in tokens and _matches_stem(tokens, {"مبلغ", "فلوس", "money"}):
        concepts.add("REFUND")
    return frozenset(concepts)


def _row_concepts(row: KnowledgeItem, tokens: set[str]) -> frozenset[str]:
    concepts = {
        concept for concept, stems in _CONCEPT_STEMS.items() if _matches_stem(tokens, stems)
    }
    row_type = row.type.upper()
    if row_type == "PRICE":
        concepts.update({"PRICING", "PRESALES"})
    if "ONBOARDING" in concepts:
        concepts.discard("PRESALES")
    return frozenset(concepts)


def _active_at(row: KnowledgeItem, now: datetime) -> bool:
    valid_from = row.valid_from
    valid_until = row.valid_until
    if valid_from is not None and valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=UTC)
    if valid_until is not None and valid_until.tzinfo is None:
        valid_until = valid_until.replace(tzinfo=UTC)
    return not ((valid_from and valid_from > now) or (valid_until and valid_until < now))


def _conflict_map(rows: list[KnowledgeItem]) -> dict[int, tuple[int, ...]]:
    groups: dict[tuple[str, str], list[KnowledgeItem]] = defaultdict(list)
    for row in rows:
        groups[(row.type.upper(), normalize_search_text(row.title))].append(row)
    conflicts: dict[int, tuple[int, ...]] = {}
    for group in groups.values():
        contents = {normalize_search_text(row.content) for row in group}
        if len(group) < 2 or len(contents) < 2:
            continue
        ids = tuple(sorted(row.id for row in group))
        for row in group:
            conflicts[row.id] = tuple(item_id for item_id in ids if item_id != row.id)
    return conflicts


def retrieve_knowledge(
    session: Session,
    *,
    owner_id: int,
    query: str,
    limit: int = 6,
    now: datetime | None = None,
) -> list[KnowledgeHit]:
    """Deterministic Arabic/English retrieval with provenance and conflict signals."""
    now = now or datetime.now(UTC)
    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    rows = [
        row
        for row in session.scalars(
            select(KnowledgeItem).where(
                KnowledgeItem.owner_id == owner_id,
                KnowledgeItem.status == "ACTIVE",
                KnowledgeItem.visibility.in_([Visibility.PUBLIC.value, Visibility.INTERNAL.value]),
            )
        )
        if _active_at(row, now)
    ]
    if not rows:
        return []

    row_tokens: dict[int, set[str]] = {}
    document_frequency: Counter[str] = Counter()
    for row in rows:
        tokens = _tokens(f"{row.title} {row.content} {' '.join(row.tags_json or [])}")
        row_tokens[row.id] = tokens
        document_frequency.update(tokens)
    query_weights = {
        token: math.log((len(rows) + 1) / (document_frequency.get(token, 0) + 1)) + 1.0
        for token in query_tokens
    }
    total_query_weight = sum(query_weights.values()) or 1.0
    normalized_query = normalize_search_text(query)
    query_concepts = infer_retrieval_intents(query)
    hinted_types = {
        item_type for item_type, hints in _TYPE_HINTS.items() if query_tokens.intersection(hints)
    }
    conflicts = _conflict_map(rows)

    scored: list[KnowledgeHit] = []
    for row in rows:
        title_tokens = _tokens(row.title)
        tag_tokens = _tokens(" ".join(row.tags_json or []))
        all_overlap = query_tokens.intersection(row_tokens[row.id])
        row_concepts = _row_concepts(row, row_tokens[row.id])
        shared_concepts = query_concepts.intersection(row_concepts)
        if not all_overlap and not shared_concepts:
            continue
        weighted_overlap = sum(query_weights[token] for token in all_overlap) / total_query_weight
        title_overlap = (
            sum(query_weights[token] for token in query_tokens.intersection(title_tokens))
            / total_query_weight
        )
        tag_overlap = (
            sum(query_weights[token] for token in query_tokens.intersection(tag_tokens))
            / total_query_weight
        )
        phrase_bonus = (
            0.12 if normalized_query in normalize_search_text(f"{row.title} {row.content}") else 0.0
        )
        type_bonus = 0.08 if row.type.upper() in hinted_types else 0.0
        semantic_bonus = 0.0
        for concept in shared_concepts:
            semantic_bonus = max(
                semantic_bonus,
                0.45 + _CONCEPT_TYPE_BONUS.get(concept, {}).get(row.type.upper(), 0.0),
            )
        score = min(
            1.0,
            (0.58 * weighted_overlap)
            + (0.28 * title_overlap)
            + (0.1 * tag_overlap)
            + phrase_bonus
            + type_bonus
            + semantic_bonus,
        )
        scored.append(
            KnowledgeHit(
                id=row.id,
                type=row.type,
                title=row.title,
                content=row.content,
                visibility=row.visibility,
                score=score,
                source=row.source,
                tags=tuple(str(tag) for tag in (row.tags_json or [])),
                version=max(1, row.version or 1),
                valid_until=row.valid_until,
                conflict_ids=conflicts.get(row.id, ()),
            )
        )

    scored.sort(key=lambda item: (-item.score, item.has_conflict, item.id))
    return scored[: max(1, limit)]
