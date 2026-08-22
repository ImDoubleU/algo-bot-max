from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    OrderStatus,
    ProductCodeStatus,
    ProductFulfillmentType,
    ProductStatus,
    StockMovementType,
    WarehouseType,
)


class ProductCategory(TimestampMixin, Base):
    __tablename__ = "product_categories"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_product_categories_tenant_slug"),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    products = relationship("Product", back_populates="category")


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_products_tenant_sku"),)

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_categories.id"), index=True
    )
    sku: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    price_astrocoins: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ProductStatus] = mapped_column(default=ProductStatus.ACTIVE, nullable=False)
    fulfillment_type: Mapped[ProductFulfillmentType] = mapped_column(
        default=ProductFulfillmentType.WAREHOUSE,
        nullable=False,
    )
    digital_codes_low_notified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    category = relationship("ProductCategory", back_populates="products")
    inventory_items = relationship("WarehouseInventory", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")
    digital_codes = relationship(
        "ProductCode",
        back_populates="product",
        cascade="all, delete-orphan",
    )


class StudentCartItem(TimestampMixin, Base):
    __tablename__ = "student_cart_items"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "student_id",
            "product_id",
            name="uq_student_cart_items_tenant_student_product",
        ),
        CheckConstraint("quantity > 0", name="student_cart_item_quantity_positive"),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id"),
        index=True,
        nullable=False,
    )
    updated_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    product = relationship("Product")


class Warehouse(TimestampMixin, Base):
    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_warehouses_tenant_slug"),)

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    venue_id: Mapped[UUID | None] = mapped_column(ForeignKey("venues.id"), index=True)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    warehouse_type: Mapped[WarehouseType] = mapped_column(nullable=False)
    address: Mapped[str | None] = mapped_column(String(260))

    tenant = relationship("Tenant", back_populates="warehouses")
    venue = relationship("Venue", back_populates="warehouses")
    inventory_items = relationship("WarehouseInventory", back_populates="warehouse")


class WarehouseInventory(TimestampMixin, Base):
    __tablename__ = "warehouse_inventory"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "warehouse_id",
            "product_id",
            name="uq_warehouse_inventory_tenant_warehouse_product",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id"),
        index=True,
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id"),
        index=True,
        nullable=False,
    )
    available_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    issued_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    returned_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    warehouse = relationship("Warehouse", back_populates="inventory_items")
    product = relationship("Product", back_populates="inventory_items")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number", name="uq_orders_tenant_order_number"),
        UniqueConstraint(
            "tenant_id",
            "created_by_account_id",
            "client_request_id",
            name="uq_orders_tenant_account_request",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    created_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
    )
    order_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.CREATED, nullable=False)
    total_astrocoins: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_name: Mapped[str | None] = mapped_column(String(160))
    venue_name: Mapped[str | None] = mapped_column(String(160))
    comment: Mapped[str | None] = mapped_column(String(500))
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    client_request_id: Mapped[str | None] = mapped_column(String(80), index=True)

    items = relationship("OrderItem", back_populates="order")
    status_history = relationship("OrderStatusHistory", back_populates="order")


class OrderItem(TimestampMixin, Base):
    __tablename__ = "order_items"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id"), index=True)
    reserved_warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id"),
        index=True,
    )
    unit_price_astrocoins: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price_astrocoins: Mapped[int] = mapped_column(Integer, nullable=False)
    is_picked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    picked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    reserved_warehouse = relationship("Warehouse", foreign_keys=[reserved_warehouse_id])
    digital_codes = relationship("ProductCode", back_populates="order_item")


class ProductCode(TimestampMixin, Base):
    __tablename__ = "product_codes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_product_codes_tenant_code",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id"),
        index=True,
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ProductCodeStatus] = mapped_column(
        default=ProductCodeStatus.AVAILABLE,
        index=True,
        nullable=False,
    )
    order_item_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("order_items.id"),
        index=True,
    )
    issued_to_student_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("students.id"),
        index=True,
    )
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    product = relationship("Product", back_populates="digital_codes")
    order_item = relationship("OrderItem", back_populates="digital_codes")
    issued_to_student = relationship("Student")


class OrderStatusHistory(TimestampMixin, Base):
    __tablename__ = "order_status_history"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    actor_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("max_accounts.id"), index=True)
    from_status: Mapped[OrderStatus | None] = mapped_column()
    to_status: Mapped[OrderStatus] = mapped_column(nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))

    order = relationship("Order", back_populates="status_history")


class StockMovement(TimestampMixin, Base):
    __tablename__ = "stock_movements"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), index=True, nullable=False)
    from_warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id"), index=True)
    to_warehouse_id: Mapped[UUID | None] = mapped_column(ForeignKey("warehouses.id"), index=True)
    order_id: Mapped[UUID | None] = mapped_column(ForeignKey("orders.id"), index=True)
    actor_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("max_accounts.id"), index=True)
    movement_type: Mapped[StockMovementType] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))

    product = relationship("Product")
    from_warehouse = relationship("Warehouse", foreign_keys=[from_warehouse_id])
    to_warehouse = relationship("Warehouse", foreign_keys=[to_warehouse_id])
