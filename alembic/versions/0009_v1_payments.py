"""V1 Telegram Stars payment orders.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-24
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return name in set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _has_table("payment_orders"):
        return
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_id", sa.String(length=40), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.Integer(), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("invoice_payload", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("provider_payment_charge_id", sa.String(length=255), nullable=True),
        sa.Column("success_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payment_order_amount_positive"),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("public_id", name="uq_payment_order_public_id"),
        sa.UniqueConstraint("invoice_payload", name="uq_payment_order_payload"),
        sa.UniqueConstraint(
            "telegram_payment_charge_id",
            name="uq_payment_order_telegram_charge",
        ),
    )
    op.create_index("ix_payment_orders_public_id", "payment_orders", ["public_id"])
    op.create_index("ix_payment_orders_owner_id", "payment_orders", ["owner_id"])
    op.create_index(
        "ix_payment_orders_conversation_id", "payment_orders", ["conversation_id"]
    )
    op.create_index("ix_payment_orders_contact_id", "payment_orders", ["contact_id"])
    op.create_index(
        "ix_payment_orders_telegram_user_id", "payment_orders", ["telegram_user_id"]
    )
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"])


def downgrade() -> None:
    if _has_table("payment_orders"):
        op.drop_table("payment_orders")
