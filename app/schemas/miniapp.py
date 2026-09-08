from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import (
    AssignmentStatus,
    BankDepositStatus,
    BankOperationType,
    LedgerCategory,
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
    staff_order_visible: bool = False
    teacher_visible: bool = False
    parent_connected: bool = False
    display_name: str
    first_name: str
    birth_date: date | None = None
    group_name: str | None = None
    course_name: str | None = None
    venue_name: str | None = None
    teacher_name: str | None = None
    balance: int
    student_status: StudentStatus = StudentStatus.ACTIVE
    access_until: date | None = None
    access_paused: bool = False
    access_days_remaining: int | None = None


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
    birth_date: date | None = None
    group_name: str | None = None
    course_name: str | None = None
    venue_name: str | None = None
    teacher_name: str | None = None
    linked_teacher_names: list[str] = Field(default_factory=list)
    status: StudentStatus
    balance: int
    imported_at: datetime
    updated_at: datetime
    status_updated_at: datetime
    departed_at: datetime | None = None
    parent_contact_ids: list[str] = Field(default_factory=list)
    parent_names: list[str] = Field(default_factory=list)
    parent_max_user_ids: list[int] = Field(default_factory=list)
    history: list[MiniAppStudentHistoryEventRead] = Field(default_factory=list)


class MiniAppStudentRegistryRead(BaseModel):
    tenant_slug: str
    students: list[MiniAppAdminStudentRead] = Field(default_factory=list)


class MiniAppStudentCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    birth_date: date | None = None
    lms_student_id: str | None = Field(default=None, max_length=120)
    crm_deal_id: str | None = Field(default=None, max_length=120)
    crm_uuid: str | None = Field(default=None, max_length=180)
    group_name: str | None = Field(default=None, max_length=160)
    course_name: str | None = Field(default=None, max_length=160)
    venue_name: str | None = Field(default=None, max_length=160)
    teacher_name: str | None = Field(default=None, max_length=160)
    status: StudentStatus = StudentStatus.ACTIVE
    parent_contact_id: str | None = Field(default=None, max_length=120)
    parent_name: str | None = Field(default=None, max_length=160)
    parent_max_user_id: int | None = Field(default=None, gt=0)
    parent_max_username: str | None = Field(default=None, max_length=120)
    initial_balance: int = Field(default=0, ge=0, le=10_000_000)


class MiniAppStudentBirthDateUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    birth_date: date | None = None


class MiniAppStudentStatusUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    status: StudentStatus


class MiniAppStudentBalanceUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    balance: int = Field(ge=0, le=10_000_000)
    reason: str = Field(default="Ручная корректировка баланса", min_length=2, max_length=240)
    comment: str | None = Field(default=None, max_length=500)


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
    group_name: str | None = None
    available: bool = True
    parent_connected: bool = True
    message: str | None = None
    bot_url: str | None = None
    qr_data_url: str | None = None
    qr_download_url: str | None = None


class MiniAppStudentAccessPolicyRead(BaseModel):
    departed_access_days: int = 30
    freeze_from: date | None = None
    freeze_until: date | None = None


class MiniAppStudentAccessPolicyUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    departed_access_days: int = Field(ge=1, le=365)
    freeze_from: date | None = None
    freeze_until: date | None = None


class MiniAppLedgerRead(BaseModel):
    id: UUID
    student_id: UUID
    direction: LedgerDirection | None = None
    category: LedgerCategory = LedgerCategory.ACCRUAL
    entry_type: str | None = None
    correlation_key: str | None = None
    amount: int
    reason: str
    comment: str | None = None
    created_at: datetime


class MiniAppBankDepositRead(BaseModel):
    id: UUID
    status: BankDepositStatus
    opened_on: date
    maturity_on: date
    closed_at: datetime | None = None
    close_reason: str | None = None
    principal_amount: int
    capitalized_interest: int
    pending_interest: Decimal
    pending_interest_rounded: int
    bank_balance: int
    returned_amount: int = 0
    forfeited_interest: int = 0
    days_remaining: int = 0


class MiniAppBankHistoryEntryRead(BaseModel):
    id: UUID
    operation_type: BankOperationType
    title: str
    amount: int
    direction: LedgerDirection | None = None
    principal_after: int
    interest_after: int
    bank_balance_after: int
    wallet_after: int | None = None
    annual_rate_bps: int | None = None
    effective_on: date | None = None
    comment: str | None = None
    created_at: datetime


class MiniAppBankSummaryRead(BaseModel):
    tenant_slug: str
    student_id: UUID
    student_name: str
    student_status: StudentStatus
    personal_balance: int
    bank_balance: int
    total_balance: int
    annual_rate_bps: int
    can_open: bool = False
    can_top_up: bool = False
    can_close_early: bool = False
    deposit: MiniAppBankDepositRead | None = None
    history: list[MiniAppBankHistoryEntryRead] = Field(default_factory=list)


class MiniAppBankDepositPreview(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    student_id: UUID
    amount: int = Field(ge=1, le=10_000_000)
    maturity_on: date


class MiniAppBankDepositPreviewRead(BaseModel):
    opened_on: date
    maturity_on: date
    amount: int
    annual_rate_bps: int
    accrual_days: int
    projected_interest: int
    projected_balance: int


class MiniAppBankDepositOpen(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    student_id: UUID
    amount: int = Field(ge=1, le=10_000_000)
    maturity_on: date
    request_key: str = Field(
        min_length=12,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniAppBankDepositTopUp(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    amount: int = Field(ge=1, le=10_000_000)
    request_key: str = Field(
        min_length=12,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniAppBankDepositEarlyClose(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    expected_return_amount: int = Field(ge=1, le=10_000_000)
    request_key: str = Field(
        min_length=12,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class MiniAppBankSettingsRead(BaseModel):
    tenant_slug: str
    annual_rate_bps: int
    effective_on: date
    updated_at: datetime | None = None


class MiniAppBankSettingsUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    annual_rate_bps: int = Field(ge=0, le=10_000)


class MiniAppBankReportEntryRead(BaseModel):
    student_id: UUID
    student_name: str
    group_name: str | None = None
    teacher_name: str | None = None
    personal_balance: int
    principal_amount: int
    capitalized_interest: int
    pending_interest: Decimal
    bank_balance: int
    total_balance: int
    annual_rate_bps: int
    opened_on: date
    maturity_on: date
    status: BankDepositStatus


class MiniAppBankReportRead(BaseModel):
    tenant_slug: str
    annual_rate_bps: int
    active_deposits: int
    total_principal: int
    total_capitalized_interest: int
    total_bank_balance: int
    entries: list[MiniAppBankReportEntryRead] = Field(default_factory=list)


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
    is_owner: bool = True


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
    can_manage: bool = True


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


class MiniAppCrmCityDistributionRead(BaseModel):
    tenant_slug: str
    city_name: str
    rows: int
    created_students: int = 0
    updated_students: int = 0
    skipped_rows: int = 0


class MiniAppCrmImportRead(BaseModel):
    tenant_slug: str
    filename: str
    dry_run: bool
    student_status: StudentStatus
    parsed_rows: int
    distinct_groups: int
    distinct_courses: int
    distinct_teachers: int
    distinct_cities: int = 0
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
    city_distribution: list[MiniAppCrmCityDistributionRead] = Field(default_factory=list)


class MiniAppProductInventoryWrite(BaseModel):
    warehouse_id: UUID
    stock_quantity: int = Field(ge=0, le=1_000_000)


class MiniAppProductUpsert(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    product_id: UUID | None = None
    sku: str | None = Field(default=None, min_length=1, max_length=120)
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
    id: UUID
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
    is_picked: bool = False


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


class MiniAppOrderItemPickBatchItem(BaseModel):
    order_id: UUID
    order_item_id: UUID
    is_picked: bool


class MiniAppOrderItemPickBatchUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    items: list[MiniAppOrderItemPickBatchItem] = Field(min_length=1, max_length=200)


class MiniAppOrderItemPickBatchRead(BaseModel):
    updated_items: int


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
    system_key: Literal["birthday"] | None = None


class MiniAppAccrualRuleWrite(BaseModel):
    reason: str = Field(min_length=2, max_length=160)
    amount: int = Field(gt=0, le=10000)
    is_active: bool = True
    system_key: Literal["birthday"] | None = None


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
    first_name: str | None = None
    last_name: str | None = None
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


class MiniAppTeacherProfileRead(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    completed: bool = False
    matched_group_names: list[str] = Field(default_factory=list)
    matched_student_count: int = 0


class MiniAppTeacherProfileUpdate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    first_name: str = Field(min_length=2, max_length=80)
    last_name: str = Field(min_length=2, max_length=80)


class MiniAppStaffInvitationCreate(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    role: StaffRole
    expires_in_days: int = Field(default=7, ge=1, le=30)


class MiniAppStaffInvitationRead(BaseModel):
    id: UUID
    tenant_slug: str
    tenant_name: str
    city_name: str
    role: StaffRole
    invite_url: str
    expires_at: datetime


class MiniAppStaffInvitationRedeem(BaseModel):
    max_user_id: int = Field(gt=0)
    token: str = Field(min_length=20, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    username: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=160)


class MiniAppStaffInvitationRedeemedRead(BaseModel):
    tenant_slug: str
    tenant_name: str
    city_name: str
    role: StaffRole
    assignment: MiniAppStaffAssignmentRead


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
    access_message: str | None = None
    account: MiniAppAccountRead | None
    staff_roles: list[StaffRole]
    student_roles: list[StudentAccessRole]
    teacher_profile: MiniAppTeacherProfileRead | None = None
    tenant: MiniAppTenantRead | None = None
    available_tenants: list[MiniAppTenantRead] = Field(default_factory=list)
    can_manage_tenants: bool = False
    can_create_tenants: bool = False
    default_warehouse_id: UUID | None = None
    student_access_policy: MiniAppStudentAccessPolicyRead | None = None
    accrual_rules: list[MiniAppAccrualRuleRead] = Field(default_factory=list)
    students: list[MiniAppStudentRead]
    access_links: list[MiniAppAccessLinkRead] = Field(default_factory=list)
    staff_assignments: list[MiniAppStaffAssignmentRead] = Field(default_factory=list)
    orders: list[MiniAppOrderRead]
    ledger: list[MiniAppLedgerRead]
