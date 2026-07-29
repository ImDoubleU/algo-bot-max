"""student carts

Revision ID: 20260729_0007
Revises: 20260728_0006
Create Date: 2026-07-29
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260729_0007"
down_revision: str | None = "20260728_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "student_cart_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0",
            name=op.f("ck_student_cart_items_student_cart_item_quantity_positive"),
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["updated_by_account_id"], ["max_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "student_id",
            "product_id",
            name="uq_student_cart_items_tenant_student_product",
        ),
    )
    for column in ("tenant_id", "student_id", "product_id", "updated_by_account_id"):
        op.create_index(
            op.f(f"ix_student_cart_items_{column}"),
            "student_cart_items",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("updated_by_account_id", "product_id", "student_id", "tenant_id"):
        op.drop_index(
            op.f(f"ix_student_cart_items_{column}"),
            table_name="student_cart_items",
        )
    op.drop_table("student_cart_items")
