from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.enums import StudentAccessRole, StudentAccessStatus
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.models.tenant import City, Partner, Tenant
from app.schemas.access import AccessLinkCreate, StudentInvitationLinkCreate
from app.services.access import (
    AccessServiceError,
    create_contact_access_links,
    create_invited_student_access_link,
    get_effective_customer_access_link,
)
from app.services.student_invitations import (
    issue_student_invitation_token,
    issue_teacher_student_invitation_token,
)


@pytest.fixture
async def binding_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        city = City(slug="review-city", name="Город")
        partner = Partner(slug="review-school", name="Школа")
        db.add_all([city, partner])
        await db.flush()
        tenant = Tenant(
            city_id=city.id, partner_id=partner.id, slug="review", name="Школа",
        )
        db.add(tenant)
        await db.flush()
        student = Student(
            tenant_id=tenant.id, student_access_code="review-child", first_name="Ученик",
        )
        contact = Contact(tenant_id=tenant.id, external_contact_id="681")
        db.add_all([student, contact])
        await db.flush()
        db.add(ContactStudentLink(
            tenant_id=tenant.id, student_id=student.id, contact_id=contact.id,
        ))
        await db.commit()
        yield db, tenant, student
    await engine.dispose()


def child_payload(tenant, student, *, token=None):
    return StudentInvitationLinkCreate(
        tenant_slug=tenant.slug, max_user_id=9901,
        token=token or issue_teacher_student_invitation_token(tenant.id, student.id),
    )


async def parent_link(db, tenant, *, user_id=9902):
    return (await create_contact_access_links(db, AccessLinkCreate(
        tenant_slug=tenant.slug, contact_id="681", max_user_id=user_id,
        role=StudentAccessRole.PARENT,
    )))[0]


async def test_repeated_teacher_qr_preserves_one_binding_and_waits_for_parent(binding_db):
    db, tenant, student = binding_db
    payload = child_payload(tenant, student)
    _, _, initial = await create_invited_student_access_link(db, payload)
    _, _, repeated = await create_invited_student_access_link(db, payload)
    assert repeated.id == initial.id
    links = list((await db.scalars(select(StudentAccessLink))).all())
    assert len(links) == 1
    assert initial.status == StudentAccessStatus.ACTIVE
    assert await get_effective_customer_access_link(
        db, tenant_id=tenant.id, account_id=initial.account_id, student_id=student.id,
    ) is None
    await parent_link(db, tenant)
    assert await get_effective_customer_access_link(
        db, tenant_id=tenant.id, account_id=initial.account_id, student_id=student.id,
    ) is not None


@pytest.mark.parametrize("invitation_type", ["teacher", "parent"])
async def test_other_max_account_cannot_take_an_already_bound_student(binding_db, invitation_type):
    db, tenant, student = binding_db
    token = issue_teacher_student_invitation_token(tenant.id, student.id)
    if invitation_type == "parent":
        sponsor = await parent_link(db, tenant)
        token = issue_student_invitation_token(tenant.id, student.id, sponsor.id)
    payload = child_payload(tenant, student, token=token)
    _, _, original = await create_invited_student_access_link(db, payload)
    original_id = original.id
    with pytest.raises(AccessServiceError) as rejected:
        await create_invited_student_access_link(
            db, payload.model_copy(update={"max_user_id": 9904}),
        )
    assert rejected.value.code == "student_profile_already_bound"
    original = await db.get(StudentAccessLink, original_id)
    assert original.status == StudentAccessStatus.ACTIVE
    assert await db.scalar(select(MaxAccount.id).where(MaxAccount.max_user_id == 9904)) is None
    failure = await db.scalar(select(AuditLog).where(
        AuditLog.action == "student_qr_access_link.failed",
    ))
    assert failure.payload["reason"] == "student_profile_already_bound"
    assert failure.payload["max_user_id"] == 9904
    assert failure.payload["student_id"] == str(original.student_id)


