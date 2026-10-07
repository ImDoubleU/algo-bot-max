# ruff: noqa: F811
import json
import sqlite3
import time
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import get_miniapp_identity
from app.bot.webhook_inbox import WebhookInbox
from app.core.config import get_settings
from app.models.account import StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import StaffRole
from app.schemas.access import AccessLinkCreate, StudentResolveRequest
from app.services.access import (
    AccessServiceError,
    create_contact_access_links,
    hash_contact_id,
    record_student_access_attempt,
)
from app.services.activity_audit import inbox_metadata
from app.services.audit_history import history_page
from app.services.binding_targets import target_from_launch
from app.services.student_invitations import issue_teacher_student_invitation_token
from tests.test_binding_ui import binding_browser  # noqa: F401
from tests.test_max_webapp_auth import signed_init_data
from tests.test_miniapp_store import (  # noqa: F401
    db_session,
    grant_store_admin,
    seed_linked_student,
)


async def audit_page(db):
    assignment = await db.scalar(select(StaffRoleAssignment))
    assignment.role = StaffRole.SUPERADMIN
    await db.commit()
    return await history_page(db, max_user_id=53364725,
                              tenant_slug="nizhniy-novgorod-partner-a", kind="audit")


async def test_targets_resolve_exact_school_ids_and_old_hashes_without_guessing(db_session):
    student = await seed_linked_student(db_session)
    await grant_store_admin(db_session, tenant_id=student.tenant_id)
    cases = {
        "raw": {"contact_id": "681"},
        "old": {"contact_id_hash": hash_contact_id("681")},
        "missing": {"contact_id": "NEW-999"},
        "unknown": {"reason": "not_linked"},
        "old_unknown": {"contact_id_hash": hash_contact_id("NOT-IMPORTED")},
        "wrong_school": {"link_target": {"kind": "contact", "id": "681",
                                         "tenant_slug": "another-school"}},
        "uuid": {"link_target": {"kind": "student", "id": str(student.id),
                                 "tenant_id": str(student.tenant_id)}},
    }
    ids = {}
    for name, payload in cases.items():
        event = AuditLog(tenant_id=student.tenant_id, action="activity.request",
                         entity_type="activity", payload={"max_user_id": 92515478, **payload})
        db_session.add(event)
        await db_session.flush()
        ids[name] = event.id
    await db_session.commit()
    rows = {entry.id: entry for entry in (await audit_page(db_session)).entries}
    for name in ["raw", "old", "uuid"]:
        assert rows[ids[name]].payload["students"][0]["lms_id"] == "ST-001"
    assert rows[ids["raw"]].payload["link_target"]["id"] == "681"
    assert rows[ids["old"]].payload["link_target"]["id"] == "681"
    assert rows[ids["missing"]].payload["link_target"]["id"] == "NEW-999"
    assert rows[ids["missing"]].payload["students"] == []
    assert rows[ids["wrong_school"]].payload["students"] == []
    assert rows[ids["unknown"]].payload["link_target"]["state"] == "not_provided"
    assert rows[ids["old_unknown"]].payload["link_target"]["state"] == "historical_id_missing"
    ordinary = await history_page(db_session, max_user_id=53364725,
                                  tenant_slug="nizhniy-novgorod-partner-a")
    assert all("contact_id" not in entry.payload and "link_target" not in entry.payload
               for entry in ordinary.entries)


