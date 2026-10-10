# ruff: noqa: F811
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import StaffRole
from app.services.audit_history import history_page
from app.services.binding_history import binding_presentation
from tests.test_binding_ui import binding_browser  # noqa: F401
from tests.test_miniapp_store import (  # noqa: F401
    db_session,
    grant_store_admin,
    seed_linked_student,
)


async def setup(db):
    pupil = await seed_linked_student(db)
    await grant_store_admin(db, tenant_id=pupil.tenant_id)
    return pupil


def event(pupil, action, *, at=None, **payload):
    return AuditLog(
        tenant_id=pupil.tenant_id, action=action, entity_type="activity",
        created_at=at or datetime.now(UTC), payload={"max_user_id": 900123, **payload},
    )


async def read(db, **kwargs):
    return await history_page(db, max_user_id=53364725,
                              tenant_slug="nizhniy-novgorod-partner-a",
                              actor_max_user_id=900123, **kwargs)


async def test_targeted_qr_visit_is_visible_without_unrelated_requests(db_session):
    pupil = await setup(db_session)
    target = {"kind": "student", "id": str(pupil.id), "tenant_id": str(pupil.tenant_id)}
    db_session.add_all([
        event(pupil, "bot.interaction", update_type="bot_started", link_target=target),
        event(pupil, "activity.request", path="/api/v1/miniapp/catalog"),
        event(pupil, "activity.request", path="/api/v1/miniapp/session", reason="not_linked"),
    ])
    await db_session.commit()
    result = await read(db_session, category="Привязки", limit=1)
    assert result.total == 1 and not result.has_more
    entry = result.entries[0]
    assert entry.title == "Ученик открыл свой QR-код"
    assert "не подтверждена" in entry.explanation
    assert entry.payload["actor_role"] == "student"
    assert entry.payload["students"][0]["lms_id"] == "ST-001"
    assert entry.payload["students"][0]["name"] == pupil.display_name
    assert "link_target" not in entry.payload and "path" not in entry.payload
    assert (await read(db_session, kind="bindings")).total == 1


async def test_stages_of_one_parent_transition_are_one_paginated_history_entry(db_session):
    pupil = await setup(db_session)
    now = datetime.now(UTC) - timedelta(seconds=20)
    target = {"kind": "contact", "id": "681"}
    db_session.add_all([
        event(pupil, "bot.interaction", at=now, update_type="bot_started", link_target=target),
        event(pupil, "contact_access.resolve_success", at=now + timedelta(seconds=1),
              contact_id="681"),
        event(pupil, "contact_access_links.created", at=now + timedelta(seconds=2),
              contact_id="681", role="parent", created_links=1),
        event(pupil, "activity.request", at=now + timedelta(seconds=3),
              path="/api/v1/miniapp/session", link_target=target),
    ])
    await db_session.commit()
    result = await read(db_session, limit=1)
    assert result.total == 1 and not result.has_more
    entry = result.entries[0]
    assert entry.action == "contact_access_links.created"
    assert entry.title == "Родитель подключился"
    assert entry.payload["students"][0]["lms_id"] == "ST-001"
    assert entry.payload["binding_subject"]["role"] == "parent"


async def test_missing_parent_target_never_invents_lms_and_retry_remains(db_session):
    pupil = await setup(db_session)
    now = datetime.now(UTC) - timedelta(seconds=20)
    db_session.add_all([
        event(pupil, "pending_binding.saved", at=now, contact_id="NEW-987",
              role="parent", reason="contact_not_found", result="pending"),
        event(pupil, "contact_access.resolve_failed", at=now + timedelta(seconds=1),
              contact_id="NEW-987", reason="contact_id_not_found", result="not_found"),
        event(pupil, "contact_access.resolve_failed", at=now + timedelta(seconds=10),
              contact_id="NEW-987", reason="contact_id_not_found", result="not_found"),
    ])
    await db_session.commit()
    result = await read(db_session, limit=1)
    assert result.total == 2 and result.has_more
    entry = result.entries[0]
    assert "ещё не добавили" in entry.explanation
    subject = entry.payload["binding_subject"]
    assert subject["target_id"] == "NEW-987" and subject["target_kind"] == "contact"
    assert subject["lms_id"] is None and entry.payload["students"] == []
    second = await read(db_session, limit=1, offset=1, snapshot_at=result.snapshot_at)
    assert second.entries[0].action == "pending_binding.saved"
    assert second.entries[0].status == "pending"
    assert second.total == 2 and not second.has_more


async def test_student_visit_preserves_distinct_targets_and_accounts(db_session):
    pupil = await setup(db_session)
    db_session.add_all([
        event(pupil, "bot.interaction", update_type="bot_started",
              link_target={"kind": "student", "id": str(pupil.id)}),
        event(pupil, "student_qr_access_link.created", student_id=str(uuid4()), role="student"),
        event(pupil, "student_qr_access_link.created", student_id=str(pupil.id),
              max_user_id=800456, role="student"),
    ])
    await db_session.commit()
    assert (await read(db_session)).total == 2