async def test_old_account_cannot_recover_after_another_account_has_connected(binding_db):
    db, tenant, student = binding_db
    payload = child_payload(tenant, student)
    _, _, old = await create_invited_student_access_link(db, payload)
    old_id = old.id
    old.status = StudentAccessStatus.REVOKED
    old.revoked_reason = "registration_reset"
    await db.commit()
    _, _, current = await create_invited_student_access_link(
        db, payload.model_copy(update={"max_user_id": 9904}),
    )
    current_id = current.id
    with pytest.raises(AccessServiceError) as rejected:
        await create_invited_student_access_link(db, payload)
    assert rejected.value.code == "student_profile_already_bound"
    assert (await db.get(StudentAccessLink, current_id)).status == StudentAccessStatus.ACTIVE
    assert (await db.get(StudentAccessLink, old_id)).status == StudentAccessStatus.REVOKED


@pytest.mark.parametrize("duplicate_direction", ["student", "account"])
async def test_database_rejects_active_student_duplicates_from_other_writers(
    binding_db, duplicate_direction,
):
    db, tenant, student = binding_db
    _, _, original = await create_invited_student_access_link(db, child_payload(tenant, student))
    original_id, tenant_id = original.id, tenant.id
    student_id, account_id = student.id, original.account_id
    if duplicate_direction == "student":
        other = MaxAccount(max_user_id=9904)
        db.add(other)
        await db.flush()
        account_id = other.id
    else:
        other = Student(tenant_id=tenant_id, student_access_code="another-child", first_name="Ян")
        db.add(other)
        await db.flush()
        student_id = other.id
    db.add(StudentAccessLink(tenant_id=tenant_id, student_id=student_id, account_id=account_id,
                             role=StudentAccessRole.STUDENT, status=StudentAccessStatus.ACTIVE))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()
    assert (await db.get(StudentAccessLink, original_id)).status == StudentAccessStatus.ACTIVE
    assert len(list(await db.scalars(select(StudentAccessLink)))) == 1


@pytest.mark.parametrize("direction", ["student", "account"])
async def test_database_conflict_returns_a_binding_error_and_logs_attempt(
    binding_db, monkeypatch, direction,
):
    db, tenant, student = binding_db
    payload = child_payload(tenant, student)
    _, _, original = await create_invited_student_access_link(db, payload)
    original_id = original.id
    rejected = payload.model_copy(update={"max_user_id": 9904})
    expected_code = "student_profile_already_bound"
    if direction == "account":
        other = Student(tenant_id=tenant.id, student_access_code="new-child", first_name="Ян")
        db.add(other)
        await db.commit()
        rejected = payload.model_copy(update={
            "token": issue_teacher_student_invitation_token(tenant.id, other.id),
        })
        expected_code = "student_already_bound"

    async def bypass_guard(*args, **kwargs):
        pass

    # Simulate a writer racing after the application-level check.
    monkeypatch.setattr("app.services.access.ensure_single_account_binding", bypass_guard)
    with pytest.raises(AccessServiceError) as error:
        await create_invited_student_access_link(db, rejected)
    assert error.value.code == expected_code
    assert (await db.get(StudentAccessLink, original_id)).status == StudentAccessStatus.ACTIVE
    failure = await db.scalar(select(AuditLog).where(
        AuditLog.action == "student_qr_access_link.failed",
    ))
    assert failure.payload["reason"] == expected_code
    assert failure.payload["max_user_id"] == rejected.max_user_id
    assert len(list(await db.scalars(select(StudentAccessLink)))) == 1


@pytest.mark.parametrize("reason", ["admin", "manual", None])
async def test_qr_does_not_override_explicit_or_unexplained_school_revocation(binding_db, reason):
    db, tenant, student = binding_db
    payload = child_payload(tenant, student)
    _, _, link = await create_invited_student_access_link(db, payload)
    link_id = link.id
    link.status = StudentAccessStatus.REVOKED
    link.revoked_reason = reason
    link.revoked_at = datetime.now(UTC)
    await db.commit()
    with pytest.raises(AccessServiceError):
        await create_invited_student_access_link(db, payload)
    stored = await db.get(StudentAccessLink, link_id)
    assert stored.status == StudentAccessStatus.REVOKED
    assert stored.revoked_reason == reason


