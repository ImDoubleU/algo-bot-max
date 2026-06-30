import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import StaffRole, TenantStatus
from app.models.tenant import City, Partner, Tenant
from app.services.staff import bootstrap_staff_role


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def seed_tenant(db_session) -> Tenant:
    city = City(slug="nizhniy-novgorod", name="Нижний Новгород")
    partner = Partner(slug="partner-a", name="Партнер A")
    tenant = Tenant(
        city=city,
        partner=partner,
        slug="nizhniy-novgorod-partner-a",
        name="Нижний Новгород / Партнер A",
        status=TenantStatus.ACTIVE,
    )
    db_session.add(tenant)
    await db_session.commit()
    return tenant


async def test_bootstrap_staff_role_is_idempotent(db_session) -> None:
    tenant = await seed_tenant(db_session)

    first = await bootstrap_staff_role(
        db_session,
        tenant_slug=tenant.slug,
        max_user_id=53364725,
        username="admin_user",
        role=StaffRole.SUPERADMIN,
    )
    second = await bootstrap_staff_role(
        db_session,
        tenant_slug=tenant.slug,
        max_user_id=53364725,
        username="admin_user",
        role=StaffRole.SUPERADMIN,
    )

    accounts = (await db_session.scalars(select(MaxAccount))).all()
    assignments = (await db_session.scalars(select(StaffRoleAssignment))).all()
    assert first.account_created is True
    assert first.assignment_created is True
    assert second.account_created is False
    assert second.assignment_created is False
    assert len(accounts) == 1
    assert len(assignments) == 1
    assert assignments[0].role == StaffRole.SUPERADMIN
