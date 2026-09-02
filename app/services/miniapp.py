import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings, is_placeholder
from app.models.account import (
    MaxAccount,
    StaffInvitation,
    StaffNotificationPreference,
    StaffRoleAssignment,
    StaffWarehousePreference,
)
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    OrderStatus,
    ProductCodeStatus,
    ProductFulfillmentType,
    ProductStatus,
    StaffRole,
    StockMovementType,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
    TenantStatus,
    WarehouseType,
)
from app.models.store import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductCategory,
    ProductCode,
    StockMovement,
    StudentCartItem,
    Warehouse,
    WarehouseInventory,
)
from app.models.student import (
    AstrocoinLedgerEntry,
    Contact,
    ContactStudentLink,
    Student,
    StudentAccessLink,
    StudentHistoryEvent,
    Wallet,
)
from app.models.tenant import AstrocoinAccrualRule, Tenant
from app.schemas.miniapp import (
    MiniAppAccessLinkRead,
    MiniAppAccessStatusRead,
    MiniAppAccessStatusUpdate,
    MiniAppAccountRead,
    MiniAppAccrualCreate,
    MiniAppAccrualRead,
    MiniAppAccrualReportEntryRead,
    MiniAppAccrualReportRead,
    MiniAppAccrualRuleRead,
    MiniAppAccrualRulesUpdate,
    MiniAppAccrualUndoCreate,
    MiniAppAdminHistoryEntryRead,
    MiniAppAdminHistoryRead,
    MiniAppAdminStudentRead,
    MiniAppCartItemRead,
    MiniAppCartRead,
    MiniAppCartWrite,
    MiniAppCatalogRead,
    MiniAppCrmCityDistributionRead,
    MiniAppCrmImportRead,
    MiniAppInventoryAdjustmentCreate,
    MiniAppInventoryAdjustmentRead,
    MiniAppInventoryTransferCreate,
    MiniAppInventoryTransferRead,
    MiniAppLedgerRead,
    MiniAppOpsLowStockRead,
    MiniAppOpsOrderStatusCount,
    MiniAppOpsSummaryRead,
    MiniAppOrderActionCreate,
    MiniAppOrderActionRead,
    MiniAppOrderCancelCreate,
    MiniAppOrderCreate,
    MiniAppOrderCreatedRead,
    MiniAppOrderItemPickBatchRead,
    MiniAppOrderItemPickBatchUpdate,
    MiniAppOrderItemRead,
    MiniAppOrderRead,
    MiniAppOrderStatusHistoryRead,
    MiniAppOrderWarehouseAssignmentCreate,
    MiniAppProductCodeRead,
    MiniAppProductImportRead,
    MiniAppProductRead,
    MiniAppProductUpsert,
    MiniAppProductWarehouseRead,
    MiniAppSessionRead,
    MiniAppStaffAssignmentRead,
    MiniAppStaffAssignmentUpdate,
    MiniAppStaffInvitationCreate,
    MiniAppStaffInvitationRead,
    MiniAppStaffInvitationRedeem,
    MiniAppStaffInvitationRedeemedRead,
    MiniAppStaffNotificationItemRead,
    MiniAppStaffNotificationSettingsRead,
    MiniAppStaffNotificationSettingsUpdate,
    MiniAppStaffOnboardingOptionsRead,
    MiniAppStaffOnboardingTenantRead,
    MiniAppStudentAccessPolicyRead,
    MiniAppStudentAccessPolicyUpdate,
    MiniAppStudentBalanceUpdate,
    MiniAppStudentBirthDateUpdate,
    MiniAppStudentCreate,
    MiniAppStudentHistoryEventRead,
    MiniAppStudentInvitationRead,
    MiniAppStudentRead,
    MiniAppStudentRegistryRead,
    MiniAppStudentStatusUpdate,
    MiniAppTeacherProfileRead,
    MiniAppTeacherProfileUpdate,
    MiniAppTenantCreate,
    MiniAppTenantCreatedRead,
    MiniAppTenantRead,
    MiniAppWarehousePreferenceRead,
    MiniAppWarehousePreferenceUpdate,
    MiniAppWarehouseRead,
    MiniAppWarehouseUpsert,
)
from app.services.access import normalize_student_code, revoke_dependent_student_links
from app.services.crm_import import CrmImportError, CrmStudentRow, parse_crm_students_content
from app.services.crm_sync import (
    CrmSyncDefaults,
    CrmSyncResult,
    ensure_contact_student_link,
    ensure_wallet,
    get_or_create_city,
    get_or_create_contact,
    get_or_create_partner,
    get_or_create_tenant,
    get_or_create_venue,
    slugify,
    upsert_crm_student_rows,
)
from app.services.google_sheets import GoogleSheetsClient, GoogleSheetsError
from app.services.max_notifications import (
    schedule_low_digital_codes_notification,
    schedule_low_stock_notification,
    schedule_new_product_notification,
    schedule_order_notification,
    schedule_staff_notification,
    schedule_staff_order_notification,
    schedule_teacher_order_transfer_notification,
)
from app.services.order_sheets import order_item_mapping, upsert_order_sheet_row
from app.services.product_import import (
    ProductImportError,
    generate_product_sku,
    import_products_for_tenant,
    parse_product_rows,
)
from app.services.staff import (
    active_staff_roles_for_tenant,
    configured_superadmin_max_user_id,
    get_or_create_max_account,
    is_global_superadmin,
    normalize_staff_name,
    staff_names_match,
    staff_venue_scope_ids,
    superadmin_identity_is_allowed,
    teacher_staff_name,
)
from app.services.staff_invitations import (
    build_max_bot_staff_invitation_deeplink,
    generate_staff_invitation_token,
    invitable_staff_roles,
    staff_invitation_token_hash,
)
from app.services.staff_notifications import (
    CATEGORY_LABELS,
    CONFIGURABLE_STAFF_NOTIFICATION_KEYS,
    MANAGEABLE_NOTIFICATION_ROLES,
    STAFF_NOTIFICATION_BY_KEY,
    STAFF_NOTIFICATION_CATALOG,
    default_notification_enabled,
)
from app.services.student_access_policy import StudentAccessWindow, student_access_window
from app.services.student_invitations import (
    StudentInvitationError,
    build_student_invitation_link,
    issue_student_invitation_token,
)
from app.services.warehouse import (
    WarehouseServiceError,
    available_for_reservation,
    build_stock_movement,
    choose_inventory_for_reservation,
    issue_reserved_inventory,
    release_reservation,
    reserve_inventory,
    transfer_inventory,
)

logger = logging.getLogger(__name__)


class MiniAppStoreError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


STORE_ADMIN_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
}

ELEVATED_STAFF_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
}

COIN_ACCRUAL_ROLES = STORE_ADMIN_ROLES | {
    StaffRole.CURATOR,
    StaffRole.TEACHER,
}

ORDER_MANAGER_ROLES = COIN_ACCRUAL_ROLES
FULFILLMENT_MANAGER_ROLES = STORE_ADMIN_ROLES | {StaffRole.CURATOR}
ACCRUAL_REPORT_ROLES = STORE_ADMIN_ROLES | {StaffRole.CURATOR}
OPEN_ORDER_STATUSES = frozenset(
    {
        OrderStatus.CREATED,
        OrderStatus.RESERVED,
        OrderStatus.AWAITING_DELIVERY,
        OrderStatus.DELIVERED_TO_VENUE,
        OrderStatus.TRANSFERRED_TO_TEACHER,
        OrderStatus.PROBLEM,
    }
)
STAFF_ROLE_PRIORITY = (
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
    StaffRole.TEACHER,
)
STAFF_ONBOARDING_ROLES = (
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
    StaffRole.TEACHER,
)

DEFAULT_ACCRUAL_RULES = (
    ("Активность на уроке", 10),
    ("Домашнее задание", 20),
    ("Проект", 30),
    ("Помощь группе", 10),
    ("Бонус", 50),
)


def _student_access_policy_to_read(tenant: Tenant) -> MiniAppStudentAccessPolicyRead:
    return MiniAppStudentAccessPolicyRead(
        departed_access_days=tenant.departed_access_days,
        freeze_from=tenant.access_freeze_from,
        freeze_until=tenant.access_freeze_until,
    )


def _require_student_account_access(
    student: Student,
    tenant: Tenant,
) -> StudentAccessWindow:
    access = student_access_window(student, tenant)
    if not access.allowed:
        raise MiniAppStoreError(
            "Срок доступа после завершения обучения истек. Данные сохранены; "
            "для восстановления обратитесь в школу.",
            status_code=403,
        )
    return access


async def _effective_student_access_rows(
    db: AsyncSession,
    *,
    account_id: UUID,
    tenant_id: UUID | None = None,
) -> list[tuple[StudentAccessLink, Student, Tenant]]:
    filters = [
        StudentAccessLink.account_id == account_id,
        StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        Tenant.status == TenantStatus.ACTIVE,
    ]
    if tenant_id is not None:
        filters.append(StudentAccessLink.tenant_id == tenant_id)
    rows = list(
        (
            await db.execute(
                select(StudentAccessLink, Student, Tenant)
                .join(Student, Student.id == StudentAccessLink.student_id)
                .join(Tenant, Tenant.id == StudentAccessLink.tenant_id)
                .where(*filters)
                .order_by(Student.group_name, Student.last_name, Student.first_name)
            )
        ).all()
    )
    return [
        (link, student, row_tenant)
        for link, student, row_tenant in rows
        if student_access_window(student, row_tenant).allowed
    ]


async def update_miniapp_student_access_policy(
    db: AsyncSession,
    *,
    payload: MiniAppStudentAccessPolicyUpdate,
    default_tenant_slug: str,
) -> MiniAppStudentAccessPolicyRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles={StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR},
    )
    if role is None:
        raise MiniAppStoreError("Настройка доступна директору", status_code=403)
    if (payload.freeze_from is None) != (payload.freeze_until is None):
        raise MiniAppStoreError("Укажите обе даты периода заморозки")
    if (
        payload.freeze_from is not None
        and payload.freeze_until is not None
        and payload.freeze_from > payload.freeze_until
    ):
        raise MiniAppStoreError("Дата начала заморозки должна быть раньше даты окончания")
    if (
        payload.freeze_from is not None
        and payload.freeze_until is not None
        and (payload.freeze_until - payload.freeze_from).days > 366
    ):
        raise MiniAppStoreError("Период заморозки не может быть длиннее одного года")

    tenant.departed_access_days = payload.departed_access_days
    tenant.access_freeze_from = payload.freeze_from
    tenant.access_freeze_until = payload.freeze_until
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student_access_policy.updated",
            entity_type="tenant",
            entity_id=str(tenant.id),
            payload={
                "departed_access_days": payload.departed_access_days,
                "freeze_from": payload.freeze_from.isoformat() if payload.freeze_from else None,
                "freeze_until": payload.freeze_until.isoformat() if payload.freeze_until else None,
            },
        )
    )
    await db.commit()
    return _student_access_policy_to_read(tenant)


async def _accrual_rules_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: UUID,
) -> list[MiniAppAccrualRuleRead]:
    rules = list(
        (
            await db.scalars(
                select(AstrocoinAccrualRule)
                .where(AstrocoinAccrualRule.tenant_id == tenant_id)
                .order_by(AstrocoinAccrualRule.sort_order, AstrocoinAccrualRule.reason)
            )
        ).all()
    )
    if not rules:
        return [
            MiniAppAccrualRuleRead(reason=reason, amount=amount, sort_order=index * 10)
            for index, (reason, amount) in enumerate(DEFAULT_ACCRUAL_RULES, start=1)
        ]
    return [
        MiniAppAccrualRuleRead(
            id=UUID(str(rule.id)),
            reason=rule.reason,
            amount=rule.amount,
            is_active=rule.is_active,
            sort_order=rule.sort_order,
        )
        for rule in rules
    ]


async def update_miniapp_accrual_rules(
    db: AsyncSession,
    *,
    payload: MiniAppAccrualRulesUpdate,
    default_tenant_slug: str,
) -> list[MiniAppAccrualRuleRead]:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, _ = await _store_admin_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на настройку начислений",
    )
    normalized_reasons = [rule.reason.strip() for rule in payload.rules]
    if len({reason.casefold() for reason in normalized_reasons}) != len(normalized_reasons):
        raise MiniAppStoreError("Причины начислений не должны повторяться", status_code=409)
    await db.execute(
        delete(AstrocoinAccrualRule).where(AstrocoinAccrualRule.tenant_id == tenant.id)
    )
    for index, rule in enumerate(payload.rules, start=1):
        db.add(
            AstrocoinAccrualRule(
                tenant_id=tenant.id,
                reason=rule.reason.strip(),
                amount=rule.amount,
                is_active=rule.is_active,
                sort_order=index * 10,
            )
        )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="astrocoin_accrual_rules.updated",
            entity_type="astrocoin_accrual_rule",
            payload={"rules_count": len(payload.rules)},
        )
    )
    await db.commit()
    return await _accrual_rules_for_tenant(db, tenant_id=tenant.id)


async def _active_staff_role(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    allowed_roles: set[StaffRole],
) -> StaffRole | None:
    roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant_id,
        account_id=account_id,
        allowed_roles=allowed_roles,
    )
    return next((role for role in STAFF_ROLE_PRIORITY if role in roles), None)


def _teacher_owns_student(account: MaxAccount, student: Student) -> bool:
    return staff_names_match(teacher_staff_name(account), student.teacher_name)


def _teacher_owns_order(account: MaxAccount, order: Order, student: Student) -> bool:
    return staff_names_match(
        teacher_staff_name(account),
        order.teacher_name or student.teacher_name,
    )


def _clean_teacher_profile_name_part(value: str, *, field_label: str) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) < 2 or not any(character.isalpha() for character in cleaned):
        raise MiniAppStoreError(f"Укажите {field_label}", status_code=422)
    if not all(character.isalpha() or character in " -'" for character in cleaned):
        raise MiniAppStoreError(
            f"Поле «{field_label.capitalize()}» может содержать только буквы, пробел и дефис",
            status_code=422,
        )
    return cleaned


async def _teacher_profile_read(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account: MaxAccount,
) -> MiniAppTeacherProfileRead:
    matching_name = teacher_staff_name(account)
    matched_students: list[Student] = []
    if matching_name:
        candidates = list(
            (
                await db.scalars(
                    select(Student).where(
                        Student.tenant_id == tenant_id,
                        Student.status == StudentStatus.ACTIVE,
                    )
                )
            ).all()
        )
        matched_students = [
            student
            for student in candidates
            if staff_names_match(matching_name, student.teacher_name)
        ]
    group_names = sorted(
        {
            student.group_name.strip()
            for student in matched_students
            if student.group_name and student.group_name.strip()
        },
        key=str.casefold,
    )
    return MiniAppTeacherProfileRead(
        first_name=account.staff_first_name,
        last_name=account.staff_last_name,
        completed=bool(
            account.staff_profile_completed_at
            and account.staff_first_name
            and account.staff_last_name
        ),
        matched_group_names=group_names,
        matched_student_count=len(matched_students),
    )


async def _teacher_order_scope(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account: MaxAccount,
) -> tuple[set[UUID], set[UUID]]:
    matching_name = teacher_staff_name(account)
    if not normalize_staff_name(matching_name):
        return set(), set()
    rows = (
        await db.execute(
            select(Order.id, Order.student_id, Order.teacher_name, Student.teacher_name)
            .join(Student, Student.id == Order.student_id)
            .where(
                Order.tenant_id == tenant_id,
                Student.tenant_id == tenant_id,
            )
        )
    ).all()
    order_ids: set[UUID] = set()
    student_ids: set[UUID] = set()
    for order_id, student_id, order_teacher_name, current_teacher_name in rows:
        if not staff_names_match(
            matching_name,
            order_teacher_name or current_teacher_name,
        ):
            continue
        order_ids.add(UUID(str(order_id)))
        student_ids.add(UUID(str(student_id)))
    return order_ids, student_ids


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9а-яё]+", "-", value.strip().lower(), flags=re.IGNORECASE)
    return slug.strip("-") or "warehouse"


async def get_tenant_by_slug(db: AsyncSession, tenant_slug: str) -> Tenant | None:
    return await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug.strip().lower()))


def _tenant_to_read(tenant: Tenant) -> MiniAppTenantRead:
    return MiniAppTenantRead(
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        city_name=tenant.city.name if tenant.city else tenant.name,
        partner_name=tenant.partner.name if tenant.partner else tenant.name,
    )


async def _active_tenants_for_superadmin(db: AsyncSession) -> list[MiniAppTenantRead]:
    tenants = (
        (
            await db.scalars(
                select(Tenant)
                .options(selectinload(Tenant.city), selectinload(Tenant.partner))
                .where(Tenant.status == TenantStatus.ACTIVE)
            )
        )
        .unique()
        .all()
    )
    tenants.sort(
        key=lambda tenant: (
            (tenant.city.name if tenant.city else "").casefold(),
            (tenant.partner.name if tenant.partner else tenant.name).casefold(),
        )
    )
    return [_tenant_to_read(tenant) for tenant in tenants]


async def _assigned_tenants_for_director(
    db: AsyncSession,
    *,
    account_id: UUID,
) -> list[MiniAppTenantRead]:
    tenants = (
        (
            await db.scalars(
                select(Tenant)
                .join(
                    StaffRoleAssignment,
                    StaffRoleAssignment.tenant_id == Tenant.id,
                )
                .options(selectinload(Tenant.city), selectinload(Tenant.partner))
                .where(
                    StaffRoleAssignment.account_id == account_id,
                    StaffRoleAssignment.role == StaffRole.PARTNER_DIRECTOR,
                    StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                    Tenant.status == TenantStatus.ACTIVE,
                )
            )
        )
        .unique()
        .all()
    )
    tenants.sort(key=lambda item: ((item.city.name if item.city else item.name).casefold()))
    return [_tenant_to_read(tenant) for tenant in tenants]


def _product_to_read(product: Product, *, include_codes: bool = False) -> MiniAppProductRead:
    warehouses: list[MiniAppProductWarehouseRead] = []
    available_total = 0
    product_codes = list(product.__dict__.get("digital_codes", []))

    if product.fulfillment_type == ProductFulfillmentType.DIGITAL_CODE:
        available_total = sum(
            code.status == ProductCodeStatus.AVAILABLE for code in product_codes
        )
    else:
        for inventory in product.inventory_items:
            if not getattr(inventory, "is_active", True):
                continue
            available = max(available_for_reservation(inventory), 0)
            if inventory.warehouse is None:
                continue

            # A single order item is reserved from one warehouse, so the shop
            # must not advertise a quantity that only exists across several
            # warehouses combined.
            available_total = max(available_total, available)
            warehouses.append(
                MiniAppProductWarehouseRead(
                    warehouse_id=UUID(str(inventory.warehouse_id)),
                    warehouse_name=inventory.warehouse.name,
                    warehouse_type=inventory.warehouse.warehouse_type.value,
                    stock_quantity=inventory.available_quantity,
                    reserved_quantity=inventory.reserved_quantity,
                    available_quantity=available,
                )
            )

    category = product.category
    return MiniAppProductRead(
        id=UUID(str(product.id)),
        sku=product.sku,
        name=product.name,
        description=product.description,
        photo_url=product.photo_url,
        category_slug=category.slug if category else None,
        category_name=category.name if category else None,
        price_astrocoins=product.price_astrocoins,
        status=product.status,
        fulfillment_type=product.fulfillment_type,
        available_quantity=available_total,
        total_code_count=len(product_codes),
        issued_code_count=sum(
            code.status == ProductCodeStatus.ISSUED for code in product_codes
        ),
        codes=(
            [
                MiniAppProductCodeRead(
                    id=UUID(str(code.id)),
                    code=code.code,
                    status=code.status,
                    student_name=(
                        code.issued_to_student.display_name
                        if code.__dict__.get("issued_to_student") is not None
                        else None
                    ),
                    order_number=(
                        code.order_item.order.order_number
                        if code.__dict__.get("order_item") is not None
                        and code.order_item.__dict__.get("order") is not None
                        else None
                    ),
                    issued_at=code.issued_at,
                    created_at=code.created_at,
                )
                for code in sorted(
                    product_codes,
                    key=lambda item: (item.created_at, str(item.id)),
                    reverse=True,
                )
            ]
            if include_codes
            else []
        ),
        warehouses=warehouses,
    )


def _order_to_read(
    order: Order,
    student: Student,
    *,
    items: list[MiniAppOrderItemRead] | None = None,
    status_history: list[MiniAppOrderStatusHistoryRead] | None = None,
    include_issued_codes: bool = True,
) -> MiniAppOrderRead:
    if items is None:
        items = [
            MiniAppOrderItemRead(
                id=UUID(str(item.id)),
                product_id=UUID(str(item.product_id)),
                product_name=item.product.name if item.product else str(item.product_id),
                quantity=item.quantity,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
                warehouse_id=UUID(str(item.warehouse_id)) if item.warehouse_id else None,
                warehouse_name=item.warehouse.name if item.warehouse else None,
                suggested_warehouse_id=(
                    UUID(str(item.reserved_warehouse_id)) if item.reserved_warehouse_id else None
                ),
                suggested_warehouse_name=(
                    item.reserved_warehouse.name if item.reserved_warehouse else None
                ),
                fulfillment_type=(
                    item.product.fulfillment_type
                    if item.product
                    else ProductFulfillmentType.WAREHOUSE
                ),
                issued_codes=(
                    [
                        code.code
                        for code in item.__dict__.get("digital_codes", [])
                        if code.status == ProductCodeStatus.ISSUED
                    ]
                    if include_issued_codes
                    else []
                ),
                is_picked=item.is_picked,
            )
            for item in order.__dict__.get("items", [])
        ]
    if status_history is None:
        status_history = [
            MiniAppOrderStatusHistoryRead(
                from_status=history.from_status,
                to_status=history.to_status,
                comment=history.comment,
                created_at=history.created_at,
            )
            for history in sorted(
                order.__dict__.get("status_history", []),
                key=lambda item: item.created_at,
            )
        ]
    return MiniAppOrderRead(
        id=UUID(str(order.id)),
        order_number=order.order_number,
        student_id=UUID(str(order.student_id)),
        student_name=student.display_name,
        status=order.status,
        total_astrocoins=order.total_astrocoins,
        teacher_name=order.teacher_name,
        venue_name=order.venue_name,
        cancellation_reason=order.cancellation_reason,
        created_at=order.created_at,
        items=items,
        status_history=status_history,
    )


