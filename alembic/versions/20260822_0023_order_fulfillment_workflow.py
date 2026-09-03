"""Add order delivery stages and fulfillment checklist.

Revision ID: 20260822_0023
Revises: 20260816_0022
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260822_0023"
down_revision: str | None = "20260816_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'AWAITING_DELIVERY'")
            op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'DELIVERED_TO_VENUE'")

    op.add_column(
        "order_items",
        sa.Column("is_picked", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "order_items",
        sa.Column("picked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        UPDATE orders AS order_row
        SET status = 'AWAITING_DELIVERY'
        WHERE order_row.status = 'RESERVED'
          AND EXISTS (
              SELECT 1
              FROM order_items AS item
              WHERE item.order_id = order_row.id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM order_items AS item
              WHERE item.order_id = order_row.id
                AND item.warehouse_id IS NULL
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE orders
        SET status = 'RESERVED'
        WHERE status IN ('AWAITING_DELIVERY', 'DELIVERED_TO_VENUE')
        """
    )
    op.drop_column("order_items", "picked_at")
    op.drop_column("order_items", "is_picked")
