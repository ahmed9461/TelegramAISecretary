"""M7 knowledge operations and versioning.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(name: str) -> set[str]:
    if not _has_table(name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}


def _foreign_key_for_column(table_name: str, column_name: str) -> str | None:
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name):
        if foreign_key.get("constrained_columns") == [column_name]:
            return foreign_key.get("name")
    return None


def upgrade() -> None:
    if not _has_table("knowledge_batches"):
        op.create_table(
            "knowledge_batches",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("source_name", sa.String(length=255), nullable=False),
            sa.Column("source_kind", sa.String(length=32), nullable=False),
            sa.Column("visibility", sa.String(length=16), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("item_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_knowledge_batches_owner_id", "knowledge_batches", ["owner_id"])
        op.create_index("ix_knowledge_batches_content_hash", "knowledge_batches", ["content_hash"])

    columns = _columns("knowledge_items")
    if "batch_id" not in columns:
        op.add_column("knowledge_items", sa.Column("batch_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_knowledge_items_batch_id",
            "knowledge_items",
            "knowledge_batches",
            ["batch_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_knowledge_items_batch_id", "knowledge_items", ["batch_id"])
    if "version" not in columns:
        op.add_column(
            "knowledge_items",
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
    if "supersedes_id" not in columns:
        op.add_column("knowledge_items", sa.Column("supersedes_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_knowledge_items_supersedes_id",
            "knowledge_items",
            "knowledge_items",
            ["supersedes_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "content_hash" not in columns:
        op.add_column(
            "knowledge_items", sa.Column("content_hash", sa.String(length=64), nullable=True)
        )
        op.create_index("ix_knowledge_items_content_hash", "knowledge_items", ["content_hash"])


def downgrade() -> None:
    columns = _columns("knowledge_items")
    if "content_hash" in columns:
        op.drop_index("ix_knowledge_items_content_hash", table_name="knowledge_items")
        op.drop_column("knowledge_items", "content_hash")
    if "supersedes_id" in columns:
        constraint_name = _foreign_key_for_column("knowledge_items", "supersedes_id")
        if constraint_name:
            op.drop_constraint(constraint_name, "knowledge_items", type_="foreignkey")
        op.drop_column("knowledge_items", "supersedes_id")
    if "version" in columns:
        op.drop_column("knowledge_items", "version")
    if "batch_id" in columns:
        op.drop_index("ix_knowledge_items_batch_id", table_name="knowledge_items")
        constraint_name = _foreign_key_for_column("knowledge_items", "batch_id")
        if constraint_name:
            op.drop_constraint(constraint_name, "knowledge_items", type_="foreignkey")
        op.drop_column("knowledge_items", "batch_id")
    if _has_table("knowledge_batches"):
        op.drop_index("ix_knowledge_batches_content_hash", table_name="knowledge_batches")
        op.drop_index("ix_knowledge_batches_owner_id", table_name="knowledge_batches")
        op.drop_table("knowledge_batches")