@pytest.mark.parametrize("reason", [
    "bot_stopped", "registration_reset", "sponsor_bot_stopped", "sponsor_revoked",
    "parent_required_hotfix",
])
async def test_valid_qr_recovers_known_technical_revocations_without_duplicates(binding_db, reason):
    db, tenant, student = binding_db
    payload = child_payload(tenant, student)
    _, _, link = await create_invited_student_access_link(db, payload)
    link_id = link.id
    link.status = StudentAccessStatus.REVOKED
    link.revoked_reason = reason
    link.revoked_at = datetime.now(UTC)
    await db.commit()
    _, _, recovered = await create_invited_student_access_link(db, payload)
    assert recovered.id == link_id
    assert recovered.status == StudentAccessStatus.ACTIVE
    assert recovered.revoked_at is None
    assert recovered.revoked_reason is None


async def test_old_parent_qr_stays_invalid_when_a_different_parent_is_active(binding_db):
    db, tenant, student = binding_db
    original_parent = await parent_link(db, tenant)
    original_parent.status = StudentAccessStatus.REVOKED
    original_parent.revoked_reason = "admin"
    await db.commit()
    replacement_parent = await parent_link(db, tenant, user_id=9903)
    assert replacement_parent.status == StudentAccessStatus.ACTIVE
    token = issue_student_invitation_token(tenant.id, student.id, original_parent.id)
    with pytest.raises(AccessServiceError):
        await create_invited_student_access_link(db, child_payload(tenant, student, token=token))
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 9901))
    assert account is None


async def test_child_cannot_switch_to_parent_using_the_letter(binding_db):
    db, tenant, student = binding_db
    _, _, child = await create_invited_student_access_link(db, child_payload(tenant, student))
    child_id = child.id
    with pytest.raises(AccessServiceError):
        await parent_link(db, tenant, user_id=9901)
    links = list((await db.scalars(select(StudentAccessLink))).all())
    assert len(links) == 1
    assert links[0].id == child_id
    assert links[0].role == StudentAccessRole.STUDENT
    assert links[0].status == StudentAccessStatus.ACTIVE


async def test_family_reconnect_failure_does_not_partially_restore_other_child(binding_db):
    db, tenant, student = binding_db
    contact = await db.scalar(select(Contact))
    second_child = Student(
        tenant_id=tenant.id, student_access_code="review-second", first_name="Ян",
    )
    db.add(second_child)
    await db.flush()
    db.add(ContactStudentLink(
        tenant_id=tenant.id, student_id=second_child.id, contact_id=contact.id,
    ))
    await db.commit()
    payload = AccessLinkCreate(
        tenant_slug=tenant.slug, contact_id="681", max_user_id=9902,
        role=StudentAccessRole.PARENT,
    )
    links = await create_contact_access_links(db, payload)
    first = next(link for link in links if link.student_id == student.id)
    second = next(link for link in links if link.student_id == second_child.id)
    first_id, second_id = first.id, second.id
    first.status = second.status = StudentAccessStatus.REVOKED
    first.revoked_reason = "registration_reset"
    second.revoked_reason = "admin"
    await db.commit()
    with pytest.raises(AccessServiceError):
        await create_contact_access_links(db, payload)
    stored_first = await db.get(StudentAccessLink, first_id)
    stored_second = await db.get(StudentAccessLink, second_id)
    assert stored_first.status == stored_second.status == StudentAccessStatus.REVOKED
    assert stored_first.revoked_reason == "registration_reset"
    assert stored_second.revoked_reason == "admin"


async def test_invalid_qr_failure_has_durable_diagnostics_without_raw_token(binding_db, caplog):
    db, tenant, student = binding_db
    token = "sensitive-broken-personal-invitation"
    payload = child_payload(tenant, student, token=token)
    with caplog.at_level("INFO", logger="app.services.access"):
        with pytest.raises(AccessServiceError):
            await create_invited_student_access_link(db, payload)
    await db.rollback()
    audit = await db.scalar(select(AuditLog).where(
        AuditLog.action == "student_qr_access_link.failed",
    ))
    assert audit is not None
    assert audit.payload["max_user_id"] == payload.max_user_id
    assert audit.payload["result"] == "failed"
    assert audit.payload["reason"] == "invitation_invalid"
    assert len(audit.payload["invitation_hash"]) == 64
    assert token not in str(audit.payload)
    assert "binding_failed" in caplog.text
    assert "invitation_invalid" in caplog.text
    assert token not in caplog.text
