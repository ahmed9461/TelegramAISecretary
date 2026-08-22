"""secretary brain foundation

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-21

Adds flexible owner identity, isolated per-contact memory, and configurable response policies.
Knowledge remains in the existing knowledge_items table so business domains can change without
schema changes.
"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if not _has_table("business_profiles"):
        op.create_table(
            "business_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("display_name", sa.String(length=255), nullable=False),
            sa.Column("activity_description", sa.Text(), nullable=False),
            sa.Column("industry", sa.String(length=255), nullable=False),
            sa.Column("reply_style", sa.String(length=255), nullable=False),
            sa.Column("language", sa.String(length=64), nullable=False),
            sa.Column("tone", sa.String(length=128), nullable=False),
            sa.Column("custom_instructions", sa.Text(), nullable=False),
            sa.Column("extras_json", sa.JSON(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("owner_id", name="uq_business_profile_owner"),
        )
        op.create_index("ix_business_profiles_owner_id", "business_profiles", ["owner_id"])

    if not _has_table("contact_memories"):
        op.create_table(
            "contact_memories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("contact_id", sa.Integer(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("facts_json", sa.JSON(), nullable=False),
            sa.Column("preferences_json", sa.JSON(), nullable=False),
            sa.Column("private_notes", sa.Text(), nullable=False),
            sa.Column("share_with_ai", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("contact_id", name="uq_contact_memory_contact"),
        )
        op.create_index("ix_contact_memories_owner_id", "contact_memories", ["owner_id"])
        op.create_index("ix_contact_memories_contact_id", "contact_memories", ["contact_id"])

    if not _has_table("response_policies"):
        op.create_table(
            "response_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("scope", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("conditions_json", sa.JSON(), nullable=False),
            sa.Column("constraints_json", sa.JSON(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_response_policies_owner_id", "response_policies", ["owner_id"])


def downgrade() -> None:
    if _has_table("response_policies"):
        op.drop_table("response_policies")
    if _has_table("contact_memories"):
        op.drop_table("contact_memories")
    if _has_table("business_profiles"):
        op.drop_table("business_profiles")
