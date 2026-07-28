import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import AssignmentStatus, StaffRole, TenantStatus
from app.models.tenant import City, Partner, Tenant
from app.services.staff import active_staff_roles_for_tenant, bootstrap_staff_role


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


async def test_superadmin_is_global_and_partner_director_is_tenant_scoped(db_session) -> None:
    first_tenant = await seed_tenant(db_session)
    second_tenant = Tenant(
        city=City(slug="kazan", name="Казань"),
        partner=Partner(slug="partner-b", name="Партнер B"),
        slug="kazan-partner-b",
        name="Казань / Партнер B",
        status=TenantStatus.ACTIVE,
    )
    db_session.add(second_tenant)
    await db_session.commit()

    await bootstrap_staff_role(
        db_session,
        tenant_slug=first_tenant.slug,
        max_user_id=53364725,
        role=StaffRole.SUPERADMIN,
    )
    director = MaxAccount(max_user_id=20480493, display_name="Директор")
    db_session.add(director)
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=first_tenant.id,
            account_id=director.id,
            role=StaffRole.PARTNER_DIRECTOR,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()

    superadmin = await db_session.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == 53364725)
    )
    assert superadmin is not None
    superadmin_roles = await active_staff_roles_for_tenant(
        db_session,
        tenant_id=second_tenant.id,
        account_id=superadmin.id,
    )
    director_roles = await active_staff_roles_for_tenant(
        db_session,
        tenant_id=second_tenant.id,
        account_id=director.id,
    )

    assert StaffRole.SUPERADMIN in superadmin_roles
    assert director_roles == set()
