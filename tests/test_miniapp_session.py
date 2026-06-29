from dataclasses import replace

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
)
from app.models.store import Order
from app.models.student import AstrocoinLedgerEntry, Student, Wallet
from app.schemas.access import AccessLinkCreate
from app.services.access import create_contact_access_links
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.miniapp import get_miniapp_session


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


async def test_get_miniapp_session_returns_linked_students_wallet_orders_and_ledger(
    db_session,
) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    await upsert_crm_student_rows(db_session, [crm_row()], defaults=defaults)
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
    wallet.balance = 1240
    db_session.add(
        Order(
            tenant_id=student.tenant_id,
            student_id=student.id,
            order_number=1,
            status=OrderStatus.CREATED,
            total_astrocoins=120,
            teacher_name=student.teacher_name,
            venue_name=student.venue_name,
        )
    )
    db_session.add(
        AstrocoinLedgerEntry(
            tenant_id=student.tenant_id,
            wallet_id=wallet.id,
            student_id=student.id,
            idempotency_key="test-ledger-1",
            direction=LedgerDirection.CREDIT,
            amount=120,
            reason="Начисление за проект",
        )
    )
    await db_session.commit()

    session = await get_miniapp_session(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.account is not None
    assert session.account.username == "parent_user"
    assert session.student_roles == [StudentAccessRole.PARENT]
    assert len(session.students) == 1
    assert session.students[0].display_name == "Алиса"
    assert session.students[0].balance == 1240
    assert len(session.orders) == 1
    assert session.orders[0].order_number == 1
    assert len(session.ledger) == 1
    assert session.ledger[0].amount == 120


async def test_staff_session_returns_tenant_students_sorted_by_group(db_session) -> None:
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    second_row = replace(
        crm_row(),
        row_number=3,
        deal_id="2468",
        uuid="uuid-2",
        lms_student_id="ST-002",
        first_name="Борис",
        group_name="Scratch, сб 12:00",
        course_name="Scratch",
        venue_name="Гагарина 64",
        contact_ids="682",
    )
    await upsert_crm_student_rows(db_session, [second_row, crm_row()], defaults=defaults)
    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
        ),
    )
    student = await db_session.scalar(select(Student).where(Student.id == links[0].student_id))
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    assert student is not None
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

    session = await get_miniapp_session(
        db_session,
        max_user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert session.staff_roles == [StaffRole.TEACHER]
    assert [student.display_name for student in session.students] == ["Алиса", "Борис"]
    assert [student.group_name for student in session.students] == [
        "Python Start, вс 10:00",
        "Scratch, сб 12:00",
    ]