async def _order_status_history_for_order(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    order_id: UUID,
) -> list[MiniAppOrderStatusHistoryRead]:
    rows = (
        await db.scalars(
            select(OrderStatusHistory)
            .where(
                OrderStatusHistory.tenant_id == tenant_id,
                OrderStatusHistory.order_id == order_id,
            )
            .order_by(OrderStatusHistory.created_at)
        )
    ).all()
    return [
        MiniAppOrderStatusHistoryRead(
            from_status=row.from_status,
            to_status=row.to_status,
            comment=row.comment,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _google_sheets_enabled() -> bool:
    settings = get_settings()
    return not is_placeholder(settings.google_service_account_file) and not is_placeholder(
        settings.google_sheets_orders_spreadsheet_id
    )


def _order_items_for_sheets(order: Order) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for item in order.items:
        items.append(
            order_item_mapping(
                product_id=str(item.product_id),
                product_name=item.product.name if item.product else None,
                quantity=item.quantity,
                warehouse_id=str(item.warehouse_id) if item.warehouse_id else None,
                warehouse_name=item.warehouse.name if item.warehouse else None,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
            )
        )
    return items


def _sync_order_to_sheets(
    *,
    tenant_slug: str,
    order: Order,
    student: Student,
    account: MaxAccount,
    items: list[dict[str, object]] | None = None,
    comment: str | None = None,
) -> None:
    if not _google_sheets_enabled():
        return

    try:
        upsert_order_sheet_row(
            client=GoogleSheetsClient.from_settings(),
            tenant_slug=tenant_slug,
            order=order,
            student=student,
            account=account,
            items=items if items is not None else _order_items_for_sheets(order),
            comment=comment,
        )
    except GoogleSheetsError as exc:
        logger.warning("Не удалось синхронизировать заказ с Google Sheets: %s", exc)


async def list_miniapp_catalog(
    db: AsyncSession,
    *,
    tenant_slug: str,
    max_user_id: int,
    include_inactive: bool = False,
) -> MiniAppCatalogRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        return MiniAppCatalogRead(tenant_slug=normalized_tenant_slug, products=[], warehouses=[])

    product_filters = [Product.tenant_id == tenant.id]
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    staff_roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
    )
    effective_access_rows = await _effective_student_access_rows(
        db,
        account_id=UUID(str(account.id)),
        tenant_id=UUID(str(tenant.id)),
    )
    if not staff_roles and not effective_access_rows:
        raise MiniAppStoreError("Нет доступа к выбранному партнеру", status_code=403)

    if include_inactive:
        admin_role = await _active_staff_role(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            allowed_roles=STORE_ADMIN_ROLES,
        )
        if admin_role is None:
            raise MiniAppStoreError("Нет прав на админский каталог", status_code=403)
    else:
        product_filters.append(Product.status == ProductStatus.ACTIVE)

    products = (
        (
            await db.scalars(
                select(Product)
                .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
                .where(*product_filters)
                .options(
                    selectinload(Product.category),
                    selectinload(Product.inventory_items).selectinload(
                        WarehouseInventory.warehouse
                    ),
                    selectinload(Product.digital_codes).selectinload(
                        ProductCode.issued_to_student
                    ),
                    selectinload(Product.digital_codes)
                    .selectinload(ProductCode.order_item)
                    .selectinload(OrderItem.order),
                )
                .order_by(ProductCategory.sort_order, Product.name)
            )
        )
        .unique()
        .all()
    )
    warehouses = (
        await db.scalars(
            select(Warehouse).where(Warehouse.tenant_id == tenant.id).order_by(Warehouse.name)
        )
    ).all()

    return MiniAppCatalogRead(
        tenant_slug=tenant.slug,
        products=[
            _product_to_read(product, include_codes=include_inactive) for product in products
        ],
        warehouses=[
            MiniAppWarehouseRead(
                id=UUID(str(warehouse.id)),
                slug=warehouse.slug,
                name=warehouse.name,
                warehouse_type=warehouse.warehouse_type.value,
                address=warehouse.address,
            )
            for warehouse in warehouses
        ],
    )


async def import_miniapp_products(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    filename: str,
    content: bytes,
) -> MiniAppProductImportRead:
    tenant, account, admin_role = await _store_admin_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на загрузку товаров",
    )

    try:
        rows = parse_product_rows(filename, content)
    except (ProductImportError, UnicodeDecodeError) as exc:
        raise MiniAppStoreError(str(exc), status_code=400) from exc

    if not rows:
        raise MiniAppStoreError("Файл не содержит товаров", status_code=400)

    try:
        result = await import_products_for_tenant(
            db,
            tenant=tenant,
            rows=rows,
            actor_account_id=UUID(str(account.id)),
        )
    except ProductImportError as exc:
        await db.rollback()
        raise MiniAppStoreError(str(exc), status_code=409) from exc
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_products.imported",
            entity_type="product_import",
            entity_id=None,
            payload={
                "filename": filename,
                "created_products": result.created_products,
                "updated_products": result.updated_products,
                "updated_inventory": result.updated_inventory,
                "admin_role": admin_role.value,
            },
        )
    )
    await db.commit()
    for product in result.new_active_products:
        await schedule_new_product_notification(db, tenant=tenant, product=product)
    for product, inventory in result.low_stock_items:
        await schedule_low_stock_notification(
            db,
            tenant=tenant,
            product=product,
            inventory=inventory,
        )

    return MiniAppProductImportRead(
        tenant_slug=result.tenant_slug,
        created_products=result.created_products,
        updated_products=result.updated_products,
        created_categories=result.created_categories,
        created_warehouses=result.created_warehouses,
        updated_inventory=result.updated_inventory,
        skipped_rows=result.skipped_rows,
        errors=result.errors,
    )


async def _store_admin_context(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    denied_message: str,
) -> tuple[Tenant, MaxAccount, StaffRole]:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Партнер не найден", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    admin_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if admin_role is None:
        raise MiniAppStoreError(denied_message, status_code=403)
    return tenant, account, admin_role


async def _student_registry_context(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> tuple[Tenant, MaxAccount, StaffRole]:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Партнер не найден", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=COIN_ACCRUAL_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на просмотр учеников", status_code=403)
    return tenant, account, staff_role


def _crm_city_aliases(value: str | None) -> set[str]:
    if not value:
        return set()
    return {slugify(part) for part in re.split(r"[,;/]+", value) if part.strip()}


async def _crm_import_city_buckets(
    db: AsyncSession,
    *,
    selected_tenant: Tenant,
    account: MaxAccount,
    rows: list[CrmStudentRow],
) -> list[tuple[Tenant, StaffRole, list[CrmStudentRow]]]:
    partner_tenants = list(
        (
            await db.scalars(
                select(Tenant)
                .options(selectinload(Tenant.city))
                .where(
                    Tenant.partner_id == selected_tenant.partner_id,
                    Tenant.status == TenantStatus.ACTIVE,
                )
                .order_by(Tenant.name)
            )
        ).all()
    )
    roles_by_tenant_id: dict[UUID, StaffRole] = {}
    aliases: dict[str, dict[UUID, Tenant]] = {}
    for tenant in partner_tenants:
        role = await _active_staff_role(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            allowed_roles=STORE_ADMIN_ROLES,
        )
        if role is not None:
            roles_by_tenant_id[tenant.id] = role
        city_aliases = {
            slugify(tenant.slug),
            slugify(tenant.city.slug),
            slugify(tenant.city.name),
        }
        for alias in city_aliases:
            aliases.setdefault(alias, {})[tenant.id] = tenant

    buckets: dict[UUID, list[CrmStudentRow]] = {}
    destinations: dict[UUID, Tenant] = {}
    errors: list[str] = []
    for row in rows:
        row_aliases = _crm_city_aliases(row.city)
        if not row_aliases:
            errors.append(f"строка {row.row_number}: город не указан")
            continue

        matched_tenants: dict[UUID, Tenant] = {}
        unknown_aliases: list[str] = []
        for alias in row_aliases:
            matches = aliases.get(alias)
            if not matches:
                unknown_aliases.append(alias)
                continue
            matched_tenants.update(matches)

        if unknown_aliases:
            errors.append(f"строка {row.row_number}: неизвестный город «{row.city}»")
            continue
        if len(matched_tenants) != 1:
            errors.append(f"строка {row.row_number}: укажите один город вместо «{row.city}»")
            continue

        destination = next(iter(matched_tenants.values()))
        if destination.id not in roles_by_tenant_id:
            errors.append(
                f"строка {row.row_number}: нет прав на импорт в город «{destination.city.name}»"
            )
            continue
        destinations[destination.id] = destination
        buckets.setdefault(destination.id, []).append(row)

    if errors:
        accessible_cities = (
            ", ".join(
                tenant.city.name for tenant in partner_tenants if tenant.id in roles_by_tenant_id
            )
            or "нет доступных городов"
        )
        shown_errors = errors[:8]
        if len(errors) > len(shown_errors):
            shown_errors.append(f"и еще {len(errors) - len(shown_errors)} строк")
        raise MiniAppStoreError(
            "Не удалось распределить учеников по городам: "
            + "; ".join(shown_errors)
            + f". Доступные города: {accessible_cities}",
            status_code=400,
        )

    return [
        (tenant, roles_by_tenant_id[tenant.id], buckets[tenant.id])
        for tenant in sorted(
            destinations.values(),
            key=lambda item: item.city.name.casefold(),
        )
    ]


def _merge_crm_sync_results(
    total: CrmSyncResult,
    current: CrmSyncResult,
) -> CrmSyncResult:
    return CrmSyncResult(
        created_cities=total.created_cities + current.created_cities,
        created_partners=total.created_partners + current.created_partners,
        created_tenants=total.created_tenants + current.created_tenants,
        created_venues=total.created_venues + current.created_venues,
        created_students=total.created_students + current.created_students,
        updated_students=total.updated_students + current.updated_students,
        created_wallets=total.created_wallets + current.created_wallets,
        created_contacts=total.created_contacts + current.created_contacts,
        created_contact_student_links=(
            total.created_contact_student_links + current.created_contact_student_links
        ),
        skipped_rows=total.skipped_rows + current.skipped_rows,
    )


async def import_miniapp_crm_students(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    filename: str,
    content: bytes,
    sheet_name: str,
    dry_run: bool,
    student_status: StudentStatus = StudentStatus.ACTIVE,
) -> MiniAppCrmImportRead:
    tenant, account, _admin_role = await _store_admin_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на импорт учеников",
    )
    try:
        rows = parse_crm_students_content(content, sheet_name=sheet_name)
    except CrmImportError as exc:
        raise MiniAppStoreError(str(exc), status_code=400) from exc

    if not rows:
        raise MiniAppStoreError("Файл не содержит учеников", status_code=400)

    city_buckets = await _crm_import_city_buckets(
        db,
        selected_tenant=tenant,
        account=account,
        rows=rows,
    )
    summary = {
        "parsed_rows": len(rows),
        "distinct_groups": len({row.group_name for row in rows if row.group_name}),
        "distinct_courses": len({row.course_name for row in rows if row.course_name}),
        "distinct_teachers": len({row.teacher_name for row in rows if row.teacher_name}),
        "distinct_cities": len(city_buckets),
        "rows_without_group": sum(not row.group_name for row in rows),
        "rows_without_student_name": sum(not row.first_name for row in rows),
        "rows_with_contacts": sum(bool(row.contact_ids) for row in rows),
    }
    if dry_run:
        return MiniAppCrmImportRead(
            tenant_slug=tenant.slug,
            filename=filename,
            dry_run=True,
            student_status=student_status,
            city_distribution=[
                MiniAppCrmCityDistributionRead(
                    tenant_slug=destination.slug,
                    city_name=destination.city.name,
                    rows=len(city_rows),
                )
                for destination, _role, city_rows in city_buckets
            ],
            **summary,
        )

    result = CrmSyncResult()
    city_distribution: list[MiniAppCrmCityDistributionRead] = []
    for destination, destination_role, city_rows in city_buckets:
        city_result = await upsert_crm_student_rows(
            db,
            city_rows,
            defaults=CrmSyncDefaults(
                partner_slug=destination.slug,
                partner_name=destination.name,
            ),
            commit=False,
            target_tenant=destination,
            student_status=student_status,
            actor_account_id=account.id,
        )
        result = _merge_crm_sync_results(result, city_result)
        city_distribution.append(
            MiniAppCrmCityDistributionRead(
                tenant_slug=destination.slug,
                city_name=destination.city.name,
                rows=len(city_rows),
                created_students=city_result.created_students,
                updated_students=city_result.updated_students,
                skipped_rows=city_result.skipped_rows,
            )
        )
        db.add(
            AuditLog(
                tenant_id=destination.id,
                actor_account_id=account.id,
                action="miniapp_crm.imported",
                entity_type="crm_import",
                entity_id=None,
                payload={
                    "filename": filename,
                    "selected_tenant_slug": tenant.slug,
                    "parsed_rows": len(city_rows),
                    "created_students": city_result.created_students,
                    "updated_students": city_result.updated_students,
                    "admin_role": destination_role.value,
                    "student_status": student_status.value,
                    "city_auto_routed": True,
                },
            )
        )
    await db.commit()

    return MiniAppCrmImportRead(
        tenant_slug=tenant.slug,
        filename=filename,
        dry_run=False,
        student_status=student_status,
        city_distribution=city_distribution,
        **summary,
        created_venues=result.created_venues,
        created_students=result.created_students,
        updated_students=result.updated_students,
        created_wallets=result.created_wallets,
        created_contacts=result.created_contacts,
        created_contact_student_links=result.created_contact_student_links,
        skipped_rows=result.skipped_rows,
    )


async def list_miniapp_student_registry(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> MiniAppStudentRegistryRead:
    tenant, account, staff_role = await _student_registry_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    students = (
        await db.scalars(
            select(Student)
            .where(Student.tenant_id == tenant.id)
            .order_by(Student.status, Student.group_name, Student.last_name, Student.first_name)
        )
    ).all()
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=staff_role,
    )
    if venue_scope_ids is not None:
        students = [student for student in students if student.venue_id in venue_scope_ids]
    if staff_role == StaffRole.TEACHER:
        students = [student for student in students if _teacher_owns_student(account, student)]
    student_ids = [student.id for student in students]
    balances = await _wallet_balances(db, student_ids)
    contact_ids_by_student: dict[UUID, list[str]] = {}
    contact_names_by_student: dict[UUID, list[str]] = {}
    parent_max_ids_by_student: dict[UUID, list[int]] = {}
    if student_ids:
        contact_rows = (
            await db.execute(
                select(
                    ContactStudentLink.student_id,
                    Contact.external_contact_id,
                    Contact.display_name,
                )
                .join(Contact, Contact.id == ContactStudentLink.contact_id)
                .where(
                    ContactStudentLink.tenant_id == tenant.id,
                    ContactStudentLink.student_id.in_(student_ids),
                )
                .order_by(Contact.display_name, Contact.external_contact_id)
            )
        ).all()
        for student_id, contact_id, contact_name in contact_rows:
            contact_ids_by_student.setdefault(student_id, []).append(contact_id)
            if contact_name:
                names = contact_names_by_student.setdefault(student_id, [])
                if contact_name not in names:
                    names.append(contact_name)

        parent_account_rows = (
            await db.execute(
                select(StudentAccessLink.student_id, MaxAccount.max_user_id)
                .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
                .where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.student_id.in_(student_ids),
                    StudentAccessLink.role == StudentAccessRole.PARENT,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
                .order_by(MaxAccount.max_user_id)
            )
        ).all()
        for student_id, parent_max_user_id in parent_account_rows:
            parent_max_ids_by_student.setdefault(student_id, []).append(parent_max_user_id)
    events_by_student: dict[UUID, list[MiniAppStudentHistoryEventRead]] = {}
    if student_ids:
        event_rows = (
            await db.execute(
                select(
                    StudentHistoryEvent,
                    MaxAccount.display_name,
                    MaxAccount.username,
                )
                .outerjoin(MaxAccount, MaxAccount.id == StudentHistoryEvent.actor_account_id)
                .where(
                    StudentHistoryEvent.tenant_id == tenant.id,
                    StudentHistoryEvent.student_id.in_(student_ids),
                )
                .order_by(StudentHistoryEvent.created_at)
            )
        ).all()
        for event, actor_display_name, actor_username in event_rows:
            actor_name = actor_display_name or (f"@{actor_username}" if actor_username else None)
            events_by_student.setdefault(event.student_id, []).append(
                MiniAppStudentHistoryEventRead(
                    id=UUID(str(event.id)),
                    event_type=event.event_type,
                    from_status=(StudentStatus(event.from_status) if event.from_status else None),
                    to_status=StudentStatus(event.to_status),
                    from_group_name=event.from_group_name,
                    to_group_name=event.to_group_name,
                    changed_fields=list(event.changed_fields or []),
                    source=event.source,
                    actor_name=actor_name,
                    occurred_at=event.created_at,
                )
            )

    registry_students: list[MiniAppAdminStudentRead] = []
    for student in students:
        history = events_by_student.get(student.id, [])
        if not any(event.event_type in {"imported", "created"} for event in history):
            history.append(
                MiniAppStudentHistoryEventRead(
                    event_type="imported",
                    to_status=(
                        StudentStatus.ACTIVE
                        if student.status != StudentStatus.ACTIVE
                        else student.status
                    ),
                    source="legacy_import",
                    occurred_at=student.created_at,
                )
            )
        if student.status != StudentStatus.ACTIVE and not any(
            event.to_status == student.status for event in history
        ):
            history.append(
                MiniAppStudentHistoryEventRead(
                    event_type="status_changed",
                    from_status=StudentStatus.ACTIVE,
                    to_status=student.status,
                    source="legacy_import",
                    occurred_at=student.status_updated_at,
                )
            )
        history.sort(key=lambda event: event.occurred_at)
        latest_history_at = history[-1].occurred_at if history else student.updated_at
        registry_students.append(
            MiniAppAdminStudentRead(
                student_id=UUID(str(student.id)),
                lms_student_id=student.lms_student_id,
                display_name=student.display_name,
                first_name=student.first_name,
                birth_date=student.birth_date,
                group_name=student.group_name,
                course_name=student.course_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
                status=student.status,
                balance=balances.get(student.id, 0),
                imported_at=student.created_at,
                updated_at=max(student.updated_at, latest_history_at),
                status_updated_at=student.status_updated_at,
                departed_at=student.departed_at,
                parent_contact_ids=contact_ids_by_student.get(student.id, []),
                parent_names=contact_names_by_student.get(student.id, []),
                parent_max_user_ids=parent_max_ids_by_student.get(student.id, []),
                history=history[-50:],
            )
        )
    return MiniAppStudentRegistryRead(
        tenant_slug=tenant.slug,
        students=registry_students,
    )


async def list_miniapp_student_ledger(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    student_id: UUID,
    limit: int = 100,
) -> list[MiniAppLedgerRead]:
    tenant, account, staff_role = await _student_registry_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    student = await db.scalar(
        select(Student).where(Student.tenant_id == tenant.id, Student.id == student_id)
    )
    if student is None:
        raise MiniAppStoreError("Ученик не найден", status_code=404)
    if staff_role == StaffRole.TEACHER and not _teacher_owns_student(account, student):
        raise MiniAppStoreError("Нет доступа к ученику другой группы", status_code=403)
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=staff_role,
    )
    if venue_scope_ids is not None and student.venue_id not in venue_scope_ids:
        raise MiniAppStoreError("Нет доступа к ученику другой площадки", status_code=403)

    entries = (
        await db.scalars(
            select(AstrocoinLedgerEntry)
            .where(
                AstrocoinLedgerEntry.tenant_id == tenant.id,
                AstrocoinLedgerEntry.student_id == student.id,
            )
            .order_by(AstrocoinLedgerEntry.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        MiniAppLedgerRead(
            id=UUID(str(entry.id)),
            student_id=UUID(str(entry.student_id)),
            direction=entry.direction,
            amount=entry.amount,
            reason=entry.reason,
            comment=entry.comment,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


def _clean_student_field(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


async def _admin_student_context(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    student_id: UUID,
) -> tuple[Tenant, MaxAccount, StaffRole, Student]:
    tenant, account, admin_role = await _store_admin_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на управление учениками",
    )
    student = await db.scalar(
        select(Student)
        .where(Student.tenant_id == tenant.id, Student.id == student_id)
        .with_for_update()
    )
    if student is None:
        raise MiniAppStoreError("Ученик не найден", status_code=404)
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=admin_role,
    )
    if venue_scope_ids is not None and student.venue_id not in venue_scope_ids:
        raise MiniAppStoreError("Нет доступа к ученику другой площадки", status_code=403)
    return tenant, account, admin_role, student


async def create_miniapp_student(
    db: AsyncSession,
    *,
    payload: MiniAppStudentCreate,
    default_tenant_slug: str,
) -> MiniAppStudentRegistryRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, admin_role = await _store_admin_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на добавление учеников",
    )
    first_name = payload.first_name.strip()
    last_name = payload.last_name.strip()
    if not first_name or not last_name:
        raise MiniAppStoreError("Укажите имя и фамилию ученика")
    if payload.birth_date and payload.birth_date > date.today():
        raise MiniAppStoreError("Дата рождения не может быть в будущем")

    lms_student_id = _clean_student_field(payload.lms_student_id)
    if lms_student_id:
        lms_student_id = normalize_student_code(lms_student_id)
        duplicate = await db.scalar(
            select(Student.id).where(
                Student.tenant_id == tenant.id,
                Student.lms_student_id == lms_student_id,
            )
        )
        if duplicate is not None:
            raise MiniAppStoreError("Ученик с таким ID уже есть в этом городе", status_code=409)

    crm_deal_id = _clean_student_field(payload.crm_deal_id)
    crm_uuid = _clean_student_field(payload.crm_uuid)
    for field, value, label in (
        (Student.crm_deal_id, crm_deal_id, "ID сделки amoCRM"),
        (Student.crm_uuid, crm_uuid, "UUID CRM"),
    ):
        if value is None:
            continue
        duplicate = await db.scalar(
            select(Student.id).where(Student.tenant_id == tenant.id, field == value)
        )
        if duplicate is not None:
            raise MiniAppStoreError(
                f"Ученик с таким {label} уже есть в этом городе",
                status_code=409,
            )

    parent_contact_id = _clean_student_field(payload.parent_contact_id)
    parent_name = _clean_student_field(payload.parent_name)
    parent_username = _clean_student_field(payload.parent_max_username)
    if parent_username:
        parent_username = parent_username.lstrip("@") or None
    if (parent_name or payload.parent_max_user_id) and not parent_contact_id:
        raise MiniAppStoreError("Для связи с родителем укажите Contact ID из CRM")

    parent_account: MaxAccount | None = None
    if payload.parent_max_user_id is not None:
        parent_account = await db.scalar(
            select(MaxAccount).where(MaxAccount.max_user_id == payload.parent_max_user_id)
        )
        if parent_account is not None:
            active_student_link = await db.scalar(
                select(StudentAccessLink.id).where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.account_id == parent_account.id,
                    StudentAccessLink.role == StudentAccessRole.STUDENT,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
            )
            if active_student_link is not None:
                raise MiniAppStoreError(
                    "Этот MAX-аккаунт уже используется учеником. Укажите аккаунт родителя",
                    status_code=409,
                )

    venue_name = _clean_student_field(payload.venue_name)
    venue, _ = await get_or_create_venue(db, tenant=tenant, name=venue_name)
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=admin_role,
    )
    if venue_scope_ids is not None and (venue is None or venue.id not in venue_scope_ids):
        raise MiniAppStoreError(
            "Выберите площадку, которой управляет директор",
            status_code=403,
        )

    now = datetime.now(UTC)
    student = Student(
        tenant_id=tenant.id,
        venue_id=venue.id if venue else None,
        crm_deal_id=crm_deal_id,
        crm_uuid=crm_uuid,
        lms_student_id=lms_student_id,
        student_access_code=f"manual-{uuid4().hex}",
        first_name=first_name,
        last_name=last_name,
        birth_date=payload.birth_date,
        group_name=_clean_student_field(payload.group_name),
        course_name=_clean_student_field(payload.course_name),
        venue_name=venue.name if venue else None,
        teacher_name=_clean_student_field(payload.teacher_name),
        status=payload.status,
        status_updated_at=now,
        departed_at=now if payload.status != StudentStatus.ACTIVE else None,
    )
    db.add(student)
    await db.flush()
    await ensure_wallet(db, tenant=tenant, student=student)
    wallet = await db.scalar(select(Wallet).where(Wallet.student_id == student.id))
    if wallet is None:
        raise MiniAppStoreError("Не удалось создать счет ученика", status_code=500)
    if payload.initial_balance:
        wallet.balance = payload.initial_balance
        db.add(
            AstrocoinLedgerEntry(
                tenant_id=tenant.id,
                wallet_id=wallet.id,
                student_id=student.id,
                actor_account_id=account.id,
                idempotency_key=f"student_initial_balance:{student.id}",
                direction=LedgerDirection.CREDIT,
                amount=payload.initial_balance,
                reason="Начальный баланс",
                comment="Указан при создании ученика",
            )
        )

    parent_contact: Contact | None = None
    if parent_contact_id:
        parent_contact, _ = await get_or_create_contact(
            db,
            tenant=tenant,
            contact_id=parent_contact_id,
            display_name=parent_name,
        )
        await ensure_contact_student_link(
            db,
            tenant=tenant,
            contact=parent_contact,
            student=student,
        )

    if payload.parent_max_user_id is not None:
        if parent_account is None:
            parent_account = MaxAccount(
                max_user_id=payload.parent_max_user_id,
                username=parent_username,
                display_name=parent_name,
            )
            db.add(parent_account)
            await db.flush()
        else:
            if parent_username:
                parent_account.username = parent_username
            if parent_name:
                parent_account.display_name = parent_name
        db.add(
            StudentAccessLink(
                tenant_id=tenant.id,
                account_id=parent_account.id,
                student_id=student.id,
                role=StudentAccessRole.PARENT,
                status=StudentAccessStatus.ACTIVE,
                source=StudentAccessSource.ADMIN,
            )
        )

    db.add(
        StudentHistoryEvent(
            tenant_id=tenant.id,
            student_id=student.id,
            actor_account_id=account.id,
            event_type="created",
            to_status=payload.status.value,
            to_group_name=student.group_name,
            changed_fields=[
                field
                for field, value in {
                    "first_name": first_name,
                    "last_name": last_name,
                    "birth_date": payload.birth_date,
                    "lms_student_id": lms_student_id,
                    "crm_deal_id": crm_deal_id,
                    "crm_uuid": crm_uuid,
                    "group_name": student.group_name,
                    "course_name": student.course_name,
                    "venue_name": student.venue_name,
                    "teacher_name": student.teacher_name,
                    "parent_contact_id": parent_contact_id,
                    "initial_balance": payload.initial_balance,
                }.items()
                if value not in (None, "", 0)
            ],
            source="manual",
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student.created",
            entity_type="student",
            entity_id=str(student.id),
            payload={
                "student_name": student.display_name,
                "status": payload.status.value,
                "group_name": student.group_name,
                "lms_student_id": lms_student_id,
                "birth_date": payload.birth_date.isoformat() if payload.birth_date else None,
                "crm_deal_id": crm_deal_id,
                "parent_contact_id": parent_contact.external_contact_id
                if parent_contact
                else None,
                "parent_max_user_id": payload.parent_max_user_id,
                "initial_balance": payload.initial_balance,
            },
        )
    )
    await db.commit()
    return await list_miniapp_student_registry(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
    )


async def update_miniapp_student_birth_date(
    db: AsyncSession,
    *,
    student_id: UUID,
    payload: MiniAppStudentBirthDateUpdate,
    default_tenant_slug: str,
) -> MiniAppStudentRegistryRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, _, student = await _admin_student_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        student_id=student_id,
    )
    if payload.birth_date and payload.birth_date > date.today():
        raise MiniAppStoreError("Дата рождения не может быть в будущем")
    if student.birth_date == payload.birth_date:
        await db.commit()
        return await list_miniapp_student_registry(
            db,
            max_user_id=payload.max_user_id,
            tenant_slug=tenant.slug,
        )

    previous_birth_date = student.birth_date
    student.birth_date = payload.birth_date
    db.add(
        StudentHistoryEvent(
            tenant_id=tenant.id,
            student_id=student.id,
            actor_account_id=account.id,
            event_type="updated",
            from_status=student.status.value,
            to_status=student.status.value,
            from_group_name=student.group_name,
            to_group_name=student.group_name,
            changed_fields=["birth_date"],
            source="manual",
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student.birth_date_changed",
            entity_type="student",
            entity_id=str(student.id),
            payload={
                "student_name": student.display_name,
                "from_birth_date": previous_birth_date.isoformat()
                if previous_birth_date
                else None,
                "to_birth_date": payload.birth_date.isoformat()
                if payload.birth_date
                else None,
            },
        )
    )
    await db.commit()
    return await list_miniapp_student_registry(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
    )


