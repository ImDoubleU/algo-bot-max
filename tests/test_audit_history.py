# ruff: noqa: F811
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.account import StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import StaffRole
from app.services.audit_history import history_page, safe_payload
from app.services.miniapp import MiniAppStoreError
from tests.test_miniapp_store import (  # noqa: F401
    db_session,
    grant_store_admin,
    seed_linked_student,
)


async def context(db):
    student = await seed_linked_student(db)
    actor = await grant_store_admin(db, tenant_id=student.tenant_id)
    return student, actor


async def page(db, **kwargs):
    return await history_page(
        db, max_user_id=53364725, tenant_slug="nizhniy-novgorod-partner-a", **kwargs
    )


async def test_admin_cannot_read_full_or_global_audit(db_session):
    await context(db_session)
    for kwargs in [{"kind": "audit"}, {"all_tenants": True}]:
        with pytest.raises(MiniAppStoreError) as error:
            await page(db_session, **kwargs)
        assert error.value.status_code == 403


async def test_pagination_snapshot_includes_unregistered_attempts_without_leaking_secrets(
    db_session,
):
    student, _ = await context(db_session)
    now = datetime.now(UTC)
    db_session.add_all(
        [
            AuditLog(
                tenant_id=student.tenant_id,
                action="student_qr_access_link.failed",
                entity_type="student",
                entity_id=str(student.id),
                created_at=now - timedelta(seconds=i + 1),
                ip_address="127.0.0.9",
                payload={
                    "max_user_id": 900123,
                    "reason": "parent_required",
                    "request_id": "correlation",
                    "token": "private",
                    "nested": {"initData": "private", "safe": "value"},
                },
            )
            for i in range(215)
        ]
    )
    await db_session.commit()
    first = await page(db_session, kind="bindings", limit=100, actor_max_user_id=900123)
    assert first.total == 215 and first.has_more and len(first.entries) == 100
    entry = first.entries[0]
    assert entry.actor_max_user_id == 900123 and entry.status == "error"
    assert entry.explanation == "Родитель ещё не завершил подключение"
    assert entry.request_id is None and entry.ip_address is None
    assert "request_id" not in entry.payload and "token" not in entry.payload
    assert entry.payload["nested"] == {"safe": "value"}
    assert entry.payload["students"][0]["name"] == student.display_name
    assert entry.payload["students"][0]["group"] == student.group_name
    assert entry.payload["actor_role"] == "student"
    db_session.add(
        AuditLog(
            tenant_id=student.tenant_id,
            action="student_qr_access_link.failed",
            entity_type="student",
            created_at=datetime.now(UTC),
            payload={"max_user_id": 900123},
        )
    )
    await db_session.commit()
    second = await page(
        db_session,
        kind="bindings",
        limit=100,
        offset=100,
        snapshot_at=first.snapshot_at,
        actor_max_user_id=900123,
    )
    third = await page(
        db_session,
        kind="bindings",
        limit=100,
        offset=200,
        snapshot_at=first.snapshot_at,
        actor_max_user_id=900123,
    )
    assert second.total == third.total == 215
    assert len(third.entries) == 15 and not third.has_more
    assert len({e.id for e in first.entries + second.entries + third.entries}) == 215


