from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import MaxAccount, StaffRoleAssignment
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
)
from app.models.store import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductCategory,
    WarehouseInventory,
)
from app.models.student import AstrocoinLedgerEntry, Student, StudentAccessLink, Wallet
from app.models.tenant import Tenant
from app.schemas.miniapp import (
    MiniAppAccountRead,
    MiniAppAccrualCreate,
    MiniAppAccrualRead,
    MiniAppCatalogRead,
    MiniAppLedgerRead,
    MiniAppOrderCreate,
    MiniAppOrderCreatedRead,
    MiniAppOrderItemRead,
    MiniAppOrderRead,
    MiniAppProductImportRead,
    MiniAppProductRead,
    MiniAppProductWarehouseRead,
    MiniAppSessionRead,
    MiniAppStudentRead,
)
from app.services.product_import import (
    ProductImportError,
    import_products_for_tenant,
    parse_product_rows,
)
from app.services.warehouse import (
    WarehouseServiceError,
    available_for_reservation,
    build_stock_movement,
    choose_inventory_for_reservation,
    reserve_inventory,
)


class MiniAppStoreError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


STORE_ADMIN_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
}

COIN_ACCRUAL_ROLES = STORE_ADMIN_ROLES | {
    StaffRole.CURATOR,
    StaffRole.TEACHER,
}


async def get_tenant_by_slug(db: AsyncSession, tenant_slug: str) -> Tenant | None:
    return await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug.strip().lower()))


def _product_to_read(product: Product) -> MiniAppProductRead:
    warehouses: list[MiniAppProductWarehouseRead] = []
    available_total = 0

    for inventory in product.inventory_items:
        available = max(available_for_reservation(inventory), 0)
        if available <= 0 or inventory.warehouse is None:
            continue

        available_total += available
        warehouses.append(
            MiniAppProductWarehouseRead(
                warehouse_id=UUID(str(inventory.warehouse_id)),
                warehouse_name=inventory.warehouse.name,
                warehouse_type=inventory.warehouse.warehouse_type.value,
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
        available_quantity=available_total,
        warehouses=warehouses,
    )


async def list_miniapp_catalog(
    db: AsyncSession,
    *,
    tenant_slug: str,
) -> MiniAppCatalogRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        return MiniAppCatalogRead(tenant_slug=normalized_tenant_slug, products=[])

    products = (
        await db.scalars(
            select(Product)
            .outerjoin(ProductCategory, ProductCategory.id == Product.category_id)
            .where(Product.tenant_id == tenant.id, Product.status == ProductStatus.ACTIVE)
            .options(
                selectinload(Product.category),
                selectinload(Product.inventory_items).selectinload(
                    WarehouseInventory.warehouse
                ),
            )
            .order_by(ProductCategory.sort_order, Product.name)
        )
    ).unique().all()

    return MiniAppCatalogRead(
        tenant_slug=tenant.slug,
        products=[_product_to_read(product) for product in products],
    )


async def import_miniapp_products(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    filename: str,
    content: bytes,
) -> MiniAppProductImportRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
    if tenant is None:
        raise MiniAppStoreError("Tenant не найден", status_code=404)

    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise MiniAppStoreError("MAX-аккаунт не найден", status_code=403)

    admin_role = await db.scalar(
        select(StaffRoleAssignment.role).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == account.id,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            StaffRoleAssignment.role.in_(STORE_ADMIN_ROLES),
        )
    )
    if admin_role is None:
        raise MiniAppStoreError("Нет прав на загрузку товаров", status_code=403)

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


async def get_miniapp_session(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> MiniAppSessionRead:
    normalized_tenant_slug = tenant_slug.strip().lower()
    tenant = await get_tenant_by_slug(db, normalized_tenant_slug)
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
            orders=[],
            ledger=[],
        )

    staff_roles = list(
        (
            await db.scalars(
                select(StaffRoleAssignment.role)
                .where(
                    StaffRoleAssignment.tenant_id == tenant.id,
                    StaffRoleAssignment.account_id == account.id,
                    StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                )
                .order_by(StaffRoleAssignment.role)
            )
        ).all()
    )

    if staff_roles:
        tenant_students = (
            await db.scalars(
                select(Student)
                .where(Student.tenant_id == tenant.id, Student.status == StudentStatus.ACTIVE)
                .order_by(Student.group_name, Student.first_name, Student.last_name)
            )
        ).all()
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

    return MiniAppSessionRead(
        tenant_slug=tenant.slug,
        account=MiniAppAccountRead(
            max_user_id=account.max_user_id,
            username=account.username,
            display_name=account.display_name,
        ),
        staff_roles=staff_roles,
        student_roles=sorted({student.role for student in students}),
        students=students,
        orders=orders,
        ledger=ledger,
    )


def _merge_order_items(payload: MiniAppOrderCreate) -> dict[tuple[UUID, UUID | None], int]:
    quantities: dict[tuple[UUID, UUID | None], int] = {}
    totals_by_product: dict[UUID, int] = {}
    for item in payload.items:
        product_id = UUID(str(item.product_id))
        warehouse_id = UUID(str(item.warehouse_id)) if item.warehouse_id else None
        key = (product_id, warehouse_id)
        quantities[key] = quantities.get(key, 0) + item.quantity
        totals_by_product[product_id] = totals_by_product.get(product_id, 0) + item.quantity

    too_large = [quantity for quantity in totals_by_product.values() if quantity > 20]
    if too_large:
        raise MiniAppStoreError("В одном заказе можно указать не больше 20 штук одного товара")
    return quantities


