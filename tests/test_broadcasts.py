import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Student, StudentAccessLink, Wallet
from app.models.tenant import City, Partner, Tenant
from app.schemas.broadcasts import BroadcastAudienceRequest
from app.services.broadcasts import preview_school_broadcast


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_broadcast_preview_scopes_and_deduplicates_recipients(db_session) -> None:
    city = City(slug="city-a", name="Город")
    partner = Partner(slug="partner-a", name="Партнёр")
    db_session.add_all([city, partner])
    await db_session.flush()
    tenant = Tenant(
        city_id=city.id,
        partner_id=partner.id,
        slug="city-a-partner-a",
        name="Город · Партнёр",
    )
    db_session.add(tenant)
    await db_session.flush()

    admin = MaxAccount(max_user_id=1001, display_name="Администратор")
    parent = MaxAccount(max_user_id=1002, display_name="Родитель")
    student_account = MaxAccount(max_user_id=1003, display_name="Ученик")
    db_session.add_all([admin, parent, student_account])
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=tenant.id,
            account_id=admin.id,
            role=StaffRole.ADMIN,
            status=AssignmentStatus.ACTIVE,
        )
    )

    first_student = Student(
        tenant_id=tenant.id,
        student_access_code="student-a",
        first_name="Алиса",
        last_name="Иванова",
        group_name="Python",
        status=StudentStatus.ACTIVE,
    )
    second_student = Student(
        tenant_id=tenant.id,
        student_access_code="student-b",
        first_name="Борис",
        last_name="Петров",
        group_name="Scratch",
        status=StudentStatus.ACTIVE,
    )
    db_session.add_all([first_student, second_student])
    await db_session.flush()
    db_session.add_all(
        [
            Wallet(tenant_id=tenant.id, student_id=first_student.id, balance=100),
            Wallet(tenant_id=tenant.id, student_id=second_student.id, balance=900),
            StudentAccessLink(
                tenant_id=tenant.id,
                account_id=parent.id,
                student_id=first_student.id,
                role=StudentAccessRole.PARENT,
                status=StudentAccessStatus.ACTIVE,
            ),
            StudentAccessLink(
                tenant_id=tenant.id,
                account_id=parent.id,
                student_id=second_student.id,
                role=StudentAccessRole.PARENT,
                status=StudentAccessStatus.ACTIVE,
            ),
            StudentAccessLink(
                tenant_id=tenant.id,
                account_id=student_account.id,
                student_id=first_student.id,
                role=StudentAccessRole.STUDENT,
                status=StudentAccessStatus.ACTIVE,
            ),
        ]
    )
    await db_session.commit()

    preview = await preview_school_broadcast(
        db_session,
        payload=BroadcastAudienceRequest(
            max_user_id=admin.max_user_id,
            tenant_slug=tenant.slug,
            recipient_category="all",
            group_names=["Python"],
        ),
        default_tenant_slug=tenant.slug,
    )
    assert preview.recipient_count == 2
    assert preview.matched_students == 1

    low_balance_parents = await preview_school_broadcast(
        db_session,
        payload=BroadcastAudienceRequest(
            max_user_id=admin.max_user_id,
            tenant_slug=tenant.slug,
            recipient_category="parents",
            audience_filter="low_balance",
            balance_threshold=300,
        ),
        default_tenant_slug=tenant.slug,
    )
    assert low_balance_parents.recipient_count == 1
    assert low_balance_parents.matched_students == 1