async def test_real_student_creation_uses_entity_id_to_hide_webhook_duplicate(db_session):
    pupil = await setup(db_session)
    visit = event(pupil, "bot.interaction", update_type="bot_started",
                  link_target={"kind": "student", "id": str(pupil.id)})
    created = event(pupil, "student_qr_access_link.created", created=True, source="teacher_qr")
    created.entity_type = "student_access"
    created.entity_id = str(pupil.id)
    db_session.add_all([visit,created])
    await db_session.commit()
    result = await read(db_session)
    assert result.total == 1
    assert result.entries[0].action == "student_qr_access_link.created"


async def test_search_finds_parent_and_student_target_by_confirmed_lms_id(db_session):
    pupil = await setup(db_session)
    now = datetime.now(UTC) - timedelta(seconds=20)
    db_session.add_all([
        event(pupil, "bot.interaction", at=now, update_type="bot_started",
              link_target={"kind": "student", "id": str(pupil.id)}),
        event(pupil, "contact_access_links.created", at=now + timedelta(seconds=10),
              contact_id="681", created_links=1, role="parent"),
    ])
    await db_session.commit()
    result = await read(db_session, q="ST-001")
    assert result.total == 2
    assert {e.action for e in result.entries} == {
        "bot.interaction", "contact_access_links.created",
    }


async def test_failed_first_visit_uses_api_account_name_and_full_audit_keeps_every_stage(
    db_session,
):
    pupil = await setup(db_session)
    db_session.add(MaxAccount(max_user_id=900123, display_name="Ekaterina Zhilina"))
    db_session.add_all([
        event(pupil, "pending_binding.saved", role="parent", contact_id="NEW-987",
              reason="contact_not_found", result="pending"),
        event(pupil, "contact_access.resolve_failed", contact_id="NEW-987",
              reason="contact_id_not_found", result="not_found"),
    ])
    await db_session.commit()
    ordinary = await read(db_session, q="Ekaterina")
    assert ordinary.total == 1
    assert ordinary.entries[0].actor_name == "Ekaterina Zhilina"
    assignment = await db_session.scalar(select(StaffRoleAssignment))
    assignment.role = StaffRole.SUPERADMIN
    await db_session.commit()
    full = await read(db_session, kind="audit")
    assert full.total == 2
    assert all("binding_subject" not in e.payload for e in full.entries)


def test_deleted_student_snapshot_preserves_confirmed_lms_id_and_name():
    result = binding_presentation("student_qr_access_link.failed", {
        "reason": "student_not_found", "role": "student",
        "student_name": "Иван Иванов", "lms_student_id": "70780000",
    }, {"students": [], "link_target": {"kind": "student", "id": str(uuid4())}})
    assert result["subject"]["lms_id"] == "70780000"
    assert result["subject"]["name"] == "Иван Иванов"
    assert result["subject"]["state"] == "not_added"


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_general_history_binding_cards_are_clear_and_keep_student_navigation(
    binding_browser, width,
):
    browser, base = binding_browser
    page = browser.new_page(viewport={"width": width, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("https://st.max.ru/**", lambda route: route.abort())
    page.goto(base + "/miniapp?demo=1", wait_until="networkidle")
    page.evaluate("""() => {
      state.role = 'admin'; state.adminTab = 'history';
      auditFeed('actions').rows = [
        {id:'parent', title:'Родитель подключился', actor_name:'Мама Алисы',
          actor_max_user_id:123, action:'contact_access_links.created', payload:{
            actor_role:'parent', binding_subject:{role:'parent', state:'known'},
            students:[{id:'student-1', name:'Алиса Васильева', lms_id:'ST-001',
              group:'Python, сб 10:00', teacher:'Иван Петров',
              accounts:[{role:'parent',name:'Второй родитель',max_user_id:999}]}]}},
        {id:'missing', title:'Родитель пытался подключиться', actor_name:'Екатерина',
          actor_max_user_id:92515478, action:'pending_binding.saved', status:'pending',
          explanation:'Попытался зайти в аккаунт ученика, но его ещё не добавили в систему.',
          payload:{actor_role:'parent', students:[], binding_subject:{state:'not_added',
            target_kind:'contact',target_id:'34368735',lms_id:null}}},
        {id:'snapshot', title:'Ученик пытался подключиться',actor_name:'Иван',
          action:'student_qr_access_link.failed', status:'error', payload:{
            actor_role:'student',students:[],binding_subject:{state:'not_added',
              name:'Иван Иванов',lms_id:'70780000'}}}
      ].map(row=>normalizeAdminHistoryEntry({...row, created_at:'2026-10-10T07:00:00Z'}));
      auditFeed('actions').total=3; renderAdminPanel(); setView('admin');
    }""")
    known = page.locator('[data-audit-entry="parent"]')
    assert known.locator('[data-audit-student="student-1"]').is_visible()
    assert known.inner_text().count("LMS ID ST-001") == 1
    assert "Второй родитель" not in known.inner_text()
    assert "Детали аудита" not in known.inner_text()
    missing = page.locator('[data-audit-entry="missing"]')
    text = " ".join(missing.inner_text().split())
    assert "LMS ID не найден" in text
    assert "ID из ссылки родителя 34368735" in text
    assert "MAX ID 92515478" in text
    snapshot = page.locator('[data-audit-entry="snapshot"]')
    assert "Иван Иванов" in snapshot.inner_text() and "70780000" in snapshot.inner_text()
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
    assert not errors
    page.close()
