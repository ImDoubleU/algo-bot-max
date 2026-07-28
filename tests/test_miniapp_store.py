import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    OrderStatus,
    ProductStatus,
    StaffRole,
    StockMovementType,
    StudentAccessRole,
    WarehouseType,
)
from app.models.store import (
    OrderItem,
    Product,
    ProductCategory,
    StockMovement,
    Warehouse,
    WarehouseInventory,
)
from app.models.student import AstrocoinLedgerEntry, Student, Wallet
from app.schemas.access import AccessLinkCreate
from app.schemas.miniapp import (
    MiniAppAccrualCreate,
    MiniAppInventoryAdjustmentCreate,
    MiniAppInventoryTransferCreate,
    MiniAppOrderActionCreate,
    MiniAppOrderCancelCreate,
    MiniAppOrderCreate,
    MiniAppOrderItemCreate,
    MiniAppOrderWarehouseAssignmentCreate,
    MiniAppOrderWarehouseAssignmentItem,
    MiniAppProductUpsert,
    MiniAppWarehousePreferenceUpdate,
    MiniAppWarehouseUpsert,
)
from app.services.access import create_contact_access_links
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.miniapp import (
    MiniAppStoreError,
    accrue_miniapp_astrocoins,
    adjust_miniapp_inventory,
    assign_miniapp_order_warehouses,
    cancel_miniapp_order,
    create_miniapp_order,
    get_miniapp_ops_summary,
    issue_miniapp_order,
    list_miniapp_catalog,
    return_miniapp_order,
    set_miniapp_warehouse_preference,
    transfer_miniapp_inventory,
    upsert_miniapp_product,
    upsert_miniapp_warehouse,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def crm_row() -> CrmStudentRow:
    return CrmStudentRow(
        row_number=2,
        deal_id="1357",
        uuid="uuid-1",
        lms_student_id="ST-001",
        first_name="Алиса",
        last_name="Васильева",
        group_name="Python Start, вс 10:00",
        course_name="Python Start",
        venue_name="Союзный 45",
        teacher_name="Олейник Д",
        city="Нижний Новгород",
        status_name="Активен",
        contact_ids="681",
        contact_names="Мама Алисы",
    )


async def seed_linked_student(db_session) -> Student:
    await upsert_crm_student_rows(
        db_session,
        [crm_row()],
        defaults=CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A"),
    )
    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
            username="parent_user",
            display_name="Родитель",
        ),
    )
    student = await db_session.scalar(select(Student).where(Student.id == links[0].student_id))
    assert student is not None

    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet is not None
    wallet.balance = 1000
    await db_session.commit()
    return student


async def seed_product(db_session, student: Student) -> tuple[Product, WarehouseInventory]:
    category = ProductCategory(
        tenant_id=student.tenant_id,
        slug="gifts",
        name="Подарки",
        sort_order=10,
    )
    product = Product(
        tenant_id=student.tenant_id,
        category=category,
        sku="PEN-LOGO",
        name="Ручка металл с лого",
        description="Сувенир для учеников",
        price_astrocoins=120,
    )
    warehouse = Warehouse(
        tenant_id=student.tenant_id,
        venue_id=student.venue_id,
        slug="soyuznyy-45",
        name="Союзный 45",
        warehouse_type=WarehouseType.VENUE,
    )
    db_session.add_all([category, product, warehouse])
    await db_session.flush()

    inventory = WarehouseInventory(
        tenant_id=student.tenant_id,
        warehouse_id=warehouse.id,
        product_id=product.id,
        available_quantity=5,
    )
    db_session.add(inventory)
    await db_session.commit()
    return product, inventory


