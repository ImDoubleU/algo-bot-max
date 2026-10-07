# ruff: noqa: F811
import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.max_client import SimulationMaxClient
from app.models.enums import StudentAccessRole, StudentAccessStatus
from app.models.pending_binding import PendingBinding
from app.models.student import Student, StudentAccessLink
from app.models.tenant import Tenant
from app.schemas.access import AccessLinkCreate, BotStoppedAccessRevoke, StudentInvitationLinkCreate
from app.services.access import (
    AccessServiceError,
    create_contact_access_links,
    create_invited_student_access_link,
    revoke_access_for_stopped_bot,
)
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.pending_bindings import (
    cancel_pending_binding,
    confirm_pending_binding,
    pending_binding_loop,
    process_pending_batch,
    recover_historical_missing_bindings,
    utc,
)
from app.services.student_invitations import issue_teacher_student_invitation_token
from tests.test_contact_access_service import (
    db_session,  # noqa: F401
    row,
    seed_two_students_for_one_contact,
)
from tests.test_miniapp_store import seed_linked_student
from tests.test_support import auth, support_client  # noqa: F401

TENANT = "nizhniy-novgorod-partner-a"


async def test_worker_starts_with_real_max_client_and_reaches_first_batch(monkeypatch, db_session):
    from app.bot.max_client import MaxApiClient

    monkeypatch.setattr("app.core.config.get_settings", lambda: SimpleNamespace(
        max_bot_token="test-production-bot-value", max_api_base="https://max.example.test",
        max_api_timeout_seconds=15,
    ))
    monkeypatch.setattr("app.db.session.AsyncSessionLocal",
                        async_sessionmaker(db_session.bind, expire_on_commit=False))
    calls = []

    async def capture(db, *, client):
        assert isinstance(client, MaxApiClient)
        assert client.api_base == "https://max.example.test"
        calls.append(client)
        raise asyncio.CancelledError  # Verify startup without making a network request.

    monkeypatch.setattr("app.services.pending_bindings.process_pending_batch", capture)
    with pytest.raises(asyncio.CancelledError):
        await pending_binding_loop()
    assert len(calls) == 1


async def wait_for_contact(db, *, user=77, contact="999"):
    with pytest.raises(AccessServiceError) as caught:
        await create_contact_access_links(db, AccessLinkCreate(
            tenant_slug=TENANT, contact_id=contact, max_user_id=user,
            role=StudentAccessRole.PARENT, display_name="Фролова Екатерина", username="parent",
        ))
    assert caught.value.code == "pending_waiting"
    item = await db.scalar(select(PendingBinding).where(PendingBinding.max_user_id == user,
                                                       PendingBinding.target_id == contact))
    return item


async def import_missing_children(db):
    from dataclasses import replace
    await upsert_crm_student_rows(db, [
        replace(row(lms_student_id="NEW-1", first_name="Александр"), contact_ids="999"),
        replace(row(lms_student_id="NEW-2", first_name="Мария"), contact_ids="999"),
    ], defaults=CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнёр A"))


async def test_import_notifies_once_and_explicit_confirmation_connects_whole_family(db_session):
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    identifier, expiry = item.id, utc(item.expires_at)
    again = await wait_for_contact(db_session)
    assert again.id == identifier and again.attempts == 2 and utc(again.expires_at) == expiry
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert not client.sent_messages
    await import_missing_children(db_session)
    await process_pending_batch(db_session, client=client)
    assert len(client.sent_messages) == 1 and client.sent_messages[0]["user_id"] == 77
    buttons = client.sent_messages[0]["attachments"][0]["payload"]["buttons"]
    assert buttons[0][0]["payload"] == f"pending:confirm:{identifier}"
    assert "Александр" not in client.sent_messages[0]["text"]  # No family info before confirmation.
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 0
    await process_pending_batch(db_session, client=client,
                                now=datetime.now(UTC) + timedelta(minutes=1))
    assert len(client.sent_messages) == 1
    with pytest.raises(AccessServiceError, match="вашего аккаунта"):
        await confirm_pending_binding(db_session, identifier, 88)
    result = await confirm_pending_binding(db_session, identifier, 77)
    assert result["role"] == "parent" and len(result["student_names"]) == 2
    links = list(await db_session.scalars(select(StudentAccessLink)))
    assert len(links) == 2 and all(link.status == StudentAccessStatus.ACTIVE for link in links)
    assert (await db_session.get(PendingBinding, identifier)).status == "completed"
    await confirm_pending_binding(db_session, identifier, 77)
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 2


async def test_delivery_retries_survive_reopening_without_duplicate_notification(db_session):
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    identifier = item.id
    await import_missing_children(db_session)

    class FailedMax:
        def send_message(self, **kwargs):
            raise RuntimeError("secret-token-must-not-be-retained")

    now = datetime.now(UTC)
    await process_pending_batch(db_session, client=FailedMax(), now=now)
    item = await db_session.get(PendingBinding, identifier)
    assert item.status == "ready" and not item.notified_at and item.notification_attempts == 1
    assert "secret-token" not in item.notification_error
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client, now=now + timedelta(seconds=40))
    assert not client.sent_messages
    await process_pending_batch(db_session, client=client, now=now + timedelta(minutes=3))
    assert len(client.sent_messages) == 1
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 0


