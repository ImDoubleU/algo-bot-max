from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.routes import miniapp


@pytest.mark.asyncio
async def test_feedback_requires_authenticated_identity():
    db = AsyncMock()
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_feedback_catalog(db, None)
    assert denied.value.status_code == 401
    db.scalar.assert_not_awaited()


@pytest.mark.asyncio
async def test_feedback_rejects_unknown_account(monkeypatch):
    db = AsyncMock()
    db.scalar.return_value = None
    check = AsyncMock()
    monkeypatch.setattr(miniapp, "is_global_superadmin", check)
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_feedback_catalog(db, SimpleNamespace(max_user_id=777))
    assert denied.value.status_code == 403
    check.assert_not_awaited()


@pytest.mark.asyncio
async def test_feedback_rejects_authenticated_non_superadmin(monkeypatch):
    db = AsyncMock()
    account_id = uuid4()
    db.scalar.return_value = account_id
    check = AsyncMock(return_value=False)
    monkeypatch.setattr(miniapp, "is_global_superadmin", check)
    with pytest.raises(HTTPException) as denied:
        await miniapp.miniapp_feedback_catalog(db, SimpleNamespace(max_user_id=777))
    assert denied.value.status_code == 403
    check.assert_awaited_once_with(db, account_id=account_id)


@pytest.mark.asyncio
async def test_feedback_returns_catalog_only_after_superadmin_check(monkeypatch):
    import json

    db = AsyncMock()
    account_id = uuid4()
    db.scalar.return_value = account_id
    check = AsyncMock(return_value=True)
    monkeypatch.setattr(miniapp, "is_global_superadmin", check)
    response = await miniapp.miniapp_feedback_catalog(db, SimpleNamespace(max_user_id=777))
    catalog = json.loads(response.body)
    assert sum(len(lessons) for lessons in catalog.values()) == 700
    assert all(
        lesson["topic"] and len(lesson["topic"]) <= 65
        for lessons in catalog.values()
        for lesson in lessons
    )
    assert response.headers["cache-control"] == "private, no-store"
    check.assert_awaited_once_with(db, account_id=account_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [True, False])
async def test_allowlisted_teacher_requires_active_teacher_assignment(monkeypatch, active):
    from app.models.enums import StaffRole

    account_id = uuid4()
    db = AsyncMock()
    db.scalar.side_effect = [account_id, uuid4() if active else None]
    monkeypatch.setattr(miniapp, "is_global_superadmin", AsyncMock(return_value=False))

    def grant(user_id, roles):
        return user_id == 777 and StaffRole.TEACHER in roles

    monkeypatch.setattr(miniapp, "feedback_teacher_is_enabled", grant)
    if active:
        response = await miniapp.miniapp_feedback_catalog(db, SimpleNamespace(max_user_id=777))
        assert response.status_code == 200
    else:
        with pytest.raises(HTTPException) as denied:
            await miniapp.miniapp_feedback_catalog(db, SimpleNamespace(max_user_id=777))
        assert denied.value.status_code == 403
    query = str(db.scalar.await_args_list[-1].args[0])
    assert "staff_role_assignments.role" in query
    assert "staff_role_assignments.status" in query


def test_feedback_teacher_allowlist_does_not_grant_other_roles(monkeypatch):
    from app.models.enums import StaffRole
    from app.services import staff

    monkeypatch.setattr(
        staff,
        "get_settings",
        lambda: SimpleNamespace(feedback_teacher_max_user_ids="777, 888, invalid, -1"),
    )
    assert staff.feedback_teacher_is_enabled(777, [StaffRole.TEACHER])
    assert staff.feedback_teacher_is_enabled(888, [StaffRole.TEACHER, StaffRole.ADMIN])
    assert not staff.feedback_teacher_is_enabled(999, [StaffRole.TEACHER])
    assert not staff.feedback_teacher_is_enabled(777, [StaffRole.ADMIN])
    assert not staff.feedback_teacher_is_enabled(777, [])
