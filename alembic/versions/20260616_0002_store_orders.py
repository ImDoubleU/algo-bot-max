"""store and orders

Revision ID: 20260616_0002
Revises: 20260616_0001
Create Date: 2026-06-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260616_0002"
down_revision: str | None = "20260616_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

product_status = sa.Enum("ACTIVE", "HIDDEN", "ARCHIVED", name="productstatus")
warehouse_type = sa.Enum("COMMON", "VENUE", "PARTNER", "EXTERNAL", name="warehousetype")
stock_movement_type = sa.Enum(
    "INITIAL",
    "ADJUSTMENT",
    "TRANSFER",
    "RESERVE",
    "RELEASE_RESERVE",
    "ISSUE",
    "RETURN",
    name="stockmovementtype",
)
order_status = sa.Enum(
    "CREATED",
    "RESERVED",
    "TRANSFERRED_TO_TEACHER",
    "ISSUED_TO_STUDENT",
    "CANCELLED",
    "RETURNED",
    "COINS_REFUNDED",
    "PROBLEM",
    name="orderstatus",
)


def upgrade() -> None:
    bind = op.get_bind()
    product_status.create(bind, checkfirst=True)
    warehouse_type.create(bind, checkfirst=True)
    stock_movement_type.create(bind, checkfirst=True)
    order_status.create(bind, checkfirst=True)

    op.create_table(
        "product_categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_product_categories_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_categories")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_product_categories_tenant_slug"),
    )
    op.create_index(
        op.f("ix_product_categories_tenant_id"), "product_categories", ["tenant_id"], unique=False
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=True),
        sa.Column("sku", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.String(length=500), nullable=True),
        sa.Column("price_astrocoins", sa.Integer(), nullable=False),
        sa.Column("status", product_status, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["product_categories.id"],
            name=op.f("fk_products_category_id_product_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_products_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),
    )
    op.create_index(op.f("ix_products_category_id"), "products", ["category_id"], unique=False)
    op.create_index(op.f("ix_products_tenant_id"), "products", ["tenant_id"], unique=False)

    op.create_table(
        "warehouses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=True),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("warehouse_type", warehouse_type, nullable=False),
        sa.Column("address", sa.String(length=260), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_warehouses_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["venue_id"], ["venues.id"], name=op.f("fk_warehouses_venue_id_venues")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouses")),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_warehouses_tenant_slug"),
    )
    op.create_index(op.f("ix_warehouses_tenant_id"), "warehouses", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_warehouses_venue_id"), "warehouses", ["venue_id"], unique=False)

    op.create_table(
        "warehouse_inventory",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False),
        sa.Column("issued_quantity", sa.Integer(), nullable=False),
        sa.Column("returned_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_warehouse_inventory_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_warehouse_inventory_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_warehouse_inventory_warehouse_id_warehouses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouse_inventory")),
        sa.UniqueConstraint(
            "tenant_id",
            "warehouse_id",
            "product_id",
            name="uq_warehouse_inventory_tenant_warehouse_product",
        ),
    )
    op.create_index(
        op.f("ix_warehouse_inventory_product_id"),
        "warehouse_inventory",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_warehouse_inventory_tenant_id"),
        "warehouse_inventory",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_warehouse_inventory_warehouse_id"),
        "warehouse_inventory",
        ["warehouse_id"],
        unique=False,
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("order_number", sa.Integer(), nullable=False),
        sa.Column("status", order_status, nullable=False),
        sa.Column("total_astrocoins", sa.Integer(), nullable=False),
        sa.Column("teacher_name", sa.String(length=160), nullable=True),
        sa.Column("venue_name", sa.String(length=160), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["created_by_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_orders_created_by_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"], name=op.f("fk_orders_student_id_students")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_orders_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint("tenant_id", "order_number", name="uq_orders_tenant_order_number"),
    )
    op.create_index(
        op.f("ix_orders_created_by_account_id"), "orders", ["created_by_account_id"], unique=False
    )
    op.create_index(op.f("ix_orders_student_id"), "orders", ["student_id"], unique=False)
    op.create_index(op.f("ix_orders_tenant_id"), "orders", ["tenant_id"], unique=False)

    op.create_table(
        "order_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("unit_price_astrocoins", sa.Integer(), nullable=False),
        sa.Column("total_price_astrocoins", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_order_items_order_id_orders")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_order_items_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_order_items_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_order_items_warehouse_id_warehouses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_items")),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"], unique=False)
    op.create_index(op.f("ix_order_items_product_id"), "order_items", ["product_id"], unique=False)
    op.create_index(op.f("ix_order_items_tenant_id"), "order_items", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_order_items_warehouse_id"),
        "order_items",
        ["warehouse_id"],
        unique=False,
    )

    op.create_table(
        "order_status_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("from_status", order_status, nullable=True),
        sa.Column("to_status", order_status, nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_order_status_history_actor_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_order_status_history_order_id_orders")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_order_status_history_tenant_id_tenants")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_history")),
    )
    op.create_index(
        op.f("ix_order_status_history_actor_account_id"),
        "order_status_history",
        ["actor_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_status_history_order_id"), "order_status_history", ["order_id"], unique=False
    )
    op.create_index(
        op.f("ix_order_status_history_tenant_id"),
        "order_status_history",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "stock_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("from_warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("to_warehouse_id", sa.Uuid(), nullable=True),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("movement_type", stock_movement_type, nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_stock_movements_actor_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["from_warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_stock_movements_from_warehouse_id_warehouses"),
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_stock_movements_order_id_orders")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_stock_movements_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name=op.f("fk_stock_movements_tenant_id_tenants")
        ),
        sa.ForeignKeyConstraint(
            ["to_warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_stock_movements_to_warehouse_id_warehouses"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_movements")),
    )
    op.create_index(
        op.f("ix_stock_movements_actor_account_id"),
        "stock_movements",
        ["actor_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_movements_from_warehouse_id"),
        "stock_movements",
        ["from_warehouse_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_movements_order_id"),
        "stock_movements",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stock_movements_product_id"), "stock_movements", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_stock_movements_tenant_id"), "stock_movements", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_stock_movements_to_warehouse_id"),
        "stock_movements",
        ["to_warehouse_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_movements_to_warehouse_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_tenant_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_product_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_order_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_from_warehouse_id"), table_name="stock_movements")
    op.drop_index(op.f("ix_stock_movements_actor_account_id"), table_name="stock_movements")
    op.drop_table("stock_movements")

    op.drop_index(op.f("ix_order_status_history_tenant_id"), table_name="order_status_history")
    op.drop_index(op.f("ix_order_status_history_order_id"), table_name="order_status_history")
    op.drop_index(
        op.f("ix_order_status_history_actor_account_id"), table_name="order_status_history"
    )
    op.drop_table("order_status_history")

    op.drop_index(op.f("ix_order_items_warehouse_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_tenant_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_product_id"), table_name="order_items")
    op.drop_index(op.f("ix_order_items_order_id"), table_name="order_items")
    op.drop_table("order_items")

    op.drop_index(op.f("ix_orders_tenant_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_student_id"), table_name="orders")
    op.drop_index(op.f("ix_orders_created_by_account_id"), table_name="orders")
    op.drop_table("orders")

    op.drop_index(op.f("ix_warehouse_inventory_warehouse_id"), table_name="warehouse_inventory")
    op.drop_index(op.f("ix_warehouse_inventory_tenant_id"), table_name="warehouse_inventory")
    op.drop_index(op.f("ix_warehouse_inventory_product_id"), table_name="warehouse_inventory")
    op.drop_table("warehouse_inventory")

    op.drop_index(op.f("ix_warehouses_venue_id"), table_name="warehouses")
    op.drop_index(op.f("ix_warehouses_tenant_id"), table_name="warehouses")
    op.drop_table("warehouses")

    op.drop_index(op.f("ix_products_tenant_id"), table_name="products")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_table("products")

    op.drop_index(op.f("ix_product_categories_tenant_id"), table_name="product_categories")
    op.drop_table("product_categories")

    bind = op.get_bind()
    order_status.drop(bind, checkfirst=True)
    stock_movement_type.drop(bind, checkfirst=True)
    warehouse_type.drop(bind, checkfirst=True)
    product_status.drop(bind, checkfirst=True)
