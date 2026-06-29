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
    StaffRole,
    StudentAccessRole,
    WarehouseType,
)
from app.models.store import OrderItem, Product, ProductCategory, Warehouse, WarehouseInventory
from app.models.student import AstrocoinLedgerEntry, Student, Wallet
from app.schemas.access import AccessLinkCreate
from app.schemas.miniapp import MiniAppAccrualCreate, MiniAppOrderCreate, MiniAppOrderItemCreate
from app.services.access import create_contact_access_links
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.miniapp import (
    accrue_miniapp_astrocoins,
    create_miniapp_order,
    list_miniapp_catalog,
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


async def test_catalog_and_order_reserve_stock_and_debit_wallet(db_session) -> None:
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
    assert created.balance_after == 760
    assert created.items[0].warehouse_name == "Союзный 45"

    await db_session.refresh(inventory)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    assert wallet is not None
    assert inventory.reserved_quantity == 2
    assert wallet.balance == 760

    order_items = (await db_session.scalars(select(OrderItem))).all()
    ledger_entries = (await db_session.scalars(select(AstrocoinLedgerEntry))).all()
    assert len(order_items) == 1
    assert len(ledger_entries) == 1
    assert ledger_entries[0].direction == LedgerDirection.DEBIT


async def test_order_uses_selected_warehouse_when_provided(db_session) -> None:
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

    assert created.items[0].warehouse_name == "Общий склад"
    await db_session.refresh(common_inventory)
    await db_session.refresh(venue_inventory)
    assert common_inventory.reserved_quantity == 3
    assert venue_inventory.reserved_quantity == 0


async def test_staff_can_accrue_astrocoins_from_miniapp(db_session) -> None:
    student = await seed_linked_student(db_session)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert account is not None
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