async def update_miniapp_student_status(
    db: AsyncSession,
    *,
    student_id: UUID,
    payload: MiniAppStudentStatusUpdate,
    default_tenant_slug: str,
) -> MiniAppStudentRegistryRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, _, student = await _admin_student_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        student_id=student_id,
    )
    previous_status = student.status
    if previous_status == payload.status:
        await db.commit()
        return await list_miniapp_student_registry(
            db,
            max_user_id=payload.max_user_id,
            tenant_slug=tenant.slug,
        )

    now = datetime.now(UTC)
    student.status = payload.status
    student.status_updated_at = now
    if payload.status == StudentStatus.ACTIVE:
        student.departed_at = None
    elif student.departed_at is None:
        student.departed_at = now
    db.add(
        StudentHistoryEvent(
            tenant_id=tenant.id,
            student_id=student.id,
            actor_account_id=account.id,
            event_type="status_changed",
            from_status=previous_status.value,
            to_status=payload.status.value,
            from_group_name=student.group_name,
            to_group_name=student.group_name,
            changed_fields=["status"],
            source="manual",
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student.status_changed",
            entity_type="student",
            entity_id=str(student.id),
            payload={
                "student_name": student.display_name,
                "from_status": previous_status.value,
                "to_status": payload.status.value,
            },
        )
    )
    await db.commit()
    return await list_miniapp_student_registry(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
    )


async def set_miniapp_student_balance(
    db: AsyncSession,
    *,
    student_id: UUID,
    payload: MiniAppStudentBalanceUpdate,
    default_tenant_slug: str,
) -> MiniAppStudentRegistryRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, _, student = await _admin_student_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        student_id=student_id,
    )
    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    if wallet is None:
        wallet = Wallet(tenant_id=tenant.id, student_id=student.id, balance=0)
        db.add(wallet)
        await db.flush()

    previous_balance = wallet.balance
    if previous_balance == payload.balance:
        await db.commit()
        return await list_miniapp_student_registry(
            db,
            max_user_id=payload.max_user_id,
            tenant_slug=tenant.slug,
        )

    delta = payload.balance - previous_balance
    reason = payload.reason.strip()
    wallet.balance = payload.balance
    db.add(
        AstrocoinLedgerEntry(
            tenant_id=tenant.id,
            wallet_id=wallet.id,
            student_id=student.id,
            actor_account_id=account.id,
            idempotency_key=f"manual_balance:{student.id}:{uuid4()}",
            direction=LedgerDirection.CREDIT if delta > 0 else LedgerDirection.DEBIT,
            amount=abs(delta),
            reason=reason,
            comment=(
                payload.comment
                or f"Баланс изменен с {previous_balance} до {payload.balance} AC"
            ),
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student.balance_adjusted",
            entity_type="student",
            entity_id=str(student.id),
            payload={
                "student_name": student.display_name,
                "previous_balance": previous_balance,
                "new_balance": payload.balance,
                "delta": delta,
                "reason": reason,
            },
        )
    )
    await db.commit()
    return await list_miniapp_student_registry(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
    )


AMOCRM_AUDIT_ACTIONS = {
    "amocrm.sync_failed",
    "amocrm.students_synced",
    "amocrm.student_status_updated",
}
REMOVED_FEATURE_AUDIT_ACTIONS = {
    "teaching_journal.lessons_updated",
    "teaching_schedule.created",
    "teaching_schedule.updated",
    "manual_feedback.generated",
    "manual_feedback.sent_to_parents",
}

AUDIT_ACTION_COPY = {
    "amocrm.sync_failed": ("Ошибка синхронизации amoCRM", "amoCRM"),
    "amocrm.students_synced": ("Синхронизация учеников amoCRM", "amoCRM"),
    "amocrm.student_status_updated": ("Обновление статусов из amoCRM", "amoCRM"),
    "miniapp_products.imported": ("Загрузка товаров", "Товары"),
    "miniapp_crm.imported": ("Импорт учеников и групп", "Ученики"),
    "product.created": ("Товар создан", "Товары"),
    "product.updated": ("Товар изменен", "Товары"),
    "product.deleted": ("Товар удален", "Товары"),
    "miniapp_order.created": ("Заказ создан", "Заказы"),
    "miniapp_order.warehouses_assigned": ("Склад заказа назначен", "Заказы"),
    "miniapp_order.item_pick_updated": ("Комплектация заказа изменена", "Заказы"),
    "miniapp_order.delivered_to_venue": ("Заказ доставлен на площадку", "Заказы"),
    "miniapp_order.cancelled": ("Заказ отменен", "Заказы"),
    "miniapp_order.issued": ("Заказ выдан", "Заказы"),
    "miniapp_order.transferred_to_teacher": ("Учитель получил заказ", "Заказы"),
    "miniapp_order.returned": ("Заказ возвращен", "Заказы"),
    "miniapp_astrocoins.accrued": ("Астрокоины начислены", "Астрокоины"),
    "miniapp_astrocoins.undone": ("Начисление отменено", "Астрокоины"),
    "student_access_link.status_changed": ("Доступ ученика изменен", "Доступ"),
    "student.created": ("Ученик добавлен вручную", "Ученики"),
    "student.status_changed": ("Статус ученика изменен", "Ученики"),
    "student.balance_adjusted": ("Баланс ученика скорректирован", "Астрокоины"),
    "staff_role_assignment.updated": ("Роль сотрудника изменена", "Сотрудники"),
    "staff_invitation.created": ("Приглашение сотрудника создано", "Сотрудники"),
    "staff_invitation.redeemed": ("Сотрудник подключен по приглашению", "Сотрудники"),
    "staff_notifications.updated": ("Уведомления сотрудника настроены", "Сотрудники"),
    "tenant.created": ("Партнер создан", "Партнеры"),
    "tenant.reopened": ("Партнер восстановлен", "Партнеры"),
    "warehouse.created": ("Склад создан", "Склады"),
    "warehouse.updated": ("Склад изменен", "Склады"),
    "warehouse.deleted": ("Склад удален", "Склады"),
    "warehouse_inventory.adjusted": ("Остаток скорректирован", "Склады"),
    "warehouse_inventory.transferred": ("Товар перемещен", "Склады"),
    "school_broadcast.sent": ("Рассылка отправлена", "Рассылки"),
}


def _audit_entry_status(action: str, payload: dict[str, object]) -> str:
    if action == "amocrm.sync_failed":
        return "error"
    if action == "amocrm.students_synced":
        if payload.get("error"):
            return "error"
        if payload.get("incomplete_leads"):
            return "partial"
    if action == "amocrm.student_status_updated" and payload.get("unmatched_lead_ids"):
        return "partial"
    return "success"


async def list_miniapp_admin_history(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    kind: str = "actions",
    period_days: int = 30,
    limit: int = 100,
) -> MiniAppAdminHistoryRead:
    tenant, _, _ = await _store_admin_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на просмотр истории действий",
    )
    normalized_kind = kind.strip().lower()
    if normalized_kind not in {"actions", "amocrm"}:
        raise MiniAppStoreError("Неизвестный вид истории")
    days = max(1, min(period_days, 365))
    row_limit = max(1, min(limit, 300))
    conditions = [
        AuditLog.tenant_id == tenant.id,
        AuditLog.created_at >= datetime.now(UTC) - timedelta(days=days),
    ]
    if normalized_kind == "amocrm":
        conditions.append(AuditLog.action.in_(AMOCRM_AUDIT_ACTIONS))
    else:
        conditions.extend(
            [
                AuditLog.actor_account_id.is_not(None),
                AuditLog.action.not_in(AMOCRM_AUDIT_ACTIONS),
                AuditLog.action.not_in(REMOVED_FEATURE_AUDIT_ACTIONS),
            ]
        )
    rows = (
        await db.execute(
            select(AuditLog, MaxAccount)
            .outerjoin(MaxAccount, MaxAccount.id == AuditLog.actor_account_id)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(row_limit)
        )
    ).all()
    entries = []
    for audit, actor in rows:
        title, category = AUDIT_ACTION_COPY.get(
            audit.action,
            (audit.action.replace("_", " ").replace(".", " · "), "Система"),
        )
        payload = dict(audit.payload or {})
        entries.append(
            MiniAppAdminHistoryEntryRead(
                id=UUID(str(audit.id)),
                action=audit.action,
                title=title,
                category=category,
                status=_audit_entry_status(audit.action, payload),
                actor_name=(
                    actor.display_name or (f"@{actor.username}" if actor.username else None)
                    if actor is not None
                    else "amoCRM"
                ),
                actor_max_user_id=actor.max_user_id if actor is not None else None,
                entity_type=audit.entity_type,
                entity_id=audit.entity_id,
                payload=payload,
                created_at=audit.created_at,
            )
        )
    return MiniAppAdminHistoryRead(
        tenant_slug=tenant.slug,
        kind=normalized_kind,
        period_days=days,
        entries=entries,
    )