async def test_expiry_and_bot_stop_cancel_unlinked_attempts(db_session):
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    identifier = item.id
    item.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.commit()
    await process_pending_batch(db_session)
    assert item.status == "expired"
    with pytest.raises(AccessServiceError) as caught:
        await confirm_pending_binding(db_session, identifier, 77)
    assert caught.value.code == "pending_expired"
    await db_session.rollback()
    item = await wait_for_contact(db_session)
    assert item.status == "pending"
    await revoke_access_for_stopped_bot(db_session, BotStoppedAccessRevoke(
        tenant_slug=TENANT, max_user_id=77,
    ))
    assert item.status == "cancelled"
    client = SimulationMaxClient()
    await import_missing_children(db_session)
    await process_pending_batch(db_session, client=client)
    assert not client.sent_messages


async def test_existing_pupil_binding_cancels_waiting_instead_of_notifying(db_session):
    from app.models.account import MaxAccount
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    identifier = item.id
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 77))
    pupil = await db_session.scalar(select(Student))
    db_session.add(StudentAccessLink(tenant_id=pupil.tenant_id, student_id=pupil.id,
                                     account_id=account.id, role=StudentAccessRole.STUDENT))
    await db_session.commit()
    await import_missing_children(db_session)
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert item.status == "cancelled" and item.reason == "account_already_connected"
    assert not client.sent_messages
    with pytest.raises(AccessServiceError) as caught:
        await confirm_pending_binding(db_session, identifier, 77)
    assert caught.value.code == "pending_already_connected"
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 1


@pytest.mark.parametrize("access_kind", ["parent", "teacher", "superadmin"])
async def test_registered_accounts_do_not_receive_or_confirm_stale_offers(db_session, access_kind):
    from app.models.account import MaxAccount, StaffRoleAssignment
    from app.models.enums import StaffRole
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    identifier = item.id
    await import_missing_children(db_session)
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert len(client.sent_messages) == 1
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 77))
    if access_kind == "parent":
        await create_contact_access_links(db_session, AccessLinkCreate(
            tenant_slug=TENANT, contact_id="681", max_user_id=77, role="parent"))
    else:
        db_session.add(StaffRoleAssignment(tenant_id=item.tenant_id, account_id=account.id,
                                          role=StaffRole(access_kind)))
        await db_session.commit()
    links_before = await db_session.scalar(select(func.count(StudentAccessLink.id)))
    with pytest.raises(AccessServiceError) as caught:
        await confirm_pending_binding(db_session, identifier, 77)
    assert caught.value.code == "pending_already_connected"
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == links_before
    assert item.status == "cancelled" and item.reason == "account_already_connected"
    await process_pending_batch(db_session, client=client,
                                now=datetime.now(UTC) + timedelta(minutes=2))
    assert len(client.sent_messages) == 1  # A stale delivered button cannot create another link.
    with pytest.raises(AccessServiceError) as caught:
        await create_contact_access_links(db_session, AccessLinkCreate(
            tenant_slug=TENANT, contact_id="MISSING", max_user_id=77, role="parent"))
    assert caught.value.code == "contact_not_found"
    assert await db_session.scalar(select(func.count(PendingBinding.id))) == 1
    if access_kind == "parent":
        # Explicit fresh family links still support all of a parent's children.
        await create_contact_access_links(db_session, AccessLinkCreate(
            tenant_slug=TENANT, contact_id="999", max_user_id=77, role="parent"))
        assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 4


async def test_worker_discards_staff_waiting_before_import_or_notification(db_session):
    from app.models.account import MaxAccount, StaffRoleAssignment
    from app.models.audit import AuditLog
    from app.models.enums import StaffRole
    from app.services.access import hash_contact_id
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    account = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 77))
    db_session.add(StaffRoleAssignment(tenant_id=item.tenant_id, account_id=account.id,
                                      role=StaffRole.TEACHER))
    await db_session.commit()
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert item.status == "cancelled" and not client.sent_messages
    db_session.add(AuditLog(tenant_id=item.tenant_id, action="contact_access.resolve_failed",
                            entity_type="contact_access", payload={"max_user_id": 77,
                                "reason": "contact_id_not_found",
                                "contact_id_hash": hash_contact_id("ANOTHER-MISSING")}))
    await db_session.commit()
    assert await recover_historical_missing_bindings(db_session) == 0


