import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.api.routes import miniapp
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import StaffRole
from app.models.student import Student
from app.models.tenant import City, Partner, Tenant
from app.schemas.feedback_schedule import FeedbackScheduleSave


@pytest.fixture
async def storage(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        tenant = Tenant(
            slug="feedback-school",
            name="School",
            city=City(slug="feedback-city", name="City"),
            partner=Partner(slug="feedback-partner", name="Partner"),
        )
        a = MaxAccount(max_user_id=1001, display_name="Иванов Иван")
        b = MaxAccount(max_user_id=1002, display_name="Петров Петр")
        db.add_all([tenant, a, b])
        await db.flush()
        for account in [a, b]:
            db.add(
                StaffRoleAssignment(
                    tenant_id=tenant.id, account_id=account.id, role=StaffRole.TEACHER
                )
            )
            db.add(
                Student(
                    tenant_id=tenant.id,
                    student_access_code=str(account.max_user_id),
                    first_name="Student",
                    group_name="Общая группа сб 10:00",
                    teacher_name=account.display_name,
                )
            )
        await db.commit()

        async def allowed(*args, **kwargs):
            return True

        monkeypatch.setattr(miniapp, "is_global_superadmin", allowed)
        yield db, tenant, a, b, factory
    await engine.dispose()


def identity(account, tenant):
    return SimpleNamespace(max_user_id=account.max_user_id, tenant_slug=tenant.slug)


def payload(revision=0):
    return FeedbackScheduleSave.model_validate(
        {
            "group_name": "Общая группа сб 10:00",
            "revision": revision,
            "schedule": {
                "course": "Питон Старт 1-й год",
                "mode": "group",
                "rows": [
                    {
                        "id": str(uuid4()),
                        "date": "2026-10-04",
                        "lesson": 1,
                        "number": 1,
                        "repeat": False,
                        "skipped": False,
                    }
                ],
            },
        }
    )


@pytest.mark.asyncio
async def test_schedule_survives_new_session_and_is_private_to_account(storage):
    db, tenant, a, b, factory = storage
    saved = await miniapp.miniapp_save_feedback_schedule(
        payload(), db, identity(a, tenant), tenant.slug
    )
    assert saved["revision"] == 1
    async with factory() as fresh:
        loaded = await miniapp.miniapp_feedback_schedules(fresh, identity(a, tenant), tenant.slug)
        assert json.loads(loaded.body)["schedules"]["Общая группа сб 10:00"] == saved
        other = await miniapp.miniapp_feedback_schedules(fresh, identity(b, tenant), tenant.slug)
        assert json.loads(other.body)["schedules"] == {}
    assert loaded.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_stale_revision_and_migration_do_not_overwrite_server_schedule(storage):
    db, tenant, a, _, _ = storage
    who = identity(a, tenant)
    slug = tenant.slug
    original = payload()
    await miniapp.miniapp_save_feedback_schedule(original, db, who, slug)
    with pytest.raises(HTTPException) as conflict:
        await miniapp.miniapp_save_feedback_schedule(payload(), db, who, slug)
    assert conflict.value.status_code == 409
    changed = payload(1)
    await miniapp.miniapp_save_feedback_schedule(changed, db, who, slug)
    with pytest.raises(HTTPException) as conflict:
        await miniapp.miniapp_save_feedback_schedule(payload(1), db, who, slug)
    assert conflict.value.status_code == 409
    result = await miniapp.miniapp_feedback_schedules(db, who, slug)
    data = json.loads(result.body)["schedules"][original.group_name]
    assert data["revision"] == 2
    assert data["schedule"] == changed.schedule.model_dump(mode="json")


@pytest.mark.asyncio
async def test_foreign_group_and_tenant_are_denied(storage):
    db, tenant, a, _, _ = storage
    forbidden = payload()
    forbidden.group_name = "Чужая группа"
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_save_feedback_schedule(
            forbidden, db, identity(a, tenant), tenant.slug
        )
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_feedback_schedules(db, identity(a, tenant), "another-school")
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_out_of_course_material_rejected_and_repeat_normalized(storage):
    db, tenant, a, _, _ = storage
    bad = payload()
    bad.schedule.rows[0].lesson = 99
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_save_feedback_schedule(bad, db, identity(a, tenant), tenant.slug)
    assert denied.value.status_code == 422
    good = payload()
    duplicate = good.schedule.rows[0].model_copy(update={"id": uuid4(), "number": 2})
    good.schedule.rows.append(duplicate)
    result = await miniapp.miniapp_save_feedback_schedule(
        good, db, identity(a, tenant), tenant.slug
    )
    assert result["schedule"]["rows"][1]["repeat"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("date", "2026-02-31"),
        ("date", 1800000000),
        ("lesson", True),
        ("lesson", 1.5),
        ("number", 0),
        ("skipped", "false"),
    ],
)
def test_schedule_rejects_malformed_rows(field, value):
    raw = payload().model_dump(mode="json")
    raw["schedule"]["rows"][0][field] = value
    with pytest.raises(ValidationError):
        FeedbackScheduleSave.model_validate(raw)


@pytest.mark.asyncio
async def test_enabled_teacher_can_save_own_schedule_but_not_foreign_group(storage, monkeypatch):
    db, tenant, teacher, other, _ = storage
    monkeypatch.setattr(miniapp, "is_global_superadmin", lambda *a, **k: _not_superadmin())
    monkeypatch.setattr(
        miniapp,
        "feedback_teacher_is_enabled",
        lambda user_id, roles: user_id == teacher.max_user_id and StaffRole.TEACHER in roles,
    )
    saved = await miniapp.miniapp_save_feedback_schedule(
        payload(), db, identity(teacher, tenant), tenant.slug
    )
    assert saved["revision"] == 1
    forbidden = payload(1)
    forbidden.group_name = "Чужая группа"
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_save_feedback_schedule(
            forbidden, db, identity(teacher, tenant), tenant.slug
        )
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_feedback_catalog(db, identity(other, tenant))
    assert denied.value.status_code == 403


async def _not_superadmin():
    return False