async def upsert_miniapp_product(
    db: AsyncSession,
    *,
    payload: MiniAppProductUpsert,
    default_tenant_slug: str,
) -> MiniAppProductRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на управление товарами", status_code=403)

    requested_sku = payload.sku.strip().upper() if payload.sku else None
    category_slug = _slugify(payload.category_slug or payload.category_name)
    category = await db.scalar(
        select(ProductCategory).where(
            ProductCategory.tenant_id == tenant.id,
            ProductCategory.slug == category_slug,
        )
    )
    category_created = False
    if category is None:
        category = ProductCategory(
            tenant_id=tenant.id,
            slug=category_slug,
            name=payload.category_name.strip(),
            sort_order=100,
        )
        db.add(category)
        await db.flush()
        category_created = True
    else:
        category.name = payload.category_name.strip()

    product = None
    if payload.product_id is not None:
        product = await db.scalar(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.id == payload.product_id,
            )
        )
        if product is None:
            raise MiniAppStoreError("Товар не найден", status_code=404)
        sku = product.sku
    else:
        sku = requested_sku or generate_product_sku()
        product = None

    product_created = False
    if product is None:
        product = Product(
            tenant_id=tenant.id,
            category_id=category.id,
            sku=sku,
            name=payload.name.strip(),
            description=payload.description,
            photo_url=payload.photo_url,
            price_astrocoins=payload.price_astrocoins,
            status=payload.status,
            fulfillment_type=payload.fulfillment_type,
        )
        db.add(product)
        await db.flush()
        product_created = True
    else:
        if product.fulfillment_type != payload.fulfillment_type:
            has_inventory = bool(
                await db.scalar(
                    select(WarehouseInventory.id)
                    .where(
                        WarehouseInventory.tenant_id == tenant.id,
                        WarehouseInventory.product_id == product.id,
                        (
                            (WarehouseInventory.available_quantity != 0)
                            | (WarehouseInventory.reserved_quantity != 0)
                            | (WarehouseInventory.issued_quantity != 0)
                        ),
                    )
                    .limit(1)
                )
            )
            has_codes = bool(
                await db.scalar(
                    select(ProductCode.id)
                    .where(ProductCode.product_id == product.id)
                    .limit(1)
                )
            )
            if has_inventory or has_codes:
                raise MiniAppStoreError(
                    "Нельзя менять способ выдачи у товара с остатками или кодами",
                    status_code=409,
                )
        product.category_id = category.id
        product.sku = sku
        product.name = payload.name.strip()
        product.description = payload.description
        product.photo_url = payload.photo_url
        product.price_astrocoins = payload.price_astrocoins
        product.status = payload.status
        product.fulfillment_type = payload.fulfillment_type

    normalized_codes = list(
        dict.fromkeys(code.strip() for code in payload.new_codes if code.strip())
    )
    if any(len(code) > 500 for code in normalized_codes):
        raise MiniAppStoreError("Один из кодов длиннее 500 символов")
    if normalized_codes and product.fulfillment_type != ProductFulfillmentType.DIGITAL_CODE:
        raise MiniAppStoreError("Коды можно добавлять только товару с автовыдачей")
    added_code_count = 0
    if normalized_codes:
        existing_codes = set(
            (
                await db.scalars(
                    select(ProductCode.code).where(
                        ProductCode.tenant_id == tenant.id,
                        ProductCode.code.in_(normalized_codes),
                    )
                )
            ).all()
        )
        for code in normalized_codes:
            if code in existing_codes:
                continue
            db.add(
                ProductCode(
                    tenant_id=tenant.id,
                    product_id=product.id,
                    code=code,
                    status=ProductCodeStatus.AVAILABLE,
                )
            )
            added_code_count += 1
        if added_code_count:
            product.digital_codes_low_notified = False
    existing_product_code = None
    if product.fulfillment_type == ProductFulfillmentType.DIGITAL_CODE:
        existing_product_code = await db.scalar(
            select(ProductCode.id).where(ProductCode.product_id == product.id).limit(1)
        )
    if (
        product.fulfillment_type == ProductFulfillmentType.DIGITAL_CODE
        and product.status == ProductStatus.ACTIVE
        and existing_product_code is None
        and added_code_count == 0
    ):
        raise MiniAppStoreError("Добавьте хотя бы один новый уникальный код")

    changed_inventory_count = 0
    low_stock_items: list[WarehouseInventory] = []
    if payload.inventories is not None:
        if product.fulfillment_type != ProductFulfillmentType.WAREHOUSE:
            if payload.inventories:
                raise MiniAppStoreError("Остатки по складам доступны только обычным товарам")
        else:
            if not payload.inventories:
                raise MiniAppStoreError("Выберите хотя бы один склад для товара")
            requested_inventory = {
                UUID(str(item.warehouse_id)): item.stock_quantity
                for item in payload.inventories
            }
            if len(requested_inventory) != len(payload.inventories):
                raise MiniAppStoreError("Один склад указан несколько раз")

            warehouse_ids = set(requested_inventory)
            if warehouse_ids:
                existing_warehouse_ids = set(
                    (
                        await db.scalars(
                            select(Warehouse.id).where(
                                Warehouse.tenant_id == tenant.id,
                                Warehouse.id.in_(warehouse_ids),
                            )
                        )
                    ).all()
                )
                if existing_warehouse_ids != warehouse_ids:
                    raise MiniAppStoreError("Один из складов не найден", status_code=404)

            inventory_rows = list(
                (
                    await db.scalars(
                        select(WarehouseInventory)
                        .where(
                            WarehouseInventory.tenant_id == tenant.id,
                            WarehouseInventory.product_id == product.id,
                        )
                        .with_for_update()
                        .options(selectinload(WarehouseInventory.warehouse))
                    )
                )
                .unique()
                .all()
            )
            inventories_by_warehouse = {
                UUID(str(inventory.warehouse_id)): inventory for inventory in inventory_rows
            }
            for warehouse_id, next_quantity in requested_inventory.items():
                inventory = inventories_by_warehouse.get(warehouse_id)
                if inventory is None:
                    inventory = WarehouseInventory(
                        tenant_id=tenant.id,
                        product_id=product.id,
                        warehouse_id=warehouse_id,
                        available_quantity=0,
                        reserved_quantity=0,
                        is_active=False,
                    )
                    db.add(inventory)
                    await db.flush()
                    inventories_by_warehouse[warehouse_id] = inventory
                if next_quantity < inventory.reserved_quantity:
                    warehouse_name = (
                        inventory.warehouse.name if inventory.warehouse is not None else "Склад"
                    )
                    raise MiniAppStoreError(
                        f"Остаток на складе «{warehouse_name}» не может быть меньше резерва",
                        status_code=409,
                    )

            inventory_changes: list[
                tuple[UUID, WarehouseInventory, int, int]
            ] = []
            for warehouse_id, inventory in inventories_by_warehouse.items():
                next_quantity = requested_inventory.get(warehouse_id, 0)
                was_active = inventory.is_active
                next_active = warehouse_id in requested_inventory
                if next_quantity < inventory.reserved_quantity:
                    warehouse_name = (
                        inventory.warehouse.name if inventory.warehouse is not None else "Склад"
                    )
                    raise MiniAppStoreError(
                        f"Склад «{warehouse_name}» нельзя убрать: на нем есть резерв",
                        status_code=409,
                    )
                inventory.is_active = next_active
                previous_quantity = inventory.available_quantity
                if previous_quantity == next_quantity and was_active == next_active:
                    continue
                if previous_quantity != next_quantity:
                    inventory.available_quantity = next_quantity
                    inventory_changes.append(
                        (warehouse_id, inventory, previous_quantity, next_quantity)
                    )
                if not next_active:
                    inventory.low_stock_notified = False
                    changed_inventory_count += 1
                    continue
                free_quantity = max(available_for_reservation(inventory), 0)
                should_notify = free_quantity <= 5 and not inventory.low_stock_notified
                inventory.low_stock_notified = free_quantity <= 5
                changed_inventory_count += 1
                if should_notify and inventory.is_active:
                    low_stock_items.append(inventory)

            decreases = [
                [warehouse_id, inventory, previous_quantity - next_quantity]
                for warehouse_id, inventory, previous_quantity, next_quantity in inventory_changes
                if next_quantity < previous_quantity
            ]
            increases = [
                [warehouse_id, inventory, next_quantity - previous_quantity]
                for warehouse_id, inventory, previous_quantity, next_quantity in inventory_changes
                if next_quantity > previous_quantity
            ]
            for decrease in decreases:
                for increase in increases:
                    moved_quantity = min(int(decrease[2]), int(increase[2]))
                    if moved_quantity <= 0:
                        continue
                    db.add(
                        build_stock_movement(
                            inventory=increase[1],
                            movement_type=StockMovementType.TRANSFER,
                            quantity=moved_quantity,
                            actor_account_id=account.id,
                            from_warehouse_id=decrease[0],
                            to_warehouse_id=increase[0],
                            comment="Остатки распределены в карточке товара",
                        )
                    )
                    decrease[2] = int(decrease[2]) - moved_quantity
                    increase[2] = int(increase[2]) - moved_quantity

            for warehouse_id, inventory, quantity in [*decreases, *increases]:
                remaining_quantity = int(quantity)
                if remaining_quantity <= 0:
                    continue
                is_decrease = any(
                    item[0] == warehouse_id and item[1] is inventory for item in decreases
                )
                db.add(
                    build_stock_movement(
                        inventory=inventory,
                        movement_type=StockMovementType.ADJUSTMENT,
                        quantity=remaining_quantity,
                        actor_account_id=account.id,
                        from_warehouse_id=warehouse_id if is_decrease else None,
                        to_warehouse_id=None if is_decrease else warehouse_id,
                        comment="Остаток изменен в карточке товара",
                    )
                )

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="product.created" if product_created else "product.updated",
            entity_type="product",
            entity_id=str(product.id),
            payload={
                "sku": product.sku,
                "name": product.name,
                "category_slug": category.slug,
                "category_created": category_created,
                "price_astrocoins": product.price_astrocoins,
                "status": product.status.value,
                "fulfillment_type": product.fulfillment_type.value,
                "added_code_count": added_code_count,
                "changed_inventory_count": changed_inventory_count,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.commit()
    product = await db.scalar(
        select(Product)
        .where(Product.id == product.id)
        .options(
            selectinload(Product.category),
            selectinload(Product.inventory_items).selectinload(WarehouseInventory.warehouse),
            selectinload(Product.digital_codes).selectinload(ProductCode.issued_to_student),
            selectinload(Product.digital_codes)
            .selectinload(ProductCode.order_item)
            .selectinload(OrderItem.order),
        )
    )
    if product is None:
        raise MiniAppStoreError("Товар не найден после сохранения", status_code=500)
    if product_created and product.status == ProductStatus.ACTIVE:
        await schedule_new_product_notification(db, tenant=tenant, product=product)
    active_low_stock_ids = {
        UUID(str(inventory.warehouse_id)) for inventory in low_stock_items
    }
    for inventory in product.inventory_items:
        if UUID(str(inventory.warehouse_id)) not in active_low_stock_ids:
            continue
        await schedule_low_stock_notification(
            db,
            tenant=tenant,
            product=product,
            inventory=inventory,
        )
    return _product_to_read(product, include_codes=True)


async def delete_miniapp_product(
    db: AsyncSession,
    *,
    product_id: UUID,
    max_user_id: int,
    tenant_slug: str,
    default_tenant_slug: str,
) -> str | None:
    normalized_tenant_slug = (tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Партнер не найден", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на удаление товаров", status_code=403)

    product = await db.scalar(
        select(Product)
        .where(Product.tenant_id == tenant.id, Product.id == product_id)
        .with_for_update()
    )
    if product is None:
        raise MiniAppStoreError("Товар не найден", status_code=404)

    order_count = int(
        await db.scalar(
            select(func.count(OrderItem.id)).where(
                OrderItem.tenant_id == tenant.id,
                OrderItem.product_id == product.id,
            )
        )
        or 0
    )
    if order_count:
        raise MiniAppStoreError(
            "Нельзя удалить товар, который есть в заказах. "
            "Переведите его в архив, чтобы сохранить историю.",
            status_code=409,
        )

    movement_count = int(
        await db.scalar(
            select(func.count(StockMovement.id)).where(
                StockMovement.tenant_id == tenant.id,
                StockMovement.product_id == product.id,
            )
        )
        or 0
    )
    if movement_count:
        raise MiniAppStoreError(
            "Нельзя удалить товар с историей движения остатков. Переведите его в архив.",
            status_code=409,
        )

    inventories = list(
        (
            await db.scalars(
                select(WarehouseInventory)
                .where(
                    WarehouseInventory.tenant_id == tenant.id,
                    WarehouseInventory.product_id == product.id,
                )
                .with_for_update()
            )
        ).all()
    )
    reserved_quantity = sum(max(inventory.reserved_quantity, 0) for inventory in inventories)
    stock_quantity = sum(max(inventory.available_quantity, 0) for inventory in inventories)
    historical_quantity = sum(
        max(inventory.issued_quantity, 0) + max(inventory.returned_quantity, 0)
        for inventory in inventories
    )
    if reserved_quantity:
        raise MiniAppStoreError(
            f"Нельзя удалить товар: в заказах зарезервировано {reserved_quantity} шт.",
            status_code=409,
        )
    if stock_quantity:
        raise MiniAppStoreError(
            f"Нельзя удалить товар: на складах числится {stock_quantity} шт. "
            "Сначала обнулите остатки.",
            status_code=409,
        )
    if historical_quantity:
        raise MiniAppStoreError(
            "Нельзя удалить товар с историей выдачи или возврата. Переведите его в архив.",
            status_code=409,
        )

    issued_code_count = int(
        await db.scalar(
            select(func.count(ProductCode.id)).where(
                ProductCode.tenant_id == tenant.id,
                ProductCode.product_id == product.id,
                (
                    (ProductCode.status == ProductCodeStatus.ISSUED)
                    | ProductCode.order_item_id.is_not(None)
                    | ProductCode.issued_to_student_id.is_not(None)
                ),
            )
        )
        or 0
    )
    if issued_code_count:
        raise MiniAppStoreError(
            "Нельзя удалить товар с выданными цифровыми кодами. Переведите его в архив.",
            status_code=409,
        )

    product_name = product.name
    product_sku = product.sku
    photo_url = product.photo_url
    await db.execute(
        delete(StudentCartItem).where(
            StudentCartItem.tenant_id == tenant.id,
            StudentCartItem.product_id == product.id,
        )
    )
    await db.execute(
        delete(ProductCode).where(
            ProductCode.tenant_id == tenant.id,
            ProductCode.product_id == product.id,
        )
    )
    await db.execute(
        delete(WarehouseInventory).where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
        )
    )
    await db.flush()
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="product.deleted",
            entity_type="product",
            entity_id=str(product.id),
            payload={
                "sku": product_sku,
                "name": product_name,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.delete(product)
    await db.commit()
    return photo_url


async def get_miniapp_session(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    discover_tenant: bool = False,
) -> MiniAppSessionRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await db.scalar(
        select(Tenant)
        .options(selectinload(Tenant.city), selectinload(Tenant.partner))
        .where(Tenant.slug == normalized_tenant_slug)
    )
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))

    if discover_tenant and account is not None:
        effective_access_rows = await _effective_student_access_rows(
            db,
            account_id=UUID(str(account.id)),
        )
        requested_has_access = False
        if tenant is not None:
            requested_has_access = bool(
                await active_staff_roles_for_tenant(
                    db,
                    tenant_id=UUID(str(tenant.id)),
                    account_id=UUID(str(account.id)),
                )
            ) or any(
                row_tenant.id == tenant.id for _, _, row_tenant in effective_access_rows
            )

        if not requested_has_access:
            accessible_tenant_ids = set(
                (
                    await db.scalars(
                        select(StaffRoleAssignment.tenant_id).where(
                            StaffRoleAssignment.account_id == account.id,
                            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                        )
                    )
                ).all()
            )
            accessible_tenant_ids.update(
                row_tenant.id for _, _, row_tenant in effective_access_rows
            )
            if accessible_tenant_ids:
                discovered_tenant = await db.scalar(
                    select(Tenant)
                    .options(selectinload(Tenant.city), selectinload(Tenant.partner))
                    .where(
                        Tenant.id.in_(accessible_tenant_ids),
                        Tenant.status == TenantStatus.ACTIVE,
                    )
                    .order_by(Tenant.name, Tenant.slug)
                    .limit(1)
                )
                if discovered_tenant is not None:
                    tenant = discovered_tenant
                    normalized_tenant_slug = tenant.slug

    if tenant is None or account is None:
        return MiniAppSessionRead(
            tenant_slug=normalized_tenant_slug,
            account=None
            if account is None
            else MiniAppAccountRead(
                max_user_id=account.max_user_id,
                username=account.username,
                display_name=account.display_name,
            ),
            staff_roles=[],
            student_roles=[],
            students=[],
            access_links=[],
            staff_assignments=[],
            orders=[],
            ledger=[],
        )

    effective_staff_roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
    )
    staff_roles = [role for role in STAFF_ROLE_PRIORITY if role in effective_staff_roles]
    own_access_rows = await _effective_student_access_rows(
        db,
        account_id=UUID(str(account.id)),
        tenant_id=UUID(str(tenant.id)),
    )
    explicit_student_roles = [link.role for link, _, _ in own_access_rows]
    own_link_rows = [(link, linked_student) for link, linked_student, _ in own_access_rows]
    linked_students_by_id: dict[UUID, Student] = {}
    access_roles_by_student: dict[UUID, set[StudentAccessRole]] = {}
    for link, linked_student in own_link_rows:
        linked_students_by_id[linked_student.id] = linked_student
        access_roles_by_student.setdefault(linked_student.id, set()).add(link.role)

    if not staff_roles and not explicit_student_roles:
        has_expired_link = bool(
            await db.scalar(
                select(StudentAccessLink.id)
                .where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.account_id == account.id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
                .limit(1)
            )
        )
        return MiniAppSessionRead(
            tenant_slug=normalized_tenant_slug,
            access_message=(
                "Срок доступа после завершения обучения истек. Данные сохранены; "
                "для восстановления обратитесь в школу."
                if has_expired_link
                else None
            ),
            account=MiniAppAccountRead(
                max_user_id=account.max_user_id,
                username=account.username,
                display_name=account.display_name,
            ),
            staff_roles=[],
            student_roles=[],
            students=[],
            access_links=[],
            staff_assignments=[],
            orders=[],
            ledger=[],
        )

    visible_order_ids: set[UUID] | None = None
    access_link_student_ids: set[UUID] | None = None
    ledger_student_ids: list[UUID]
    if staff_roles:
        ordered_student_ids = select(Order.student_id).where(Order.tenant_id == tenant.id)
        tenant_students = (
            await db.scalars(
                select(Student)
                .where(
                    Student.tenant_id == tenant.id,
                    (Student.status == StudentStatus.ACTIVE)
                    | Student.id.in_(ordered_student_ids),
                )
                .order_by(Student.group_name, Student.first_name, Student.last_name)
            )
        ).all()
        effective_staff_role = next(
            (role for role in STAFF_ROLE_PRIORITY if role in staff_roles),
            None,
        )
        director_venue_ids = await staff_venue_scope_ids(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            role=effective_staff_role,
        ) if effective_staff_role is not None else None
        if director_venue_ids is not None:
            tenant_students = [
                student for student in tenant_students if student.venue_id in director_venue_ids
            ]
        teacher_scoped = effective_staff_role == StaffRole.TEACHER
        if teacher_scoped:
            current_teacher_students = [
                student
                for student in tenant_students
                if _teacher_owns_student(account, student)
            ]
            visible_order_ids, order_student_ids = await _teacher_order_scope(
                db,
                tenant_id=tenant.id,
                account=account,
            )
            current_teacher_student_ids = {student.id for student in current_teacher_students}
            tenant_students = [
                student
                for student in tenant_students
                if student.id in current_teacher_student_ids or student.id in order_student_ids
            ]
            staff_student_ids = current_teacher_student_ids
            staff_order_student_ids = order_student_ids
        else:
            staff_student_ids = {student.id for student in tenant_students}
            staff_order_student_ids = set(staff_student_ids)
        visible_students_by_id = {student.id: student for student in tenant_students}
        visible_students_by_id.update(linked_students_by_id)
        tenant_students = sorted(
            visible_students_by_id.values(),
            key=lambda student: (
                student.group_name or "",
                student.first_name or "",
                student.last_name or "",
            ),
        )
        student_ids = [student.id for student in tenant_students]
        ledger_student_ids = list(staff_student_ids | set(linked_students_by_id))
        if director_venue_ids is not None:
            access_link_student_ids = staff_student_ids | set(linked_students_by_id)
        balances = await _wallet_balances(db, student_ids)
        students = [
            MiniAppStudentRead(
                student_id=UUID(str(student.id)),
                lms_student_id=student.lms_student_id,
                role=(
                    StudentAccessRole.PARENT
                    if StudentAccessRole.PARENT in access_roles_by_student.get(student.id, set())
                    else StudentAccessRole.STUDENT
                ),
                staff_visible=student.id in staff_student_ids,
                staff_order_visible=student.id in staff_order_student_ids,
                display_name=student.display_name,
                first_name=student.first_name,
                birth_date=student.birth_date,
                group_name=student.group_name,
                course_name=student.course_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
                balance=balances.get(student.id, 0),
                student_status=student.status,
                access_until=student_access_window(student, tenant).access_until,
                access_paused=student_access_window(student, tenant).paused,
                access_days_remaining=student_access_window(student, tenant).days_remaining,
            )
            for student in tenant_students
        ]
    else:
        linked_students = list(linked_students_by_id.values())
        student_ids = [student.id for student in linked_students]
        ledger_student_ids = list(student_ids)
        balances = await _wallet_balances(db, student_ids)
        students = [
            MiniAppStudentRead(
                student_id=UUID(str(student.id)),
                lms_student_id=student.lms_student_id,
                role=(
                    StudentAccessRole.PARENT
                    if StudentAccessRole.PARENT in access_roles_by_student.get(student.id, set())
                    else StudentAccessRole.STUDENT
                ),
                display_name=student.display_name,
                first_name=student.first_name,
                birth_date=student.birth_date,
                group_name=student.group_name,
                course_name=student.course_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
                balance=balances.get(student.id, 0),
                student_status=student.status,
                access_until=student_access_window(student, tenant).access_until,
                access_paused=student_access_window(student, tenant).paused,
                access_days_remaining=student_access_window(student, tenant).days_remaining,
            )
            for student in linked_students
        ]

    orders = await _orders_for_students(
        db,
        tenant_id=tenant.id,
        student_ids=student_ids,
        visible_order_ids=visible_order_ids,
        unrestricted_student_ids=set(linked_students_by_id),
        issued_code_student_ids=(set(linked_students_by_id) if staff_roles else None),
    )
    ledger = await _ledger_for_students(
        db,
        tenant_id=tenant.id,
        student_ids=ledger_student_ids,
    )
    access_links = await _access_links_for_session(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        include_all=bool(set(staff_roles) & ELEVATED_STAFF_ROLES),
        student_ids=access_link_student_ids,
    )
    staff_assignments = await _staff_assignments_for_session(
        db,
        tenant_id=tenant.id,
        actor_roles=staff_roles,
    )
    teacher_profile = (
        await _teacher_profile_read(db, tenant_id=tenant.id, account=account)
        if StaffRole.TEACHER in effective_staff_roles
        else None
    )
    default_warehouse_id = None
    if staff_roles:
        default_warehouse_id = await db.scalar(
            select(StaffWarehousePreference.warehouse_id).where(
                StaffWarehousePreference.tenant_id == tenant.id,
                StaffWarehousePreference.account_id == account.id,
            )
        )

    return MiniAppSessionRead(
        tenant_slug=tenant.slug,
        has_access=True,
        account=MiniAppAccountRead(
            max_user_id=account.max_user_id,
            username=account.username,
            display_name=account.display_name,
        ),
        staff_roles=staff_roles,
        student_roles=sorted(set(explicit_student_roles)),
        teacher_profile=teacher_profile,
        tenant=_tenant_to_read(tenant),
        available_tenants=(
            await _active_tenants_for_superadmin(db)
            if StaffRole.SUPERADMIN in effective_staff_roles
            else await _assigned_tenants_for_director(db, account_id=account.id)
            if StaffRole.PARTNER_DIRECTOR in effective_staff_roles
            else []
        ),
        can_manage_tenants=bool(
            {StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR} & effective_staff_roles
        ),
        can_create_tenants=StaffRole.SUPERADMIN in effective_staff_roles,
        default_warehouse_id=(UUID(str(default_warehouse_id)) if default_warehouse_id else None),
        student_access_policy=_student_access_policy_to_read(tenant),
        accrual_rules=await _accrual_rules_for_tenant(db, tenant_id=tenant.id),
        students=students,
        access_links=access_links,
        staff_assignments=staff_assignments,
        orders=orders,
        ledger=ledger,
    )


async def get_miniapp_student_invitation(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    student_id: UUID,
) -> MiniAppStudentInvitationRead:
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Школа не найдена", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("Сначала привяжите профиль в боте", status_code=403)

    student = await db.scalar(
        select(Student).where(
            Student.id == student_id,
            Student.tenant_id == tenant.id,
        )
    )
    if student is None:
        raise MiniAppStoreError("Ученик не найден", status_code=404)

    parent_link = await db.scalar(
        select(StudentAccessLink).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id == student_id,
            StudentAccessLink.role == StudentAccessRole.PARENT,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
    )
    if parent_link is not None:
        _require_student_account_access(student, tenant)
    else:
        teacher_role = await _active_staff_role(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            allowed_roles={StaffRole.TEACHER},
        )
        if (
            teacher_role != StaffRole.TEACHER
            or student.status != StudentStatus.ACTIVE
            or not _teacher_owns_student(account, student)
        ):
            raise MiniAppStoreError(
                "QR-код доступен родителю или преподавателю этой группы",
                status_code=403,
            )
        parent_link = await db.scalar(
            select(StudentAccessLink)
            .where(
                StudentAccessLink.tenant_id == tenant.id,
                StudentAccessLink.student_id == student.id,
                StudentAccessLink.role == StudentAccessRole.PARENT,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            )
            .order_by(StudentAccessLink.created_at)
            .limit(1)
        )
        if parent_link is None:
            return MiniAppStudentInvitationRead(
                student_id=UUID(str(student.id)),
                student_name=student.display_name,
                group_name=student.group_name,
                available=False,
                parent_connected=False,
                message=(
                    "Родитель еще не подключен. Попросите его открыть письмо школы "
                    "и перейти по персональной ссылке."
                ),
            )

    return _student_invitation_to_read(tenant, student, parent_link)


def _student_invitation_to_read(
    tenant: Tenant,
    student: Student,
    parent_link: StudentAccessLink,
) -> MiniAppStudentInvitationRead:
    settings = get_settings()
    if is_placeholder(settings.max_bot_username):
        raise MiniAppStoreError(
            "Имя MAX-бота не настроено",
            status_code=503,
        )
    try:
        invitation_token = issue_student_invitation_token(
            UUID(str(tenant.id)),
            UUID(str(student.id)),
            UUID(str(parent_link.id)),
        )
        bot_url = build_student_invitation_link(
            str(settings.max_bot_username),
            UUID(str(tenant.id)),
            UUID(str(student.id)),
            UUID(str(parent_link.id)),
        )
    except StudentInvitationError as exc:
        raise MiniAppStoreError(str(exc), status_code=503) from exc

    return MiniAppStudentInvitationRead(
        student_id=UUID(str(student.id)),
        student_name=student.display_name,
        group_name=student.group_name,
        bot_url=bot_url,
        qr_data_url=f"/miniapp/qr/{invitation_token}.png?preview=1",
        qr_download_url=f"/miniapp/qr/{invitation_token}.png",
    )


async def list_miniapp_teacher_invitations(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> list[MiniAppStudentInvitationRead]:
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Школа не найдена", status_code=404)
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("Сначала привяжите профиль в боте", status_code=403)
    teacher_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles={StaffRole.TEACHER},
    )
    if teacher_role != StaffRole.TEACHER:
        raise MiniAppStoreError("Раздел доступен преподавателю", status_code=403)

    students = list(
        (
            await db.scalars(
                select(Student)
                .where(
                    Student.tenant_id == tenant.id,
                    Student.status == StudentStatus.ACTIVE,
                )
                .order_by(Student.group_name, Student.last_name, Student.first_name)
            )
        ).all()
    )
    students = [student for student in students if _teacher_owns_student(account, student)]
    if not students:
        return []

    parent_links = list(
        (
            await db.scalars(
                select(StudentAccessLink)
                .where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.student_id.in_([student.id for student in students]),
                    StudentAccessLink.role == StudentAccessRole.PARENT,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
                .order_by(StudentAccessLink.created_at)
            )
        ).all()
    )
    parent_link_by_student: dict[UUID, StudentAccessLink] = {}
    for link in parent_links:
        parent_link_by_student.setdefault(UUID(str(link.student_id)), link)

    result: list[MiniAppStudentInvitationRead] = []
    for student in students:
        parent_link = parent_link_by_student.get(UUID(str(student.id)))
        if parent_link is None:
            result.append(
                MiniAppStudentInvitationRead(
                    student_id=UUID(str(student.id)),
                    student_name=student.display_name,
                    group_name=student.group_name,
                    available=False,
                    parent_connected=False,
                    message=(
                        "Родитель еще не подключен. Попросите его открыть письмо школы "
                        "и перейти по персональной ссылке."
                    ),
                )
            )
            continue
        result.append(_student_invitation_to_read(tenant, student, parent_link))
    return result


async def _student_cart_context(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    student_id: UUID,
    lock_student: bool = False,
) -> tuple[Tenant, MaxAccount, Student]:
    tenant = await get_tenant_by_slug(db, tenant_slug.strip().lower())
    if tenant is None:
        raise MiniAppStoreError("Школа не найдена", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("Сначала привяжите профиль в боте", status_code=403)

    student_query = select(Student).where(
        Student.tenant_id == tenant.id,
        Student.id == student_id,
    )
    if lock_student:
        student_query = student_query.with_for_update()
    student = await db.scalar(student_query)
    if student is None:
        raise MiniAppStoreError("Ученик не найден", status_code=404)
    _require_student_account_access(student, tenant)

    active_link = await db.scalar(
        select(StudentAccessLink.id).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id == student.id,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
    )
    if active_link is None:
        raise MiniAppStoreError(
            "Нет доступа к корзине выбранного ученика",
            status_code=403,
        )
    return tenant, account, student


async def get_miniapp_cart(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    student_id: UUID,
) -> MiniAppCartRead:
    tenant, _, student = await _student_cart_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
        student_id=student_id,
    )
    cart_items = (
        await db.scalars(
            select(StudentCartItem)
            .join(Product, Product.id == StudentCartItem.product_id)
            .where(
                StudentCartItem.tenant_id == tenant.id,
                StudentCartItem.student_id == student.id,
                Product.tenant_id == tenant.id,
                Product.status == ProductStatus.ACTIVE,
            )
            .order_by(StudentCartItem.created_at, StudentCartItem.id)
        )
    ).all()
    return MiniAppCartRead(
        student_id=UUID(str(student.id)),
        items=[
            MiniAppCartItemRead(
                product_id=UUID(str(item.product_id)),
                quantity=item.quantity,
            )
            for item in cart_items
        ],
    )


async def replace_miniapp_cart(
    db: AsyncSession,
    *,
    student_id: UUID,
    payload: MiniAppCartWrite,
    tenant_slug: str,
) -> MiniAppCartRead:
    tenant, account, student = await _student_cart_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        student_id=student_id,
        lock_student=True,
    )
    quantities: dict[UUID, int] = {}
    for item in payload.items:
        product_id = UUID(str(item.product_id))
        quantities[product_id] = quantities.get(product_id, 0) + item.quantity
        if quantities[product_id] > 20:
            raise MiniAppStoreError("В корзине может быть не больше 20 штук одного товара")

    if quantities:
        product_ids = set(
            await db.scalars(
                select(Product.id).where(
                    Product.tenant_id == tenant.id,
                    Product.id.in_(quantities),
                    Product.status == ProductStatus.ACTIVE,
                )
            )
        )
        missing_product_ids = set(quantities) - product_ids
        if missing_product_ids:
            raise MiniAppStoreError(
                "Один или несколько товаров больше недоступны",
                status_code=409,
            )

    await db.execute(
        delete(StudentCartItem).where(
            StudentCartItem.tenant_id == tenant.id,
            StudentCartItem.student_id == student.id,
        )
    )
    db.add_all(
        [
            StudentCartItem(
                tenant_id=tenant.id,
                student_id=student.id,
                product_id=product_id,
                updated_by_account_id=account.id,
                quantity=quantity,
            )
            for product_id, quantity in quantities.items()
        ]
    )
    await db.commit()
    return MiniAppCartRead(
        student_id=UUID(str(student.id)),
        items=[
            MiniAppCartItemRead(product_id=product_id, quantity=quantity)
            for product_id, quantity in quantities.items()
        ],
    )


async def get_miniapp_ops_summary(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    low_stock_threshold: int = 5,
) -> MiniAppOpsSummaryRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    threshold = max(0, min(low_stock_threshold, 999))
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX account не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=ORDER_MANAGER_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на операционную сводку", status_code=403)

    order_filters = [Order.tenant_id == tenant.id]
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=staff_role,
    )
    if venue_scope_ids is not None:
        scoped_student_ids = select(Student.id).where(
            Student.tenant_id == tenant.id,
            Student.venue_id.in_(venue_scope_ids),
        )
        order_filters.append(Order.student_id.in_(scoped_student_ids))
    if staff_role == StaffRole.TEACHER:
        teacher_order_ids, _teacher_student_ids = await _teacher_order_scope(
            db,
            tenant_id=tenant.id,
            account=account,
        )
        order_filters.append(Order.id.in_(teacher_order_ids))

    status_rows = (
        await db.execute(
            select(Order.status, func.count(Order.id)).where(*order_filters).group_by(Order.status)
        )
    ).all()
    status_counts = {status: int(count or 0) for status, count in status_rows}
    order_statuses = [
        MiniAppOpsOrderStatusCount(status=status, count=count)
        for status, count in sorted(status_counts.items(), key=lambda item: item[0].value)
    ]
    total_orders = sum(status_counts.values())

    open_statuses = OPEN_ORDER_STATUSES
    pending_issue_statuses = {
        OrderStatus.DELIVERED_TO_VENUE,
        OrderStatus.TRANSFERRED_TO_TEACHER,
    }
    open_orders = sum(status_counts.get(status, 0) for status in open_statuses)
    pending_issue_orders = sum(status_counts.get(status, 0) for status in pending_issue_statuses)

    open_order_rows = (
        await db.execute(
            select(Order, Student)
            .join(Student, Student.id == Order.student_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.items).selectinload(OrderItem.digital_codes),
                selectinload(Order.items).selectinload(OrderItem.warehouse),
                selectinload(Order.items).selectinload(OrderItem.reserved_warehouse),
                selectinload(Order.status_history),
            )
            .where(*order_filters, Order.status.in_(open_statuses))
            .order_by(Order.created_at.asc())
            .limit(8)
        )
    ).all()
    recent_open_orders = [_order_to_read(order, student) for order, student in open_order_rows]

    active_products = int(
        await db.scalar(
            select(func.count(Product.id)).where(
                Product.tenant_id == tenant.id,
                Product.status == ProductStatus.ACTIVE,
            )
        )
        or 0
    )
    warehouses = int(
        await db.scalar(select(func.count(Warehouse.id)).where(Warehouse.tenant_id == tenant.id))
        or 0
    )
    total_stock_quantity = int(
        await db.scalar(
            select(func.coalesce(func.sum(WarehouseInventory.available_quantity), 0)).where(
                WarehouseInventory.tenant_id == tenant.id,
                WarehouseInventory.is_active.is_(True),
            )
        )
        or 0
    )
    total_reserved_quantity = int(
        await db.scalar(
            select(func.coalesce(func.sum(WarehouseInventory.reserved_quantity), 0)).where(
                WarehouseInventory.tenant_id == tenant.id,
                WarehouseInventory.is_active.is_(True),
            )
        )
        or 0
    )

    available_expr = WarehouseInventory.available_quantity - WarehouseInventory.reserved_quantity
    low_stock_rows = (
        await db.execute(
            select(WarehouseInventory, Product, Warehouse, available_expr.label("available"))
            .join(Product, Product.id == WarehouseInventory.product_id)
            .join(Warehouse, Warehouse.id == WarehouseInventory.warehouse_id)
            .where(
                WarehouseInventory.tenant_id == tenant.id,
                WarehouseInventory.is_active.is_(True),
                Product.status != ProductStatus.ARCHIVED,
                Product.fulfillment_type == ProductFulfillmentType.WAREHOUSE,
                available_expr <= threshold,
            )
            .order_by(available_expr.asc(), Product.name, Warehouse.name)
            .limit(12)
        )
    ).all()
    low_stock = [
        MiniAppOpsLowStockRead(
            product_id=UUID(str(product.id)),
            sku=product.sku,
            product_name=product.name,
            product_status=product.status,
            warehouse_id=UUID(str(warehouse.id)),
            warehouse_name=warehouse.name,
            stock_quantity=inventory.available_quantity,
            reserved_quantity=inventory.reserved_quantity,
            available_quantity=max(int(available or 0), 0),
        )
        for inventory, product, warehouse, available in low_stock_rows
    ]

    return MiniAppOpsSummaryRead(
        tenant_slug=normalized_tenant_slug,
        staff_role=staff_role,
        total_orders=total_orders,
        open_orders=open_orders,
        pending_issue_orders=pending_issue_orders,
        order_statuses=order_statuses,
        recent_open_orders=recent_open_orders,
        low_stock=low_stock,
        low_stock_threshold=threshold,
        active_products=active_products,
        warehouses=warehouses,
        total_stock_quantity=total_stock_quantity,
        total_reserved_quantity=total_reserved_quantity,
    )


