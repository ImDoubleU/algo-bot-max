from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    OrderStatus,
    ProductCodeStatus,
    ProductFulfillmentType,
    ProductStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
    WarehouseType,
)


class MiniAppAccountRead(BaseModel):
    max_user_id: int
    username: str | None = None
    display_name: str | None = None


class MiniAppTenantRead(BaseModel):
    tenant_slug: str
    tenant_name: str
    city_name: str
    partner_name: str


class MiniAppTenantCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    city_name: str = Field(min_length=2, max_length=160)
    partner_name: str = Field(min_length=2, max_length=160)
    partner_director_max_user_id: int | None = Field(default=None, gt=0)
    partner_director_display_name: str | None = Field(default=None, max_length=160)


class MiniAppTenantCreatedRead(BaseModel):
    tenant: MiniAppTenantRead
    created: bool
    partner_director: "MiniAppStaffAssignmentRead | None" = None


class MiniAppStudentRead(BaseModel):
    student_id: UUID
    lms_student_id: str | None = None
    role: StudentAccessRole
    access_status: StudentAccessStatus = StudentAccessStatus.ACTIVE
    staff_visible: bool = False
    display_name: str
    group_name: str | None = None
    course_name: str | None = None
    venue_name: str | None = None
    teacher_name: str | None = None
    balance: int


class MiniAppStudentHistoryEventRead(BaseModel):
    id: UUID | None = None
    event_type: str
    from_status: StudentStatus | None = None
    to_status: StudentStatus
    from_group_name: str | None = None
    to_group_name: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    source: str
    actor_name: str | None = None
    occurred_at: datetime


class MiniAppAdminStudentRead(BaseModel):
    student_id: UUID
    lms_student_id: str | None = None
    display_name: str
    group_name: str | None = None
    course_name: str | None = None
    venue_name: str | None = None
    teacher_name: str | None = None
    status: StudentStatus
    balance: int
    imported_at: datetime
    updated_at: datetime
    status_updated_at: datetime
    departed_at: datetime | None = None
    history: list[MiniAppStudentHistoryEventRead] = Field(default_factory=list)


class MiniAppStudentRegistryRead(BaseModel):
    tenant_slug: str
    students: list[MiniAppAdminStudentRead] = Field(default_factory=list)


class MiniAppAdminHistoryEntryRead(BaseModel):
    id: UUID
    action: str
    title: str
    category: str
    status: str
    actor_name: str | None = None
    actor_max_user_id: int | None = None
    entity_type: str
    entity_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class MiniAppAdminHistoryRead(BaseModel):
    tenant_slug: str
    kind: str
    period_days: int
    entries: list[MiniAppAdminHistoryEntryRead] = Field(default_factory=list)


class MiniAppStudentInvitationRead(BaseModel):
    student_id: UUID
    student_name: str
    bot_url: str
    qr_data_url: str
    qr_download_url: str


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
    stock_quantity: int
    reserved_quantity: int
    available_quantity: int


class MiniAppWarehouseRead(BaseModel):
    id: UUID
    slug: str
    name: str
    warehouse_type: WarehouseType
    address: str | None = None


class MiniAppProductCodeRead(BaseModel):
    id: UUID
    code: str
    status: ProductCodeStatus
    order_number: int | None = None
    student_name: str | None = None
    issued_at: datetime | None = None
    created_at: datetime


class MiniAppProductRead(BaseModel):
    id: UUID
    sku: str
    name: str
    description: str | None = None
    photo_url: str | None = None
    category_slug: str | None = None
    category_name: str | None = None
    price_astrocoins: int
    status: ProductStatus = ProductStatus.ACTIVE
    fulfillment_type: ProductFulfillmentType = ProductFulfillmentType.WAREHOUSE
    available_quantity: int
    total_code_count: int = 0
    issued_code_count: int = 0
    codes: list[MiniAppProductCodeRead] = Field(default_factory=list)
    warehouses: list[MiniAppProductWarehouseRead] = Field(default_factory=list)


