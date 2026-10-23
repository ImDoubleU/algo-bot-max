from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_contact_access_service import (
    db_session as _db_session,
)
from test_contact_access_service import (
    row,
    seed_two_students_for_one_contact,
)

from app.bot.onboarding_state import OnboardingState
from app.models.account import MaxAccount, StaffRoleAssignment, StaffVenueScope
from app.models.enums import AssignmentStatus, StaffRole, StudentAccessRole, StudentAccessStatus
from app.models.pending_binding import PendingBinding
from app.models.student import Student, Wallet
from app.models.tenant import Venue
from app.schemas.access import AccessLinkCreate, StudentInvitationLinkCreate
from app.schemas.miniapp import MiniAppAccessStatusUpdate
from app.services.access import create_contact_access_links, create_invited_student_access_link
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.miniapp import MiniAppStoreError, update_miniapp_access_link_status
from app.services.student_invitations import issue_teacher_student_invitation_token

db_session = _db_session
SLUG = "nizhniy-novgorod-partner-a"


async def setup_accounts(db):
    await seed_two_students_for_one_contact(db)
    payload = AccessLinkCreate(tenant_slug=SLUG, contact_id="681", max_user_id=71001,
                              role=StudentAccessRole.PARENT)
    parents = await create_contact_access_links(db, payload)
    student = await db.get(Student, parents[0].student_id)
    actor = MaxAccount(max_user_id=71002)
    db.add(actor)
    await db.flush()
    db.add(StaffRoleAssignment(tenant_id=student.tenant_id, account_id=actor.id,
                              role=StaffRole.ADMIN, status=AssignmentStatus.ACTIVE))
    await db.commit()
    return actor, student, parents, payload


async def detach(db, link):
    return await update_miniapp_access_link_status(db, link_id=link.id,
        payload=MiniAppAccessStatusUpdate(max_user_id=71002, tenant_slug=SLUG,
            status=StudentAccessStatus.REVOKED, detach_account=True), default_tenant_slug=SLUG)


async def test_full_detach_resets_all_children_pending_and_allows_rebind(db_session, tmp_path,
                                                                      monkeypatch):
    _, student, parents, payload = await setup_accounts(db_session)
    state_file = tmp_path / "onboarding.sqlite3"
    monkeypatch.setenv("MAX_ONBOARDING_STATE_PATH", str(state_file))
    state = OnboardingState(state_file)
    state.save(71001, contact_id="681", tenant_slug=SLUG, role="parent",
               correlation_id="detach-test", ttl=300)
    assert state.get(71001) is not None
    # A stale admin-revoked sibling must not block a fresh registration.
    parents[1].status = StudentAccessStatus.REVOKED
    parents[1].revoked_reason = "admin"
    child_payload = StudentInvitationLinkCreate(tenant_slug=SLUG, max_user_id=71003,
        token=issue_teacher_student_invitation_token(student.tenant_id, student.id))
    _, _, child = await create_invited_student_access_link(db_session, child_payload)
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == student.id))
    wallet.balance = 777
    now = datetime.now(UTC)
    attempts = []
    for index, status in enumerate(["pending", "review", "completed"]):
        attempt = PendingBinding(tenant_id=student.tenant_id, max_user_id=71001, role="parent",
            kind="contact", target_id="681", fingerprint=str(index), status=status,
            reason="auto_connected" if status == "completed" else "contact_not_found",
            last_attempt_at=now, expires_at=now + timedelta(days=30))
        db_session.add(attempt)
        attempts.append(attempt)
    await db_session.commit()
    result = await detach(db_session, parents[0])
    assert result.status == StudentAccessStatus.REVOKED
    assert all(link.revoked_reason == "registration_reset" for link in parents)
    assert all(attempt.status == "cancelled" for attempt in attempts)
    assert child.status == StudentAccessStatus.REVOKED
    assert child.revoked_reason == "sponsor_revoked"
    assert wallet.balance == 777
    assert state.get(71001) is None
    reconnected = await create_contact_access_links(db_session, payload)
    assert len(reconnected) == 2
    assert all(link.status == StudentAccessStatus.ACTIVE for link in reconnected)
    _, _, restored = await create_invited_student_access_link(db_session, child_payload)
    assert restored.id == child.id
    assert restored.status == StudentAccessStatus.ACTIVE