async def test_valid_missing_invitation_waits_for_exact_uuid_and_keeps_parent_gate(db_session):
    from app.services.access import get_effective_customer_access_link
    await seed_two_students_for_one_contact(db_session)
    tenant = await db_session.scalar(select(Tenant))
    tenant_id, student_id = tenant.id, uuid4()
    token = issue_teacher_student_invitation_token(tenant_id, student_id)
    with pytest.raises(AccessServiceError) as caught:
        await create_invited_student_access_link(db_session, StudentInvitationLinkCreate(
            tenant_slug=TENANT, token=token, max_user_id=99, display_name="Ребёнок",
        ))
    assert caught.value.code == "pending_waiting"
    item = await db_session.scalar(select(PendingBinding).where(PendingBinding.max_user_id == 99))
    identifier = item.id
    assert item.target_id == str(student_id) and item.issuer == "teacher"
    db_session.add(Student(id=student_id, tenant_id=tenant_id, first_name="Александр",
                           student_access_code="not-a-public-secret"))
    await db_session.commit()
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert len(client.sent_messages) == 1
    result = await confirm_pending_binding(db_session, identifier, 99)
    assert result["role"] == "student"
    link = await db_session.scalar(select(StudentAccessLink).where(
        StudentAccessLink.student_id == student_id,
    ))
    assert link.status == StudentAccessStatus.ACTIVE
    assert await get_effective_customer_access_link(db_session, tenant_id=tenant_id,
                                                   student_id=student_id,
                                                   account_id=link.account_id) is None


async def test_cancel_cannot_be_used_to_modify_another_user_or_existing_links(db_session):
    await seed_two_students_for_one_contact(db_session)
    item = await wait_for_contact(db_session)
    with pytest.raises(HTTPException) as caught:
        await cancel_pending_binding(db_session, item.id, 88)
    assert caught.value.status_code == 404
    assert item.status == "pending"
    await cancel_pending_binding(db_session, item.id, 4242, owner=True)
    assert item.status == "cancelled"


async def test_historical_hash_matches_only_school_contact_and_merges_new_attempt(db_session):
    from app.models.audit import AuditLog
    from app.services.access import hash_contact_id
    await seed_two_students_for_one_contact(db_session)
    tenant = await db_session.scalar(select(Tenant))
    db_session.add(AuditLog(
        tenant_id=tenant.id, action="contact_access.resolve_failed", entity_type="contact_access",
        payload={"max_user_id": 77, "reason": "contact_id_not_found",
                 "contact_id_hash": hash_contact_id("999")},
    ))
    await db_session.commit()
    assert await recover_historical_missing_bindings(db_session) == 1
    assert await recover_historical_missing_bindings(db_session) == 0
    item = await db_session.scalar(select(PendingBinding))
    identifier = item.id
    assert item.target_id.startswith("sha256:")
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert not client.sent_messages
    fresh = await wait_for_contact(db_session)
    assert fresh.id == identifier and fresh.target_id == "999" and fresh.attempts == 2
    await import_missing_children(db_session)
    await process_pending_batch(db_session, client=client)
    assert len(client.sent_messages) == 1
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 0


async def test_historical_hash_can_resolve_after_import_without_another_click(db_session):
    from app.models.audit import AuditLog
    from app.services.access import hash_contact_id
    await seed_two_students_for_one_contact(db_session)
    tenant = await db_session.scalar(select(Tenant))
    for user in (77, 88):
        db_session.add(AuditLog(
            tenant_id=tenant.id, action="contact_access.resolve_failed",
            entity_type="contact_access",
            payload={"max_user_id": user, "reason": "contact_id_not_found",
                     "contact_id_hash": hash_contact_id("999")},
        ))
    await db_session.flush()
    db_session.add(AuditLog(action="bot.interaction", entity_type="activity",
                            created_at=datetime.now(UTC) + timedelta(seconds=1),
                            payload={"max_user_id": 88, "update_type": "bot_stopped"}))
    await db_session.commit()
    assert await recover_historical_missing_bindings(db_session) == 1
    await import_missing_children(db_session)
    client = SimulationMaxClient()
    await process_pending_batch(db_session, client=client)
    assert client.sent_messages[0]["user_id"] == 77
    item = await db_session.scalar(select(PendingBinding))
    assert item.target_id == "999" and item.status == "ready"
    await confirm_pending_binding(db_session, item.id, 77)
    assert await db_session.scalar(select(func.count(StudentAccessLink.id))) == 2