async def test_superadmin_global_audit_filters_and_details(db_session):
    student, actor = await context(db_session)
    assignment = await db_session.scalar(select(StaffRoleAssignment))
    assignment.role = StaffRole.SUPERADMIN
    db_session.add_all(
        [
            AuditLog(
                action="activity.request",
                actor_account_id=actor.id,
                entity_type="activity",
                ip_address="1.2.3.4",
                payload={
                    "outcome": "denied",
                    "request_id": "request-1",
                    "reason": "identity_mismatch",
                    "operation": "Вход",
                },
            ),
            AuditLog(
                tenant_id=student.tenant_id,
                action="product.updated",
                actor_account_id=actor.id,
                entity_type="product",
                payload={"name": "A"},
            ),
        ]
    )
    await db_session.commit()
    result = await page(db_session, kind="audit", all_tenants=True, outcome="denied")
    assert len(result.entries) == 1
    assert result.entries[0].request_id == "request-1"
    assert result.entries[0].ip_address == "1.2.3.4"
    assert result.entries[0].tenant_slug is None
    assert (
        len(
            (
                await page(
                    db_session, kind="audit", all_tenants=True, q="53364725", category="Товары"
                )
            ).entries
        )
        == 1
    )
    assert (
        len((await page(db_session, kind="audit", all_tenants=True, q="товар измен")).entries) == 1
    )
    ordinary = await page(db_session)
    assert all(entry.action != "activity.request" for entry in ordinary.entries)


async def test_student_history_permissions_and_scope(db_session):
    student, actor = await context(db_session)
    result = await page(db_session, student_id=student.id)
    assert result.entries
    assignment = await db_session.scalar(select(StaffRoleAssignment))
    assignment.role = StaffRole.TEACHER
    actor.display_name = "Другой преподаватель"
    await db_session.commit()
    with pytest.raises(MiniAppStoreError) as error:
        await page(db_session, student_id=student.id)
    assert error.value.status_code == 403


async def test_attention_filter_includes_all_unsuccessful_statuses_and_paginates(db_session):
    student, actor = await context(db_session)
    assignment = await db_session.scalar(select(StaffRoleAssignment))
    assignment.role = StaffRole.SUPERADMIN
    now = datetime.now(UTC)
    cases = [
        ({"outcome": "denied"}, "denied"),
        ({"result": "", "outcome": "DENIED"}, "denied"),
        ({"result": "failed"}, "error"),
        ({"error": "Delivery failed"}, "error"),
        ({"incomplete_leads": {"123": "missing"}}, "partial"),
        ({"unmatched_lead_ids": [123]}, "partial"),
        ({"result": "processing"}, "pending"),
        ({"result": "success", "incomplete_leads": [], "unmatched_lead_ids": {}}, "success"),
        ({"result": "success", "incomplete_leads": {}, "unmatched_lead_ids": []}, "success"),
        ({}, "success"),
    ]
    rows = [
        AuditLog(
            tenant_id=student.tenant_id,
            actor_account_id=actor.id,
            action="activity.request",
            entity_type="activity",
            created_at=now - timedelta(seconds=i + 1),
            payload=payload,
        )
        for i, (payload, _) in enumerate(cases)
    ]
    db_session.add_all(rows)
    await db_session.commit()
    expected = {row.id: status for row, (_, status) in zip(rows, cases, strict=True)}
    first = await page(db_session, kind="audit", category="Запросы", outcome="attention", limit=3)
    second = await page(
        db_session, kind="audit", category="Запросы", outcome="attention", limit=10,
        offset=3, snapshot_at=first.snapshot_at,
    )
    assert first.total == second.total == 7
    assert first.has_more and not second.has_more
    entries = first.entries + second.entries
    assert {entry.id: entry.status for entry in entries} == {
        row_id: status for row_id, status in expected.items() if status != "success"
    }
    for status in {"success", "error", "denied", "partial", "pending"}:
        filtered = await page(db_session, kind="audit", category="Запросы", outcome=status)
        assert {entry.id for entry in filtered.entries} == {
            row_id for row_id, value in expected.items() if value == status
        }
        assert all(entry.status == status for entry in filtered.entries)


def test_sensitive_payload_is_removed_recursively():
    cleaned = safe_payload(
        {
            "body": "private",
            "password": "private",
            "children": [{"qr_token": "private", "max_user_id": 42}],
            "detail": "URL https://example.com/?token=private Bearer private",
        }
    )
    assert cleaned["children"] == [{"max_user_id": 42}]
    assert "private" not in str(cleaned)
