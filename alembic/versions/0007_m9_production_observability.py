"""M9 production observability.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-22
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _has_table("ai_runs"):
        return
    op.create_table(
        "ai_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("trigger_message_id", sa.Integer(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("risk", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("confidence_json", sa.JSON(), nullable=False),
        sa.Column("knowledge_refs_json", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("token_usage_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["trigger_message_id"], ["messages.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_ai_runs_owner_id", "ai_runs", ["owner_id"])
    op.create_index("ix_ai_runs_conversation_id", "ai_runs", ["conversation_id"])
    op.create_index("ix_ai_runs_trace_id", "ai_runs", ["trace_id"])
    op.create_index("ix_ai_runs_operation", "ai_runs", ["operation"])
    op.create_index("ix_ai_runs_status", "ai_runs", ["status"])


def downgrade() -> None:
    if _has_table("ai_runs"):
        op.drop_table("ai_runs")
