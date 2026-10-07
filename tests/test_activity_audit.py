from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.requests import Request

from app.models.audit import AuditLog
from app.models.support import SupportTicket
from app.services import activity_audit
from tests.test_miniapp_store import db_session, seed_linked_student  # noqa: F401

# ruff: noqa: F811


async def test_verified_identity_and_duplicate_correlation_ids_are_separate_actions(monkeypatch):
    saved = []

    async def capture(**kwargs):
        saved.append(kwargs)

    monkeypatch.setattr(activity_audit, "persist_event", capture)
    monkeypatch.setattr(
        activity_audit, "get_settings", lambda: SimpleNamespace(app_env="production")
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/api/v1/miniapp/session",
            "headers": [],
            "query_string": b"max_user_id=99&tenant_slug=school&token=private",
            "server": ("example.com", 443),
            "client": ("1.2.3.4", 1),
        }
    )
    request.state.audit_verified_max_user_id = 42
    request.state.audit_reason = "parent_required"
    request_id = str(uuid4())
    for _ in range(2):
        await activity_audit.persist_request(
            request, request_id=request_id, status=200, elapsed_ms=10
        )
    assert len(saved) == 2
    assert all("event_id" not in event for event in saved)
    assert saved[0]["user_id"] == 42
    assert saved[0]["payload"]["requested_max_user_id"] == 99
    assert saved[0]["payload"]["outcome"] == "denied"
    assert "private" not in str(saved)


async def test_bot_export_event_is_idempotent_and_keeps_actor(monkeypatch, db_session):
    student = await seed_linked_student(db_session)
    monkeypatch.setattr(
        "app.db.session.AsyncSessionLocal",
        async_sessionmaker(db_session.bind, expire_on_commit=False),
    )
    key = uuid4()
    for _ in range(2):
        await activity_audit.persist_event(
            action="bot.interaction", event_id=key, user_id=53364725, payload={"outcome": "success"}
        )
    row = await db_session.get(AuditLog, key)
    assert row.actor_account_id is not None
    assert row.payload["max_user_id"] == 53364725
    assert await db_session.scalar(select(func.count()).where(AuditLog.id == key)) == 1
    assert student is not None


async def test_permanent_ticket_deletion_is_not_retained_as_history(monkeypatch):
    saved = []

    async def capture(**kwargs):
        saved.append(kwargs)

    monkeypatch.setattr(activity_audit, "persist_event", capture)
    monkeypatch.setattr(
        activity_audit, "get_settings", lambda: SimpleNamespace(app_env="production")
    )
    request = Request({"type": "http", "method": "DELETE", "scheme": "https",
                       "path": "/api/v1/support/tickets/1", "headers": [],
                       "query_string": b"", "server": ("example.com", 443), "client": None})
    request.state.audit_skip = True
    await activity_audit.persist_request(request, request_id=str(uuid4()), status=204, elapsed_ms=1)
    assert saved == []
    await activity_audit.persist_request(request, request_id=str(uuid4()), status=403, elapsed_ms=1)
    assert len(saved) == 1 and saved[0]["payload"]["outcome"] == "denied"


async def test_late_successful_request_does_not_recreate_deleted_ticket_history(
    monkeypatch, db_session,
):
    monkeypatch.setattr(
        "app.db.session.AsyncSessionLocal",
        async_sessionmaker(db_session.bind, expire_on_commit=False),
    )
    ticket = SupportTicket(request_id=uuid4(), max_user_id=77, role="parent",
                           first_name="Анна", last_name="Иванова", message="Проблема",
                           source="miniapp")
    db_session.add(ticket)
    await db_session.commit()
    payload = {"path": f"/api/v1/support/tickets/{ticket.id}/replies", "http_status": 202}
    key = uuid4()
    await activity_audit.persist_event(action="activity.request", event_id=key, payload=payload)
    audit = await db_session.get(AuditLog, key)
    assert audit is not None
    await db_session.delete(audit)
    await db_session.delete(ticket)
    await db_session.commit()
    await activity_audit.persist_event(action="activity.request", payload=payload)
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 0
    await activity_audit.persist_event(
        action="activity.request", payload={**payload, "http_status": 403},
    )
    assert await db_session.scalar(select(func.count()).select_from(AuditLog)) == 1
