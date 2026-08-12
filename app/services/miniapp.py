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
    StudentCartItem,
    Warehouse,
    WarehouseInventory,
)
from app.models.student import (
    AstrocoinLedgerEntry,
    Student,
    StudentAccessLink,
    StudentHistoryEvent,
    Wallet,
)
from app.models.tenant import Tenant
from app.schemas.miniapp import (
    MiniAppAccessLinkRead,
    MiniAppAccessStatusRead,
    MiniAppAccessStatusUpdate,
    MiniAppAccountRead,
    MiniAppAccrualCreate,
    MiniAppAccrualRead,
    MiniAppAccrualReportEntryRead,
    MiniAppAccrualReportRead,
    MiniAppAccrualUndoCreate,
    MiniAppAdminHistoryEntryRead,
    MiniAppAdminHistoryRead,
    MiniAppAdminStudentRead,
    MiniAppCartItemRead,
    MiniAppCartRead,
    MiniAppCartWrite,
    MiniAppCatalogRead,
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
    MiniAppStaffNotificationItemRead,
    MiniAppStaffNotificationSettingsRead,
    MiniAppStaffNotificationSettingsUpdate,
    MiniAppStaffOnboardingOptionsRead,
    MiniAppStaffOnboardingTenantRead,
    MiniAppStudentHistoryEventRead,
    MiniAppStudentInvitationRead,
    MiniAppStudentRead,
    MiniAppStudentRegistryRead,
    MiniAppTenantCreate,
    MiniAppTenantCreatedRead,
    MiniAppTenantRead,
    MiniAppWarehousePreferenceRead,
    MiniAppWarehousePreferenceUpdate,
    MiniAppWarehouseRead,
    MiniAppWarehouseUpsert,
)
from app.services.access import revoke_dependent_student_links
from app.services.crm_import import CrmImportError, parse_crm_students_content
from app.services.crm_sync import (
    CrmSyncDefaults,
    get_or_create_city,
    get_or_create_partner,
    get_or_create_tenant,
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
)
from app.services.order_sheets import order_item_mapping, upsert_order_sheet_row
from app.services.product_import import (
    ProductImportError,
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
    superadmin_identity_is_allowed,
)
from app.services.staff_notifications import (
    CATEGORY_LABELS,
    CONFIGURABLE_STAFF_NOTIFICATION_KEYS,
    MANAGEABLE_NOTIFICATION_ROLES,
    STAFF_NOTIFICATION_BY_KEY,
    STAFF_NOTIFICATION_CATALOG,
    default_notification_enabled,
)
from app.services.student_invitations import (
    StudentInvitationError,
    build_student_invitation_link,
    invitation_qr_data_url,
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
    return_inventory,
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
ACCRUAL_REPORT_ROLES = STORE_ADMIN_ROLES | {StaffRole.CURATOR}
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
    return staff_names_match(account.display_name, student.teacher_name)


async def _teacher_student_ids(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account: MaxAccount,
) -> list[UUID]:
    if not normalize_staff_name(account.display_name):
        return []
    rows = (
        await db.execute(
            select(Student.id, Student.teacher_name).where(
                Student.tenant_id == tenant_id,
                Student.status == StudentStatus.ACTIVE,
            )
        )
    ).all()
    return [
        student_id for student_id, name in rows if staff_names_match(account.display_name, name)
    ]


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
            available = max(available_for_reservation(inventory), 0)
            if inventory.warehouse is None:
                continue

            available_total += available
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
) -> MiniAppOrderRead:
    if items is None:
        items = [
            MiniAppOrderItemRead(
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
                issued_codes=[
                    code.code
                    for code in item.__dict__.get("digital_codes", [])
                    if code.status == ProductCodeStatus.ISSUED
                ],
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
    active_access_link = await db.scalar(
        select(StudentAccessLink.id)
        .where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
        .limit(1)
    )
    if not staff_roles and active_access_link is None:
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
    tenant, account, admin_role = await _store_admin_context(
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

    summary = {
        "parsed_rows": len(rows),
        "distinct_groups": len({row.group_name for row in rows if row.group_name}),
        "distinct_courses": len({row.course_name for row in rows if row.course_name}),
        "distinct_teachers": len({row.teacher_name for row in rows if row.teacher_name}),
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
            **summary,
        )

    result = await upsert_crm_student_rows(
        db,
        rows,
        defaults=CrmSyncDefaults(
            partner_slug=tenant.slug,
            partner_name=tenant.name,
        ),
        commit=False,
        target_tenant=tenant,
        student_status=student_status,
        actor_account_id=account.id,
    )
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="miniapp_crm.imported",
            entity_type="crm_import",
            entity_id=None,
            payload={
                "filename": filename,
                "parsed_rows": len(rows),
                "created_students": result.created_students,
                "updated_students": result.updated_students,
                "admin_role": admin_role.value,
                "student_status": student_status.value,
            },
        )
    )
    await db.commit()

    return MiniAppCrmImportRead(
        tenant_slug=tenant.slug,
        filename=filename,
        dry_run=False,
        student_status=student_status,
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
    tenant, _, _ = await _store_admin_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
        denied_message="Нет прав на просмотр реестра учеников",
    )
    students = (
        await db.scalars(
            select(Student)
            .where(Student.tenant_id == tenant.id)
            .order_by(Student.status, Student.group_name, Student.last_name, Student.first_name)
        )
    ).all()
    student_ids = [student.id for student in students]
    balances = await _wallet_balances(db, student_ids)
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
                    changed_fields=list(event.changed_fields or []),
                    source=event.source,
                    actor_name=actor_name,
                    occurred_at=event.created_at,
                )
            )

    registry_students: list[MiniAppAdminStudentRead] = []
    for student in students:
        history = events_by_student.get(student.id, [])
        if not any(event.event_type == "imported" for event in history):
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
                history=history[-50:],
            )
        )
    return MiniAppStudentRegistryRead(
        tenant_slug=tenant.slug,
        students=registry_students,
    )