async def test_missing_profile_failures_save_original_id_and_do_not_log_it(db_session, caplog):
    student = await seed_linked_student(db_session)
    await grant_store_admin(db_session, tenant_id=student.tenant_id)
    payload = StudentResolveRequest(tenant_slug="nizhniy-novgorod-partner-a",
                                    contact_id="new-987", max_user_id=92515478)
    await record_student_access_attempt(db_session, payload=payload,
                                       action="contact_access.resolve_failed", result="not_found",
                                       tenant_id=student.tenant_id, reason="contact_id_not_found")
    await db_session.commit()
    with pytest.raises(AccessServiceError):
        await create_contact_access_links(db_session, AccessLinkCreate(
            **payload.model_dump(exclude={"username", "display_name"}), role="parent"))
    entries = (await audit_page(db_session)).entries
    failures = [e for e in entries if e.action in {"contact_access.resolve_failed",
                                                  "contact_access_link.failed"}]
    assert len(failures) == 2
    assert all(e.payload["link_target"]["id"] == "NEW-987" for e in failures)
    assert "NEW-987" not in caplog.text


def test_webhook_receipt_keeps_target_after_discarding_body_but_never_qr_token(tmp_path):
    store = WebhookInbox(tmp_path / "inbox.sqlite3")
    tenant, student = uuid4(), uuid4()
    token = issue_teacher_student_invitation_token(tenant, student)
    for n, payload in enumerate(["shop_school~681", "student_" + token]):
        store.put({"update_type": "bot_started", "user": {"user_id": n + 1},
                   "payload": payload, "timestamp": n})
        store.finish(store.claim())
    rows = inbox_metadata(store.path)
    assert json.loads(rows[0][-1])["link_target"]["id"] == "681"
    assert json.loads(rows[1][-1])["link_target"]["id"] == str(student)
    assert token not in str(rows)
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT body FROM webhook_inbox").fetchall() == [(None,), (None,)]
    assert target_from_launch("staff_school~teacher", allow_bare_id=True) is None
    assert target_from_launch("student_broken") is None
    assert target_from_launch("Это текст заявки") is None
    assert target_from_launch("https://example.com/?start=cid_681") is None


def test_only_signed_max_launch_target_is_accepted(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", "test-real-bot-token")
    get_settings.cache_clear()
    app = FastAPI()

    @app.get("/target")
    async def target(request: Request):
        await get_miniapp_identity(None, request.headers.get("X-Max-WebApp-Data"), request)
        return request.state.audit_link_target

    try:
        data = signed_init_data(user_id=92515478, auth_date=int(time.time()),
                                bot_token="test-real-bot-token", start_param="shop_school~681")
        client = TestClient(app)
        result = client.get("/target", headers={"X-Max-WebApp-Data": data})
        assert result.json() == {"kind": "contact", "id": "681", "tenant_slug": "school"}
        changed = client.get("/target", headers={"X-Max-WebApp-Data": data.replace("681", "999")})
        assert changed.status_code == 401
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("width", [320, 1440])
def test_audit_target_visible_without_duplicate_lms_ids(binding_browser, width):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    page.evaluate("""() => {
      state.role = 'admin'; state.adminTab = 'audit';
      auditFeed('audit').rows = [
        {id: 'known', actor_max_user_id: 100, payload: {
          link_target: {kind: 'contact', id: '681'}, students: [
            {id: 'student-1', name: 'Ученик', lms_id: 'ST-001', accounts: []}]}},
        {id: 'unknown', actor_max_user_id: 92515478, payload: {
          reason: 'not_linked', link_target: {kind: 'unknown', state: 'not_provided'},
          students: []}}
      ].map(row => normalizeAdminHistoryEntry({...row, actor_name: 'Екатерина Фролова',
        action: 'activity.request', status: 'denied', created_at: '2026-10-08T10:30:00Z'}));
      renderAdminPanel();
    }""")
    known = page.locator('[data-audit-entry="known"]')
    assert known.locator('.audit-link-target').inner_text().split() == [
        "ID", "родителя", "из", "ссылки", "681"]
    assert known.inner_text().count("LMS ID ST-001") == 1
    assert known.locator('[data-audit-student="student-1"]').count() == 1
    unknown = page.locator('[data-audit-entry="unknown"]')
    assert "ID ссылки при входе не был передан" in unknown.inner_text()
    assert "LMS ID —" in unknown.inner_text()
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    page.close()