def _merge_order_items(payload: MiniAppOrderCreate) -> dict[UUID, int]:
    quantities: dict[UUID, int] = {}
    for item in payload.items:
        product_id = UUID(str(item.product_id))
        quantities[product_id] = quantities.get(product_id, 0) + item.quantity

    too_large = [quantity for quantity in quantities.values() if quantity > 20]
    if too_large:
        raise MiniAppStoreError("В одном заказе можно указать не больше 20 штук одного товара")
    return quantities


async def _load_order_action_context(
    db: AsyncSession,
    *,
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    default_tenant_slug: str,
    require_manager: bool,
) -> tuple[Tenant, MaxAccount, Order, Student, StaffRole | None]:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    row = (
        await db.execute(
            select(Order, Student)
            .join(Student, Student.id == Order.student_id)
            .where(Order.tenant_id == tenant.id, Order.id == order_id)
            .with_for_update()
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.items).selectinload(OrderItem.digital_codes),
                selectinload(Order.items).selectinload(OrderItem.warehouse),
                selectinload(Order.items).selectinload(OrderItem.reserved_warehouse),
                selectinload(Order.status_history),
            )
        )
    ).one_or_none()
    if row is None:
        raise MiniAppStoreError("Заказ не найден", status_code=404)

    order, student = row
    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=ORDER_MANAGER_ROLES,
    )
    if staff_role is not None:
        venue_scope_ids = await staff_venue_scope_ids(
            db,
            tenant_id=tenant.id,
            account_id=account.id,
            role=staff_role,
        )
        if venue_scope_ids is not None and student.venue_id not in venue_scope_ids:
            raise MiniAppStoreError("Нет доступа к заказу другой площадки", status_code=403)
        if staff_role != StaffRole.TEACHER or _teacher_owns_order(account, order, student):
            return tenant, account, order, student, staff_role
        if require_manager:
            raise MiniAppStoreError("Нет доступа к заказу чужой группы", status_code=403)

    if require_manager:
        raise MiniAppStoreError("Нет прав на управление заказом", status_code=403)

    active_student_link = await db.scalar(
        select(StudentAccessLink.id).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id == order.student_id,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
    )
    if active_student_link is None:
        raise MiniAppStoreError("Нет доступа к выбранному заказу", status_code=403)
    _require_student_account_access(student, tenant)

    return tenant, account, order, student, None


async def _inventory_for_order_item(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    item: OrderItem,
    allow_provisional: bool = False,
) -> WarehouseInventory:
    warehouse_id = item.warehouse_id
    if warehouse_id is None and allow_provisional:
        warehouse_id = item.reserved_warehouse_id
    if warehouse_id is None:
        raise MiniAppStoreError("У позиции заказа не указан склад", status_code=409)

    inventory = await db.scalar(
        select(WarehouseInventory)
        .where(
            WarehouseInventory.tenant_id == tenant_id,
            WarehouseInventory.warehouse_id == warehouse_id,
            WarehouseInventory.product_id == item.product_id,
        )
        .with_for_update()
    )
    if inventory is None:
        raise MiniAppStoreError("Складская позиция заказа не найдена", status_code=409)
    return inventory


async def create_miniapp_order(
    db: AsyncSession,
    *,
    payload: MiniAppOrderCreate,
    default_tenant_slug: str,
) -> MiniAppOrderCreatedRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug).with_for_update())
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError(
            "Сначала свяжите MAX-аккаунт с Contact ID в боте",
            status_code=403,
        )

    student = await db.scalar(
        select(Student).where(
            Student.tenant_id == tenant.id,
            Student.id == payload.student_id,
        ).with_for_update()
    )
    if student is None:
        raise MiniAppStoreError("Ученик не найден у выбранного партнера", status_code=404)
    _require_student_account_access(student, tenant)

    active_student_link = await db.scalar(
        select(StudentAccessLink.id).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id == student.id,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
    )
    if active_student_link is None:
        raise MiniAppStoreError(
            "Покупки доступны только ученикам и родителям",
            status_code=403,
        )

    quantities = _merge_order_items(payload)
    request_key = payload.request_key.strip() if payload.request_key else None
    if request_key:
        existing_row = (
            await db.execute(
                select(Order, Student)
                .join(Student, Student.id == Order.student_id)
                .where(
                    Order.tenant_id == tenant.id,
                    Order.created_by_account_id == account.id,
                    Order.client_request_id == request_key,
                )
                .options(
                    selectinload(Order.items).selectinload(OrderItem.product),
                    selectinload(Order.items).selectinload(OrderItem.digital_codes),
                    selectinload(Order.items).selectinload(OrderItem.warehouse),
                    selectinload(Order.items).selectinload(OrderItem.reserved_warehouse),
                    selectinload(Order.status_history),
                )
            )
        ).one_or_none()
        if existing_row is not None:
            existing_order, existing_student = existing_row
            existing_quantities: dict[UUID, int] = {}
            for item in existing_order.items:
                product_id = UUID(str(item.product_id))
                existing_quantities[product_id] = (
                    existing_quantities.get(product_id, 0) + item.quantity
                )
            if (
                existing_order.student_id != student.id
                or existing_order.comment != payload.comment
                or existing_quantities != quantities
            ):
                raise MiniAppStoreError(
                    "Этот ключ запроса уже использован для другого заказа",
                    status_code=409,
                )
            existing_wallet = await db.scalar(
                select(Wallet).where(
                    Wallet.tenant_id == tenant.id,
                    Wallet.student_id == student.id,
                )
            )
            if existing_wallet is None:
                raise MiniAppStoreError("Кошелек ученика не найден", status_code=409)
            await db.execute(
                delete(StudentCartItem).where(
                    StudentCartItem.tenant_id == tenant.id,
                    StudentCartItem.student_id == student.id,
                    StudentCartItem.product_id.in_(quantities),
                )
            )
            await db.commit()
            order_read = _order_to_read(existing_order, existing_student)
            return MiniAppOrderCreatedRead(
                order=order_read,
                items=order_read.items,
                balance_after=existing_wallet.balance,
            )

    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    if wallet is None:
        raise MiniAppStoreError("Кошелек ученика не найден", status_code=409)

    products = (
        (
            await db.scalars(
                select(Product)
                .where(
                    Product.tenant_id == tenant.id,
                    Product.id.in_(quantities),
                    Product.status == ProductStatus.ACTIVE,
                )
                .options(
                    selectinload(Product.inventory_items).selectinload(
                        WarehouseInventory.warehouse
                    ),
                    selectinload(Product.digital_codes),
                )
            )
        )
        .unique()
        .all()
    )
    products_by_id = {UUID(str(product.id)): product for product in products}
    requested_product_ids = set(quantities)
    missing_ids = [
        product_id for product_id in requested_product_ids if product_id not in products_by_id
    ]
    if missing_ids:
        raise MiniAppStoreError("Один или несколько товаров недоступны", status_code=404)

    fulfillment_types = {product.fulfillment_type for product in products}
    if len(fulfillment_types) != 1:
        raise MiniAppStoreError(
            "Товары с кодами и товары со склада нужно оформить отдельными заказами",
            status_code=409,
        )
    is_digital_order = fulfillment_types == {ProductFulfillmentType.DIGITAL_CODE}

    total_astrocoins = sum(
        products_by_id[product_id].price_astrocoins * quantity
        for product_id, quantity in quantities.items()
    )
    if wallet.balance < total_astrocoins:
        raise MiniAppStoreError(
            "Недостаточно астрокоинов для оформления заказа",
            status_code=409,
        )

    locked_inventories: list[WarehouseInventory] = []
    if not is_digital_order:
        locked_inventories = list(
            (
                await db.scalars(
                    select(WarehouseInventory)
                    .where(
                        WarehouseInventory.tenant_id == tenant.id,
                        WarehouseInventory.product_id.in_(requested_product_ids),
                        WarehouseInventory.is_active.is_(True),
                    )
                    .order_by(WarehouseInventory.product_id, WarehouseInventory.id)
                    .with_for_update()
                    .options(
                        selectinload(WarehouseInventory.product),
                        selectinload(WarehouseInventory.warehouse),
                    )
                )
            )
            .unique()
            .all()
        )
    inventories_by_product: dict[UUID, list[WarehouseInventory]] = {}
    for inventory in locked_inventories:
        inventories_by_product.setdefault(UUID(str(inventory.product_id)), []).append(inventory)

    available_codes_by_product: dict[UUID, list[ProductCode]] = {}
    if is_digital_order:
        locked_codes = (
            await db.scalars(
                select(ProductCode)
                .where(
                    ProductCode.tenant_id == tenant.id,
                    ProductCode.product_id.in_(requested_product_ids),
                    ProductCode.status == ProductCodeStatus.AVAILABLE,
                )
                .order_by(ProductCode.product_id, ProductCode.created_at, ProductCode.id)
                .with_for_update()
            )
        ).all()
        for code in locked_codes:
            available_codes_by_product.setdefault(UUID(str(code.product_id)), []).append(code)

    order_plan: list[
        tuple[Product, int, WarehouseInventory | None, list[ProductCode]]
    ] = []
    for product_id, quantity in quantities.items():
        product = products_by_id[product_id]
        if is_digital_order:
            codes = available_codes_by_product.get(product_id, [])[:quantity]
            if len(codes) < quantity:
                raise MiniAppStoreError(
                    f"Для товара «{product.name}» осталось недостаточно кодов",
                    status_code=409,
                )
            order_plan.append((product, quantity, None, codes))
            continue
        reservation_inventory = choose_inventory_for_reservation(
            inventories_by_product.get(product_id, []),
            quantity=quantity,
            venue_id=student.venue_id,
        )
        if reservation_inventory is None:
            await schedule_staff_notification(
                db,
                tenant=tenant,
                event_key="orders.insufficient_stock",
                title="Не хватает товара для заказа",
                facts=[
                    ("Ученик", student.display_name),
                    ("Товар", product.name),
                    ("Нужно", f"{quantity} шт."),
                ],
                view="admin",
                button_label="Проверить остатки",
            )
            raise MiniAppStoreError(
                f"Товара «{product.name}» недостаточно на одном из складов",
                status_code=409,
            )
        order_plan.append((product, quantity, reservation_inventory, []))

    last_order_number = await db.scalar(
        select(func.max(Order.order_number)).where(Order.tenant_id == tenant.id)
    )
    order_number = int(last_order_number or 0) + 1
    order = Order(
        tenant_id=tenant.id,
        student_id=student.id,
        created_by_account_id=account.id,
        order_number=order_number,
        status=(OrderStatus.ISSUED_TO_STUDENT if is_digital_order else OrderStatus.RESERVED),
        total_astrocoins=total_astrocoins,
        teacher_name=student.teacher_name,
        venue_name=student.venue_name,
        comment=payload.comment,
        client_request_id=request_key,
    )
    db.add(order)
    await db.flush()

    response_items: list[MiniAppOrderItemRead] = []
    sheets_items: list[dict[str, object]] = []
    low_stock_events: list[tuple[Product, WarehouseInventory]] = []
    low_code_events: list[tuple[Product, int]] = []
    issued_codes: list[str] = []
    for product, quantity, reservation_inventory, selected_codes in order_plan:
        if reservation_inventory is not None:
            try:
                reserve_inventory(reservation_inventory, quantity)
            except WarehouseServiceError as exc:
                await schedule_staff_notification(
                    db,
                    tenant=tenant,
                    event_key="orders.insufficient_stock",
                    title="Не удалось зарезервировать товар",
                    message=str(exc),
                    facts=[
                        ("Ученик", student.display_name),
                        ("Товар", product.name),
                        ("Нужно", f"{quantity} шт."),
                    ],
                    view="admin",
                    button_label="Проверить остатки",
                )
                raise MiniAppStoreError(str(exc), status_code=409) from exc
            free_quantity = max(available_for_reservation(reservation_inventory), 0)
            if free_quantity <= 5 and not reservation_inventory.low_stock_notified:
                reservation_inventory.low_stock_notified = True
                low_stock_events.append((product, reservation_inventory))
            elif free_quantity > 5:
                reservation_inventory.low_stock_notified = False

        total_price = product.price_astrocoins * quantity
        order_item = OrderItem(
            tenant_id=tenant.id,
            order_id=order.id,
            product_id=product.id,
            quantity=quantity,
            warehouse_id=None,
            reserved_warehouse_id=(
                reservation_inventory.warehouse_id if reservation_inventory else None
            ),
            unit_price_astrocoins=product.price_astrocoins,
            total_price_astrocoins=total_price,
        )
        db.add(order_item)
        await db.flush()
        if reservation_inventory is not None:
            db.add(
                build_stock_movement(
                    inventory=reservation_inventory,
                    movement_type=StockMovementType.RESERVE,
                    quantity=quantity,
                    actor_account_id=account.id,
                    order_id=order.id,
                    from_warehouse_id=reservation_inventory.warehouse_id,
                    comment=f"Предварительный резерв заказа №{order_number}",
                )
            )
        for code in selected_codes:
            code.status = ProductCodeStatus.ISSUED
            code.order_item_id = order_item.id
            code.issued_to_student_id = student.id
            code.issued_at = datetime.now(UTC)
            issued_codes.append(code.code)
        if selected_codes:
            available_before = len(available_codes_by_product.get(UUID(str(product.id)), []))
            available_after = available_before - len(selected_codes)
            if available_after <= 5 and not product.digital_codes_low_notified:
                product.digital_codes_low_notified = True
                low_code_events.append((product, available_after))
            elif available_after > 5:
                product.digital_codes_low_notified = False
        response_items.append(
            MiniAppOrderItemRead(
                id=UUID(str(order_item.id)),
                product_id=UUID(str(product.id)),
                product_name=product.name,
                quantity=quantity,
                unit_price_astrocoins=product.price_astrocoins,
                total_price_astrocoins=total_price,
                warehouse_id=None,
                warehouse_name=None,
                suggested_warehouse_id=(
                    UUID(str(reservation_inventory.warehouse_id))
                    if reservation_inventory
                    else None
                ),
                suggested_warehouse_name=(
                    reservation_inventory.warehouse.name
                    if reservation_inventory and reservation_inventory.warehouse
                    else None
                ),
                fulfillment_type=product.fulfillment_type,
                issued_codes=[code.code for code in selected_codes],
                is_picked=False,
            )
        )
        sheets_items.append(
            order_item_mapping(
                product_id=str(product.id),
                product_name=product.name,
                quantity=quantity,
                warehouse_id=None,
                warehouse_name=None,
                unit_price_astrocoins=product.price_astrocoins,
                total_price_astrocoins=total_price,
            )
        )

    wallet.balance -= total_astrocoins
    db.add(
        AstrocoinLedgerEntry(
            tenant_id=tenant.id,
            wallet_id=wallet.id,
            student_id=student.id,
            actor_account_id=account.id,
            idempotency_key=f"order:{order.id}:debit",
            direction=LedgerDirection.DEBIT,
            amount=total_astrocoins,
            reason=f"Покупка в магазине, заказ №{order_number}",
            comment=payload.comment,
        )
    )
    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=None,
            to_status=order.status,
            comment=(
                "Цифровой товар оплачен и готов к использованию"
                if is_digital_order
                else "Заказ создан в приложении Algo MAX"
            ),
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_order.created",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order_number,
                "student_id": str(student.id),
                "total_astrocoins": total_astrocoins,
                "items": [
                    {
                        "product_id": str(product.id),
                        "quantity": quantity,
                        "warehouse_id": None,
                        "reserved_warehouse_id": (
                            str(reservation_inventory.warehouse_id)
                            if reservation_inventory
                            else None
                        ),
                    }
                    for product, quantity, reservation_inventory, _ in order_plan
                ],
            },
        )
    )
    await db.execute(
        delete(StudentCartItem).where(
            StudentCartItem.tenant_id == tenant.id,
            StudentCartItem.student_id == student.id,
            StudentCartItem.product_id.in_(requested_product_ids),
        )
    )

    await db.commit()
    await db.refresh(order)
    await db.refresh(wallet)
    for product, inventory in low_stock_events:
        await schedule_low_stock_notification(
            db,
            tenant=tenant,
            product=product,
            inventory=inventory,
        )
    for product, available_codes in low_code_events:
        await schedule_low_digital_codes_notification(
            db,
            tenant=tenant,
            product=product,
            available_codes=available_codes,
        )
    status_history = await _order_status_history_for_order(
        db,
        tenant_id=tenant.id,
        order_id=order.id,
    )
    _sync_order_to_sheets(
        tenant_slug=tenant.slug,
        order=order,
        student=student,
        account=account,
        items=sheets_items,
        comment=payload.comment,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        balance_after=wallet.balance,
        issued_codes=issued_codes,
    )
    await schedule_staff_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        event_key="orders.issued" if is_digital_order else "orders.created",
        title="Код выдан автоматически" if is_digital_order else "Новый заказ",
        actor_name=account.display_name,
        message=(
            "Цифровой товар оплачен и выдан ученику."
            if is_digital_order
            else "Заказ зарезервирован и ожидает подтверждения склада."
        ),
    )

    return MiniAppOrderCreatedRead(
        order=_order_to_read(
            order,
            student,
            items=response_items,
            status_history=status_history,
        ),
        items=response_items,
        balance_after=wallet.balance,
    )


async def assign_miniapp_order_warehouses(
    db: AsyncSession,
    *,
    order_id: UUID,
    payload: MiniAppOrderWarehouseAssignmentCreate,
    default_tenant_slug: str,
) -> MiniAppOrderActionRead:
    tenant, account, order, student, staff_role = await _load_order_action_context(
        db,
        order_id=order_id,
        payload=MiniAppOrderActionCreate(
            max_user_id=payload.max_user_id,
            tenant_slug=payload.tenant_slug,
            comment=payload.comment,
        ),
        default_tenant_slug=default_tenant_slug,
        require_manager=True,
    )
    if staff_role not in STORE_ADMIN_ROLES:
        raise MiniAppStoreError(
            "Назначить склад может только администратор или директор",
            status_code=403,
        )
    previous_status = order.status
    if previous_status not in {
        OrderStatus.CREATED,
        OrderStatus.RESERVED,
        OrderStatus.PROBLEM,
    }:
        raise MiniAppStoreError(
            "Склад можно назначить зарезервированному или проблемному заказу",
            status_code=409,
        )
    assignments = {
        UUID(str(item.product_id)): UUID(str(item.warehouse_id)) for item in payload.items
    }
    if len(assignments) != len(payload.items):
        raise MiniAppStoreError("Для каждого товара укажите один склад")

    order_product_ids = {UUID(str(item.product_id)) for item in order.items}
    if set(assignments) != order_product_ids:
        raise MiniAppStoreError("Назначьте склад для каждой позиции заказа")

    reservation_plan: list[tuple[OrderItem, WarehouseInventory | None, WarehouseInventory]] = []
    for item in order.items:
        target_warehouse_id = assignments[UUID(str(item.product_id))]
        source_warehouse_id = item.warehouse_id or item.reserved_warehouse_id
        warehouse_ids = {UUID(str(target_warehouse_id))}
        if source_warehouse_id is not None:
            warehouse_ids.add(UUID(str(source_warehouse_id)))
        inventory_rows = list(
            (
                await db.scalars(
                    select(WarehouseInventory)
                    .where(
                        WarehouseInventory.tenant_id == tenant.id,
                        WarehouseInventory.product_id == item.product_id,
                        WarehouseInventory.warehouse_id.in_(warehouse_ids),
                    )
                    .order_by(WarehouseInventory.id)
                    .with_for_update()
                    .options(selectinload(WarehouseInventory.warehouse))
                )
            )
            .unique()
            .all()
        )
        inventories_by_warehouse = {
            UUID(str(inventory.warehouse_id)): inventory for inventory in inventory_rows
        }
        target_inventory = inventories_by_warehouse.get(UUID(str(target_warehouse_id)))
        source_inventory = (
            inventories_by_warehouse.get(UUID(str(source_warehouse_id)))
            if source_warehouse_id is not None
            else None
        )
        product_name = item.product.name if item.product else str(item.product_id)
        if source_warehouse_id is not None and source_inventory is None:
            raise MiniAppStoreError(
                f"Не найден текущий резерв товара «{product_name}»",
                status_code=409,
            )
        additional_quantity = (
            0
            if source_inventory is not None and source_inventory.warehouse_id == target_warehouse_id
            else item.quantity
        )
        if (
            target_inventory is None
            or not target_inventory.is_active
            or available_for_reservation(target_inventory) < additional_quantity
        ):
            await schedule_staff_order_notification(
                db,
                tenant=tenant,
                order=order,
                student=student,
                event_key="orders.insufficient_stock",
                title="Не хватает товара на выбранном складе",
                actor_name=account.display_name,
                extra_facts=[("Товар", product_name)],
            )
            raise MiniAppStoreError(
                f"На выбранном складе недостаточно товара «{product_name}»",
                status_code=409,
            )
        reservation_plan.append((item, source_inventory, target_inventory))

    response_items: list[MiniAppOrderItemRead] = []
    sheets_items: list[dict[str, object]] = []
    low_stock_events: list[tuple[Product, WarehouseInventory]] = []
    for item, source_inventory, target_inventory in reservation_plan:
        product_name = item.product.name if item.product else str(item.product_id)
        moved_reservation = (
            source_inventory is None
            or source_inventory.warehouse_id != target_inventory.warehouse_id
        )
        if moved_reservation:
            try:
                if source_inventory is not None:
                    release_reservation(source_inventory, item.quantity)
                reserve_inventory(target_inventory, item.quantity)
            except WarehouseServiceError as exc:
                await schedule_staff_order_notification(
                    db,
                    tenant=tenant,
                    order=order,
                    student=student,
                    event_key="orders.problem",
                    title="Не удалось назначить склад заказу",
                    actor_name=account.display_name,
                    message=str(exc),
                    extra_facts=[("Товар", product_name)],
                )
                raise MiniAppStoreError(str(exc), status_code=409) from exc
            if source_inventory is not None:
                if available_for_reservation(source_inventory) > 5:
                    source_inventory.low_stock_notified = False
                db.add(
                    build_stock_movement(
                        inventory=source_inventory,
                        movement_type=StockMovementType.RELEASE_RESERVE,
                        quantity=item.quantity,
                        actor_account_id=account.id,
                        order_id=order.id,
                        to_warehouse_id=source_inventory.warehouse_id,
                        comment=f"Перенос резерва заказа №{order.order_number}",
                    )
                )
            db.add(
                build_stock_movement(
                    inventory=target_inventory,
                    movement_type=StockMovementType.RESERVE,
                    quantity=item.quantity,
                    actor_account_id=account.id,
                    order_id=order.id,
                    from_warehouse_id=target_inventory.warehouse_id,
                    comment=payload.comment or f"Склад назначен заказу №{order.order_number}",
                )
            )

        free_quantity = max(available_for_reservation(target_inventory), 0)
        if free_quantity <= 5 and not target_inventory.low_stock_notified and item.product:
            target_inventory.low_stock_notified = True
            low_stock_events.append((item.product, target_inventory))
        elif free_quantity > 5:
            target_inventory.low_stock_notified = False
        item.warehouse_id = target_inventory.warehouse_id
        item.reserved_warehouse_id = None
        warehouse_name = target_inventory.warehouse.name if target_inventory.warehouse else None
        response_items.append(
            MiniAppOrderItemRead(
                id=UUID(str(item.id)),
                product_id=UUID(str(item.product_id)),
                product_name=product_name,
                quantity=item.quantity,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
                warehouse_id=UUID(str(target_inventory.warehouse_id)),
                warehouse_name=warehouse_name,
                is_picked=item.is_picked,
            )
        )
        sheets_items.append(
            order_item_mapping(
                product_id=str(item.product_id),
                product_name=product_name,
                quantity=item.quantity,
                warehouse_id=str(target_inventory.warehouse_id),
                warehouse_name=warehouse_name,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
            )
        )

    order.status = OrderStatus.AWAITING_DELIVERY

    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=previous_status,
            to_status=order.status,
            comment=payload.comment
            or (
                "Проблема устранена, склад назначен. Заказ ожидает доставки"
                if previous_status == OrderStatus.PROBLEM
                else "Склад назначен. Заказ ожидает доставки"
            ),
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_order.warehouses_assigned",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order.order_number,
                "actor_role": staff_role.value,
                "items": [
                    {
                        "product_id": str(item.product_id),
                        "warehouse_id": str(target_inventory.warehouse_id),
                        "quantity": item.quantity,
                    }
                    for item, _source_inventory, target_inventory in reservation_plan
                ],
            },
        )
    )
    await db.commit()
    await db.refresh(order)
    for product, inventory in low_stock_events:
        await schedule_low_stock_notification(
            db,
            tenant=tenant,
            product=product,
            inventory=inventory,
        )
    status_history = await _order_status_history_for_order(
        db,
        tenant_id=tenant.id,
        order_id=order.id,
    )
    _sync_order_to_sheets(
        tenant_slug=tenant.slug,
        order=order,
        student=student,
        account=account,
        items=sheets_items,
        comment=payload.comment,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
    )
    return MiniAppOrderActionRead(
        order=_order_to_read(
            order,
            student,
            items=response_items,
            status_history=status_history,
        ),
        balance_after=None,
    )


