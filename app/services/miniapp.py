import logging
import re
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings, is_placeholder
from app.models.account import (
    MaxAccount,
    StaffRoleAssignment,
    StaffWarehousePreference,
)
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    OrderStatus,
    ProductStatus,
    StaffRole,
    StockMovementType,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
    TenantStatus,
)
from app.models.store import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductCategory,
    Warehouse,
    WarehouseInventory,
)
from app.models.student import AstrocoinLedgerEntry, Student, StudentAccessLink, Wallet
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
    MiniAppProductImportRead,
    MiniAppProductRead,
    MiniAppProductUpsert,
    MiniAppProductWarehouseRead,
    MiniAppSessionRead,
    MiniAppStaffAssignmentRead,
    MiniAppStaffAssignmentUpdate,
    MiniAppStaffOnboardingOptionsRead,
    MiniAppStaffOnboardingTenantRead,
    MiniAppStudentRead,
    MiniAppTenantCreate,
    MiniAppTenantCreatedRead,
    MiniAppTenantRead,
    MiniAppWarehousePreferenceRead,
    MiniAppWarehousePreferenceUpdate,
    MiniAppWarehouseRead,
    MiniAppWarehouseUpsert,
)
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
    schedule_low_stock_notification,
    schedule_new_product_notification,
    schedule_order_notification,
)
from app.services.order_sheets import order_item_mapping, upsert_order_sheet_row
from app.services.product_import import (
    ProductImportError,
    import_products_for_tenant,
    parse_product_rows,
)
from app.services.staff import (
    active_staff_roles_for_tenant,
    get_or_create_max_account,
    is_global_superadmin,
    normalize_staff_name,
    staff_names_match,
)
from app.services.warehouse import (
    WarehouseServiceError,
    available_for_reservation,
    build_stock_movement,
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
        student_id
        for student_id, name in rows
        if staff_names_match(account.display_name, name)
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
        await db.scalars(
            select(Tenant)
            .options(selectinload(Tenant.city), selectinload(Tenant.partner))
            .where(Tenant.status == TenantStatus.ACTIVE)
        )
    ).unique().all()
    tenants.sort(
        key=lambda tenant: (
            (tenant.city.name if tenant.city else "").casefold(),
            (tenant.partner.name if tenant.partner else tenant.name).casefold(),
        )
    )
    return [_tenant_to_read(tenant) for tenant in tenants]


def _product_to_read(product: Product) -> MiniAppProductRead:
    warehouses: list[MiniAppProductWarehouseRead] = []
    available_total = 0

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
        available_quantity=available_total,
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
    return (
        not is_placeholder(settings.google_service_account_file)
        and not is_placeholder(settings.google_sheets_orders_spreadsheet_id)
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
    max_user_id: int | None = None,
    include_inactive: bool = False,
) -> MiniAppCatalogRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        return MiniAppCatalogRead(tenant_slug=normalized_tenant_slug, products=[], warehouses=[])

    product_filters = [Product.tenant_id == tenant.id]
    if max_user_id is not None:
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
        if max_user_id is None:
            raise MiniAppStoreError(
                "MAX user_id обязателен для админского каталога",
                status_code=403,
            )
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
        await db.scalars(
            select(Product)
            .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
            .where(*product_filters)
            .options(
                selectinload(Product.category),
                selectinload(Product.inventory_items).selectinload(
                    WarehouseInventory.warehouse
                ),
            )
            .order_by(ProductCategory.sort_order, Product.name)
        )
    ).unique().all()
    warehouses = (
        await db.scalars(
            select(Warehouse)
            .where(Warehouse.tenant_id == tenant.id)
            .order_by(Warehouse.name)
        )
    ).all()

    return MiniAppCatalogRead(
        tenant_slug=tenant.slug,
        products=[_product_to_read(product) for product in products],
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

    result = await import_products_for_tenant(db, tenant=tenant, rows=rows)
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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


async def upsert_miniapp_product(
    db: AsyncSession,
    *,
    payload: MiniAppProductUpsert,
    default_tenant_slug: str,
) -> MiniAppProductRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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
        )
        db.add(product)
        await db.flush()
        product_created = True
    else:
        product.category_id = category.id
        product.sku = sku
        product.name = payload.name.strip()
        product.description = payload.description
        product.photo_url = payload.photo_url
        product.price_astrocoins = payload.price_astrocoins
        product.status = payload.status

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
        )
    )
    if product is None:
        raise MiniAppStoreError("Товар не найден после сохранения", status_code=500)
    if product_created and product.status == ProductStatus.ACTIVE:
        await schedule_new_product_notification(db, tenant=tenant, product=product)
    return _product_to_read(product)


