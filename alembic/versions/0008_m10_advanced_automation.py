"""M10 advanced automation.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def _columns(name: str) -> set[str]:
    if not _has_table(name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}


def upgrade() -> None:
    if "definition_json" not in _columns("flow_sessions"):
        op.add_column(
            "flow_sessions",
            sa.Column("definition_json", sa.JSON(), nullable=False, server_default="{}"),
        )

    if not _has_table("schedules"):
        op.create_table(
            "schedules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("type", sa.String(length=32), nullable=False),
            sa.Column("timezone", sa.String(length=64), nullable=False),
            sa.Column("config_json", sa.JSON(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_schedules_owner_id", "schedules", ["owner_id"])


def downgrade() -> None:
    if _has_table("schedules"):
        op.drop_table("schedules")
    if "definition_json" in _columns("flow_sessions"):
        op.drop_column("flow_sessions", "definition_json")
