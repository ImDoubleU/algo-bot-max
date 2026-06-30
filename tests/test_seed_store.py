from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.cli.seed_store import DEMO_PRODUCTS, upsert_demo_store_in_session
from app.models.base import Base
from app.models.store import Product
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink, Wallet


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def seed_args(**overrides):
    defaults = {
        "tenant_slug": "nizhniy-novgorod-partner-a",
        "tenant_name": "Нижний Новгород / Партнер A",
        "city_slug": "nizhniy-novgorod",
        "city_name": "Нижний Новгород",
        "partner_slug": "partner-a",
        "partner_name": "Партнер A",
        "warehouse_slug": "common",
        "warehouse_name": "Общий склад",
        "skip_students": False,
        "student_balance": 1000,
        "max_user_id": 53364725,
        "access_role": "parent",
        "username": "parent_user",
        "display_name": "Родитель",
    }
    return SimpleNamespace(**(defaults | overrides))


async def test_seed_store_creates_demo_store_students_and_access_links(db_session) -> None:
    first = await upsert_demo_store_in_session(db_session, seed_args())
    second = await upsert_demo_store_in_session(db_session, seed_args())

    product_count = await db_session.scalar(select(func.count()).select_from(Product))
    student_count = await db_session.scalar(select(func.count()).select_from(Student))
    wallet_count = await db_session.scalar(select(func.count()).select_from(Wallet))
    contact_count = await db_session.scalar(select(func.count()).select_from(Contact))
    crm_link_count = await db_session.scalar(select(func.count()).select_from(ContactStudentLink))
    access_link_count = await db_session.scalar(select(func.count()).select_from(StudentAccessLink))

    assert first["created_products"] == len(DEMO_PRODUCTS)
    assert first["created_students"] == 2
    assert first["created_contacts"] == 1
    assert first["access_links"] == 2
    assert second["updated_products"] == len(DEMO_PRODUCTS)
    assert second["updated_students"] == 2
    assert second["access_links"] == 2
    assert product_count == len(DEMO_PRODUCTS)
    assert student_count == 2
    assert wallet_count == 2
    assert contact_count == 1
    assert crm_link_count == 2
    assert access_link_count == 2
