"""digital product codes

Revision ID: 20260812_0016
Revises: 20260811_0015
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260812_0016"
down_revision: str | None = "20260811_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

product_fulfillment_type = postgresql.ENUM(
    "WAREHOUSE",
    "DIGITAL_CODE",
    name="productfulfillmenttype",
    create_type=False,
)
product_code_status = postgresql.ENUM(
    "AVAILABLE",
    "ISSUED",
    "DISABLED",
    name="productcodestatus",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    product_fulfillment_type.create(bind, checkfirst=True)
    product_code_status.create(bind, checkfirst=True)

    op.add_column(
        "products",
        sa.Column(
            "fulfillment_type",
            product_fulfillment_type,
            server_default="WAREHOUSE",
            nullable=False,
        ),
    )
    op.create_table(
        "product_codes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=500), nullable=False),
        sa.Column("status", product_code_status, nullable=False),
        sa.Column("order_item_id", sa.Uuid(), nullable=True),
        sa.Column("issued_to_student_id", sa.Uuid(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["issued_to_student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_product_codes_tenant_code",
        ),
    )
    op.create_index(op.f("ix_product_codes_tenant_id"), "product_codes", ["tenant_id"])
    op.create_index(op.f("ix_product_codes_product_id"), "product_codes", ["product_id"])
    op.create_index(op.f("ix_product_codes_status"), "product_codes", ["status"])
    op.create_index(op.f("ix_product_codes_order_item_id"), "product_codes", ["order_item_id"])
    op.create_index(
        op.f("ix_product_codes_issued_to_student_id"),
        "product_codes",
        ["issued_to_student_id"],
    )


def downgrade() -> None:
    op.drop_table("product_codes")
    op.drop_column("products", "fulfillment_type")
    bind = op.get_bind()
    product_code_status.drop(bind, checkfirst=True)
    product_fulfillment_type.drop(bind, checkfirst=True)