async def set_miniapp_order_items_picked(
    db: AsyncSession,
    *,
    payload: MiniAppOrderItemPickBatchUpdate,
    default_tenant_slug: str,
) -> MiniAppOrderItemPickBatchRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=FULFILLMENT_MANAGER_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на комплектацию заказа", status_code=403)

    update_keys = [
        (UUID(str(item.order_id)), UUID(str(item.order_item_id)))
        for item in payload.items
    ]
    if len(set(update_keys)) != len(update_keys):
        raise MiniAppStoreError("Позиция заказа указана несколько раз")
    order_ids = {order_id for order_id, _item_id in update_keys}
    order_rows = (
        await db.execute(
            select(Order, Student)
            .join(Student, Student.id == Order.student_id)
            .where(Order.tenant_id == tenant.id, Order.id.in_(order_ids))
            .order_by(Order.id)
            .with_for_update()
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
            )
        )
    ).all()
    orders_by_id = {UUID(str(order.id)): (order, student) for order, student in order_rows}
    if set(orders_by_id) != order_ids:
        raise MiniAppStoreError("Один или несколько заказов не найдены", status_code=404)

    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=staff_role,
    )
    pending_updates: list[tuple[Order, OrderItem, bool]] = []
    for item_update, (order_id, order_item_id) in zip(payload.items, update_keys, strict=True):
        order, student = orders_by_id[order_id]
        if venue_scope_ids is not None and student.venue_id not in venue_scope_ids:
            raise MiniAppStoreError("Нет доступа к заказу другой площадки", status_code=403)
        if order.status != OrderStatus.AWAITING_DELIVERY:
            raise MiniAppStoreError(
                "Комплектацию можно менять только до доставки на площадку",
                status_code=409,
            )
        order_item = next(
            (item for item in order.items if UUID(str(item.id)) == order_item_id),
            None,
        )
        if order_item is None:
            raise MiniAppStoreError("Позиция заказа не найдена", status_code=404)
        if (
            order_item.product
            and order_item.product.fulfillment_type == ProductFulfillmentType.DIGITAL_CODE
        ):
            raise MiniAppStoreError("Цифровой товар не требует комплектации", status_code=409)
        if order_item.warehouse_id is None:
            raise MiniAppStoreError(
                "Сначала подтвердите склад для каждой позиции заказа",
                status_code=409,
            )
        pending_updates.append((order, order_item, item_update.is_picked))

    picked_at = datetime.now(UTC)
    for order, order_item, is_picked in pending_updates:
        order_item.is_picked = is_picked
        order_item.picked_at = picked_at if is_picked else None
        db.add(
            AuditLog(
                tenant_id=tenant.id,
                actor_account_id=account.id,
                action="miniapp_order.item_pick_updated",
                entity_type="order_item",
                entity_id=str(order_item.id),
                payload={
                    "order_id": str(order.id),
                    "order_number": order.order_number,
                    "product_id": str(order_item.product_id),
                    "is_picked": is_picked,
                    "actor_role": staff_role.value,
                    "batch": True,
                },
            )
        )
    await db.commit()
    return MiniAppOrderItemPickBatchRead(updated_items=len(pending_updates))


async def mark_miniapp_order_delivered_to_venue(
    db: AsyncSession,
    *,
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    default_tenant_slug: str,
) -> MiniAppOrderActionRead:
    tenant, account, order, student, staff_role = await _load_order_action_context(
        db,
        order_id=order_id,
        payload=payload,
        default_tenant_slug=default_tenant_slug,
        require_manager=True,
    )
    if staff_role not in FULFILLMENT_MANAGER_ROLES:
        raise MiniAppStoreError("Нет прав на доставку заказа", status_code=403)
    if order.status != OrderStatus.AWAITING_DELIVERY:
        raise MiniAppStoreError(
            "Доставленным на площадку можно отметить только заказ в пути",
            status_code=409,
        )
    if any(
        item.product
        and item.product.fulfillment_type == ProductFulfillmentType.WAREHOUSE
        and item.warehouse_id is None
        for item in order.items
    ):
        raise MiniAppStoreError(
            "Сначала подтвердите склад для каждой позиции заказа",
            status_code=409,
        )
    if any(
        item.product
        and item.product.fulfillment_type == ProductFulfillmentType.WAREHOUSE
        and not item.is_picked
        for item in order.items
    ):
        raise MiniAppStoreError(
            "Сначала подтвердите сборку всех товаров",
            status_code=409,
        )

    order.status = OrderStatus.DELIVERED_TO_VENUE
    comment = payload.comment or "Заказ доставлен на площадку"
    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=OrderStatus.AWAITING_DELIVERY,
            to_status=order.status,
            comment=comment,
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_order.delivered_to_venue",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order.order_number,
                "student_id": str(order.student_id),
                "venue_name": order.venue_name,
                "actor_role": staff_role.value,
            },
        )
    )
    await db.commit()
    await db.refresh(order)
    status_history = await _order_status_history_for_order(
        db,
        tenant_id=tenant.id,
        order_id=order.id,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
    )
    await schedule_staff_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        event_key="orders.delivered_to_venue",
        title="Заказ доставлен на площадку",
        actor_name=account.display_name,
        extra_facts=[("Площадка", order.venue_name or "Не указана")],
    )
    return MiniAppOrderActionRead(
        order=_order_to_read(order, student, status_history=status_history),
        balance_after=None,
    )


async def cancel_miniapp_order(
    db: AsyncSession,
    *,
    order_id: UUID,
    payload: MiniAppOrderCancelCreate,
    default_tenant_slug: str,
) -> MiniAppOrderActionRead:
    reason = payload.reason.strip()
    custom_reason = (payload.custom_reason or "").strip()
    if reason.casefold() == "другое":
        if not custom_reason:
            raise MiniAppStoreError("Укажите причину отмены")
        cancellation_reason = custom_reason
    else:
        cancellation_reason = reason

    tenant, account, order, student, staff_role = await _load_order_action_context(
        db,
        order_id=order_id,
        payload=MiniAppOrderActionCreate(
            max_user_id=payload.max_user_id,
            tenant_slug=payload.tenant_slug,
            comment=cancellation_reason,
        ),
        default_tenant_slug=default_tenant_slug,
        require_manager=False,
    )
    if staff_role not in STORE_ADMIN_ROLES:
        raise MiniAppStoreError(
            "Отменить заказ может только администратор или директор",
            status_code=403,
        )
    if order.status not in OPEN_ORDER_STATUSES:
        raise MiniAppStoreError("Отменить можно только заказ в работе", status_code=409)

    out_of_stock_product_ids: set[UUID] = set()
    if reason.casefold() == "товар закончился":
        if staff_role not in STORE_ADMIN_ROLES:
            raise MiniAppStoreError(
                "Причину «Товар закончился» может выбрать только администратор",
                status_code=403,
            )
        order_product_ids = {UUID(str(item.product_id)) for item in order.items}
        selected_product_id = payload.out_of_stock_product_id
        if selected_product_id is None:
            if len(order_product_ids) != 1:
                raise MiniAppStoreError("Укажите, какой товар закончился")
            selected_product_id = next(iter(order_product_ids))
        if selected_product_id not in order_product_ids:
            raise MiniAppStoreError("Выбранного товара нет в заказе")
        out_of_stock_product_ids.add(selected_product_id)

    for item in order.items:
        if item.warehouse_id is None and item.reserved_warehouse_id is None:
            continue
        inventory = await _inventory_for_order_item(
            db,
            tenant_id=tenant.id,
            item=item,
            allow_provisional=True,
        )
        try:
            release_reservation(inventory, item.quantity)
        except WarehouseServiceError as exc:
            await schedule_staff_order_notification(
                db,
                tenant=tenant,
                order=order,
                student=student,
                event_key="orders.problem",
                title="Не удалось отменить заказ",
                actor_name=account.display_name,
                message=str(exc),
            )
            raise MiniAppStoreError(str(exc), status_code=409) from exc
        if available_for_reservation(inventory) > 5:
            inventory.low_stock_notified = False
        item.reserved_warehouse_id = None
        db.add(
            build_stock_movement(
                inventory=inventory,
                movement_type=StockMovementType.RELEASE_RESERVE,
                quantity=item.quantity,
                actor_account_id=account.id,
                order_id=order.id,
                to_warehouse_id=inventory.warehouse_id,
                comment=cancellation_reason,
            )
        )

    if out_of_stock_product_ids:
        inventory_rows = (
            await db.scalars(
                select(WarehouseInventory)
                .where(
                    WarehouseInventory.tenant_id == tenant.id,
                    WarehouseInventory.product_id.in_(out_of_stock_product_ids),
                    WarehouseInventory.is_active.is_(True),
                )
                .with_for_update()
            )
        ).all()
        for inventory in inventory_rows:
            inventory.available_quantity = inventory.reserved_quantity
            inventory.low_stock_notified = True

    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == order.student_id)
        .with_for_update()
    )
    if wallet is None:
        raise MiniAppStoreError("Кошелек ученика не найден", status_code=409)

    wallet.balance += order.total_astrocoins
    db.add(
        AstrocoinLedgerEntry(
            tenant_id=tenant.id,
            wallet_id=wallet.id,
            student_id=order.student_id,
            actor_account_id=account.id,
            idempotency_key=f"order:{order.id}:refund",
            direction=LedgerDirection.REVERSAL,
            amount=order.total_astrocoins,
            reason=f"Возврат за отмену заказа №{order.order_number}",
            comment=cancellation_reason,
        )
    )

    previous_status = order.status
    order.status = OrderStatus.CANCELLED
    order.cancellation_reason = cancellation_reason
    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=previous_status,
            to_status=order.status,
            comment=cancellation_reason,
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_order.cancelled",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order.order_number,
                "student_id": str(order.student_id),
                "refund_astrocoins": order.total_astrocoins,
                "reason": cancellation_reason,
                "actor_role": staff_role.value if staff_role else "student_access",
            },
        )
    )
    await db.commit()
    await db.refresh(order)
    await db.refresh(wallet)
    status_history = await _order_status_history_for_order(
        db,
        tenant_id=tenant.id,
        order_id=order.id,
    )
    _sync_order_to_sheets(
        tenant_slug=tenant.slug,
        order=order,
        student=student,
        account=account,
        comment=cancellation_reason,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        balance_after=wallet.balance,
    )
    await schedule_staff_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        event_key="orders.cancelled",
        title="Заказ отменен",
        actor_name=account.display_name,
        extra_facts=[("Причина", cancellation_reason)],
    )
    if out_of_stock_product_ids:
        product_names = ", ".join(
            item.product.name
            for item in order.items
            if UUID(str(item.product_id)) in out_of_stock_product_ids and item.product
        )
        await schedule_staff_order_notification(
            db,
            tenant=tenant,
            order=order,
            student=student,
            event_key="orders.stock_zeroed",
            title="Остатки товара обнулены",
            actor_name=account.display_name,
            extra_facts=[("Товар", product_names)],
        )
    return MiniAppOrderActionRead(
        order=_order_to_read(order, student, status_history=status_history),
        balance_after=wallet.balance,
    )


async def issue_miniapp_order(
    db: AsyncSession,
    *,
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    default_tenant_slug: str,
) -> MiniAppOrderActionRead:
    tenant, account, order, student, staff_role = await _load_order_action_context(
        db,
        order_id=order_id,
        payload=payload,
        default_tenant_slug=default_tenant_slug,
        require_manager=True,
    )
    if order.status != OrderStatus.TRANSFERRED_TO_TEACHER:
        raise MiniAppStoreError(
            "Передать заказ ученику можно после получения учителем",
            status_code=409,
        )

    for item in order.items:
        inventory = await _inventory_for_order_item(db, tenant_id=tenant.id, item=item)
        try:
            issue_reserved_inventory(inventory, item.quantity)
        except WarehouseServiceError as exc:
            await schedule_staff_order_notification(
                db,
                tenant=tenant,
                order=order,
                student=student,
                event_key="orders.problem",
                title="Не удалось выдать заказ",
                actor_name=account.display_name,
                message=str(exc),
            )
            raise MiniAppStoreError(str(exc), status_code=409) from exc
        if available_for_reservation(inventory) > 5:
            inventory.low_stock_notified = False
        db.add(
            build_stock_movement(
                inventory=inventory,
                movement_type=StockMovementType.ISSUE,
                quantity=item.quantity,
                actor_account_id=account.id,
                order_id=order.id,
                from_warehouse_id=inventory.warehouse_id,
                comment=payload.comment or f"Выдача заказа №{order.order_number}",
            )
        )

    previous_status = order.status
    order.status = OrderStatus.ISSUED_TO_STUDENT
    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=previous_status,
            to_status=order.status,
            comment=payload.comment,
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_order.issued",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order.order_number,
                "student_id": str(order.student_id),
                "actor_role": staff_role.value if staff_role else None,
            },
        )
    )
    await db.commit()
    await db.refresh(order)
    status_history = await _order_status_history_for_order(
        db,
        tenant_id=tenant.id,
        order_id=order.id,
    )
    _sync_order_to_sheets(
        tenant_slug=tenant.slug,
        order=order,
        student=student,
        account=account,
        comment=payload.comment,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
    )
    await schedule_staff_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        event_key="orders.issued",
        title="Заказ выдан ученику",
        actor_name=account.display_name,
    )
    return MiniAppOrderActionRead(
        order=_order_to_read(order, student, status_history=status_history),
        balance_after=None,
    )


async def transfer_miniapp_order_to_teacher(
    db: AsyncSession,
    *,
    order_id: UUID,
    payload: MiniAppOrderActionCreate,
    default_tenant_slug: str,
) -> MiniAppOrderActionRead:
    tenant, account, order, student, staff_role = await _load_order_action_context(
        db,
        order_id=order_id,
        payload=payload,
        default_tenant_slug=default_tenant_slug,
        require_manager=True,
    )
    if order.status != OrderStatus.DELIVERED_TO_VENUE:
        raise MiniAppStoreError(
            "Учитель может получить заказ после доставки на площадку",
            status_code=409,
        )
    if any(item.warehouse_id is None for item in order.items):
        raise MiniAppStoreError("Сначала подтвердите склад для каждой позиции", status_code=409)

    order.status = OrderStatus.TRANSFERRED_TO_TEACHER
    comment = payload.comment or "Учитель получил заказ"
    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=OrderStatus.DELIVERED_TO_VENUE,
            to_status=order.status,
            comment=comment,
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_order.transferred_to_teacher",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order.order_number,
                "student_id": str(order.student_id),
                "actor_role": staff_role.value if staff_role else None,
            },
        )
    )
    await db.commit()
    await db.refresh(order)
    status_history = await _order_status_history_for_order(
        db,
        tenant_id=tenant.id,
        order_id=order.id,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
    )
    await schedule_staff_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        event_key="orders.transferred",
        title="Учитель получил заказ",
        actor_name=account.display_name,
        extra_facts=[("Преподаватель", order.teacher_name or "Не указан")],
    )
    await schedule_teacher_order_transfer_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
    )
    return MiniAppOrderActionRead(
        order=_order_to_read(order, student, status_history=status_history),
        balance_after=None,
    )


async def accrue_miniapp_astrocoins(
    db: AsyncSession,
    *,
    payload: MiniAppAccrualCreate,
    default_tenant_slug: str,
) -> MiniAppAccrualRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug).with_for_update())
    if tenant is None:
        raise MiniAppStoreError("Партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=COIN_ACCRUAL_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на начисление астрокоинов", status_code=403)

    if not payload.custom_reason:
        stored_rules = list(
            (
                await db.scalars(
                    select(AstrocoinAccrualRule).where(
                        AstrocoinAccrualRule.tenant_id == tenant.id,
                        AstrocoinAccrualRule.is_active.is_(True),
                    )
                )
            ).all()
        )
        if stored_rules and not any(
            rule.reason == payload.reason.strip() and rule.amount == payload.amount
            for rule in stored_rules
        ):
            raise MiniAppStoreError(
                "Выбранная причина связана с другой суммой. Обновите данные и повторите.",
                status_code=409,
            )

    unique_student_ids = list(
        dict.fromkeys(UUID(str(student_id)) for student_id in payload.student_ids)
    )
    students = (
        await db.scalars(
            select(Student).where(
                Student.tenant_id == tenant.id,
                Student.id.in_(unique_student_ids),
                Student.status == StudentStatus.ACTIVE,
            )
        )
    ).all()
    if len(students) != len(unique_student_ids):
        raise MiniAppStoreError("Один или несколько учеников не найдены", status_code=404)
    if staff_role == StaffRole.TEACHER and any(
        not _teacher_owns_student(account, student) for student in students
    ):
        raise MiniAppStoreError("Нельзя начислять AC ученикам чужой группы", status_code=403)

    wallets = (
        await db.scalars(
            select(Wallet)
            .where(
                Wallet.tenant_id == tenant.id,
                Wallet.student_id.in_(unique_student_ids),
            )
            .order_by(Wallet.student_id)
            .with_for_update()
        )
    ).all()
    wallets_by_student = {wallet.student_id: wallet for wallet in wallets}

    request_key = payload.request_key.strip() if payload.request_key else None
    idempotency_keys = (
        {student.id: f"miniapp_accrual:{request_key}:{student.id}" for student in students}
        if request_key
        else {}
    )
    if request_key:
        existing_entries = (
            await db.scalars(
                select(AstrocoinLedgerEntry).where(
                    AstrocoinLedgerEntry.idempotency_key.startswith(
                        f"miniapp_accrual:{request_key}:"
                    )
                )
            )
        ).all()
        if existing_entries:
            expected_keys = set(idempotency_keys.values())
            actual_keys = {entry.idempotency_key for entry in existing_entries}
            valid_replay = actual_keys == expected_keys and all(
                entry.tenant_id == tenant.id
                and entry.actor_account_id == account.id
                and entry.direction == LedgerDirection.CREDIT
                and entry.amount == payload.amount
                and entry.reason == payload.reason
                and entry.comment == payload.comment
                for entry in existing_entries
            )
            if not valid_replay:
                raise MiniAppStoreError(
                    "Этот ключ запроса уже использован для другого начисления",
                    status_code=409,
                )
            return MiniAppAccrualRead(
                tenant_slug=tenant.slug,
                credited_students=len(students),
                amount=payload.amount,
                total_astrocoins=payload.amount * len(students),
            )

    for student in students:
        wallet = wallets_by_student.get(student.id)
        if wallet is None:
            wallet = Wallet(tenant_id=tenant.id, student_id=student.id, balance=0)
            db.add(wallet)
            await db.flush()
            wallets_by_student[student.id] = wallet

        wallet.balance += payload.amount
        db.add(
            AstrocoinLedgerEntry(
                tenant_id=tenant.id,
                wallet_id=wallet.id,
                student_id=student.id,
                actor_account_id=account.id,
                idempotency_key=(
                    idempotency_keys[student.id]
                    if request_key
                    else f"miniapp_accrual:{wallet.id}:{uuid4()}"
                ),
                direction=LedgerDirection.CREDIT,
                amount=payload.amount,
                reason=payload.reason,
                comment=payload.comment,
            )
        )

    total_astrocoins = payload.amount * len(students)
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_astrocoins.accrued",
            entity_type="astrocoin_accrual",
            entity_id=None,
            payload={
                "student_ids": [str(student.id) for student in students],
                "amount": payload.amount,
                "total_astrocoins": total_astrocoins,
                "reason": payload.reason,
                "custom_reason": payload.custom_reason,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.commit()

    return MiniAppAccrualRead(
        tenant_slug=tenant.slug,
        credited_students=len(students),
        amount=payload.amount,
        total_astrocoins=total_astrocoins,
    )


async def undo_miniapp_astrocoins(
    db: AsyncSession,
    *,
    payload: MiniAppAccrualUndoCreate,
    default_tenant_slug: str,
) -> MiniAppAccrualRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        raise MiniAppStoreError("Партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=COIN_ACCRUAL_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на отмену начисления", status_code=403)

    credit_prefix = f"miniapp_accrual:{payload.request_key}:"
    credits = (
        await db.scalars(
            select(AstrocoinLedgerEntry)
            .where(AstrocoinLedgerEntry.idempotency_key.startswith(credit_prefix))
            .with_for_update()
        )
    ).all()
    if not credits:
        raise MiniAppStoreError("Начисление для отмены не найдено", status_code=404)
    if any(
        entry.tenant_id != tenant.id
        or entry.actor_account_id != account.id
        or entry.direction != LedgerDirection.CREDIT
        for entry in credits
    ):
        raise MiniAppStoreError("Нельзя отменить это начисление", status_code=403)

    newest_allowed = datetime.now(UTC) - timedelta(minutes=5)
    if any(
        (entry.created_at if entry.created_at.tzinfo else entry.created_at.replace(tzinfo=UTC))
        < newest_allowed
        for entry in credits
    ):
        raise MiniAppStoreError("Время быстрой отмены истекло", status_code=409)

    undo_prefix = f"miniapp_accrual_undo:{payload.request_key}:"
    existing_undos = (
        await db.scalars(
            select(AstrocoinLedgerEntry).where(
                AstrocoinLedgerEntry.idempotency_key.startswith(undo_prefix)
            )
        )
    ).all()
    amount = credits[0].amount
    total = sum(entry.amount for entry in credits)
    if existing_undos:
        return MiniAppAccrualRead(
            tenant_slug=tenant.slug,
            credited_students=len(existing_undos),
            amount=-amount,
            total_astrocoins=-sum(entry.amount for entry in existing_undos),
        )

    student_ids = [entry.student_id for entry in credits]
    wallets = (
        await db.scalars(
            select(Wallet)
            .where(Wallet.tenant_id == tenant.id, Wallet.student_id.in_(student_ids))
            .with_for_update()
        )
    ).all()
    wallets_by_student = {wallet.student_id: wallet for wallet in wallets}
    for credit in credits:
        wallet = wallets_by_student.get(credit.student_id)
        if wallet is None or wallet.balance < credit.amount:
            raise MiniAppStoreError(
                "Начисление уже использовано и не может быть отменено",
                status_code=409,
            )
        wallet.balance -= credit.amount
        db.add(
            AstrocoinLedgerEntry(
                tenant_id=tenant.id,
                wallet_id=wallet.id,
                student_id=credit.student_id,
                actor_account_id=account.id,
                idempotency_key=f"{undo_prefix}{credit.student_id}",
                direction=LedgerDirection.DEBIT,
                amount=credit.amount,
                reason=f"Отмена: {credit.reason}"[:240],
                comment="Быстрая отмена начисления",
            )
        )

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_astrocoins.undone",
            entity_type="astrocoin_accrual",
            entity_id=None,
            payload={
                "request_key": payload.request_key,
                "student_ids": [str(student_id) for student_id in student_ids],
                "total_astrocoins": total,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.commit()
    return MiniAppAccrualRead(
        tenant_slug=tenant.slug,
        credited_students=len(credits),
        amount=-amount,
        total_astrocoins=-total,
    )


async def get_miniapp_accrual_report(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    date_from: date,
    date_to: date,
) -> MiniAppAccrualReportRead:
    if date_to < date_from:
        raise MiniAppStoreError("Дата окончания раньше даты начала")
    if (date_to - date_from).days > 366:
        raise MiniAppStoreError("Период отчета не должен превышать 366 дней")

    tenant = await get_tenant_by_slug(db, tenant_slug.strip().lower())
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=ACCRUAL_REPORT_ROLES,
    )
    if role is None:
        raise MiniAppStoreError(
            "Отчет доступен куратору, администратору и директору",
            status_code=403,
        )

    report_timezone = ZoneInfo(get_settings().app_timezone)
    started_at = datetime.combine(date_from, time.min, tzinfo=report_timezone).astimezone(UTC)
    ended_at = datetime.combine(
        date_to + timedelta(days=1),
        time.min,
        tzinfo=report_timezone,
    ).astimezone(UTC)
    rows = (
        await db.execute(
            select(AstrocoinLedgerEntry, Student, MaxAccount)
            .join(Student, Student.id == AstrocoinLedgerEntry.student_id)
            .join(MaxAccount, MaxAccount.id == AstrocoinLedgerEntry.actor_account_id)
            .where(
                AstrocoinLedgerEntry.tenant_id == tenant.id,
                AstrocoinLedgerEntry.direction == LedgerDirection.CREDIT,
                AstrocoinLedgerEntry.created_at >= started_at,
                AstrocoinLedgerEntry.created_at < ended_at,
            )
            .order_by(AstrocoinLedgerEntry.created_at.desc())
        )
    ).all()
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=role,
    )
    if venue_scope_ids is not None:
        rows = [row for row in rows if row[1].venue_id in venue_scope_ids]
    actor_ids = {entry.actor_account_id for entry, _student, _actor in rows}
    assignments = []
    if actor_ids:
        assignments = (
            await db.scalars(
                select(StaffRoleAssignment).where(
                    StaffRoleAssignment.tenant_id == tenant.id,
                    StaffRoleAssignment.account_id.in_(actor_ids),
                    StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                )
            )
        ).all()
    roles_by_actor: dict[UUID, StaffRole] = {}
    for candidate in STAFF_ROLE_PRIORITY:
        for assignment in assignments:
            if assignment.role == candidate:
                roles_by_actor.setdefault(assignment.account_id, candidate)

    entries = [
        MiniAppAccrualReportEntryRead(
            created_at=entry.created_at,
            teacher_id=UUID(str(actor.id)),
            teacher_name=(
                teacher_staff_name(actor)
                or actor.display_name
                or actor.username
                or str(actor.max_user_id)
            ),
            teacher_role=roles_by_actor.get(entry.actor_account_id),
            student_id=UUID(str(student.id)),
            student_name=student.display_name,
            group_name=student.group_name,
            amount=entry.amount,
            reason=entry.reason,
        )
        for entry, student, actor in rows
    ]
    return MiniAppAccrualReportRead(
        date_from=date_from,
        date_to=date_to,
        total_astrocoins=sum(entry.amount for entry in entries),
        entries=entries,
    )


