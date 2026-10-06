from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.enums import (
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Student, StudentAccessLink
from app.models.tenant import City, Partner, Tenant
from app.services.access import get_effective_customer_access_link
from deploy.restore_student_bindings_20261006 import restore_bindings


@pytest.fixture
async def binding_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        tenant = Tenant(
            slug="school",
            name="School",
            city=City(slug="city", name="City"),
            partner=Partner(slug="partner", name="Partner"),
        )
        account = MaxAccount(max_user_id=123, display_name="Student")
        db.add_all([tenant, account])
        await db.flush()
        student = Student(tenant_id=tenant.id, student_access_code="student", first_name="Student")
        db.add(student)
        await db.flush()
        link = StudentAccessLink(
            tenant_id=tenant.id,
            student_id=student.id,
            account_id=account.id,
            role=StudentAccessRole.STUDENT,
            source=StudentAccessSource.TEACHER_QR,
            status=StudentAccessStatus.REVOKED,
            revoked_reason="parent_required_hotfix",
            revoked_at=datetime.now(UTC),
        )
        db.add(link)
        await db.commit()
        yield db, tenant, student, account, link
    await engine.dispose()


async def test_restore_keeps_parent_gate_and_is_idempotent(binding_db):
    db, tenant, student, account, link = binding_db
    result = await restore_bindings(db)
    assert len(result) == 1
    assert result[0]["effective_access_after"] is False
    assert link.status == StudentAccessStatus.ACTIVE
    assert link.revoked_reason is None and link.revoked_at is None
    assert (
        await get_effective_customer_access_link(
            db,
            tenant_id=tenant.id,
            student_id=student.id,
            account_id=account.id,
        )
        is None
    )
    assert await restore_bindings(db) == []
    assert len((await db.scalars(select(AuditLog))).all()) == 1


async def test_restored_binding_works_when_parent_has_connected(binding_db):
    db, tenant, student, account, link = binding_db
    parent = MaxAccount(max_user_id=456, display_name="Parent")
    db.add(parent)
    await db.flush()
    db.add(
        StudentAccessLink(
            tenant_id=tenant.id,
            student_id=student.id,
            account_id=parent.id,
            role=StudentAccessRole.PARENT,
            source=StudentAccessSource.ID_ENTRY,
            status=StudentAccessStatus.ACTIVE,
        )
    )
    await db.flush()
    result = await restore_bindings(db)
    assert result[0]["effective_access_after"] is True
    assert (
        await get_effective_customer_access_link(
            db,
            tenant_id=tenant.id,
            student_id=student.id,
            account_id=account.id,
        )
        is link
    )


@pytest.mark.parametrize("reason", ["admin", "bot_stopped", "sponsor_bot_stopped", None])
async def test_legitimate_revocations_are_preserved(binding_db, reason):
    db, _, _, _, link = binding_db
    link.revoked_reason = reason
    await db.flush()
    assert await restore_bindings(db) == []
    assert link.status == StudentAccessStatus.REVOKED


async def test_departed_students_are_not_reactivated(binding_db):
    db, _, student, _, link = binding_db
    student.status = StudentStatus.DEPARTED
    await db.flush()
    assert await restore_bindings(db) == []
    assert link.status == StudentAccessStatus.REVOKED