AMOCRM_AUDIT_ACTIONS = {
    "amocrm.sync_failed",
    "amocrm.students_synced",
    "amocrm.student_status_updated",
}

AUDIT_ACTION_COPY = {
    "amocrm.sync_failed": ("Ошибка синхронизации amoCRM", "amoCRM"),
    "amocrm.students_synced": ("Синхронизация учеников amoCRM", "amoCRM"),
    "amocrm.student_status_updated": ("Обновление статусов из amoCRM", "amoCRM"),
    "miniapp_products.imported": ("Загрузка товаров", "Товары"),
    "miniapp_crm.imported": ("Импорт учеников и групп", "Ученики"),
    "product.created": ("Товар создан", "Товары"),
    "product.updated": ("Товар изменен", "Товары"),
    "miniapp_order.created": ("Заказ создан", "Заказы"),
    "miniapp_order.warehouses_assigned": ("Склад заказа назначен", "Заказы"),
    "miniapp_order.cancelled": ("Заказ отменен", "Заказы"),
    "miniapp_order.issued": ("Заказ выдан", "Заказы"),
    "miniapp_order.transferred_to_teacher": ("Заказ передан преподавателю", "Заказы"),
    "miniapp_order.returned": ("Заказ возвращен", "Заказы"),
    "miniapp_astrocoins.accrued": ("Астрокоины начислены", "Астрокоины"),
    "miniapp_astrocoins.undone": ("Начисление отменено", "Астрокоины"),
    "student_access_link.status_changed": ("Доступ ученика изменен", "Доступ"),
    "staff_role_assignment.updated": ("Роль сотрудника изменена", "Сотрудники"),
    "staff_notifications.updated": ("Уведомления сотрудника настроены", "Сотрудники"),
    "tenant.created": ("Партнер создан", "Партнеры"),
    "tenant.reopened": ("Партнер восстановлен", "Партнеры"),
    "warehouse.created": ("Склад создан", "Склады"),
    "warehouse.updated": ("Склад изменен", "Склады"),
    "warehouse_inventory.adjusted": ("Остаток скорректирован", "Склады"),
    "warehouse_inventory.transferred": ("Товар перемещен", "Склады"),
    "school_broadcast.sent": ("Рассылка отправлена", "Рассылки"),
    "teaching_journal.lessons_updated": ("Журнал занятий изменен", "Журнал"),
    "teaching_schedule.created": ("Расписание создано", "Расписание"),
    "teaching_schedule.updated": ("Расписание изменено", "Расписание"),
    "manual_feedback.sent_to_parents": ("Обратная связь отправлена", "Обратная связь"),
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

    sku = payload.sku.strip().upper()
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
        duplicate = await db.scalar(
            select(Product).where(
                Product.tenant_id == tenant.id,
                Product.sku == sku,
                Product.id != product.id,
            )
        )
        if duplicate is not None:
            raise MiniAppStoreError("Товар с таким SKU уже существует", status_code=409)
    else:
        product = await db.scalar(
            select(Product).where(Product.tenant_id == tenant.id, Product.sku == sku)
        )

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
    return _product_to_read(product, include_codes=True)


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
        requested_has_access = False
        if tenant is not None:
            requested_has_access = bool(
                await active_staff_roles_for_tenant(
                    db,
                    tenant_id=UUID(str(tenant.id)),
                    account_id=UUID(str(account.id)),
                )
            ) or bool(
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
                (
                    await db.scalars(
                        select(StudentAccessLink.tenant_id).where(
                            StudentAccessLink.account_id == account.id,
                            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                        )
                    )
                ).all()
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
    explicit_student_roles = list(
        (
            await db.scalars(
                select(StudentAccessLink.role)
                .where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.account_id == account.id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
                .order_by(StudentAccessLink.role)
            )
        ).all()
    )
    own_link_rows = list(
        (
            await db.execute(
                select(StudentAccessLink, Student)
                .join(Student, Student.id == StudentAccessLink.student_id)
                .where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.account_id == account.id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                    Student.status == StudentStatus.ACTIVE,
                )
                .order_by(Student.group_name, Student.first_name, Student.last_name)
            )
        ).all()
    )
    linked_students_by_id: dict[UUID, Student] = {}
    access_roles_by_student: dict[UUID, set[StudentAccessRole]] = {}
    for link, linked_student in own_link_rows:
        linked_students_by_id[linked_student.id] = linked_student
        access_roles_by_student.setdefault(linked_student.id, set()).add(link.role)

    if not staff_roles and not explicit_student_roles:
        return MiniAppSessionRead(
            tenant_slug=normalized_tenant_slug,
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

    if staff_roles:
        tenant_students = (
            await db.scalars(
                select(Student)
                .where(Student.tenant_id == tenant.id, Student.status == StudentStatus.ACTIVE)
                .order_by(Student.group_name, Student.first_name, Student.last_name)
            )
        ).all()
        effective_staff_role = next(
            (role for role in STAFF_ROLE_PRIORITY if role in staff_roles),
            None,
        )
        teacher_scoped = effective_staff_role == StaffRole.TEACHER
        if teacher_scoped:
            tenant_students = [
                student
                for student in tenant_students
                if staff_names_match(account.display_name, student.teacher_name)
            ]
        staff_student_ids = {student.id for student in tenant_students}
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
                display_name=student.display_name,
                group_name=student.group_name,
                course_name=student.course_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
                balance=balances.get(student.id, 0),
            )
            for student in tenant_students
        ]
    else:
        linked_students = list(linked_students_by_id.values())
        student_ids = [student.id for student in linked_students]
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
                group_name=student.group_name,
                course_name=student.course_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
                balance=balances.get(student.id, 0),
            )
            for student in linked_students
        ]

    orders = await _orders_for_students(db, tenant_id=tenant.id, student_ids=student_ids)
    ledger = await _ledger_for_students(db, tenant_id=tenant.id, student_ids=student_ids)
    access_links = await _access_links_for_session(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        include_all=bool(set(staff_roles) & ELEVATED_STAFF_ROLES),
    )
    staff_assignments = await _staff_assignments_for_session(
        db,
        tenant_id=tenant.id,
        actor_roles=staff_roles,
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
        tenant=_tenant_to_read(tenant),
        available_tenants=(
            await _active_tenants_for_superadmin(db)
            if StaffRole.SUPERADMIN in effective_staff_roles
            else []
        ),
        can_manage_tenants=StaffRole.SUPERADMIN in effective_staff_roles,
        default_warehouse_id=(UUID(str(default_warehouse_id)) if default_warehouse_id else None),
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

    parent_link = await db.scalar(
        select(StudentAccessLink).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id == student_id,
            StudentAccessLink.role == StudentAccessRole.PARENT,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
    )
    if parent_link is None:
        raise MiniAppStoreError(
            "QR-код доступен только родителю связанного ученика",
            status_code=403,
        )

    student = await db.scalar(
        select(Student).where(
            Student.id == student_id,
            Student.tenant_id == tenant.id,
            Student.status == StudentStatus.ACTIVE,
        )
    )
    if student is None:
        raise MiniAppStoreError("Ученик не найден", status_code=404)

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
        bot_url=bot_url,
        qr_data_url=invitation_qr_data_url(bot_url),
        qr_download_url=f"/miniapp/qr/{invitation_token}.png",
    )


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
        Student.status == StudentStatus.ACTIVE,
    )
    if lock_student:
        student_query = student_query.with_for_update()
    student = await db.scalar(student_query)
    if student is None:
        raise MiniAppStoreError("Ученик не найден", status_code=404)

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
    if staff_role == StaffRole.TEACHER:
        teacher_student_ids = await _teacher_student_ids(
            db,
            tenant_id=tenant.id,
            account=account,
        )
        order_filters.append(Order.student_id.in_(teacher_student_ids))

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

    open_statuses = {
        OrderStatus.CREATED,
        OrderStatus.RESERVED,
        OrderStatus.TRANSFERRED_TO_TEACHER,
        OrderStatus.PROBLEM,
    }
    pending_issue_statuses = {
        OrderStatus.RESERVED,
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
                WarehouseInventory.tenant_id == tenant.id
            )
        )
        or 0
    )
    total_reserved_quantity = int(
        await db.scalar(
            select(func.coalesce(func.sum(WarehouseInventory.reserved_quantity), 0)).where(
                WarehouseInventory.tenant_id == tenant.id
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
                Product.status != ProductStatus.ARCHIVED,
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
        if staff_role != StaffRole.TEACHER or _teacher_owns_student(account, student):
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
            Student.status == StudentStatus.ACTIVE,
        )
    )
    if student is None:
        raise MiniAppStoreError("Ученик не найден у выбранного партнера", status_code=404)

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
                "Код выдан автоматически после оплаты"
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
    if previous_status not in {OrderStatus.RESERVED, OrderStatus.PROBLEM}:
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
        product_name = item.product.name if item.product else str(item.product_id)
        warehouse_name = target_inventory.warehouse.name if target_inventory.warehouse else None
        response_items.append(
            MiniAppOrderItemRead(
                product_id=UUID(str(item.product_id)),
                product_name=product_name,
                quantity=item.quantity,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
                warehouse_id=UUID(str(target_inventory.warehouse_id)),
                warehouse_name=warehouse_name,
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

    if previous_status == OrderStatus.PROBLEM:
        order.status = OrderStatus.RESERVED

    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=previous_status,
            to_status=order.status,
            comment=payload.comment
            or (
                "Проблема устранена, склад назначен администратором"
                if previous_status == OrderStatus.PROBLEM
                else "Склад назначен администратором"
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
    if order.status not in {OrderStatus.RESERVED, OrderStatus.TRANSFERRED_TO_TEACHER}:
        raise MiniAppStoreError("Отменить можно только зарезервированный заказ", status_code=409)

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
    if order.status not in {OrderStatus.RESERVED, OrderStatus.TRANSFERRED_TO_TEACHER}:
        raise MiniAppStoreError("Выдать можно только зарезервированный заказ", status_code=409)

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
    if order.status != OrderStatus.RESERVED:
        raise MiniAppStoreError(
            "Передать учителю можно только зарезервированный заказ",
            status_code=409,
        )
    if any(item.warehouse_id is None for item in order.items):
        raise MiniAppStoreError("Сначала подтвердите склад для каждой позиции", status_code=409)

    order.status = OrderStatus.TRANSFERRED_TO_TEACHER
    comment = payload.comment or "Заказ передан учителю"
    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=OrderStatus.RESERVED,
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
        title="Заказ передан преподавателю",
        actor_name=account.display_name,
        extra_facts=[("Преподаватель", order.teacher_name or "Не указан")],
    )
    return MiniAppOrderActionRead(
        order=_order_to_read(order, student, status_history=status_history),
        balance_after=None,
    )


async def return_miniapp_order(
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
    if order.status != OrderStatus.ISSUED_TO_STUDENT:
        raise MiniAppStoreError("Вернуть можно только выданный заказ", status_code=409)
    if any(
        item.product
        and item.product.fulfillment_type == ProductFulfillmentType.DIGITAL_CODE
        for item in order.items
    ):
        raise MiniAppStoreError(
            "Выданный цифровой код нельзя вернуть в магазин",
            status_code=409,
        )

    for item in order.items:
        inventory = await _inventory_for_order_item(db, tenant_id=tenant.id, item=item)
        try:
            return_inventory(inventory, item.quantity)
        except WarehouseServiceError as exc:
            await schedule_staff_order_notification(
                db,
                tenant=tenant,
                order=order,
                student=student,
                event_key="orders.problem",
                title="Не удалось оформить возврат",
                actor_name=account.display_name,
                message=str(exc),
            )
            raise MiniAppStoreError(str(exc), status_code=409) from exc
        if available_for_reservation(inventory) > 5:
            inventory.low_stock_notified = False
        db.add(
            build_stock_movement(
                inventory=inventory,
                movement_type=StockMovementType.RETURN,
                quantity=item.quantity,
                actor_account_id=account.id,
                order_id=order.id,
                to_warehouse_id=inventory.warehouse_id,
                comment=payload.comment or f"Возврат заказа №{order.order_number}",
            )
        )

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
            idempotency_key=f"order:{order.id}:return_refund",
            direction=LedgerDirection.REVERSAL,
            amount=order.total_astrocoins,
            reason=f"Возврат за заказ №{order.order_number}",
            comment=payload.comment,
        )
    )

    previous_status = order.status
    order.status = OrderStatus.RETURNED
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
            action="miniapp_order.returned",
            entity_type="order",
            entity_id=str(order.id),
            payload={
                "order_number": order.order_number,
                "student_id": str(order.student_id),
                "refund_astrocoins": order.total_astrocoins,
                "actor_role": staff_role.value if staff_role else None,
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
        comment=payload.comment,
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
        event_key="orders.returned",
        title="Оформлен возврат заказа",
        actor_name=account.display_name,
        extra_facts=[("Комментарий", payload.comment or "Без комментария")],
    )
    return MiniAppOrderActionRead(
        order=_order_to_read(order, student, status_history=status_history),
        balance_after=wallet.balance,
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
            teacher_name=actor.display_name or actor.username or str(actor.max_user_id),
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
    if not actor_roles.intersection(STORE_ADMIN_ROLES) and not is_global_superadmin:
        raise MiniAppStoreError("Нет прав на управление сотрудниками", status_code=403)
    if payload.role in ELEVATED_STAFF_ROLES and not is_global_superadmin:
        raise MiniAppStoreError(
            "Управляющие роли может менять только superadmin",
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
    if source is None:
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
) -> list[MiniAppAccessLinkRead]:
    conditions = [StudentAccessLink.tenant_id == tenant_id]
    if not include_all:
        conditions.append(StudentAccessLink.account_id == account_id)

    rows = (
        await db.execute(
            select(StudentAccessLink, MaxAccount, Student)
            .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
            .join(Student, Student.id == StudentAccessLink.student_id)
            .where(*conditions)
            .order_by(Student.group_name, Student.first_name, MaxAccount.max_user_id)
            .limit(200)
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
            .limit(200)
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
) -> list[MiniAppOrderRead]:
    if not student_ids:
        return []

    rows = (
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
            .where(Order.tenant_id == tenant_id, Order.student_id.in_(student_ids))
            .order_by(Order.created_at.desc())
            .limit(50)
        )
    ).all()
    return [_order_to_read(order, student) for order, student in rows]


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
