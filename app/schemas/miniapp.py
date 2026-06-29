from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import LedgerDirection, OrderStatus, StaffRole, StudentAccessRole


class MiniAppAccountRead(BaseModel):
    max_user_id: int
    username: str | None = None
    display_name: str | None = None


class MiniAppStudentRead(BaseModel):
    student_id: UUID
    lms_student_id: str | None = None
    role: StudentAccessRole
    display_name: str
    group_name: str | None = None
    course_name: str | None = None
    venue_name: str | None = None
    teacher_name: str | None = None
    balance: int


class MiniAppOrderRead(BaseModel):
    id: UUID
    order_number: int
    student_id: UUID
    student_name: str
    status: OrderStatus
    total_astrocoins: int
    teacher_name: str | None = None
    venue_name: str | None = None
    created_at: datetime


class MiniAppLedgerRead(BaseModel):
    id: UUID
    student_id: UUID
    direction: LedgerDirection
    amount: int
    reason: str
    comment: str | None = None
    created_at: datetime


class MiniAppProductWarehouseRead(BaseModel):
    warehouse_id: UUID
    warehouse_name: str
    warehouse_type: str
    available_quantity: int


class MiniAppProductRead(BaseModel):
    id: UUID
    sku: str
    name: str
    description: str | None = None
    photo_url: str | None = None
    category_slug: str | None = None
    category_name: str | None = None
    price_astrocoins: int
    available_quantity: int
    warehouses: list[MiniAppProductWarehouseRead] = Field(default_factory=list)


class MiniAppCatalogRead(BaseModel):
    tenant_slug: str
    products: list[MiniAppProductRead]


class MiniAppProductImportRead(BaseModel):
    tenant_slug: str
    created_products: int
    updated_products: int
    created_categories: int
    created_warehouses: int
    updated_inventory: int
    skipped_rows: int
    errors: list[str] = Field(default_factory=list)


class MiniAppOrderItemCreate(BaseModel):
    product_id: UUID
    warehouse_id: UUID | None = None
    quantity: int = Field(gt=0, le=20)


class MiniAppOrderCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    student_id: UUID
    items: list[MiniAppOrderItemCreate] = Field(min_length=1, max_length=20)
    comment: str | None = Field(default=None, max_length=500)


class MiniAppOrderItemRead(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    unit_price_astrocoins: int
    total_price_astrocoins: int
    warehouse_id: UUID | None = None
    warehouse_name: str | None = None


class MiniAppOrderCreatedRead(BaseModel):
    order: MiniAppOrderRead
    items: list[MiniAppOrderItemRead]
    balance_after: int


class MiniAppAccrualCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    student_ids: list[UUID] = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0, le=10000)
    reason: str = Field(min_length=2, max_length=240)
    comment: str | None = Field(default=None, max_length=500)


class MiniAppAccrualRead(BaseModel):
    tenant_slug: str
    credited_students: int
    amount: int
    total_astrocoins: int


class MiniAppSessionRead(BaseModel):
    tenant_slug: str
    account: MiniAppAccountRead | None
    staff_roles: list[StaffRole]
    student_roles: list[StudentAccessRole]
    students: list[MiniAppStudentRead]
    orders: list[MiniAppOrderRead]
    ledger: list[MiniAppLedgerRead]
