from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
import app.services.miniapp as miniapp_service
from app.models.account import (
    MaxAccount,
    StaffRoleAssignment,
    StaffVenueScope,
    StaffWarehousePreference,
)
from app.models.audit import AuditLog
from app.models.base import Base
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
    WarehouseType,
)
from app.models.store import (
    Order,
    OrderItem,
    Product,
    ProductCategory,
    ProductCode,
    StockMovement,
    StudentCartItem,
    Warehouse,
    WarehouseInventory,
)
from app.models.student import AstrocoinLedgerEntry, Student, Wallet
from app.models.tenant import Venue
from app.schemas.access import AccessLinkCreate
from app.schemas.miniapp import (
    MiniAppAccrualCreate,
    MiniAppInventoryAdjustmentCreate,
    MiniAppInventoryTransferCreate,
    MiniAppOrderActionCreate,
    MiniAppOrderCancelCreate,
    MiniAppOrderCreate,
    MiniAppOrderItemCreate,
    MiniAppOrderItemPickBatchItem,
    MiniAppOrderItemPickBatchUpdate,
    MiniAppOrderWarehouseAssignmentCreate,
    MiniAppOrderWarehouseAssignmentItem,
    MiniAppProductInventoryWrite,
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
    delete_miniapp_product,
    delete_miniapp_warehouse,
    get_miniapp_ops_summary,
    issue_miniapp_order,
    list_miniapp_admin_history,
    list_miniapp_catalog,
    mark_miniapp_order_delivered_to_venue,
    set_miniapp_order_items_picked,
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


async def grant_store_admin(db_session, *, tenant_id: UUID) -> MaxAccount:
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    db_session.add(
        StaffRoleAssignment(
            tenant_id=tenant_id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    return account


async def test_order_waits_for_admin_warehouse_and_debits_wallet(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    secondary_warehouse = Warehouse(
        tenant_id=student.tenant_id,
        slug="secondary-stock",
        name="Дополнительный склад",
        warehouse_type=WarehouseType.COMMON,
    )
    db_session.add(secondary_warehouse)
    await db_session.flush()
    db_session.add(
        WarehouseInventory(
            tenant_id=student.tenant_id,
            warehouse_id=secondary_warehouse.id,
            product_id=product.id,
            available_quantity=4,
        )
    )
    db_session.add(
        StudentCartItem(
            tenant_id=student.tenant_id,
            student_id=student.id,
            product_id=product.id,
            quantity=2,
        )
    )
    await db_session.commit()

    catalog = await list_miniapp_catalog(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        max_user_id=53364725,
    )

    assert len(catalog.products) == 1
    # One item cannot be assembled from several warehouses, so 5 + 4 must not
    # be exposed as 9 purchasable units.
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
    assert created.items[0].suggested_warehouse_id == inventory.warehouse_id

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet is not None
    assert inventory.reserved_quantity == 2
    assert wallet.balance == 760
    assert await db_session.scalar(
        select(StudentCartItem.id).where(StudentCartItem.student_id == student.id)
    ) is None

    order_items = (await db_session.scalars(select(OrderItem))).all()
    ledger_entries = (await db_session.scalars(select(AstrocoinLedgerEntry))).all()
    assert len(order_items) == 1
    assert len(ledger_entries) == 1
    assert ledger_entries[0].direction == LedgerDirection.DEBIT


async def test_digital_product_issues_one_retained_code_and_is_idempotent(
    db_session,
    monkeypatch,
) -> None:
    low_code_notifications: list[int] = []

    async def capture_low_codes(*_args, available_codes: int, **_kwargs) -> None:
        low_code_notifications.append(available_codes)

    monkeypatch.setattr(
        miniapp_service,
        "schedule_low_digital_codes_notification",
        capture_low_codes,
    )
    student = await seed_linked_student(db_session)
    category = ProductCategory(
        tenant_id=student.tenant_id,
        slug="digital-gifts",
        name="Цифровые подарки",
        sort_order=10,
    )
    product = Product(
        tenant_id=student.tenant_id,
        category=category,
        sku="ROBLOX-100",
        name="Карта Roblox",
        price_astrocoins=200,
        fulfillment_type=ProductFulfillmentType.DIGITAL_CODE,
    )
    db_session.add_all([category, product])
    await db_session.flush()
    db_session.add_all(
        [
            ProductCode(tenant_id=student.tenant_id, product_id=product.id, code="RBX-ONE"),
            ProductCode(tenant_id=student.tenant_id, product_id=product.id, code="RBX-TWO"),
        ]
    )
    await db_session.commit()

    payload = MiniAppOrderCreate(
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_id=student.id,
        items=[MiniAppOrderItemCreate(product_id=product.id, quantity=1)],
        request_key="digital-order-001",
    )
    created = await create_miniapp_order(
        db_session,
        payload=payload,
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    db_session.add(
        StudentCartItem(
            tenant_id=student.tenant_id,
            student_id=student.id,
            product_id=product.id,
            quantity=1,
        )
    )
    await db_session.commit()
    repeated = await create_miniapp_order(
        db_session,
        payload=payload,
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert created.order.status == OrderStatus.ISSUED_TO_STUDENT
    assert len(created.items[0].issued_codes) == 1
    assert created.items[0].issued_codes[0] in {"RBX-ONE", "RBX-TWO"}
    assert repeated.items[0].issued_codes == created.items[0].issued_codes
    codes = (await db_session.scalars(select(ProductCode).order_by(ProductCode.code))).all()
    assert len(codes) == 2
    assert [code.status for code in codes].count(ProductCodeStatus.ISSUED) == 1
    await db_session.refresh(product)
    assert product.digital_codes_low_notified is True
    assert low_code_notifications == [1]
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet is not None
    assert wallet.balance == 800
    assert await db_session.scalar(
        select(StudentCartItem.id).where(StudentCartItem.student_id == student.id)
    ) is None


async def test_digital_and_warehouse_products_require_separate_orders(db_session) -> None:
    student = await seed_linked_student(db_session)
    physical_product, _ = await seed_product(db_session, student)
    digital_product = Product(
        tenant_id=student.tenant_id,
        category_id=physical_product.category_id,
        sku="DIGITAL-1",
        name="Цифровой код",
        price_astrocoins=100,
        fulfillment_type=ProductFulfillmentType.DIGITAL_CODE,
    )
    db_session.add(digital_product)
    await db_session.flush()
    db_session.add(
        ProductCode(
            tenant_id=student.tenant_id,
            product_id=digital_product.id,
            code="DIGITAL-CODE-1",
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="отдельными заказами"):
        await create_miniapp_order(
            db_session,
            payload=MiniAppOrderCreate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
                student_id=student.id,
                items=[
                    MiniAppOrderItemCreate(product_id=physical_product.id, quantity=1),
                    MiniAppOrderItemCreate(product_id=digital_product.id, quantity=1),
                ],
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_admin_history_is_limited_to_selected_tenant(db_session) -> None:
    student = await seed_linked_student(db_session)
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
    db_session.add_all(
        [
            AuditLog(
                tenant_id=student.tenant_id,
                actor_account_id=account.id,
                action="product.updated",
                entity_type="product",
                payload={"name": "Тестовый товар"},
            ),
            AuditLog(
                tenant_id=student.tenant_id,
                action="amocrm.students_synced",
                entity_type="student",
                payload={"lead_ids": ["1"], "incomplete_leads": {}},
            ),
        ]
    )
    await db_session.commit()

    actions = await list_miniapp_admin_history(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        kind="actions",
    )
    amocrm = await list_miniapp_admin_history(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        kind="amocrm",
    )

    action_names = [entry.action for entry in actions.entries]
    assert "product.updated" in action_names
    assert "amocrm.students_synced" not in action_names
    assert [entry.action for entry in amocrm.entries] == ["amocrm.students_synced"]


async def test_repeated_order_request_does_not_debit_twice(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    payload = MiniAppOrderCreate(
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_id=student.id,
        items=[MiniAppOrderItemCreate(product_id=product.id, quantity=2)],
        request_key="order-request-0001",
    )

    first = await create_miniapp_order(
        db_session,
        payload=payload,
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    repeated = await create_miniapp_order(
        db_session,
        payload=payload,
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    orders = (await db_session.scalars(select(Order))).all()
    entries = (await db_session.scalars(select(AstrocoinLedgerEntry))).all()
    assert repeated.order.id == first.order.id
    assert wallet is not None
    assert wallet.balance == 760
    assert inventory.reserved_quantity == 2
    assert len(orders) == 1
    assert len(entries) == 1


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
    assert summary.pending_issue_orders == 0
    assert summary.order_statuses[0].status == OrderStatus.RESERVED
    assert summary.order_statuses[0].count == 1
    assert summary.recent_open_orders[0].id == created.order.id
    assert summary.recent_open_orders[0].items[0].product_name == product.name
    assert len(summary.low_stock) == 1
    assert summary.low_stock[0].available_quantity == 3
    assert summary.total_stock_quantity == 5
    assert summary.total_reserved_quantity == 2


async def test_director_ops_summary_excludes_orders_from_other_venues(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, _inventory = await seed_product(db_session, student)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    assignment = StaffRoleAssignment(
        tenant_id=student.tenant_id,
        account_id=account.id,
        role=StaffRole.PARTNER_DIRECTOR,
        status=AssignmentStatus.ACTIVE,
    )
    other_venue = Venue(
        tenant_id=student.tenant_id,
        slug="other-venue",
        name="Другая площадка",
    )
    db_session.add_all([assignment, other_venue])
    await db_session.flush()
    db_session.add(StaffVenueScope(assignment_id=assignment.id, venue_id=student.venue_id))
    other_student = Student(
        tenant_id=student.tenant_id,
        venue_id=other_venue.id,
        student_access_code="other-venue-student",
        first_name="Чужой",
        last_name="Ученик",
        venue_name=other_venue.name,
    )
    db_session.add(other_student)
    await db_session.flush()
    db_session.add(
        Order(
            tenant_id=student.tenant_id,
            student_id=other_student.id,
            order_number=999,
            status=OrderStatus.RESERVED,
            total_astrocoins=product.price_astrocoins,
            venue_name=other_venue.name,
        )
    )
    await db_session.commit()

    await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=1)],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    summary = await get_miniapp_ops_summary(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert summary.staff_role == StaffRole.PARTNER_DIRECTOR
    assert summary.total_orders == 1
    assert len(summary.recent_open_orders) == 1
    assert summary.recent_open_orders[0].student_id == student.id


@pytest.mark.parametrize(
    "initial_status",
    [OrderStatus.CREATED, OrderStatus.RESERVED, OrderStatus.PROBLEM],
)
async def test_admin_assigns_order_warehouse_after_checkout(
    db_session,
    initial_status: OrderStatus,
) -> None:
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
    assert venue_inventory.reserved_quantity == 3

    order = await db_session.get(Order, created.order.id)
    assert order is not None
    order.status = initial_status
    await db_session.commit()

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
    assert assigned.order.status == OrderStatus.AWAITING_DELIVERY
    await db_session.refresh(common_inventory)
    await db_session.refresh(venue_inventory)
    assert common_inventory.reserved_quantity == 3
    assert venue_inventory.reserved_quantity == 0


async def test_cancel_order_releases_stock_and_refunds_wallet(db_session) -> None:
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


async def test_parent_cannot_cancel_after_warehouse_is_confirmed(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, _inventory = await seed_product(db_session, student)
    created = await create_miniapp_order(
        db_session,
        payload=MiniAppOrderCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            student_id=student.id,
            items=[MiniAppOrderItemCreate(product_id=product.id, quantity=1)],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    admin = MaxAccount(max_user_id=90000001, display_name="Администратор")
    db_session.add(admin)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    inventory = await db_session.scalar(
        select(WarehouseInventory).where(WarehouseInventory.product_id == product.id)
    )
    assert inventory is not None
    await assign_miniapp_order_warehouses(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderWarehouseAssignmentCreate(
            max_user_id=admin.max_user_id,
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

    with pytest.raises(MiniAppStoreError, match="только администратор или директор"):
        await cancel_miniapp_order(
            db_session,
            order_id=created.order.id,
            payload=MiniAppOrderCancelCreate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
                reason="Передумали",
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_staff_completes_physical_order_workflow(db_session) -> None:
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
    assigned = await assign_miniapp_order_warehouses(
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

    with pytest.raises(MiniAppStoreError, match="подтвердите сборку"):
        await mark_miniapp_order_delivered_to_venue(
            db_session,
            order_id=created.order.id,
            payload=MiniAppOrderActionCreate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )

    assigned_item = await db_session.get(OrderItem, assigned.order.items[0].id)
    assert assigned_item is not None
    assigned_warehouse_id = assigned_item.warehouse_id
    assigned_item.warehouse_id = None
    await db_session.commit()
    with pytest.raises(MiniAppStoreError, match="подтвердите склад"):
        await set_miniapp_order_items_picked(
            db_session,
            payload=MiniAppOrderItemPickBatchUpdate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
                items=[
                    MiniAppOrderItemPickBatchItem(
                        order_id=created.order.id,
                        order_item_id=assigned.order.items[0].id,
                        is_picked=True,
                    )
                ],
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )
    assigned_item.warehouse_id = assigned_warehouse_id
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="Позиция заказа не найдена"):
        await set_miniapp_order_items_picked(
            db_session,
            payload=MiniAppOrderItemPickBatchUpdate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
                items=[
                    MiniAppOrderItemPickBatchItem(
                        order_id=created.order.id,
                        order_item_id=assigned.order.items[0].id,
                        is_picked=True,
                    ),
                    MiniAppOrderItemPickBatchItem(
                        order_id=created.order.id,
                        order_item_id=uuid4(),
                        is_picked=True,
                    ),
                ],
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )
    unchanged_item = await db_session.get(OrderItem, assigned.order.items[0].id)
    assert unchanged_item is not None
    assert unchanged_item.is_picked is False

    picked = await set_miniapp_order_items_picked(
        db_session,
        payload=MiniAppOrderItemPickBatchUpdate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            items=[
                MiniAppOrderItemPickBatchItem(
                    order_id=created.order.id,
                    order_item_id=assigned.order.items[0].id,
                    is_picked=True,
                )
            ],
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert picked.updated_items == 1
    picked_item = await db_session.get(OrderItem, assigned.order.items[0].id)
    assert picked_item is not None
    assert picked_item.is_picked is True

    delivered = await mark_miniapp_order_delivered_to_venue(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderActionCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert delivered.order.status == OrderStatus.DELIVERED_TO_VENUE

    with pytest.raises(MiniAppStoreError, match="только до доставки"):
        await set_miniapp_order_items_picked(
            db_session,
            payload=MiniAppOrderItemPickBatchUpdate(
                max_user_id=53364725,
                tenant_slug="nizhniy-novgorod-partner-a",
                items=[
                    MiniAppOrderItemPickBatchItem(
                        order_id=created.order.id,
                        order_item_id=assigned.order.items[0].id,
                        is_picked=False,
                    )
                ],
            ),
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )

    transferred = await miniapp_service.transfer_miniapp_order_to_teacher(
        db_session,
        order_id=created.order.id,
        payload=MiniAppOrderActionCreate(
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    assert transferred.order.status == OrderStatus.TRANSFERRED_TO_TEACHER

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


async def test_repeated_accrual_request_does_not_credit_twice(db_session) -> None:
    student = await seed_linked_student(db_session)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
    account.display_name = student.teacher_name
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    payload = MiniAppAccrualCreate(
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_ids=[student.id],
        amount=75,
        reason="За проект на уроке",
        request_key="accrual-request-0001",
    )

    await accrue_miniapp_astrocoins(
        db_session,
        payload=payload,
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )
    repeated = await accrue_miniapp_astrocoins(
        db_session,
        payload=payload,
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
    assert repeated.credited_students == 1
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
            name="Новый склад",
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
            name="Новый склад 2",
            address="Партнер",
        ),
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    warehouse = await db_session.scalar(select(Warehouse).where(Warehouse.id == created.id))
    assert created.slug == "новый-склад"
    assert updated.name == "Новый склад 2"
    assert updated.slug == "новый-склад"
    assert updated.warehouse_type == WarehouseType.COMMON
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
    first_warehouse = Warehouse(
        tenant_id=student.tenant_id,
        slug="main-stock",
        name="Основной склад",
        warehouse_type=WarehouseType.COMMON,
    )
    second_warehouse = Warehouse(
        tenant_id=student.tenant_id,
        slug="reserve-stock",
        name="Резервный склад",
        warehouse_type=WarehouseType.COMMON,
    )
    db_session.add_all([first_warehouse, second_warehouse])
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
            inventories=[
                MiniAppProductInventoryWrite(
                    warehouse_id=first_warehouse.id,
                    stock_quantity=12,
                ),
                MiniAppProductInventoryWrite(
                    warehouse_id=second_warehouse.id,
                    stock_quantity=4,
                ),
            ],
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
            inventories=[
                MiniAppProductInventoryWrite(
                    warehouse_id=second_warehouse.id,
                    stock_quantity=14,
                )
            ],
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
    assert updated.available_quantity == 14
    assert [warehouse.warehouse_name for warehouse in updated.warehouses] == [
        "Резервный склад"
    ]
    assert product is not None
    assert product.status == ProductStatus.HIDDEN
    assert category is not None

    inventory_rows = (
        await db_session.scalars(
            select(WarehouseInventory)
            .where(WarehouseInventory.product_id == created.id)
            .order_by(WarehouseInventory.warehouse_id)
        )
    ).all()
    inventory_by_warehouse = {row.warehouse_id: row for row in inventory_rows}
    assert inventory_by_warehouse[first_warehouse.id].available_quantity == 0
    assert inventory_by_warehouse[first_warehouse.id].is_active is False
    assert inventory_by_warehouse[second_warehouse.id].available_quantity == 14
    assert inventory_by_warehouse[second_warehouse.id].is_active is True

    public_catalog = await list_miniapp_catalog(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        max_user_id=53364725,
    )
    assert created.id not in {item.id for item in public_catalog.products}

    with pytest.raises(MiniAppStoreError):
        await list_miniapp_catalog(
            db_session,
            tenant_slug="nizhniy-novgorod-partner-a",
            max_user_id=999999999,
            include_inactive=True,
        )

    admin_catalog = await list_miniapp_catalog(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        max_user_id=53364725,
        include_inactive=True,
    )
    assert created.id in {item.id for item in admin_catalog.products}


async def test_admin_can_delete_unused_product_and_related_drafts(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    await grant_store_admin(db_session, tenant_id=student.tenant_id)
    product.photo_url = "https://algo.test/media/products/deleted.png"
    product.fulfillment_type = ProductFulfillmentType.DIGITAL_CODE
    inventory.available_quantity = 0
    db_session.add_all(
        [
            ProductCode(
                tenant_id=student.tenant_id,
                product_id=product.id,
                code="UNUSED-CODE",
                status=ProductCodeStatus.AVAILABLE,
            ),
            StudentCartItem(
                tenant_id=student.tenant_id,
                student_id=student.id,
                product_id=product.id,
                quantity=1,
            ),
        ]
    )
    await db_session.commit()

    photo_url = await delete_miniapp_product(
        db_session,
        product_id=product.id,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert photo_url == "https://algo.test/media/products/deleted.png"
    assert await db_session.scalar(select(Product).where(Product.id == product.id)) is None
    assert await db_session.scalar(
        select(WarehouseInventory).where(WarehouseInventory.product_id == product.id)
    ) is None
    assert await db_session.scalar(
        select(StudentCartItem).where(StudentCartItem.product_id == product.id)
    ) is None
    assert await db_session.scalar(
        select(ProductCode).where(ProductCode.product_id == product.id)
    ) is None
    assert await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "product.deleted")
    ) is not None


async def test_product_delete_rejects_stock_and_order_history(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    await grant_store_admin(db_session, tenant_id=student.tenant_id)

    with pytest.raises(MiniAppStoreError, match="числится 5 шт"):
        await delete_miniapp_product(
            db_session,
            product_id=product.id,
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )

    inventory.available_quantity = 0
    order = Order(
        tenant_id=student.tenant_id,
        student_id=student.id,
        order_number=101,
        status=OrderStatus.RESERVED,
        total_astrocoins=120,
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add(
        OrderItem(
            tenant_id=student.tenant_id,
            order_id=order.id,
            product_id=product.id,
            quantity=1,
            unit_price_astrocoins=120,
            total_price_astrocoins=120,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="есть в заказах"):
        await delete_miniapp_product(
            db_session,
            product_id=product.id,
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )


async def test_admin_can_delete_empty_warehouse_and_default_preference(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    account = await grant_store_admin(db_session, tenant_id=student.tenant_id)
    inventory.available_quantity = 0
    db_session.add(
        StaffWarehousePreference(
            tenant_id=student.tenant_id,
            account_id=account.id,
            warehouse_id=inventory.warehouse_id,
        )
    )
    await db_session.commit()

    await delete_miniapp_warehouse(
        db_session,
        warehouse_id=inventory.warehouse_id,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        default_tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert await db_session.scalar(
        select(Warehouse).where(Warehouse.id == inventory.warehouse_id)
    ) is None
    assert await db_session.scalar(
        select(WarehouseInventory).where(WarehouseInventory.warehouse_id == inventory.warehouse_id)
    ) is None
    assert await db_session.scalar(
        select(StaffWarehousePreference).where(
            StaffWarehousePreference.warehouse_id == inventory.warehouse_id
        )
    ) is None
    assert await db_session.scalar(select(Product).where(Product.id == product.id)) is not None
    assert await db_session.scalar(
        select(AuditLog).where(AuditLog.action == "warehouse.deleted")
    ) is not None


async def test_warehouse_delete_rejects_stock_and_movement_history(db_session) -> None:
    student = await seed_linked_student(db_session)
    product, inventory = await seed_product(db_session, student)
    account = await grant_store_admin(db_session, tenant_id=student.tenant_id)

    with pytest.raises(MiniAppStoreError, match="числится 5 шт"):
        await delete_miniapp_warehouse(
            db_session,
            warehouse_id=inventory.warehouse_id,
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )

    inventory.available_quantity = 0
    db_session.add(
        StockMovement(
            tenant_id=student.tenant_id,
            product_id=product.id,
            to_warehouse_id=inventory.warehouse_id,
            actor_account_id=account.id,
            movement_type=StockMovementType.INITIAL,
            quantity=5,
        )
    )
    await db_session.commit()

    with pytest.raises(MiniAppStoreError, match="историей движения товаров"):
        await delete_miniapp_warehouse(
            db_session,
            warehouse_id=inventory.warehouse_id,
            max_user_id=53364725,
            tenant_slug="nizhniy-novgorod-partner-a",
            default_tenant_slug="nizhniy-novgorod-partner-a",
        )
