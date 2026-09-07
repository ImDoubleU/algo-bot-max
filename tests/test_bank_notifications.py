from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
)
from app.models.student import Student, StudentAccessLink
from app.models.tenant import City, Partner, Tenant
from app.services.max_notifications import (
    schedule_bank_early_close_notification,
    schedule_bank_rate_change_notification,
    schedule_bank_top_up_notification,
)


@pytest.fixture
async def notification_context():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        city = City(slug="notify-city", name="Notify City")
        partner = Partner(slug="notify-partner", name="Notify Partner")
        session.add_all([city, partner])
        await session.flush()
        tenant = Tenant(
            city_id=city.id,
            partner_id=partner.id,
            slug="notify-city-partner",
            name="Notify City / Partner",
        )
        student = Student(
            tenant=tenant,
            student_access_code="NOTIFY-STUDENT",
            first_name="Alex",
            last_name="Student",
        )
        student_account = MaxAccount(max_user_id=92001, display_name="Alex")
        parent_account = MaxAccount(max_user_id=92002, display_name="Parent")
        staff_account = MaxAccount(max_user_id=92003, display_name="Admin")
        session.add_all([tenant, student, student_account, parent_account, staff_account])
        await session.flush()
        session.add_all(
            [
                StudentAccessLink(
                    tenant_id=tenant.id,
                    account_id=student_account.id,
                    student_id=student.id,
                    role=StudentAccessRole.STUDENT,
                    status=StudentAccessStatus.ACTIVE,
                    source=StudentAccessSource.ADMIN,
                ),
                StudentAccessLink(
                    tenant_id=tenant.id,
                    account_id=parent_account.id,
                    student_id=student.id,
                    role=StudentAccessRole.PARENT,
                    status=StudentAccessStatus.ACTIVE,
                    source=StudentAccessSource.ADMIN,
                ),
                StaffRoleAssignment(
                    tenant_id=tenant.id,
                    account_id=staff_account.id,
                    role=StaffRole.ADMIN,
                    status=AssignmentStatus.ACTIVE,
                ),
            ]
        )
        await session.commit()
        yield session, tenant, student
    await engine.dispose()


async def test_bank_notifications_target_student_and_parent_with_expected_copy(
    notification_context,
    monkeypatch,
):
    session, tenant, student = notification_context
    captured: list[dict] = []
    monkeypatch.setattr(
        "app.services.max_notifications.get_settings",
        lambda: SimpleNamespace(
            max_order_notifications_enabled=True,
            max_bot_token="test-token",
        ),
    )
    monkeypatch.setattr(
        "app.services.max_notifications._schedule_direct_notification",
        lambda **kwargs: captured.append(kwargs),
    )

    await schedule_bank_top_up_notification(
        session,
        tenant=tenant,
        student=student,
        amount=100,
        personal_balance=900,
        bank_balance=1100,
        maturity_on=date(2026, 12, 31),
    )
    await schedule_bank_rate_change_notification(
        session,
        tenant=tenant,
        students=[student],
        old_rate_bps=3650,
        new_rate_bps=7300,
        effective_on=date(2026, 9, 6),
    )
    await schedule_bank_early_close_notification(
        session,
        tenant=tenant,
        student=student,
        returned_principal=1000,
        forfeited_interest=30,
        personal_balance=2000,
    )

    assert len(captured) == 3
    assert all(item["user_ids"] == {92001, 92002} for item in captured)
    assert all(item["view"] == "bank" for item in captured)
    assert "Вклад пополнен" in captured[0]["text"]
    assert "100 AC" in captured[0]["text"]
    assert "73,00% годовых" in captured[1]["text"]
    assert "Вклад закрыт досрочно" in captured[2]["text"]
    assert "30 AC" in captured[2]["text"]