async def test_detached_student_account_can_change_to_parent_role(
    db_session, tmp_path, monkeypatch,
):
    monkeypatch.setenv("MAX_ONBOARDING_STATE_PATH", str(tmp_path / "missing.sqlite3"))
    _, student, _, _ = await setup_accounts(db_session)
    _, _, child = await create_invited_student_access_link(db_session,
        StudentInvitationLinkCreate(tenant_slug=SLUG, max_user_id=71003,
            token=issue_teacher_student_invitation_token(student.tenant_id, student.id)))
    await detach(db_session, child)
    links = await create_contact_access_links(db_session,
        AccessLinkCreate(tenant_slug=SLUG, contact_id="681", max_user_id=71003,
                        role=StudentAccessRole.PARENT))
    assert len(links) == 2
    assert all(link.status == StudentAccessStatus.ACTIVE for link in links)


async def test_detach_checks_every_child_scope_before_changing_anything(db_session):
    actor, student, parents, _ = await setup_accounts(db_session)
    other = await db_session.get(Student, parents[1].student_id)
    venue = Venue(tenant_id=student.tenant_id, name="Other venue", slug="other")
    db_session.add(venue)
    await db_session.flush()
    other.venue_id = venue.id
    assignment = await db_session.scalar(select(StaffRoleAssignment).where(
        StaffRoleAssignment.account_id == actor.id))
    assignment.role = StaffRole.PARTNER_DIRECTOR
    db_session.add(StaffVenueScope(assignment_id=assignment.id, venue_id=student.venue_id))
    await db_session.commit()
    with pytest.raises(MiniAppStoreError) as exc:
        await detach(db_session, parents[0])
    assert exc.value.status_code == 403
    assert all(link.status == StudentAccessStatus.ACTIVE for link in parents)


async def test_detach_cannot_be_used_to_restore_access(db_session):
    _, _, parents, _ = await setup_accounts(db_session)
    with pytest.raises(MiniAppStoreError):
        await update_miniapp_access_link_status(db_session, link_id=parents[0].id,
            payload=MiniAppAccessStatusUpdate(max_user_id=71002, tenant_slug=SLUG,
                status=StudentAccessStatus.ACTIVE, detach_account=True), default_tenant_slug=SLUG)
    assert all(link.status == StudentAccessStatus.ACTIVE for link in parents)


async def test_full_detach_is_atomic_across_cities(db_session, tmp_path, monkeypatch):
    monkeypatch.setenv("MAX_ONBOARDING_STATE_PATH", str(tmp_path / "missing.sqlite3"))
    actor, _, parents, _ = await setup_accounts(db_session)
    foreign_row = replace(row(lms_student_id="ST-003", first_name="Other child"), city="Бор")
    await upsert_crm_student_rows(db_session, [foreign_row],
        defaults=CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A"))
    foreign_links = await create_contact_access_links(db_session,
        AccessLinkCreate(tenant_slug="bor-partner-a", contact_id="681", max_user_id=71001,
                        role=StudentAccessRole.PARENT))
    with pytest.raises(MiniAppStoreError) as exc:
        await detach(db_session, parents[0])
    assert exc.value.status_code == 403
    assert all(link.status == StudentAccessStatus.ACTIVE for link in parents + foreign_links)
    db_session.add(StaffRoleAssignment(tenant_id=foreign_links[0].tenant_id, account_id=actor.id,
                                      role=StaffRole.ADMIN, status=AssignmentStatus.ACTIVE))
    await db_session.commit()
    await detach(db_session, parents[0])
    assert all(link.status == StudentAccessStatus.REVOKED for link in parents + foreign_links)
