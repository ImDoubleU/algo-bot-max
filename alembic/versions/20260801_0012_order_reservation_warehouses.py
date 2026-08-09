"""order request idempotency and provisional reservation warehouses

Revision ID: 20260801_0012
Revises: 20260731_0011
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_0012"
down_revision: str | None = "20260731_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column("client_request_id", sa.String(length=80), nullable=True),
        )
        batch_op.create_index(
            op.f("ix_orders_client_request_id"),
            ["client_request_id"],
            unique=False,
        )
        batch_op.create_unique_constraint(
            "uq_orders_tenant_account_request",
            ["tenant_id", "created_by_account_id", "client_request_id"],
        )
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.add_column(
            sa.Column("reserved_warehouse_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_foreign_key(
            op.f("fk_order_items_reserved_warehouse_id_warehouses"),
            "warehouses",
            ["reserved_warehouse_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_order_items_reserved_warehouse_id"),
            ["reserved_warehouse_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("order_items") as batch_op:
        batch_op.drop_index(op.f("ix_order_items_reserved_warehouse_id"))
        batch_op.drop_constraint(
            op.f("fk_order_items_reserved_warehouse_id_warehouses"),
            type_="foreignkey",
        )
        batch_op.drop_column("reserved_warehouse_id")
    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint(
            "uq_orders_tenant_account_request",
            type_="unique",
        )
        batch_op.drop_index(op.f("ix_orders_client_request_id"))
        batch_op.drop_column("client_request_id")