async def create_miniapp_order(
    db: AsyncSession,
    *,
    payload: MiniAppOrderCreate,
    default_tenant_slug: str,
) -> MiniAppOrderCreatedRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant = await get_tenant_by_slug(db, tenant_slug)
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
        select(Student).where(Student.tenant_id == tenant.id, Student.id == payload.student_id)
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
    active_staff_role = await db.scalar(
        select(StaffRoleAssignment.id).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == account.id,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
        )
    )
    if active_student_link is None and active_staff_role is None:
        raise MiniAppStoreError("Нет доступа к выбранному ученику", status_code=403)

    wallet = await db.scalar(
        select(Wallet).where(Wallet.tenant_id == tenant.id, Wallet.student_id == student.id)
    )
    if wallet is None:
        raise MiniAppStoreError("Кошелек ученика не найден", status_code=409)

    quantities = _merge_order_items(payload)
    products = (
        await db.scalars(
            select(Product)
            .where(
                Product.tenant_id == tenant.id,
                Product.id.in_({product_id for product_id, _ in quantities}),
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
    requested_product_ids = {product_id for product_id, _ in quantities}
    missing_ids = [
        product_id for product_id in requested_product_ids if product_id not in products_by_id
    ]
    if missing_ids:
        raise MiniAppStoreError("Один или несколько товаров недоступны", status_code=404)

    total_astrocoins = sum(
        products_by_id[product_id].price_astrocoins * quantity
        for (product_id, _), quantity in quantities.items()
    )
    if wallet.balance < total_astrocoins:
        raise MiniAppStoreError(
            "Недостаточно астроcoins для оформления заказа",
            status_code=409,
        )

    reservation_plan: list[tuple[Product, WarehouseInventory, int]] = []
    for (product_id, warehouse_id), quantity in quantities.items():
        product = products_by_id[product_id]
        if warehouse_id is None:
            inventory = choose_inventory_for_reservation(
                product.inventory_items,
                quantity=quantity,
                venue_id=student.venue_id,
            )
        else:
            inventory = next(
                (
                    item
                    for item in product.inventory_items
                    if UUID(str(item.warehouse_id)) == warehouse_id
                    and available_for_reservation(item) >= quantity
                ),
                None,
            )
        if inventory is None:
            raise MiniAppStoreError(
                f"Товар «{product.name}» сейчас нельзя зарезервировать",
                status_code=409,
            )
        reservation_plan.append((product, inventory, quantity))

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
    for product, inventory, quantity in reservation_plan:
        try:
            reserve_inventory(inventory, quantity)
        except WarehouseServiceError as exc:
            raise MiniAppStoreError(str(exc), status_code=409) from exc

        total_price = product.price_astrocoins * quantity
        db.add(
            OrderItem(
                tenant_id=tenant.id,
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                warehouse_id=inventory.warehouse_id,
                unit_price_astrocoins=product.price_astrocoins,
                total_price_astrocoins=total_price,
            )
        )
        db.add(
            build_stock_movement(
                inventory=inventory,
                movement_type=StockMovementType.RESERVE,
                quantity=quantity,
                actor_account_id=account.id,
                order_id=order.id,
                from_warehouse_id=inventory.warehouse_id,
                comment=f"Резерв заказа №{order_number}",
            )
        )
        response_items.append(
            MiniAppOrderItemRead(
                product_id=UUID(str(product.id)),
                product_name=product.name,
                quantity=quantity,
                unit_price_astrocoins=product.price_astrocoins,
                total_price_astrocoins=total_price,
                warehouse_id=UUID(str(inventory.warehouse_id)),
                warehouse_name=inventory.warehouse.name if inventory.warehouse else None,
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
                        "warehouse_id": str(inventory.warehouse_id),
                    }
                    for product, inventory, quantity in reservation_plan
                ],
            },
        )
    )

    await db.commit()
    await db.refresh(order)
    await db.refresh(wallet)

    return MiniAppOrderCreatedRead(
        order=MiniAppOrderRead(
            id=UUID(str(order.id)),
            order_number=order.order_number,
            student_id=UUID(str(student.id)),
            student_name=student.display_name,
            status=order.status,
            total_astrocoins=order.total_astrocoins,
            teacher_name=order.teacher_name,
            venue_name=order.venue_name,
            created_at=order.created_at,
        ),
        items=response_items,
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

    staff_role = await db.scalar(
        select(StaffRoleAssignment.role).where(
            StaffRoleAssignment.tenant_id == tenant.id,
            StaffRoleAssignment.account_id == account.id,
            StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            StaffRoleAssignment.role.in_(COIN_ACCRUAL_ROLES),
        )
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
            )
        )
    ).all()
    if len(students) != len(unique_student_ids):
        raise MiniAppStoreError("Один или несколько учеников не найдены", status_code=404)

    wallets = (
        await db.scalars(
            select(Wallet).where(
                Wallet.tenant_id == tenant.id,
                Wallet.student_id.in_(unique_student_ids),
            )
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


async def _wallet_balances(db: AsyncSession, student_ids: list[UUID]) -> dict[UUID, int]:
    if not student_ids:
        return {}

    rows = (
        await db.execute(
            select(Wallet.student_id, Wallet.balance).where(Wallet.student_id.in_(student_ids))
        )
    ).all()
    return {student_id: balance for student_id, balance in rows}


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
            .where(Order.tenant_id == tenant_id, Order.student_id.in_(student_ids))
            .order_by(Order.created_at.desc())
            .limit(50)
        )
    ).all()
    return [
        MiniAppOrderRead(
            id=UUID(str(order.id)),
            order_number=order.order_number,
            student_id=UUID(str(order.student_id)),
            student_name=student.display_name,
            status=order.status,
            total_astrocoins=order.total_astrocoins,
            teacher_name=order.teacher_name,
            venue_name=order.venue_name,
            created_at=order.created_at,
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
