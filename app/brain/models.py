from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class BusinessProfile(Base):
    """Owner-controlled identity/configuration for the secretary.

    The core fields cover common identity needs while ``extras_json`` keeps the profile
    extensible without tying the project to one industry or requiring a migration for every
    future business-specific attribute.
    """

    __tablename__ = "business_profiles"
    __table_args__ = (UniqueConstraint("owner_id", name="uq_business_profile_owner"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("owners.id", ondelete="CASCADE"),
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(255), default="")
    activity_description: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(255), default="")
    reply_style: Mapped[str] = mapped_column(String(255), default="احترافي وودود")
    language: Mapped[str] = mapped_column(String(64), default="AUTO")
    tone: Mapped[str] = mapped_column(String(128), default="ودود")
    custom_instructions: Mapped[str] = mapped_column(Text, default="")
    extras_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ContactMemory(Base):
    """Isolated memory for exactly one contact.

    ``private_notes`` is owner-only and must never be put in the LLM context. The other fields
    are included only when ``share_with_ai`` is true and the Contact itself allows memory.
    JSON fields intentionally keep memory flexible as use cases change.
    """

    __tablename__ = "contact_memories"
    __table_args__ = (UniqueConstraint("contact_id", name="uq_contact_memory_contact"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("owners.id", ondelete="CASCADE"),
        index=True,
    )
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"),
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, default="")
    facts_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    private_notes: Mapped[str] = mapped_column(Text, default="")
    share_with_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    provenance_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class MemorySuggestion(Base):
    """A reviewable proposal; it never mutates ContactMemory until explicit approval."""

    __tablename__ = "memory_suggestions"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    source_message_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    facts_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences_json: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    rationale: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResponsePolicy(Base):
    """Configurable owner rule, independent from a specific business vertical."""

    __tablename__ = "response_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("owners.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str] = mapped_column(String(64), default="GLOBAL")
    action: Mapped[str] = mapped_column(String(64), default="REQUIRE_APPROVAL")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    conditions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