async def set_miniapp_warehouse_preference(
    db: AsyncSession,
    *,
    payload: MiniAppWarehousePreferenceUpdate,
    default_tenant_slug: str,
) -> MiniAppWarehousePreferenceRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)
    role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if role is None:
        raise MiniAppStoreError(
            "Основной склад назначает администратор или директор",
            status_code=403,
        )
    warehouse = await db.scalar(
        select(Warehouse).where(
            Warehouse.tenant_id == tenant.id,
            Warehouse.id == payload.warehouse_id,
        )
    )
    if warehouse is None:
        raise MiniAppStoreError("Склад не найден", status_code=404)
    preference = await db.scalar(
        select(StaffWarehousePreference).where(
            StaffWarehousePreference.tenant_id == tenant.id,
            StaffWarehousePreference.account_id == account.id,
        )
    )
    if preference is None:
        preference = StaffWarehousePreference(
            tenant_id=tenant.id,
            account_id=account.id,
            warehouse_id=warehouse.id,
        )
        db.add(preference)
    else:
        preference.warehouse_id = warehouse.id
    await db.commit()
    return MiniAppWarehousePreferenceRead(
        warehouse_id=UUID(str(warehouse.id)),
        warehouse_name=warehouse.name,
    )


async def update_miniapp_access_link_status(
    db: AsyncSession,
    *,
    link_id: UUID,
    payload: MiniAppAccessStatusUpdate,
    default_tenant_slug: str,
) -> MiniAppAccessStatusRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    if payload.status not in {StudentAccessStatus.ACTIVE, StudentAccessStatus.REVOKED}:
        raise MiniAppStoreError("Поддерживаются только статусы active и revoked", status_code=400)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на управление связями доступа", status_code=403)

    link = await db.scalar(
        select(StudentAccessLink).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.id == link_id,
        )
    )
    if link is None:
        raise MiniAppStoreError("Связь доступа не найдена", status_code=404)
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=staff_role,
    )
    if venue_scope_ids is not None:
        student_venue_id = await db.scalar(
            select(Student.venue_id).where(
                Student.tenant_id == tenant.id,
                Student.id == link.student_id,
            )
        )
        if student_venue_id not in venue_scope_ids:
            raise MiniAppStoreError(
                "Нет доступа к связи ученика другой площадки",
                status_code=403,
            )

    if payload.status == StudentAccessStatus.ACTIVE and link.role == StudentAccessRole.STUDENT:
        parent_conditions = [
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.student_id == link.student_id,
            StudentAccessLink.role == StudentAccessRole.PARENT,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        ]
        if link.sponsor_access_link_id is not None:
            parent_conditions.append(StudentAccessLink.id == link.sponsor_access_link_id)
        active_parent_id = await db.scalar(
            select(StudentAccessLink.id).where(*parent_conditions).limit(1)
        )
        if active_parent_id is None:
            raise MiniAppStoreError(
                "Сначала восстановите родительскую связь, затем выдайте ребенку новый QR-код.",
                status_code=409,
            )

    previous_status = link.status
    link.status = payload.status
    revoked_at = datetime.now(UTC) if payload.status == StudentAccessStatus.REVOKED else None
    link.revoked_at = revoked_at
    link.revoked_reason = "admin" if revoked_at is not None else None
    revoked_child_links: list[StudentAccessLink] = []
    if revoked_at is not None and link.role == StudentAccessRole.PARENT:
        revoked_child_links = await revoke_dependent_student_links(
            db,
            parent_links=[link],
            revoked_at=revoked_at,
            reason="sponsor_admin_revoked",
        )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student_access_link.status_changed",
            entity_type="student_access_link",
            entity_id=str(link.id),
            payload={
                "student_id": str(link.student_id),
                "target_account_id": str(link.account_id),
                "role": link.role.value,
                "from_status": previous_status.value,
                "to_status": link.status.value,
                "actor_role": staff_role.value,
                "revoked_child_links": len(revoked_child_links),
            },
        )
    )
    await db.commit()
    await db.refresh(link)
    return MiniAppAccessStatusRead(
        student_id=UUID(str(link.student_id)),
        role=link.role,
        status=link.status,
    )


async def update_miniapp_staff_assignment(
    db: AsyncSession,
    *,
    payload: MiniAppStaffAssignmentUpdate,
    default_tenant_slug: str,
) -> MiniAppStaffAssignmentRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    if payload.status not in {AssignmentStatus.ACTIVE, AssignmentStatus.REVOKED}:
        raise MiniAppStoreError("Поддерживаются только статусы active и revoked", status_code=400)

    actor = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id))
    if actor is None:
        raise MiniAppStoreError("MAX-аккаунт администратора не найден", status_code=403)

    actor_roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=actor.id,
    )
    is_global_superadmin = StaffRole.SUPERADMIN in actor_roles
    is_partner_director = StaffRole.PARTNER_DIRECTOR in actor_roles
    if not actor_roles.intersection(STORE_ADMIN_ROLES) and not is_global_superadmin:
        raise MiniAppStoreError("Нет прав на управление сотрудниками", status_code=403)
    director_updates_existing_admin = (
        is_partner_director and payload.role == StaffRole.ADMIN
    )
    if (
        payload.role in ELEVATED_STAFF_ROLES
        and not is_global_superadmin
        and not director_updates_existing_admin
    ):
        raise MiniAppStoreError(
            "Управляющие роли может менять только суперадминистратор",
            status_code=403,
        )
    if payload.role == StaffRole.SUPERADMIN and not superadmin_identity_is_allowed(
        payload.target_max_user_id
    ):
        raise MiniAppStoreError(
            "Роль суперадминистра закреплена за настроенным MAX ID",
            status_code=403,
        )
    if (
        payload.role == StaffRole.SUPERADMIN
        and payload.status == AssignmentStatus.REVOKED
        and payload.target_max_user_id == configured_superadmin_max_user_id()
    ):
        raise MiniAppStoreError(
            "Роль основного суперадминистра нельзя отозвать в приложении",
            status_code=409,
        )

    target = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.target_max_user_id)
    )
    if director_updates_existing_admin and target is None:
        raise MiniAppStoreError(
            "Директор может только отзывать и восстанавливать существующих администраторов",
            status_code=403,
        )
    account_created = False
    if target is None:
        target = MaxAccount(
            max_user_id=payload.target_max_user_id,
            username=payload.username,
            display_name=payload.display_name,
        )
        db.add(target)
        await db.flush()
        account_created = True
    else:
        if payload.username is not None:
            target.username = payload.username
        if payload.display_name is not None:
            target.display_name = payload.display_name

    assignment = await db.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == target.id,
            StaffRoleAssignment.role == payload.role,
        )
    )

    if director_updates_existing_admin:
        if assignment is None:
            raise MiniAppStoreError(
                "Директор может только отзывать и восстанавливать существующих администраторов",
                status_code=403,
            )
        protected_target_role = await db.scalar(
            select(StaffRoleAssignment.role).where(
                StaffRoleAssignment.tenant_id == tenant.id,
                StaffRoleAssignment.account_id == target.id,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                StaffRoleAssignment.role.in_(
                    {StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR}
                ),
            )
        )
        if protected_target_role is not None:
            raise MiniAppStoreError(
                "Директор не может управлять ролями другого директора или суперадминистратора",
                status_code=403,
            )

    if (
        target.id == actor.id
        and payload.status == AssignmentStatus.REVOKED
        and payload.role in STORE_ADMIN_ROLES
    ):
        other_manager_roles = await db.scalar(
            select(func.count(StaffRoleAssignment.id)).where(
                StaffRoleAssignment.tenant_id == tenant.id,
                StaffRoleAssignment.account_id == actor.id,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                StaffRoleAssignment.role.in_(STORE_ADMIN_ROLES),
                StaffRoleAssignment.role != payload.role,
            )
        )
        if not other_manager_roles:
            raise MiniAppStoreError(
                "Нельзя отозвать собственную последнюю управляющую роль",
                status_code=409,
            )

    previous_status = assignment.status if assignment else None
    assignment_created = False
    if assignment is None:
        assignment = StaffRoleAssignment(
            tenant_id=tenant.id,
            account_id=target.id,
            role=payload.role,
            status=payload.status,
        )
        db.add(assignment)
        await db.flush()
        assignment_created = True
    else:
        assignment.status = payload.status

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=actor.id,
            action="staff_role_assignment.updated",
            entity_type="staff_role_assignment",
            entity_id=str(assignment.id),
            payload={
                "target_max_user_id": target.max_user_id,
                "role": assignment.role.value,
                "from_status": previous_status.value if previous_status else None,
                "to_status": assignment.status.value,
                "account_created": account_created,
                "assignment_created": assignment_created,
            },
        )
    )
    await db.commit()
    await db.refresh(assignment)
    await db.refresh(target)
    return MiniAppStaffAssignmentRead(
        id=UUID(str(assignment.id)),
        account_id=UUID(str(target.id)),
        max_user_id=target.max_user_id,
        username=target.username,
        display_name=target.display_name,
        role=assignment.role,
        status=assignment.status,
    )


async def update_miniapp_teacher_profile(
    db: AsyncSession,
    *,
    payload: MiniAppTeacherProfileUpdate,
    default_tenant_slug: str,
) -> MiniAppTeacherProfileRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount)
        .where(MaxAccount.max_user_id == payload.max_user_id)
        .with_for_update()
    )
    if account is None:
        raise MiniAppStoreError("Сначала подключите аккаунт в MAX", status_code=403)

    teacher_assignment = await db.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == account.id,
            StaffRoleAssignment.role == StaffRole.TEACHER,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
        )
    )
    if teacher_assignment is None:
        raise MiniAppStoreError("Активная роль преподавателя не найдена", status_code=403)

    first_name = _clean_teacher_profile_name_part(payload.first_name, field_label="имя")
    last_name = _clean_teacher_profile_name_part(payload.last_name, field_label="фамилию")
    candidate_name = f"{last_name} {first_name}"

    other_teacher_accounts = list(
        (
            await db.scalars(
                select(MaxAccount)
                .join(
                    StaffRoleAssignment,
                    StaffRoleAssignment.account_id == MaxAccount.id,
                )
                .where(
                    StaffRoleAssignment.tenant_id == tenant.id,
                    StaffRoleAssignment.role == StaffRole.TEACHER,
                    StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                    MaxAccount.id != account.id,
                    MaxAccount.staff_profile_completed_at.is_not(None),
                )
            )
        ).unique().all()
    )
    duplicate_account = next(
        (
            other
            for other in other_teacher_accounts
            if normalize_staff_name(teacher_staff_name(other))
            == normalize_staff_name(candidate_name)
        ),
        None,
    )
    if duplicate_account is not None:
        raise MiniAppStoreError(
            "Это ФИО уже связано с другим преподавателем. Обратитесь к администратору",
            status_code=409,
        )

    previous_name = teacher_staff_name(account)
    account.staff_first_name = first_name
    account.staff_last_name = last_name
    account.staff_profile_completed_at = datetime.now(UTC)
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="teacher_profile.updated",
            entity_type="max_account",
            entity_id=str(account.id),
            payload={
                "previous_name": previous_name,
                "current_name": candidate_name,
            },
        )
    )
    await db.commit()
    await db.refresh(account)
    return await _teacher_profile_read(db, tenant_id=tenant.id, account=account)


async def create_miniapp_staff_invitation(
    db: AsyncSession,
    *,
    payload: MiniAppStaffInvitationCreate,
    default_tenant_slug: str,
) -> MiniAppStaffInvitationRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await db.scalar(
        select(Tenant)
        .options(selectinload(Tenant.city))
        .where(Tenant.slug == tenant_slug)
    )
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    actor = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id))
    if actor is None:
        raise MiniAppStoreError("MAX-аккаунт сотрудника не найден", status_code=403)
    actor_roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=actor.id,
    )
    allowed_roles = invitable_staff_roles(actor_roles)
    if payload.role not in allowed_roles:
        raise MiniAppStoreError("Нет прав на приглашение сотрудника с этой ролью", status_code=403)

    settings = get_settings()
    if not settings.max_bot_username or is_placeholder(settings.max_bot_username):
        raise MiniAppStoreError("В настройках сервера не указан MAX_BOT_USERNAME", status_code=503)

    raw_token = ""
    token_hash = ""
    for _ in range(5):
        raw_token = generate_staff_invitation_token()
        token_hash = staff_invitation_token_hash(raw_token)
        exists = await db.scalar(
            select(StaffInvitation.id).where(StaffInvitation.token_hash == token_hash)
        )
        if exists is None:
            break
    else:
        raise MiniAppStoreError(
            "Не удалось создать приглашение. Повторите попытку",
            status_code=503,
        )

    expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)
    invitation = StaffInvitation(
        tenant_id=tenant.id,
        role=payload.role,
        token_hash=token_hash,
        created_by_account_id=actor.id,
        expires_at=expires_at,
    )
    db.add(invitation)
    await db.flush()
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=actor.id,
            action="staff_invitation.created",
            entity_type="staff_invitation",
            entity_id=str(invitation.id),
            payload={
                "role": payload.role.value,
                "expires_at": expires_at.isoformat(),
            },
        )
    )
    await db.commit()
    await db.refresh(invitation)
    return MiniAppStaffInvitationRead(
        id=UUID(str(invitation.id)),
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        city_name=tenant.city.name if tenant.city else tenant.name,
        role=invitation.role,
        invite_url=build_max_bot_staff_invitation_deeplink(
            settings.max_bot_username,
            raw_token,
        ),
        expires_at=invitation.expires_at,
    )


async def redeem_miniapp_staff_invitation(
    db: AsyncSession,
    *,
    payload: MiniAppStaffInvitationRedeem,
) -> MiniAppStaffInvitationRedeemedRead:
    now = datetime.now(UTC)
    token_hash = staff_invitation_token_hash(payload.token.strip())
    invitation = await db.scalar(
        select(StaffInvitation)
        .options(selectinload(StaffInvitation.tenant).selectinload(Tenant.city))
        .where(StaffInvitation.token_hash == token_hash)
        .with_for_update()
    )
    if invitation is None:
        raise MiniAppStoreError("Приглашение не найдено или ссылка повреждена", status_code=404)
    if invitation.revoked_at is not None:
        raise MiniAppStoreError("Это приглашение отозвано", status_code=410)
    if invitation.redeemed_at is not None:
        raise MiniAppStoreError("Это приглашение уже использовано", status_code=409)
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        raise MiniAppStoreError("Срок действия приглашения истек", status_code=410)

    creator_roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=invitation.tenant_id,
        account_id=invitation.created_by_account_id,
    )
    if invitation.role not in invitable_staff_roles(creator_roles):
        raise MiniAppStoreError(
            "Автор приглашения больше не может выдавать эту роль",
            status_code=409,
        )

    target, account_created = await get_or_create_max_account(
        db,
        max_user_id=payload.max_user_id,
        username=payload.username,
        display_name=payload.display_name,
    )
    assignment = await db.scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.tenant_id == invitation.tenant_id,
            StaffRoleAssignment.account_id == target.id,
            StaffRoleAssignment.role == invitation.role,
        )
    )
    previous_status = assignment.status if assignment else None
    assignment_created = assignment is None
    if assignment is None:
        assignment = StaffRoleAssignment(
            tenant_id=invitation.tenant_id,
            account_id=target.id,
            role=invitation.role,
            status=AssignmentStatus.ACTIVE,
        )
        db.add(assignment)
        await db.flush()
    else:
        assignment.status = AssignmentStatus.ACTIVE

    invitation.redeemed_at = now
    invitation.redeemed_by_account_id = target.id
    db.add(
        AuditLog(
            tenant_id=invitation.tenant_id,
            actor_account_id=target.id,
            action="staff_invitation.redeemed",
            entity_type="staff_invitation",
            entity_id=str(invitation.id),
            payload={
                "created_by_account_id": str(invitation.created_by_account_id),
                "target_max_user_id": target.max_user_id,
                "role": invitation.role.value,
                "previous_status": previous_status.value if previous_status else None,
                "account_created": account_created,
                "assignment_created": assignment_created,
            },
        )
    )
    await db.commit()
    await db.refresh(target)
    await db.refresh(assignment)
    tenant = invitation.tenant
    assignment_read = MiniAppStaffAssignmentRead(
        id=UUID(str(assignment.id)),
        account_id=UUID(str(target.id)),
        max_user_id=target.max_user_id,
        username=target.username,
        display_name=target.display_name,
        role=assignment.role,
        status=assignment.status,
    )
    return MiniAppStaffInvitationRedeemedRead(
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        city_name=tenant.city.name if tenant.city else tenant.name,
        role=assignment.role,
        assignment=assignment_read,
    )


async def _staff_notification_management_context(
    db: AsyncSession,
    *,
    actor_max_user_id: int,
    tenant_slug: str,
    target_account_id: UUID,
) -> tuple[Tenant, MaxAccount, MaxAccount, set[StaffRole]]:
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    actor = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == actor_max_user_id))
    if actor is None:
        raise MiniAppStoreError("MAX-аккаунт управляющего не найден", status_code=403)
    actor_roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=actor.id,
    )
    if not actor_roles.intersection({StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR}):
        raise MiniAppStoreError(
            "Настройки уведомлений доступны директору и суперадминистратору",
            status_code=403,
        )

    target = await db.get(MaxAccount, target_account_id)
    if target is None:
        raise MiniAppStoreError("Сотрудник не найден", status_code=404)
    target_roles = set(
        (
            await db.scalars(
                select(StaffRoleAssignment.role).where(
                    StaffRoleAssignment.tenant_id == tenant.id,
                    StaffRoleAssignment.account_id == target.id,
                    StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                )
            )
        ).all()
    )
    if target_roles.intersection({StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR}):
        raise MiniAppStoreError(
            "Персональные настройки доступны только администраторам и кураторам",
            status_code=403,
        )
    manageable_roles = target_roles.intersection(MANAGEABLE_NOTIFICATION_ROLES)
    if not manageable_roles:
        raise MiniAppStoreError(
            "У сотрудника нет активной роли администратора или куратора",
            status_code=409,
        )
    return tenant, actor, target, manageable_roles


async def _staff_notification_settings_read(
    db: AsyncSession,
    *,
    tenant: Tenant,
    target: MaxAccount,
    target_roles: set[StaffRole],
) -> MiniAppStaffNotificationSettingsRead:
    preferences = {
        preference.event_key: preference.enabled
        for preference in (
            await db.scalars(
                select(StaffNotificationPreference).where(
                    StaffNotificationPreference.tenant_id == tenant.id,
                    StaffNotificationPreference.account_id == target.id,
                )
            )
        ).all()
    }
    items = []
    for definition in STAFF_NOTIFICATION_CATALOG:
        if definition.key not in CONFIGURABLE_STAFF_NOTIFICATION_KEYS:
            continue
        default_enabled = default_notification_enabled(definition, target_roles)
        customized = definition.key in preferences
        items.append(
            MiniAppStaffNotificationItemRead(
                event_key=definition.key,
                category=definition.category,
                category_label=CATEGORY_LABELS[definition.category],
                label=definition.label,
                description=definition.description,
                enabled=preferences.get(definition.key, default_enabled),
                default_enabled=default_enabled,
                customized=customized,
            )
        )
    return MiniAppStaffNotificationSettingsRead(
        account_id=UUID(str(target.id)),
        max_user_id=target.max_user_id,
        display_name=target.display_name or target.username,
        roles=[role for role in STAFF_ROLE_PRIORITY if role in target_roles],
        items=items,
    )


