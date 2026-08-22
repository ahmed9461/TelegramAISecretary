"""M8 memory intelligence and response feedback.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(name: str) -> set[str]:
    if not _has_table(name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}


def upgrade() -> None:
    memory_columns = _columns("contact_memories")
    if "provenance_json" not in memory_columns:
        op.add_column(
            "contact_memories",
            sa.Column("provenance_json", sa.JSON(), nullable=False, server_default="{}"),
        )
    if "confidence_json" not in memory_columns:
        op.add_column(
            "contact_memories",
            sa.Column("confidence_json", sa.JSON(), nullable=False, server_default="{}"),
        )
    if "retention_until" not in memory_columns:
        op.add_column(
            "contact_memories",
            sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        )
    if "last_reviewed_at" not in memory_columns:
        op.add_column(
            "contact_memories",
            sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not _has_table("memory_suggestions"):
        op.create_table(
            "memory_suggestions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("contact_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("source_message_ids_json", sa.JSON(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("facts_json", sa.JSON(), nullable=False),
            sa.Column("preferences_json", sa.JSON(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_memory_suggestions_owner_id", "memory_suggestions", ["owner_id"])
        op.create_index("ix_memory_suggestions_contact_id", "memory_suggestions", ["contact_id"])
        op.create_index(
            "ix_memory_suggestions_conversation_id",
            "memory_suggestions",
            ["conversation_id"],
        )

    if not _has_table("feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("contact_id", sa.Integer(), nullable=False),
            sa.Column("conversation_id", sa.Integer(), nullable=False),
            sa.Column("approval_id", sa.Integer(), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=32), nullable=False),
            sa.Column("category", sa.String(length=64), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("approval_id", name="uq_feedback_approval"),
        )
        op.create_index("ix_feedback_owner_id", "feedback", ["owner_id"])
        op.create_index("ix_feedback_contact_id", "feedback", ["contact_id"])
        op.create_index("ix_feedback_conversation_id", "feedback", ["conversation_id"])
        op.create_index("ix_feedback_approval_id", "feedback", ["approval_id"])


def downgrade() -> None:
    if _has_table("feedback"):
        op.drop_table("feedback")
    if _has_table("memory_suggestions"):
        op.drop_table("memory_suggestions")
    memory_columns = _columns("contact_memories")
    for column_name in (
        "last_reviewed_at",
        "retention_until",
        "confidence_json",
        "provenance_json",
    ):
        if column_name in memory_columns:
            op.drop_column("contact_memories", column_name)