async def get_miniapp_session(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> MiniAppSessionRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await db.scalar(
        select(Tenant)
        .options(selectinload(Tenant.city), selectinload(Tenant.partner))
        .where(Tenant.slug == normalized_tenant_slug)
    )
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))

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
    staff_roles = [
        role for role in STAFF_ROLE_PRIORITY if role in effective_staff_roles
    ]
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
        student_ids = [student.id for student in tenant_students]
        balances = await _wallet_balances(db, student_ids)
        students = [
            MiniAppStudentRead(
                student_id=UUID(str(student.id)),
                lms_student_id=student.lms_student_id,
                role=StudentAccessRole.STUDENT,
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
        link_rows = (
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

        student_ids = [student.id for _, student in link_rows]
        balances = await _wallet_balances(db, student_ids)
        students = [
            MiniAppStudentRead(
                student_id=UUID(str(student.id)),
                lms_student_id=student.lms_student_id,
                role=link.role,
                access_status=link.status,
                display_name=student.display_name,
                group_name=student.group_name,
                course_name=student.course_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
                balance=balances.get(student.id, 0),
            )
            for link, student in link_rows
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
        default_warehouse_id=(
            UUID(str(default_warehouse_id)) if default_warehouse_id else None
        ),
        students=students,
        access_links=access_links,
        staff_assignments=staff_assignments,
        orders=orders,
        ledger=ledger,
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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
            select(Order.status, func.count(Order.id))
            .where(*order_filters)
            .group_by(Order.status)
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
                selectinload(Order.items).selectinload(OrderItem.warehouse),
                selectinload(Order.status_history),
            )
            .where(*order_filters, Order.status.in_(open_statuses))
            .order_by(Order.created_at.asc())
            .limit(8)
        )
    ).all()
    recent_open_orders = [
        _order_to_read(order, student)
        for order, student in open_order_rows
    ]

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
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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
                selectinload(Order.items).selectinload(OrderItem.warehouse),
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
) -> WarehouseInventory:
    if item.warehouse_id is None:
        raise MiniAppStoreError("У позиции заказа не указан склад", status_code=409)

    inventory = await db.scalar(
        select(WarehouseInventory).where(
            WarehouseInventory.tenant_id == tenant_id,
            WarehouseInventory.warehouse_id == item.warehouse_id,
            WarehouseInventory.product_id == item.product_id,
        ).with_for_update()
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
    tenant = await db.scalar(
        select(Tenant).where(Tenant.slug == tenant_slug).with_for_update()
    )
    if tenant is None:
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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
        raise MiniAppStoreError("Ученик не найден в выбранном tenant", status_code=404)

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

    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
        .with_for_update()
    )
    if wallet is None:
        raise MiniAppStoreError("Кошелек ученика не найден", status_code=409)

    quantities = _merge_order_items(payload)
    products = (
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
                )
            )
        )
    ).unique().all()
    products_by_id = {UUID(str(product.id)): product for product in products}
    requested_product_ids = set(quantities)
    missing_ids = [
        product_id for product_id in requested_product_ids if product_id not in products_by_id
    ]
    if missing_ids:
        raise MiniAppStoreError("Один или несколько товаров недоступны", status_code=404)

    total_astrocoins = sum(
        products_by_id[product_id].price_astrocoins * quantity
        for product_id, quantity in quantities.items()
    )
    if wallet.balance < total_astrocoins:
        raise MiniAppStoreError(
            "Недостаточно астроcoins для оформления заказа",
            status_code=409,
        )

    order_plan: list[tuple[Product, int]] = []
    for product_id, quantity in quantities.items():
        product = products_by_id[product_id]
        total_available = sum(
            max(available_for_reservation(inventory), 0)
            for inventory in product.inventory_items
        )
        if total_available < quantity:
            raise MiniAppStoreError(
                f"Товара «{product.name}» сейчас недостаточно для заказа",
                status_code=409,
            )
        order_plan.append((product, quantity))

    last_order_number = await db.scalar(
        select(func.max(Order.order_number)).where(Order.tenant_id == tenant.id)
    )
    order_number = int(last_order_number or 0) + 1
    order = Order(
        tenant_id=tenant.id,
        student_id=student.id,
        created_by_account_id=account.id,
        order_number=order_number,
        status=OrderStatus.RESERVED,
        total_astrocoins=total_astrocoins,
        teacher_name=student.teacher_name,
        venue_name=student.venue_name,
        comment=payload.comment,
    )
    db.add(order)
    await db.flush()

    response_items: list[MiniAppOrderItemRead] = []
    sheets_items: list[dict[str, object]] = []
    for product, quantity in order_plan:
        total_price = product.price_astrocoins * quantity
        db.add(
            OrderItem(
                tenant_id=tenant.id,
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                warehouse_id=None,
                unit_price_astrocoins=product.price_astrocoins,
                total_price_astrocoins=total_price,
            )
        )
        response_items.append(
            MiniAppOrderItemRead(
                product_id=UUID(str(product.id)),
                product_name=product.name,
                quantity=quantity,
                unit_price_astrocoins=product.price_astrocoins,
                total_price_astrocoins=total_price,
                warehouse_id=None,
                warehouse_name=None,
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
            to_status=OrderStatus.RESERVED,
            comment="Заказ создан из MAX mini app",
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
                    }
                    for product, quantity in order_plan
                ],
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
        items=sheets_items,
        comment=payload.comment,
    )
    await schedule_order_notification(
        db,
        tenant=tenant,
        order=order,
        student=student,
        balance_after=wallet.balance,
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
    if order.status != OrderStatus.RESERVED:
        raise MiniAppStoreError(
            "Склад можно назначить только зарезервированному заказу",
            status_code=409,
        )
    if any(item.warehouse_id is not None for item in order.items):
        raise MiniAppStoreError("Склад для этого заказа уже назначен", status_code=409)

    assignments = {
        UUID(str(item.product_id)): UUID(str(item.warehouse_id))
        for item in payload.items
    }
    if len(assignments) != len(payload.items):
        raise MiniAppStoreError("Для каждого товара укажите один склад")

    order_product_ids = {UUID(str(item.product_id)) for item in order.items}
    if set(assignments) != order_product_ids:
        raise MiniAppStoreError("Назначьте склад для каждой позиции заказа")

    reservation_plan: list[tuple[OrderItem, WarehouseInventory]] = []
    for item in order.items:
        warehouse_id = assignments[UUID(str(item.product_id))]
        inventory = await db.scalar(
            select(WarehouseInventory)
            .where(
                WarehouseInventory.tenant_id == tenant.id,
                WarehouseInventory.product_id == item.product_id,
                WarehouseInventory.warehouse_id == warehouse_id,
            )
            .with_for_update()
            .options(selectinload(WarehouseInventory.warehouse))
        )
        product_name = item.product.name if item.product else str(item.product_id)
        if inventory is None or available_for_reservation(inventory) < item.quantity:
            raise MiniAppStoreError(
                f"На выбранном складе недостаточно товара «{product_name}»",
                status_code=409,
            )
        reservation_plan.append((item, inventory))

    response_items: list[MiniAppOrderItemRead] = []
    sheets_items: list[dict[str, object]] = []
    low_stock_events: list[tuple[Product, WarehouseInventory]] = []
    for item, inventory in reservation_plan:
        try:
            reserve_inventory(inventory, item.quantity)
        except WarehouseServiceError as exc:
            raise MiniAppStoreError(str(exc), status_code=409) from exc
        free_quantity = max(available_for_reservation(inventory), 0)
        if free_quantity <= 5 and not inventory.low_stock_notified and item.product:
            inventory.low_stock_notified = True
            low_stock_events.append((item.product, inventory))
        elif free_quantity > 5:
            inventory.low_stock_notified = False
        item.warehouse_id = inventory.warehouse_id
        db.add(
            build_stock_movement(
                inventory=inventory,
                movement_type=StockMovementType.RESERVE,
                quantity=item.quantity,
                actor_account_id=account.id,
                order_id=order.id,
                from_warehouse_id=inventory.warehouse_id,
                comment=payload.comment or f"Склад назначен заказу №{order.order_number}",
            )
        )
        product_name = item.product.name if item.product else str(item.product_id)
        warehouse_name = inventory.warehouse.name if inventory.warehouse else None
        response_items.append(
            MiniAppOrderItemRead(
                product_id=UUID(str(item.product_id)),
                product_name=product_name,
                quantity=item.quantity,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
                warehouse_id=UUID(str(inventory.warehouse_id)),
                warehouse_name=warehouse_name,
            )
        )
        sheets_items.append(
            order_item_mapping(
                product_id=str(item.product_id),
                product_name=product_name,
                quantity=item.quantity,
                warehouse_id=str(inventory.warehouse_id),
                warehouse_name=warehouse_name,
                unit_price_astrocoins=item.unit_price_astrocoins,
                total_price_astrocoins=item.total_price_astrocoins,
            )
        )

    db.add(
        OrderStatusHistory(
            tenant_id=tenant.id,
            order_id=order.id,
            actor_account_id=account.id,
            from_status=order.status,
            to_status=order.status,
            comment=payload.comment or "Склад назначен администратором",
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
                        "warehouse_id": str(inventory.warehouse_id),
                        "quantity": item.quantity,
                    }
                    for item, inventory in reservation_plan
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

    for item in order.items:
        if item.warehouse_id is None:
            continue
        inventory = await _inventory_for_order_item(db, tenant_id=tenant.id, item=item)
        try:
            release_reservation(inventory, item.quantity)
        except WarehouseServiceError as exc:
            raise MiniAppStoreError(str(exc), status_code=409) from exc
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

    if reason.casefold() == "товар закончился":
        product_ids = {item.product_id for item in order.items}
        inventory_rows = (
            await db.scalars(
                select(WarehouseInventory)
                .where(
                    WarehouseInventory.tenant_id == tenant.id,
                    WarehouseInventory.product_id.in_(product_ids),
                )
                .with_for_update()
            )
        ).all()
        for inventory in inventory_rows:
            inventory.available_quantity = inventory.reserved_quantity
            inventory.low_stock_notified = True

    wallet = await db.scalar(
        select(Wallet).where(Wallet.tenant_id == tenant.id, Wallet.student_id == order.student_id)
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
            raise MiniAppStoreError(str(exc), status_code=409) from exc
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

    for item in order.items:
        inventory = await _inventory_for_order_item(db, tenant_id=tenant.id, item=item)
        try:
            return_inventory(inventory, item.quantity)
        except WarehouseServiceError as exc:
            raise MiniAppStoreError(str(exc), status_code=409) from exc
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
        select(Wallet).where(Wallet.tenant_id == tenant.id, Wallet.student_id == order.student_id)
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
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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
            select(Wallet).where(
                Wallet.tenant_id == tenant.id,
                Wallet.student_id.in_(unique_student_ids),
            )
            .order_by(Wallet.student_id)
            .with_for_update()
        )
    ).all()
    wallets_by_student = {wallet.student_id: wallet for wallet in wallets}

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
                idempotency_key=f"miniapp_accrual:{wallet.id}:{uuid4()}",
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)
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

    started_at = datetime.combine(date_from, time.min, tzinfo=UTC)
    ended_at = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)
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

    previous_status = link.status
    link.status = payload.status
    link.revoked_at = datetime.now(UTC) if payload.status == StudentAccessStatus.REVOKED else None
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)
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


