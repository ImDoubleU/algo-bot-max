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
    assert sum(len(lessons) for lessons in catalog.values()) == 736
    assert response.headers["cache-control"] == "private, no-store"
    check.assert_awaited_once_with(db, account_id=account_id)
