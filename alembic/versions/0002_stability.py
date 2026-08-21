"""approval lifecycle and message edit/delete metadata

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-21

The initial project migration uses Base.metadata.create_all(), so a brand-new database may
already contain columns introduced by newer model code. This migration is intentionally
idempotent at the column level so both upgrade paths are safe:
- existing M3 database: add the missing M4 columns;
- fresh M4 database: 0001 creates current metadata, 0002 detects the columns and no-ops.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table)}


def _add_if_missing(table: str, column: sa.Column) -> None:
    if column.name not in _column_names(table):
        op.add_column(table, column)


def _drop_if_present(table: str, column_name: str) -> None:
    if column_name in _column_names(table):
        op.drop_column(table, column_name)


def upgrade() -> None:
    _add_if_missing("messages", sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True))
    _add_if_missing("messages", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    _add_if_missing("approvals", sa.Column("owner_chat_id", sa.BigInteger(), nullable=True))
    _add_if_missing("approvals", sa.Column("owner_message_id", sa.BigInteger(), nullable=True))
    _add_if_missing("approvals", sa.Column("sent_telegram_message_id", sa.BigInteger(), nullable=True))
    _add_if_missing("approvals", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    _drop_if_present("approvals", "expires_at")
    _drop_if_present("approvals", "sent_telegram_message_id")
    _drop_if_present("approvals", "owner_message_id")
    _drop_if_present("approvals", "owner_chat_id")
    _drop_if_present("messages", "deleted_at")
    _drop_if_present("messages", "edited_at")
