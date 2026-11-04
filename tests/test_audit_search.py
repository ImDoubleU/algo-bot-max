# ruff: noqa: F811
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import StaffRole
from app.models.student import Contact, ContactStudentLink
from app.models.tenant import Tenant
from tests.test_audit_history import context, page
from tests.test_miniapp_store import db_session  # noqa: F401


async def searchable_student(db):
    student, actor = await context(db)
    assignment = await db.scalar(select(StaffRoleAssignment))
    assignment.role = StaffRole.SUPERADMIN
    # SQLite's built-in lower() is ASCII-only; production PostgreSQL handles Cyrillic.
    student.first_name = "мария"
    student.last_name = "цурилова"
    await db.commit()
    return student, actor


async def test_search_finds_student_and_parent_targets_without_correlated_scans(db_session):
    student, _ = await searchable_student(db_session)
    shapes = [
        ("student", str(student.id), {}),
        ("student_access", student.id.hex, {}),
        ("other", None, {"student_id": str(student.id)}),
        ("other", None, {"student_ids": [student.id.hex]}),
        ("other", None, {"link_target": {"kind": "student", "id": str(student.id)}}),
        ("other", None, {"contact_id": "681"}),
        ("other", None, {"contact_id": 681}),
        ("other", None, {"link_target": {"kind": "contact", "id": "681"}}),
    ]
    logs = [
        AuditLog(
            tenant_id=student.tenant_id,
            action="search.fixture",
            entity_type=kind,
            entity_id=key,
            payload=payload,
        )
        for kind, key, payload in shapes
    ]
    db_session.add_all(logs)
    await db_session.commit()
    expected = {log.id for log in logs}
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    engine = db_session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        for query in ("Цурилова Мария", "Мария Цурилова", "цурилова", "ST-001"):
            result = await page(db_session, kind="audit", q=query)
            assert {e.id for e in result.entries if e.action == "search.fixture"} == expected
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    counts = [sql for sql in statements if "select count(*)" in sql]
    assert counts
    assert all(
        "join max_accounts" not in sql
        and "from students" not in sql
        and "from contact_student_links" not in sql
        for sql in counts
    )
    pages = [sql for sql in statements if "left outer join max_accounts" in sql]
    assert pages and all("max_accounts.id = audit_logs.actor_account_id" in sql for sql in pages)
    assert all(
        " or "
        not in sql.split("left outer join max_accounts")[1].split("left outer join tenants")[0]
        for sql in pages
    )
    first = await page(db_session, kind="audit", q="Цурилова", limit=3)
    second = await page(
        db_session, kind="audit", q="Цурилова", limit=3, offset=3, snapshot_at=first.snapshot_at
    )
    assert first.total == second.total >= len(expected)
    assert first.has_more and len(first.entries) == len(second.entries) == 3
    assert not ({e.id for e in first.entries} & {e.id for e in second.entries})


@pytest.mark.parametrize("payload_id", [987654321, "987654321"])
async def test_legacy_actor_search_and_actor_filter_preserve_identity(db_session, payload_id):
    student, _ = await searchable_student(db_session)
    legacy = MaxAccount(max_user_id=987654321, display_name="legacy actor")
    other = MaxAccount(max_user_id=987654322, display_name="different actor")
    db_session.add_all([legacy, other])
    await db_session.flush()
    good = AuditLog(
        tenant_id=student.tenant_id,
        action="search.fixture",
        entity_type="activity",
        payload={"max_user_id": payload_id},
    )
    # An explicit actor remains authoritative even if payload contains another MAX ID.
    different = AuditLog(
        tenant_id=student.tenant_id,
        action="search.fixture",
        actor_account_id=other.id,
        entity_type="activity",
        payload={"max_user_id": payload_id},
    )
    db_session.add_all([good, different])
    await db_session.commit()
    result = await page(db_session, kind="audit", q="legacy actor")
    assert [e.id for e in result.entries] == [good.id]
    assert result.entries[0].actor_name == legacy.display_name
    assert result.entries[0].actor_max_user_id == legacy.max_user_id
    filtered = await page(
        db_session, kind="audit", q="legacy actor", actor_max_user_id=legacy.max_user_id
    )
    assert filtered.total == 1 and filtered.entries[0].id == good.id
    by_id = await page(db_session, kind="audit", q="987654321")
    assert {e.id for e in by_id.entries} == {good.id, different.id}


async def test_search_keeps_tenant_scope_and_literal_wildcards(db_session):
    student, _ = await searchable_student(db_session)
    original = await db_session.get(Tenant, student.tenant_id)
    foreign = Tenant(city_id=original.city_id, partner_id=uuid4(), slug="foreign", name="Foreign")
    db_session.add(foreign)
    await db_session.flush()
    foreign_contact = Contact(tenant_id=foreign.id, external_contact_id="foreign-contact")
    db_session.add(foreign_contact)
    await db_session.flush()
    db_session.add(
        ContactStudentLink(
            tenant_id=foreign.id, student_id=student.id, contact_id=foreign_contact.id
        )
    )
    logs = [
        AuditLog(
            tenant_id=foreign.id,
            action="search.fixture",
            entity_type="other",
            payload={"student_id": str(student.id)},
        ),
        AuditLog(
            tenant_id=foreign.id,
            action="search.fixture",
            entity_type="other",
            payload={"contact_id": foreign_contact.external_contact_id},
        ),
        AuditLog(
            tenant_id=student.tenant_id,
            action="search.fixture",
            entity_type="other",
            payload={"detail": "literal_%text"},
        ),
        AuditLog(
            tenant_id=student.tenant_id,
            action="search.fixture",
            entity_type="other",
            payload={"detail": "literalABtext"},
        ),
    ]
    db_session.add_all(logs)
    await db_session.commit()
    global_result = await page(db_session, kind="audit", all_tenants=True, q="Цурилова")
    assert not ({e.id for e in global_result.entries} & {logs[0].id, logs[1].id})
    local = await page(db_session, kind="audit", q="foreign-contact")
    assert local.total == 0
    literal = await page(db_session, kind="audit", q="_%")
    assert [e.id for e in literal.entries] == [logs[2].id]