class MiniAppCatalogRead(BaseModel):
    tenant_slug: str
    products: list[MiniAppProductRead]
    warehouses: list[MiniAppWarehouseRead] = Field(default_factory=list)


class MiniAppProductImportRead(BaseModel):
    tenant_slug: str
    created_products: int
    updated_products: int
    created_categories: int
    created_warehouses: int
    updated_inventory: int
    skipped_rows: int
    errors: list[str] = Field(default_factory=list)


class MiniAppCrmImportRead(BaseModel):
    tenant_slug: str
    filename: str
    dry_run: bool
    student_status: StudentStatus
    parsed_rows: int
    distinct_groups: int
    distinct_courses: int
    distinct_teachers: int
    rows_without_group: int
    rows_without_student_name: int
    rows_with_contacts: int
    created_venues: int = 0
    created_students: int = 0
    updated_students: int = 0
    created_wallets: int = 0
    created_contacts: int = 0
    created_contact_student_links: int = 0
    skipped_rows: int = 0


class MiniAppProductInventoryWrite(BaseModel):
    warehouse_id: UUID
    stock_quantity: int = Field(ge=0, le=1_000_000)


class MiniAppProductUpsert(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    product_id: UUID | None = None
    sku: str | None = Field(default=None, min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=200)
    category_name: str = Field(default="Без категории", min_length=2, max_length=160)
    category_slug: str | None = Field(default=None, min_length=2, max_length=100)
    price_astrocoins: int = Field(ge=0, le=1_000_000)
    description: str | None = Field(default=None, max_length=1000)
    photo_url: str | None = Field(default=None, max_length=500)
    status: ProductStatus = ProductStatus.ACTIVE
    fulfillment_type: ProductFulfillmentType = ProductFulfillmentType.WAREHOUSE
    new_codes: list[str] = Field(default_factory=list, max_length=500)
    inventories: list[MiniAppProductInventoryWrite] | None = Field(
        default=None,
        max_length=500,
    )


class MiniAppOrderItemCreate(BaseModel):
    product_id: UUID
    warehouse_id: UUID | None = None
    quantity: int = Field(gt=0, le=20)


class MiniAppCartItemWrite(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, le=20)


class MiniAppCartWrite(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    items: list[MiniAppCartItemWrite] = Field(default_factory=list, max_length=20)


class MiniAppCartItemRead(BaseModel):
    product_id: UUID
    quantity: int


class MiniAppCartRead(BaseModel):
    student_id: UUID
    items: list[MiniAppCartItemRead] = Field(default_factory=list)


class MiniAppOrderItemRead(BaseModel):
    product_id: UUID
    product_name: str
    quantity: int
    unit_price_astrocoins: int
    total_price_astrocoins: int
    warehouse_id: UUID | None = None
    warehouse_name: str | None = None
    suggested_warehouse_id: UUID | None = None
    suggested_warehouse_name: str | None = None
    fulfillment_type: ProductFulfillmentType = ProductFulfillmentType.WAREHOUSE
    issued_codes: list[str] = Field(default_factory=list)


class MiniAppOrderStatusHistoryRead(BaseModel):
    from_status: OrderStatus | None = None
    to_status: OrderStatus
    comment: str | None = None
    created_at: datetime


class MiniAppOrderRead(BaseModel):
    id: UUID
    order_number: int
    student_id: UUID
    student_name: str
    status: OrderStatus
    total_astrocoins: int
    teacher_name: str | None = None
    venue_name: str | None = None
    cancellation_reason: str | None = None
    created_at: datetime
    items: list[MiniAppOrderItemRead] = Field(default_factory=list)
    status_history: list[MiniAppOrderStatusHistoryRead] = Field(default_factory=list)


class MiniAppOrderCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    student_id: UUID
    items: list[MiniAppOrderItemCreate] = Field(min_length=1, max_length=20)
    comment: str | None = Field(default=None, max_length=500)
    request_key: str | None = Field(
        default=None,
        min_length=12,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniAppOrderCreatedRead(BaseModel):
    order: MiniAppOrderRead
    items: list[MiniAppOrderItemRead]
    balance_after: int


class MiniAppOrderActionCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    comment: str | None = Field(default=None, max_length=500)


class MiniAppOrderCancelCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    reason: str = Field(min_length=2, max_length=160)
    custom_reason: str | None = Field(default=None, max_length=500)
    out_of_stock_product_id: UUID | None = None


class MiniAppOrderWarehouseAssignmentItem(BaseModel):
    product_id: UUID
    warehouse_id: UUID


class MiniAppOrderWarehouseAssignmentCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    items: list[MiniAppOrderWarehouseAssignmentItem] = Field(min_length=1, max_length=20)
    comment: str | None = Field(default=None, max_length=500)


class MiniAppOrderActionRead(BaseModel):
    order: MiniAppOrderRead
    balance_after: int | None = None


class MiniAppOpsOrderStatusCount(BaseModel):
    status: OrderStatus
    count: int


class MiniAppOpsLowStockRead(BaseModel):
    product_id: UUID
    sku: str
    product_name: str
    product_status: ProductStatus
    warehouse_id: UUID
    warehouse_name: str
    stock_quantity: int
    reserved_quantity: int
    available_quantity: int


class MiniAppOpsSummaryRead(BaseModel):
    tenant_slug: str
    staff_role: StaffRole
    total_orders: int
    open_orders: int
    pending_issue_orders: int
    order_statuses: list[MiniAppOpsOrderStatusCount]
    recent_open_orders: list[MiniAppOrderRead] = Field(default_factory=list)
    low_stock: list[MiniAppOpsLowStockRead] = Field(default_factory=list)
    low_stock_threshold: int
    active_products: int
    warehouses: int
    total_stock_quantity: int
    total_reserved_quantity: int


class MiniAppAccrualCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    student_ids: list[UUID] = Field(min_length=1, max_length=100)
    amount: int = Field(gt=0, le=10000)
    reason: str = Field(min_length=2, max_length=240)
    custom_reason: bool = False
    comment: str | None = Field(default=None, max_length=500)
    request_key: str | None = Field(
        default=None,
        min_length=12,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniAppAccrualUndoCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    request_key: str = Field(
        min_length=12,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniAppAccrualRead(BaseModel):
    tenant_slug: str
    credited_students: int
    amount: int
    total_astrocoins: int


class MiniAppAccrualRuleRead(BaseModel):
    id: UUID | None = None
    reason: str
    amount: int
    is_active: bool = True
    sort_order: int = 100


class MiniAppAccrualRuleWrite(BaseModel):
    reason: str = Field(min_length=2, max_length=160)
    amount: int = Field(gt=0, le=10000)
    is_active: bool = True


class MiniAppAccrualRulesUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    rules: list[MiniAppAccrualRuleWrite] = Field(min_length=1, max_length=50)


class MiniAppAccrualReportEntryRead(BaseModel):
    created_at: datetime
    teacher_id: UUID
    teacher_name: str
    teacher_role: StaffRole | None = None
    student_id: UUID
    student_name: str
    group_name: str | None = None
    amount: int
    reason: str


class MiniAppAccrualReportRead(BaseModel):
    date_from: date
    date_to: date
    total_astrocoins: int
    entries: list[MiniAppAccrualReportEntryRead] = Field(default_factory=list)


class MiniAppAccessStatusUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    status: StudentAccessStatus


class MiniAppAccessStatusRead(BaseModel):
    student_id: UUID
    role: StudentAccessRole
    status: StudentAccessStatus


class MiniAppAccessLinkRead(BaseModel):
    id: UUID
    account_id: UUID
    max_user_id: int
    username: str | None = None
    display_name: str | None = None
    student_id: UUID
    student_name: str
    group_name: str | None = None
    role: StudentAccessRole
    status: StudentAccessStatus


class MiniAppStaffAssignmentRead(BaseModel):
    id: UUID
    account_id: UUID
    max_user_id: int
    username: str | None = None
    display_name: str | None = None
    role: StaffRole
    status: AssignmentStatus


class MiniAppStaffAssignmentUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    target_max_user_id: int = Field(gt=0)
    role: StaffRole
    status: AssignmentStatus = AssignmentStatus.ACTIVE
    username: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)


class MiniAppStaffNotificationItemRead(BaseModel):
    event_key: str
    category: str
    category_label: str
    label: str
    description: str
    enabled: bool
    default_enabled: bool
    customized: bool


class MiniAppStaffNotificationSettingsRead(BaseModel):
    account_id: UUID
    max_user_id: int
    display_name: str | None = None
    roles: list[StaffRole] = Field(default_factory=list)
    items: list[MiniAppStaffNotificationItemRead] = Field(default_factory=list)


class MiniAppStaffNotificationPreferenceWrite(BaseModel):
    event_key: str = Field(min_length=3, max_length=80)
    enabled: bool


class MiniAppStaffNotificationSettingsUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    preferences: list[MiniAppStaffNotificationPreferenceWrite] = Field(
        min_length=1,
        max_length=100,
    )


class MiniAppStaffOnboardingTenantRead(BaseModel):
    tenant_slug: str
    tenant_name: str
    city_name: str


class MiniAppStaffOnboardingOptionsRead(BaseModel):
    tenants: list[MiniAppStaffOnboardingTenantRead] = Field(default_factory=list)
    roles: list[StaffRole] = Field(default_factory=list)


class MiniAppInventoryAdjustmentCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    product_id: UUID
    warehouse_id: UUID
    available_quantity: int = Field(ge=0)
    comment: str | None = Field(default=None, max_length=500)


class MiniAppInventoryAdjustmentRead(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    warehouse_name: str
    stock_quantity: int
    reserved_quantity: int
    available_quantity: int


class MiniAppInventoryTransferCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    product_id: UUID
    from_warehouse_id: UUID
    to_warehouse_id: UUID
    quantity: int = Field(gt=0, le=10000)
    comment: str | None = Field(default=None, max_length=500)


class MiniAppInventoryTransferRead(BaseModel):
    product_id: UUID
    from_warehouse_id: UUID
    from_warehouse_name: str
    from_stock_quantity: int
    from_available_quantity: int
    to_warehouse_id: UUID
    to_warehouse_name: str
    to_stock_quantity: int
    to_available_quantity: int
    quantity: int


class MiniAppWarehouseUpsert(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    warehouse_id: UUID | None = None
    slug: str | None = Field(default=None, min_length=2, max_length=120)
    name: str = Field(min_length=2, max_length=180)
    warehouse_type: WarehouseType | None = None
    address: str | None = Field(default=None, max_length=260)


class MiniAppWarehousePreferenceUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    warehouse_id: UUID


class MiniAppWarehousePreferenceRead(BaseModel):
    warehouse_id: UUID
    warehouse_name: str


class MiniAppSessionRead(BaseModel):
    tenant_slug: str
    has_access: bool = False
    account: MiniAppAccountRead | None
    staff_roles: list[StaffRole]
    student_roles: list[StudentAccessRole]
    tenant: MiniAppTenantRead | None = None
    available_tenants: list[MiniAppTenantRead] = Field(default_factory=list)
    can_manage_tenants: bool = False
    can_create_tenants: bool = False
    default_warehouse_id: UUID | None = None
    accrual_rules: list[MiniAppAccrualRuleRead] = Field(default_factory=list)
    students: list[MiniAppStudentRead]
    access_links: list[MiniAppAccessLinkRead] = Field(default_factory=list)
    staff_assignments: list[MiniAppStaffAssignmentRead] = Field(default_factory=list)
    orders: list[MiniAppOrderRead]
    ledger: list[MiniAppLedgerRead]
