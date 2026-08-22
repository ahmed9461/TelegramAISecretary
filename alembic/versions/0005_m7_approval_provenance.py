"""Persist approval provenance snapshots.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def _columns(name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}


def upgrade() -> None:
    if "context_json" not in _columns("approvals"):
        op.add_column(
            "approvals",
            sa.Column("context_json", sa.JSON(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    if "context_json" in _columns("approvals"):
        op.drop_column("approvals", "context_json")