async def get_miniapp_staff_notification_settings(
    db: AsyncSession,
    *,
    actor_max_user_id: int,
    tenant_slug: str,
    target_account_id: UUID,
) -> MiniAppStaffNotificationSettingsRead:
    tenant, _actor, target, target_roles = await _staff_notification_management_context(
        db,
        actor_max_user_id=actor_max_user_id,
        tenant_slug=tenant_slug,
        target_account_id=target_account_id,
    )
    return await _staff_notification_settings_read(
        db,
        tenant=tenant,
        target=target,
        target_roles=target_roles,
    )


async def update_miniapp_staff_notification_settings(
    db: AsyncSession,
    *,
    target_account_id: UUID,
    payload: MiniAppStaffNotificationSettingsUpdate,
    default_tenant_slug: str,
) -> MiniAppStaffNotificationSettingsRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, actor, target, target_roles = await _staff_notification_management_context(
        db,
        actor_max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
        target_account_id=target_account_id,
    )
    requested = {item.event_key: item.enabled for item in payload.preferences}
    if len(requested) != len(payload.preferences):
        raise MiniAppStoreError("Настройка уведомления передана дважды", status_code=400)
    unknown_keys = sorted(set(requested) - CONFIGURABLE_STAFF_NOTIFICATION_KEYS)
    if unknown_keys:
        raise MiniAppStoreError(
            f"Неизвестная настройка уведомлений: {unknown_keys[0]}",
            status_code=400,
        )

    existing = {
        preference.event_key: preference
        for preference in (
            await db.scalars(
                select(StaffNotificationPreference).where(
                    StaffNotificationPreference.tenant_id == tenant.id,
                    StaffNotificationPreference.account_id == target.id,
                )
            )
        ).all()
    }
    for event_key, enabled in requested.items():
        definition = STAFF_NOTIFICATION_BY_KEY[event_key]
        default_enabled = default_notification_enabled(definition, target_roles)
        preference = existing.get(event_key)
        if enabled == default_enabled:
            if preference is not None:
                await db.delete(preference)
            continue
        if preference is None:
            db.add(
                StaffNotificationPreference(
                    tenant_id=tenant.id,
                    account_id=target.id,
                    event_key=event_key,
                    enabled=enabled,
                )
            )
        else:
            preference.enabled = enabled

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=actor.id,
            action="staff_notifications.updated",
            entity_type="max_account",
            entity_id=str(target.id),
            payload={
                "target_max_user_id": target.max_user_id,
                "target_roles": sorted(role.value for role in target_roles),
                "updated_event_keys": sorted(requested),
            },
        )
    )
    await db.commit()
    return await _staff_notification_settings_read(
        db,
        tenant=tenant,
        target=target,
        target_roles=target_roles,
    )


async def list_miniapp_staff_onboarding_options(
    db: AsyncSession,
    *,
    max_user_id: int,
) -> MiniAppStaffOnboardingOptionsRead:
    actor = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if actor is None:
        raise MiniAppStoreError("MAX-аккаунт суперадминистра не найден", status_code=403)

    is_superadmin = await is_global_superadmin(db, account_id=actor.id)
    if not is_superadmin:
        raise MiniAppStoreError("Нет прав на регистрацию сотрудников", status_code=403)

    tenants = (
        (
            await db.scalars(
                select(Tenant)
                .options(selectinload(Tenant.city))
                .where(Tenant.status == TenantStatus.ACTIVE)
            )
        )
        .unique()
        .all()
    )
    tenants.sort(
        key=lambda tenant: (
            (tenant.city.name if tenant.city else "").casefold(),
            tenant.name.casefold(),
        )
    )
    return MiniAppStaffOnboardingOptionsRead(
        tenants=[
            MiniAppStaffOnboardingTenantRead(
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                city_name=tenant.city.name if tenant.city else tenant.name,
            )
            for tenant in tenants
        ],
        roles=list(STAFF_ONBOARDING_ROLES),
    )


async def create_miniapp_tenant(
    db: AsyncSession,
    *,
    payload: MiniAppTenantCreate,
) -> MiniAppTenantCreatedRead:
    actor = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id))
    if actor is None:
        raise MiniAppStoreError("MAX-аккаунт суперадминистратора не найден", status_code=403)
    if not await is_global_superadmin(db, account_id=actor.id):
        raise MiniAppStoreError(
            "Создавать города и партнеров может только superadmin",
            status_code=403,
        )

    city_name = payload.city_name.strip()
    partner_name = payload.partner_name.strip()
    city, _ = await get_or_create_city(db, city_name)
    partner, _ = await get_or_create_partner(
        db,
        slug=_slugify(partner_name),
        name=partner_name,
    )
    tenant, tenant_created = await get_or_create_tenant(
        db,
        city=city,
        partner=partner,
    )
    tenant.status = TenantStatus.ACTIVE

    director_read = None
    if payload.partner_director_max_user_id is not None:
        director, _ = await get_or_create_max_account(
            db,
            max_user_id=payload.partner_director_max_user_id,
            display_name=(payload.partner_director_display_name or "").strip() or None,
        )
        assignment = await db.scalar(
            select(StaffRoleAssignment).where(
                StaffRoleAssignment.tenant_id == tenant.id,
                StaffRoleAssignment.account_id == director.id,
                StaffRoleAssignment.role == StaffRole.PARTNER_DIRECTOR,
            )
        )
        if assignment is None:
            assignment = StaffRoleAssignment(
                tenant_id=tenant.id,
                account_id=director.id,
                role=StaffRole.PARTNER_DIRECTOR,
                status=AssignmentStatus.ACTIVE,
            )
            db.add(assignment)
            await db.flush()
        else:
            assignment.status = AssignmentStatus.ACTIVE
        director_read = MiniAppStaffAssignmentRead(
            id=UUID(str(assignment.id)),
            account_id=UUID(str(director.id)),
            max_user_id=director.max_user_id,
            username=director.username,
            display_name=director.display_name,
            role=assignment.role,
            status=assignment.status,
        )

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=actor.id,
            action="tenant.created" if tenant_created else "tenant.reopened",
            entity_type="tenant",
            entity_id=str(tenant.id),
            payload={
                "city": city.name,
                "partner": partner.name,
                "partner_director_max_user_id": payload.partner_director_max_user_id,
            },
        )
    )
    await db.commit()

    return MiniAppTenantCreatedRead(
        tenant=MiniAppTenantRead(
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            city_name=city.name,
            partner_name=partner.name,
        ),
        created=tenant_created,
        partner_director=director_read,
    )


async def upsert_miniapp_warehouse(
    db: AsyncSession,
    *,
    payload: MiniAppWarehouseUpsert,
    default_tenant_slug: str,
) -> MiniAppWarehouseRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на управление складами", status_code=403)

    warehouse = None
    if payload.warehouse_id is not None:
        warehouse = await db.scalar(
            select(Warehouse).where(
                Warehouse.tenant_id == tenant.id,
                Warehouse.id == payload.warehouse_id,
            )
        )
        if warehouse is None:
            raise MiniAppStoreError("Склад не найден", status_code=404)
    else:
        slug = _slugify(payload.slug or payload.name)
        warehouse = await db.scalar(
            select(Warehouse).where(Warehouse.tenant_id == tenant.id, Warehouse.slug == slug)
        )

    if warehouse is None:
        warehouse = Warehouse(
            tenant_id=tenant.id,
            slug=slug,
            name=payload.name.strip(),
            warehouse_type=payload.warehouse_type or WarehouseType.COMMON,
            address=payload.address.strip() if payload.address else None,
        )
        db.add(warehouse)
        await db.flush()
        action = "warehouse.created"
    else:
        slug = _slugify(payload.slug) if payload.slug else warehouse.slug
        duplicate = await db.scalar(
            select(Warehouse).where(
                Warehouse.tenant_id == tenant.id,
                Warehouse.slug == slug,
                Warehouse.id != warehouse.id,
            )
        )
        if duplicate is not None:
            raise MiniAppStoreError("Склад с таким названием уже существует", status_code=409)
        warehouse.slug = slug
        warehouse.name = payload.name.strip()
        if payload.warehouse_type is not None:
            warehouse.warehouse_type = payload.warehouse_type
        warehouse.address = payload.address.strip() if payload.address else None
        action = "warehouse.updated"

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action=action,
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            payload={
                "slug": warehouse.slug,
                "name": warehouse.name,
                "warehouse_type": warehouse.warehouse_type.value,
                "address": warehouse.address,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.commit()
    await db.refresh(warehouse)
    return MiniAppWarehouseRead(
        id=UUID(str(warehouse.id)),
        slug=warehouse.slug,
        name=warehouse.name,
        warehouse_type=warehouse.warehouse_type,
        address=warehouse.address,
    )


async def delete_miniapp_warehouse(
    db: AsyncSession,
    *,
    warehouse_id: UUID,
    max_user_id: int,
    tenant_slug: str,
    default_tenant_slug: str,
) -> None:
    normalized_tenant_slug = (tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на удаление складов", status_code=403)

    warehouse = await db.scalar(
        select(Warehouse)
        .where(Warehouse.tenant_id == tenant.id, Warehouse.id == warehouse_id)
        .with_for_update()
    )
    if warehouse is None:
        raise MiniAppStoreError("Склад не найден", status_code=404)

    order_count = int(
        await db.scalar(
            select(func.count(OrderItem.id)).where(
                OrderItem.tenant_id == tenant.id,
                (
                    (OrderItem.warehouse_id == warehouse.id)
                    | (OrderItem.reserved_warehouse_id == warehouse.id)
                ),
            )
        )
        or 0
    )
    if order_count:
        raise MiniAppStoreError(
            "Нельзя удалить склад, который использовался в заказах: это нарушит историю выдачи.",
            status_code=409,
        )

    movement_count = int(
        await db.scalar(
            select(func.count(StockMovement.id)).where(
                StockMovement.tenant_id == tenant.id,
                (
                    (StockMovement.from_warehouse_id == warehouse.id)
                    | (StockMovement.to_warehouse_id == warehouse.id)
                ),
            )
        )
        or 0
    )
    if movement_count:
        raise MiniAppStoreError(
            "Нельзя удалить склад с историей движения товаров. "
            "Его можно переименовать и больше не использовать.",
            status_code=409,
        )

    inventories = list(
        (
            await db.scalars(
                select(WarehouseInventory)
                .where(
                    WarehouseInventory.tenant_id == tenant.id,
                    WarehouseInventory.warehouse_id == warehouse.id,
                )
                .with_for_update()
            )
        ).all()
    )
    reserved_quantity = sum(max(inventory.reserved_quantity, 0) for inventory in inventories)
    stock_quantity = sum(max(inventory.available_quantity, 0) for inventory in inventories)
    historical_quantity = sum(
        max(inventory.issued_quantity, 0) + max(inventory.returned_quantity, 0)
        for inventory in inventories
    )
    if reserved_quantity:
        raise MiniAppStoreError(
            f"Нельзя удалить склад: на нем зарезервировано {reserved_quantity} шт. товара.",
            status_code=409,
        )
    if stock_quantity:
        raise MiniAppStoreError(
            f"Нельзя удалить склад: на нем числится {stock_quantity} шт. товара. "
            "Сначала перенесите или обнулите остатки.",
            status_code=409,
        )
    if historical_quantity:
        raise MiniAppStoreError(
            "Нельзя удалить склад с историей выдачи или возврата товаров.",
            status_code=409,
        )

    warehouse_name = warehouse.name
    warehouse_slug = warehouse.slug
    await db.execute(
        delete(StaffWarehousePreference).where(
            StaffWarehousePreference.tenant_id == tenant.id,
            StaffWarehousePreference.warehouse_id == warehouse.id,
        )
    )
    await db.execute(
        delete(WarehouseInventory).where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.warehouse_id == warehouse.id,
        )
    )
    await db.flush()
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="warehouse.deleted",
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            payload={
                "slug": warehouse_slug,
                "name": warehouse_name,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.delete(warehouse)
    await db.commit()


async def adjust_miniapp_inventory(
    db: AsyncSession,
    *,
    payload: MiniAppInventoryAdjustmentCreate,
    default_tenant_slug: str,
) -> MiniAppInventoryAdjustmentRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на корректировку остатков", status_code=403)

    product = await db.scalar(
        select(Product)
        .where(
            Product.tenant_id == tenant.id,
            Product.id == payload.product_id,
        )
        .with_for_update()
    )
    if product is None:
        raise MiniAppStoreError("Товар не найден", status_code=404)

    warehouse = await db.scalar(
        select(Warehouse).where(
            Warehouse.tenant_id == tenant.id,
            Warehouse.id == payload.warehouse_id,
        )
    )
    if warehouse is None:
        raise MiniAppStoreError("Склад не найден", status_code=404)

    inventory = await db.scalar(
        select(WarehouseInventory)
        .where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
            WarehouseInventory.warehouse_id == warehouse.id,
        )
        .with_for_update()
    )
    if inventory is None:
        inventory = WarehouseInventory(
            tenant_id=tenant.id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            available_quantity=0,
            reserved_quantity=0,
        )
        db.add(inventory)
        await db.flush()
    inventory.is_active = True

    if payload.available_quantity < inventory.reserved_quantity:
        raise MiniAppStoreError(
            "Фактический остаток не может быть меньше резерва",
            status_code=409,
        )

    previous_quantity = inventory.available_quantity
    inventory.available_quantity = payload.available_quantity
    free_quantity = max(available_for_reservation(inventory), 0)
    should_notify_low_stock = free_quantity <= 5 and not inventory.low_stock_notified
    inventory.low_stock_notified = free_quantity <= 5
    delta = payload.available_quantity - previous_quantity
    if delta != 0:
        quantity = abs(delta)
        db.add(
            build_stock_movement(
                inventory=inventory,
                movement_type=StockMovementType.ADJUSTMENT,
                quantity=quantity,
                actor_account_id=account.id,
                from_warehouse_id=warehouse.id if delta < 0 else None,
                to_warehouse_id=warehouse.id if delta > 0 else None,
                comment=payload.comment or "Корректировка остатка в приложении Algo MAX",
            )
        )

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="warehouse_inventory.adjusted",
            entity_type="warehouse_inventory",
            entity_id=str(inventory.id),
            payload={
                "product_id": str(product.id),
                "warehouse_id": str(warehouse.id),
                "from_quantity": previous_quantity,
                "to_quantity": inventory.available_quantity,
                "reserved_quantity": inventory.reserved_quantity,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.commit()
    await db.refresh(inventory)
    inventory.warehouse = warehouse
    if should_notify_low_stock:
        await schedule_low_stock_notification(
            db,
            tenant=tenant,
            product=product,
            inventory=inventory,
        )

    return MiniAppInventoryAdjustmentRead(
        product_id=UUID(str(product.id)),
        warehouse_id=UUID(str(warehouse.id)),
        warehouse_name=warehouse.name,
        stock_quantity=inventory.available_quantity,
        reserved_quantity=inventory.reserved_quantity,
        available_quantity=max(available_for_reservation(inventory), 0),
    )


async def transfer_miniapp_inventory(
    db: AsyncSession,
    *,
    payload: MiniAppInventoryTransferCreate,
    default_tenant_slug: str,
) -> MiniAppInventoryTransferRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Город или партнер не найден", status_code=404)
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise MiniAppStoreError("Склады отправки и получения должны отличаться", status_code=400)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    staff_role = await _active_staff_role(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=STORE_ADMIN_ROLES,
    )
    if staff_role is None:
        raise MiniAppStoreError("Нет прав на перемещение остатков", status_code=403)

    product = await db.scalar(
        select(Product)
        .where(
            Product.tenant_id == tenant.id,
            Product.id == payload.product_id,
        )
        .with_for_update()
    )
    if product is None:
        raise MiniAppStoreError("Товар не найден", status_code=404)

    warehouses = (
        await db.scalars(
            select(Warehouse).where(
                Warehouse.tenant_id == tenant.id,
                Warehouse.id.in_([payload.from_warehouse_id, payload.to_warehouse_id]),
            )
        )
    ).all()
    warehouses_by_id = {warehouse.id: warehouse for warehouse in warehouses}
    source_warehouse = warehouses_by_id.get(payload.from_warehouse_id)
    target_warehouse = warehouses_by_id.get(payload.to_warehouse_id)
    if source_warehouse is None or target_warehouse is None:
        raise MiniAppStoreError("Один из складов не найден", status_code=404)

    source = await db.scalar(
        select(WarehouseInventory)
        .where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
            WarehouseInventory.warehouse_id == source_warehouse.id,
        )
        .with_for_update()
    )
    if source is None or not source.is_active:
        raise MiniAppStoreError("На складе отправки нет выбранного товара", status_code=404)

    target = await db.scalar(
        select(WarehouseInventory)
        .where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
            WarehouseInventory.warehouse_id == target_warehouse.id,
        )
        .with_for_update()
    )
    if target is None:
        target = WarehouseInventory(
            tenant_id=tenant.id,
            product_id=product.id,
            warehouse_id=target_warehouse.id,
            available_quantity=0,
            reserved_quantity=0,
        )
        db.add(target)
        await db.flush()
    target.is_active = True

    try:
        transfer_inventory(source=source, target=target, quantity=payload.quantity)
    except WarehouseServiceError as exc:
        raise MiniAppStoreError(str(exc), status_code=409) from exc

    low_stock_items: list[WarehouseInventory] = []
    for inventory in (source, target):
        free_quantity = max(available_for_reservation(inventory), 0)
        if free_quantity <= 5 and not inventory.low_stock_notified:
            inventory.low_stock_notified = True
            low_stock_items.append(inventory)
        elif free_quantity > 5:
            inventory.low_stock_notified = False

    db.add(
        build_stock_movement(
            inventory=source,
            movement_type=StockMovementType.TRANSFER,
            quantity=payload.quantity,
            actor_account_id=account.id,
            from_warehouse_id=source_warehouse.id,
            to_warehouse_id=target_warehouse.id,
            comment=payload.comment or "Перемещение остатка в приложении Algo MAX",
        )
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="warehouse_inventory.transferred",
            entity_type="warehouse_inventory",
            entity_id=str(source.id),
            payload={
                "product_id": str(product.id),
                "from_warehouse_id": str(source_warehouse.id),
                "to_warehouse_id": str(target_warehouse.id),
                "quantity": payload.quantity,
                "staff_role": staff_role.value,
            },
        )
    )
    await db.commit()
    await db.refresh(source)
    await db.refresh(target)
    source.warehouse = source_warehouse
    target.warehouse = target_warehouse
    for inventory in low_stock_items:
        await schedule_low_stock_notification(
            db,
            tenant=tenant,
            product=product,
            inventory=inventory,
        )

    return MiniAppInventoryTransferRead(
        product_id=UUID(str(product.id)),
        from_warehouse_id=UUID(str(source_warehouse.id)),
        from_warehouse_name=source_warehouse.name,
        from_stock_quantity=source.available_quantity,
        from_available_quantity=max(available_for_reservation(source), 0),
        to_warehouse_id=UUID(str(target_warehouse.id)),
        to_warehouse_name=target_warehouse.name,
        to_stock_quantity=target.available_quantity,
        to_available_quantity=max(available_for_reservation(target), 0),
        quantity=payload.quantity,
    )


async def _wallet_balances(db: AsyncSession, student_ids: list[UUID]) -> dict[UUID, int]:
    if not student_ids:
        return {}

    rows = (
        await db.execute(
            select(Wallet.student_id, Wallet.balance).where(Wallet.student_id.in_(student_ids))
        )
    ).all()
    return {student_id: balance for student_id, balance in rows}


async def _access_links_for_session(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    include_all: bool,
    student_ids: set[UUID] | None = None,
) -> list[MiniAppAccessLinkRead]:
    conditions = [StudentAccessLink.tenant_id == tenant_id]
    if not include_all:
        conditions.append(StudentAccessLink.account_id == account_id)
    if student_ids is not None:
        conditions.append(StudentAccessLink.student_id.in_(student_ids))

    rows = (
        await db.execute(
            select(StudentAccessLink, MaxAccount, Student)
            .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
            .join(Student, Student.id == StudentAccessLink.student_id)
            .where(*conditions)
            .order_by(Student.group_name, Student.first_name, MaxAccount.max_user_id)
        )
    ).all()
    return [
        MiniAppAccessLinkRead(
            id=UUID(str(link.id)),
            account_id=UUID(str(account.id)),
            max_user_id=account.max_user_id,
            username=account.username,
            display_name=account.display_name,
            student_id=UUID(str(student.id)),
            student_name=student.display_name,
            group_name=student.group_name,
            role=link.role,
            status=link.status,
        )
        for link, account, student in rows
    ]


async def _staff_assignments_for_session(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    actor_roles: list[StaffRole],
) -> list[MiniAppStaffAssignmentRead]:
    if not set(actor_roles).intersection(STORE_ADMIN_ROLES):
        return []

    rows = (
        await db.execute(
            select(StaffRoleAssignment, MaxAccount)
            .join(MaxAccount, MaxAccount.id == StaffRoleAssignment.account_id)
            .where(StaffRoleAssignment.tenant_id == tenant_id)
            .order_by(
                StaffRoleAssignment.status,
                StaffRoleAssignment.role,
                MaxAccount.max_user_id,
            )
        )
    ).all()
    return [
        MiniAppStaffAssignmentRead(
            id=UUID(str(assignment.id)),
            account_id=UUID(str(account.id)),
            max_user_id=account.max_user_id,
            username=account.username,
            display_name=account.display_name,
            role=assignment.role,
            status=assignment.status,
        )
        for assignment, account in rows
    ]


async def _orders_for_students(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_ids: list[UUID],
    visible_order_ids: set[UUID] | None = None,
    unrestricted_student_ids: set[UUID] | None = None,
    issued_code_student_ids: set[UUID] | None = None,
) -> list[MiniAppOrderRead]:
    if not student_ids:
        return []

    order_filters = [Order.tenant_id == tenant_id, Order.student_id.in_(student_ids)]
    if visible_order_ids is not None:
        order_scope = Order.id.in_(visible_order_ids)
        if unrestricted_student_ids:
            order_scope = order_scope | Order.student_id.in_(unrestricted_student_ids)
        order_filters.append(order_scope)

    query = (
        select(Order, Student)
        .join(Student, Student.id == Order.student_id)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.items).selectinload(OrderItem.digital_codes),
            selectinload(Order.items).selectinload(OrderItem.warehouse),
            selectinload(Order.items).selectinload(OrderItem.reserved_warehouse),
            selectinload(Order.status_history),
        )
        .where(*order_filters)
    )
    open_rows = (
        await db.execute(
            query.where(Order.status.in_(OPEN_ORDER_STATUSES)).order_by(Order.created_at.desc())
        )
    ).all()
    archive_rows = (
        await db.execute(
            query.where(Order.status.not_in(OPEN_ORDER_STATUSES))
            .order_by(Order.created_at.desc())
            .limit(100)
        )
    ).all()
    rows = sorted(
        [*open_rows, *archive_rows],
        key=lambda row: row[0].created_at,
        reverse=True,
    )
    return [
        _order_to_read(
            order,
            student,
            include_issued_codes=(
                issued_code_student_ids is None or student.id in issued_code_student_ids
            ),
        )
        for order, student in rows
    ]


async def _ledger_for_students(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_ids: list[UUID],
) -> list[MiniAppLedgerRead]:
    if not student_ids:
        return []

    entries = (
        await db.scalars(
            select(AstrocoinLedgerEntry)
            .where(
                AstrocoinLedgerEntry.tenant_id == tenant_id,
                AstrocoinLedgerEntry.student_id.in_(student_ids),
            )
            .order_by(AstrocoinLedgerEntry.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        MiniAppLedgerRead(
            id=UUID(str(entry.id)),
            student_id=UUID(str(entry.student_id)),
            direction=entry.direction,
            amount=entry.amount,
            reason=entry.reason,
            comment=entry.comment,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
