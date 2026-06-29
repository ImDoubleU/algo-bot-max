import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import AssignmentStatus, StaffRole
from app.models.store import Product, ProductCategory, Warehouse, WarehouseInventory
from app.models.tenant import City, Partner, Tenant
from app.services.miniapp import import_miniapp_products


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def seed_admin(db_session) -> None:
    city = City(slug="nizhniy-novgorod", name="Нижний Новгород")
    partner = Partner(slug="partner-a", name="Партнер A")
    db_session.add_all([city, partner])
    await db_session.flush()

    tenant = Tenant(
        city_id=city.id,
        partner_id=partner.id,
        slug="nizhniy-novgorod-partner-a",
        name="Нижний Новгород / Партнер A",
    )
    account = MaxAccount(max_user_id=53364725, username="admin_user")
    db_session.add_all([tenant, account])
    await db_session.flush()

    db_session.add(
        StaffRoleAssignment(
            tenant_id=tenant.id,
            account_id=account.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()


async def test_admin_imports_products_from_miniapp_csv(db_session) -> None:
    await seed_admin(db_session)
    content = (
        "sku,name,category,price_astrocoins,quantity,warehouse\n"
        "PEN-LOGO,Ручка металл с лого,Канцелярия,120,18,Союзный 45\n"
    ).encode()

    result = await import_miniapp_products(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        filename="products.csv",
        content=content,
    )

    assert result.created_products == 1
    assert result.created_categories == 1
    assert result.created_warehouses == 1
    assert result.updated_inventory == 1

    product = await db_session.scalar(select(Product).where(Product.sku == "PEN-LOGO"))
    category = await db_session.scalar(select(ProductCategory))
    warehouse = await db_session.scalar(select(Warehouse))
    inventory = await db_session.scalar(select(WarehouseInventory))

    assert product is not None
    assert product.name == "Ручка металл с лого"
    assert product.price_astrocoins == 120
    assert category is not None
    assert category.name == "Канцелярия"
    assert warehouse is not None
    assert warehouse.name == "Союзный 45"
    assert inventory is not None
    assert inventory.available_quantity == 18