async def test_invalid_links_and_closed_existing_families_are_not_queued(db_session):
    from app.models.enums import StudentStatus
    await seed_two_students_for_one_contact(db_session)
    with pytest.raises(AccessServiceError) as caught:
        await create_invited_student_access_link(db_session, StudentInvitationLinkCreate(
            tenant_slug=TENANT, token="not-a-valid-signed-invitation", max_user_id=77,
        ))
    assert caught.value.code == "invitation_invalid"
    for student in await db_session.scalars(select(Student)):
        student.status = StudentStatus.ARCHIVED
    await db_session.commit()
    with pytest.raises(AccessServiceError) as caught:
        await create_contact_access_links(db_session, AccessLinkCreate(
            tenant_slug=TENANT, contact_id="681", max_user_id=77, role=StudentAccessRole.PARENT,
        ))
    assert caught.value.code == "contact_has_no_students"
    assert await db_session.scalar(select(func.count(PendingBinding.id))) == 0


def test_failed_resolve_persists_identity_and_pending_inbox_is_private(support_client):
    import asyncio
    client, factory = support_client

    async def seed():
        async with factory() as db:
            student = await seed_linked_student(db)
            tenant = await db.get(Tenant, student.tenant_id)
            tenant.slug = "test-city"
            await db.commit()

    asyncio.run(seed())
    payload = {"max_user_id": 77, "tenant_slug": "test-city", "contact_id": "7777",
               "username": "parent", "display_name": "Фролова Екатерина"}
    result = client.post("/api/v1/access/resolve-contact", headers=auth(), json=payload)
    assert result.status_code == 404 and result.headers["X-Access-Error-Code"] == "pending_waiting"
    assert "сохранили" in result.json()["detail"]
    route = "/api/v1/access/pending?tenant_slug=test-city"
    assert client.get(route).status_code == 401
    assert client.get(route, headers=auth()).status_code == 403
    inbox = client.get(route, headers=auth(4242))
    assert inbox.status_code == 200 and "no-store" in inbox.headers["cache-control"]
    item = inbox.json()["items"][0]
    assert item["name"] == "Фролова Екатерина" and item["target_id"] == "7777"
    assert item["max_user_id"] == "77" and item["role"] == "parent"
    assert "fingerprint" not in item and "token" not in item
    path = f'/api/v1/access/pending/{item["id"]}/confirm'
    action = {"max_user_id": 77, "tenant_slug": "test-city"}
    assert client.post(path, json=action).status_code == 401
    assert client.post(path, headers=auth(88), json=action).status_code == 403
    forwarded = {**action, "max_user_id": 88}
    assert client.post(path, headers=auth(88), json=forwarded).status_code == 400
    cancel = path.replace("confirm", "cancel")
    assert client.post(cancel, headers=auth(88), json=forwarded).status_code == 404
    response = client.post(cancel, headers=auth(4242), json={**action, "max_user_id": 4242})
    assert response.status_code == 204
    assert client.get(route, headers=auth(4242)).json()["items"] == []


def test_bot_waiting_copy_and_confirmation_callback_restore_correct_school(tmp_path):
    from app.bot.backend_client import BackendApiError
    from app.bot.max_long_polling import LongPollingBot

    class Backend:
        def get_session(self, **kwargs):
            return {"has_access": False, "students": [], "staff_roles": []}

        def resolve_contact(self, **kwargs):
            raise BackendApiError("HTTP 404", status_code=404, error_code="pending_waiting")

        def pending_binding_action(self, **kwargs):
            assert kwargs["max_user_id"] == 77 and kwargs["action"] == "confirm"
            return {"tenant_slug": "another-school", "role": "parent",
                    "student_names": ["Кузнецов Александр"]}

    client = SimulationMaxClient()
    bot = LongPollingBot(client, backend_client=Backend(), default_tenant_slug=TENANT,
                          onboarding_state_path=tmp_path / "onboarding.sqlite3")
    response = bot.handle_contact_payload_response(payload="cid_999", user_id=77)
    assert "сохранили вашу попытку" in response.text
    assert "HTTP" not in response.text and "Не получилось" not in response.text
    assert not bot.pending_contact_ids
    bot.handle_message_callback({"callback": {
        "payload": f"pending:confirm:{uuid4()}", "callback_id": "callback-1",
        "user": {"user_id": 77},
    }})
    assert bot.user_tenant_slugs[77] == "another-school"
    assert bot.user_menu_roles[(77, "another-school")] == "parent"
    assert "Подключение завершено" in client.sent_messages[-1]["text"]
