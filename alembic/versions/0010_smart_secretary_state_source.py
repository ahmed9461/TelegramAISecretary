"""Track inherited versus explicit conversation state.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-24
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    if table not in set(sa.inspect(op.get_bind()).get_table_names()):
        return False
    return column in {item["name"] for item in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("conversations", "state_is_explicit"):
        op.add_column(
            "conversations",
            sa.Column(
                "state_is_explicit",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.execute(
            sa.text(
                """
                UPDATE conversations
                SET state_is_explicit = TRUE
                WHERE state NOT IN ('AI_AUTO', 'AI_APPROVAL')
                   OR EXISTS (
                        SELECT 1
                        FROM audit_logs
                        WHERE audit_logs.entity_type = 'CONVERSATION'
                          AND audit_logs.entity_id = CAST(conversations.id AS VARCHAR)
                          AND audit_logs.action = 'CONVERSATION_STATE_CHANGED'
                   )
                """
            )
        )
    if not _has_column("ai_runs", "decision_context_json"):
        op.add_column(
            "ai_runs",
            sa.Column(
                "decision_context_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
        )


def downgrade() -> None:
    if _has_column("ai_runs", "decision_context_json"):
        op.drop_column("ai_runs", "decision_context_json")
    if _has_column("conversations", "state_is_explicit"):
        op.drop_column("conversations", "state_is_explicit")