async def test_order_waits_for_admin_warehouse_and_debits_wallet(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)

    catalog = await list_miniapp_catalog(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert len(catalog.products) == 1
    assert catalog.products[0].available_quantity == 5

    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=2)],
            comment="MAX mini app",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert created.order.status == OrderStatus.RESERVED
    assert created.order.total_astrocoins == 240
    assert len(created.order.status_history) == 1
    assert created.order.status_history[0].to_status == OrderStatus.RESERVED
    assert created.balance_after == 760
    assert created.items[0].warehouse_name is None
    assert created.items[0].warehouse_id is None

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet is not None
    assert inventory.reserved_quantity == 0
    assert wallet.balance == 760

    order_items = (await db_session.scalars(select(OrderItem))).all()
    ledger_entries = (await db_session.scalars(select(AstrocoinLedgerEntry))).all()
    assert len(order_items) == 1
    assert len(ledger_entries) == 1
    assert ledger_entries[0].direction == LedgerDirection.DEBIT


async def test_admin_can_save_personal_default_warehouse(db_session) -> None:
    student = await seed_linked_student(db_session)
    _product, inventory = await seed_product(db_session, student)
    account = await db_session.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == 53364725)
    )
    assert account is not None
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    preference = await set_miniapp_warehouse_preference(
        db_session,
        payload=MiniAppWarehousePreferenceUpdate(
            max_user_id=account.max_user_id,
            tenant_slug="nizhniy-novgorod-partner-a",
            warehouse_id=inventory.warehouse_id,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert preference.warehouse_id == inventory.warehouse_id


async def test_staff_without_student_link_cannot_place_order(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, _inventory = await seed_product(db_session, student)
    staff_account = MaxAccount(max_user_id=90000001, display_name="Сотрудник")
    db_session.add(staff_account)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=staff_account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="только ученикам и родителям"):
        await create_miniapp_order(
            db_session,
            payload=MiniAppOrderCreate(
                max_user_id=staff_account.max_user_id,
                tenant_slug="nizhniy-novgorod-partner-a",
                student_id=student.id,
                items=[MiniAppOrderItemCreate(product_id=product.id, quantity=1)],
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_ops_summary_reports_open_orders_and_low_stock(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, _inventory = await seed_product(db_session, student)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    account.display_name = "Олейник Д"
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=2)],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    summary = await get_miniapp_ops_summary(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        low_stock_threshold=3,
    )

    assert summary.staff_role == StaffRole.ADMIN
    assert summary.total_orders == 1
    assert summary.open_orders == 1
    assert summary.pending_issue_orders == 1
    assert summary.order_statuses[0].status == OrderStatus.RESERVED
    assert summary.order_statuses[0].count == 1
    assert summary.recent_open_orders[0].id == created.order.id
    assert summary.recent_open_orders[0].items[0].product_name == product.name
    assert summary.low_stock == []
    assert summary.total_stock_quantity == 5
    assert summary.total_reserved_quantity == 0


async def test_admin_assigns_order_warehouse_after_checkout(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, venue_inventory = await seed_product(db_session, student)
    common_warehouse = Warehouse(
        tenant_id=student.tenant_id,
        slug="common",
        name="Общий склад",
        warehouse_type=WarehouseType.COMMON,
    )
    db_session.add(common_warehouse)
    await db_session.flush()
    common_inventory = WarehouseInventory(
        tenant_id=student.tenant_id,
        warehouse_id=common_warehouse.id,
        product_id=product.id,
        available_quantity=5,
    )
    db_session.add(common_inventory)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[
                MiniAppOrderItemCreate(
                    product_id=product.id,
                    warehouse_id=common_warehouse.id,
                    quantity=3,
                )
            ],
            comment="MAX mini app",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert created.items[0].warehouse_name is None
    await db_session.refresh(common_inventory)
    await db_session.refresh(venue_inventory)
    assert common_inventory.reserved_quantity == 0
    assert venue_inventory.reserved_quantity == 0

    assigned = await assign_miniapp_order_warehouses(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderWarehouseAssignmentCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            items=[
                MiniAppOrderWarehouseAssignmentItem(
                    product_id=product.id,
                    warehouse_id=common_warehouse.id,
                )
            ],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert assigned.order.items[0].warehouse_name == "Общий склад"
    await db_session.refresh(common_inventory)
    assert common_inventory.reserved_quantity == 3


async def test_cancel_order_releases_stock_and_refunds_wallet(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=2)],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    cancelled = await cancel_miniapp_order(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderCancelCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            reason="Передумали",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    entries = (await db_session.scalars(select(AstrocoinLedgerEntry))).all()
    assert cancelled.order.status == OrderStatus.CANCELLED
    assert cancelled.balance_after == 1000
    assert wallet is not None
    assert wallet.balance == 1000
    assert inventory.reserved_quantity == 0
    assert inventory.available_quantity == 5
    assert [entry.direction for entry in entries] == [
        LedgerDirection.DEBIT,
        LedgerDirection.REVERSAL,
    ]


async def test_staff_can_issue_reserved_order(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    account.display_name = "Олейник Д"
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=2)],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    await assign_miniapp_order_warehouses(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderWarehouseAssignmentCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            items=[
                MiniAppOrderWarehouseAssignmentItem(
                    product_id=product.id,
                    warehouse_id=inventory.warehouse_id,
                )
            ],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    issued = await issue_miniapp_order(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderActionCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            comment="Выдано на уроке",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert issued.order.status == OrderStatus.ISSUED_TO_STUDENT
    assert issued.balance_after is None
    assert wallet is not None
    assert wallet.balance == 760
    assert inventory.reserved_quantity == 0
    assert inventory.available_quantity == 3
    assert inventory.issued_quantity == 2


async def test_staff_can_return_issued_order_and_refund_wallet(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    account.display_name = "Олейник Д"
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=2)],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    await assign_miniapp_order_warehouses(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderWarehouseAssignmentCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            items=[
                MiniAppOrderWarehouseAssignmentItem(
                    product_id=product.id,
                    warehouse_id=inventory.warehouse_id,
                )
            ],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    await issue_miniapp_order(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderActionCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    returned = await return_miniapp_order(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderActionCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            comment="Вернули товар",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    entries = (await db_session.scalars(select(AstrocoinLedgerEntry))).all()
    assert returned.order.status == OrderStatus.RETURNED
    assert returned.balance_after == 1000
    assert wallet is not None
    assert wallet.balance == 1000
    assert inventory.reserved_quantity == 0
    assert inventory.available_quantity == 5
    assert inventory.issued_quantity == 2
    assert inventory.returned_quantity == 2
    assert [entry.direction for entry in entries] == [
        LedgerDirection.DEBIT,
        LedgerDirection.REVERSAL,
    ]


async def test_staff_can_accrue_astrocoins_from_miniapp(db_session) -> None:
    student = await seed_linked_student(db_session)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    account.display_name = "Олейник Д"
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    result = await accrue_miniapp_astrocoins(
        db_session,
        payload=MiniAppAccrualCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_ids=[student.id],
            amount=75,
            reason="За проект на уроке",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    entries = (
        await db_session.scalars(
            select(AstrocoinLedgerEntry).where(
                AstrocoinLedgerEntry.direction == LedgerDirection.CREDIT
            )
        )
    ).all()
    assert result.credited_students == 1
    assert result.total_astrocoins == 75
    assert wallet is not None
    assert wallet.balance == 1075
    assert len(entries) == 1


async def test_admin_can_adjust_inventory_and_write_stock_movement(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    result = await adjust_miniapp_inventory(
        db_session,
        payload=MiniAppInventoryAdjustmentCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            product_id=product.id,
            warehouse_id=inventory.warehouse_id,
            available_quantity=8,
            comment="Ручная инвентаризация",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(inventory)
    movement = await db_session.scalar(select(StockMovement))
    assert result.stock_quantity == 8
    assert result.available_quantity == 8
    assert inventory.available_quantity == 8
    assert movement is not None
    assert movement.movement_type == StockMovementType.ADJUSTMENT
    assert movement.quantity == 3
    assert movement.to_warehouse_id == inventory.warehouse_id


async def test_inventory_adjustment_rejects_quantity_below_reserved(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    inventory.reserved_quantity = 3
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="меньше резерва"):
        await adjust_miniapp_inventory(
            db_session,
            payload=MiniAppInventoryAdjustmentCreate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
                product_id=product.id,
                warehouse_id=inventory.warehouse_id,
                available_quantity=2,
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_admin_can_transfer_inventory_between_warehouses(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, source_inventory = await seed_product(db_session, student)
    target_warehouse = Warehouse(
        tenant_id=student.tenant_id,
        slug="common",
        name="Общий склад",
        warehouse_type=WarehouseType.COMMON,
    )
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    db_session.add(target_warehouse)
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    result = await transfer_miniapp_inventory(
        db_session,
        payload=MiniAppInventoryTransferCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            product_id=product.id,
            from_warehouse_id=source_inventory.warehouse_id,
            to_warehouse_id=target_warehouse.id,
            quantity=2,
            comment="Перемещение в общий склад",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(source_inventory)
    target_inventory = await db_session.scalar(
        select(WarehouseInventory).where(
            WarehouseInventory.warehouse_id == target_warehouse.id,
            WarehouseInventory.product_id == product.id,
        )
    )
    movement = await db_session.scalar(
        select(StockMovement).where(StockMovement.movement_type == StockMovementType.TRANSFER)
    )
    assert result.quantity == 2
    assert result.from_stock_quantity == 3
    assert result.to_stock_quantity == 2
    assert source_inventory.available_quantity == 3
    assert target_inventory is not None
    assert target_inventory.available_quantity == 2
    assert movement is not None
    assert movement.from_warehouse_id == source_inventory.warehouse_id
    assert movement.to_warehouse_id == target_warehouse.id


async def test_admin_can_create_and_update_warehouse_from_miniapp(db_session) -> None:
    student = await seed_linked_student(db_session)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    created = await upsert_miniapp_warehouse(
        db_session,
        payload=MiniAppWarehouseUpsert(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            slug="new-storage",
            name="Новый склад",
            warehouse_type=WarehouseType.EXTERNAL,
            address="Поставщик",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    updated = await upsert_miniapp_warehouse(
        db_session,
        payload=MiniAppWarehouseUpsert(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            warehouse_id=created.id,
            slug="new-storage",
            name="Новый склад 2",
            warehouse_type=WarehouseType.PARTNER,
            address="Партнер",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    warehouse = await db_session.scalar(select(Warehouse).where(Warehouse.id == created.id))
    assert created.slug == "new-storage"
    assert updated.name == "Новый склад 2"
    assert updated.warehouse_type == WarehouseType.PARTNER
    assert warehouse is not None
    assert warehouse.address == "Партнер"


async def test_admin_can_create_and_update_product_from_miniapp(db_session) -> None:
    student = await seed_linked_student(db_session)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    created = await upsert_miniapp_product(
        db_session,
        payload=MiniAppProductUpsert(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            sku="book-1",
            name="Книга Python",
            category_name="Книги",
            price_astrocoins=500,
            description="Подарочная книга",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    updated = await upsert_miniapp_product(
        db_session,
        payload=MiniAppProductUpsert(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            product_id=created.id,
            sku="book-1",
            name="Книга Python 2",
            category_name="Книги",
            price_astrocoins=650,
            status=ProductStatus.HIDDEN,
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    product = await db_session.scalar(select(Product).where(Product.id == created.id))
    category = await db_session.scalar(
        select(ProductCategory).where(ProductCategory.name == "Книги")
    )
    assert created.sku == "BOOK-1"
    assert created.category_name == "Книги"
    assert updated.name == "Книга Python 2"
    assert updated.price_astrocoins == 650
    assert updated.status == ProductStatus.HIDDEN
    assert product is not None
    assert product.status == ProductStatus.HIDDEN
    assert category is not None

    public_catalog = await list_miniapp_catalog(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert created.id not in {item.id for item in public_catalog.products}

    with pytest.raises(MiniAppStoreError):
        await list_miniapp_catalog(
            db_session,
            tenant_slug="nizhniy-novgorod-partner-a",
            include_inactive=True,
        )

    admin_catalog = await list_miniapp_catalog(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        max_user_id=53364725,
        include_inactive=True,
    )
    assert created.id in {item.id for item in admin_catalog.products}