async def list_miniapp_staff_onboarding_options(
    db: AsyncSession,
    *,
    max_user_id: int,
) -> MiniAppStaffOnboardingOptionsRead:
    actor = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if actor is None:
        raise MiniAppStoreError("MAX-аккаунт суперадминистра не найден", status_code=403)

    is_superadmin = bool(
        await db.scalar(
            select(func.count(StaffRoleAssignment.id)).where(
                StaffRoleAssignment.account_id == actor.id,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                StaffRoleAssignment.role == StaffRole.SUPERADMIN,
            )
        )
    )
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
        raise MiniAppStoreError("MAX-аккаунт суперadmin не найден", status_code=403)
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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

    slug = _slugify(payload.slug or payload.name)
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
        warehouse = await db.scalar(
            select(Warehouse).where(Warehouse.tenant_id == tenant.id, Warehouse.slug == slug)
        )

    if warehouse is None:
        warehouse = Warehouse(
            tenant_id=tenant.id,
            slug=slug,
            name=payload.name.strip(),
            warehouse_type=payload.warehouse_type,
            address=payload.address,
        )
        db.add(warehouse)
        await db.flush()
        action = "warehouse.created"
    else:
        duplicate = await db.scalar(
            select(Warehouse).where(
                Warehouse.tenant_id == tenant.id,
                Warehouse.slug == slug,
                Warehouse.id != warehouse.id,
            )
        )
        if duplicate is not None:
            raise MiniAppStoreError("Склад с таким slug уже существует", status_code=409)
        warehouse.slug = slug
        warehouse.name = payload.name.strip()
        warehouse.warehouse_type = payload.warehouse_type
        warehouse.address = payload.address
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)

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
        select(Product).where(
            Product.tenant_id == tenant.id,
            Product.id == payload.product_id,
        ).with_for_update()
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
        select(WarehouseInventory).where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
            WarehouseInventory.warehouse_id == warehouse.id,
        ).with_for_update()
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
                comment=payload.comment or "Корректировка остатка из MAX mini app",
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
        raise MiniAppStoreError("Tenant не найден", status_code=404)
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
        select(Product).where(
            Product.tenant_id == tenant.id,
            Product.id == payload.product_id,
        ).with_for_update()
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
        select(WarehouseInventory).where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
            WarehouseInventory.warehouse_id == source_warehouse.id,
        ).with_for_update()
    )
    if source is None:
        raise MiniAppStoreError("На складе отправки нет выбранного товара", status_code=404)

    target = await db.scalar(
        select(WarehouseInventory).where(
            WarehouseInventory.tenant_id == tenant.id,
            WarehouseInventory.product_id == product.id,
            WarehouseInventory.warehouse_id == target_warehouse.id,
        ).with_for_update()
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

    db.add(
        build_stock_movement(
            inventory=source,
            movement_type=StockMovementType.TRANSFER,
            quantity=payload.quantity,
            actor_account_id=account.id,
            from_warehouse_id=source_warehouse.id,
            to_warehouse_id=target_warehouse.id,
            comment=payload.comment or "Перемещение остатка из MAX mini app",
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
                selectinload(Order.items).selectinload(OrderItem.warehouse),
                selectinload(Order.status_history),
            )
            .where(Order.tenant_id == tenant_id, Order.student_id.in_(student_ids))
            .order_by(Order.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        _order_to_read(order, student)
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
