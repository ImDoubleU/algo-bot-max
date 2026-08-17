import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount
from app.models.base import Base
from app.models.enums import StudentAccessRole, StudentAccessStatus
from app.models.student import StudentAccessLink
from app.schemas.access import AccessLinkCreate, StudentInvitationLinkCreate, StudentResolveRequest
from app.services.access import (
    AccessServiceError,
    create_contact_access_links,
    create_invited_student_access_link,
    resolve_students_by_contact_id,
)
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.student_invitations import issue_student_invitation_token


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def row(*, lms_student_id: str, first_name: str) -> CrmStudentRow:
    return CrmStudentRow(
        row_number=2,
        deal_id=lms_student_id,
        uuid=f"uuid-{lms_student_id}",
        lms_student_id=lms_student_id,
        first_name=first_name,
        last_name=None,
        group_name="\u0421\u043e\u044e\u0437\u043d\u044b\u0439 45, \u0432\u0441 10:00",
        course_name="Python Start",
        venue_name="\u0421\u043e\u044e\u0437\u043d\u044b\u0439 45",
        teacher_name="\u041e\u043b\u0435\u0439\u043d\u0438\u043a \u0414",
        city="\u041d\u0438\u0436\u043d\u0438\u0439 \u041d\u043e\u0432\u0433\u043e\u0440\u043e\u0434",  # noqa: E501
        status_name="\u0410\u043a\u0442\u0438\u0432\u0435\u043d",
        contact_ids="681",
        contact_names="\u041c\u0430\u043c\u0430",
    )


async def seed_two_students_for_one_contact(db_session) -> None:
    await upsert_crm_student_rows(
        db_session,
        [
            row(lms_student_id="ST-001", first_name="\u0410\u043b\u0438\u0441\u0430"),
            row(lms_student_id="ST-002", first_name="\u0418\u0432\u0430\u043d"),
        ],
        defaults=CrmSyncDefaults(
            partner_slug="partner-a",
            partner_name="\u041f\u0430\u0440\u0442\u043d\u0435\u0440 A",
        ),
    )


async def test_resolve_students_by_contact_id_returns_all_linked_students(db_session) -> None:
    await seed_two_students_for_one_contact(db_session)

    resolved = await resolve_students_by_contact_id(
        db_session,
        StudentResolveRequest(tenant_slug="nizhniy-novgorod-partner-a", contact_id="681"),
    )

    assert resolved is not None
    contact, students = resolved
    assert contact.external_contact_id == "681"
    assert len(students) == 2


async def test_create_contact_access_links_creates_link_per_student(db_session) -> None:
    await seed_two_students_for_one_contact(db_session)

    links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
            username="ImDoubleU",
        ),
    )

    stored_links = (await db_session.scalars(select(StudentAccessLink))).all()
    assert len(links) == 2
    assert len(stored_links) == 2


async def test_relink_without_profile_data_keeps_existing_max_account_name(db_session) -> None:
    await seed_two_students_for_one_contact(db_session)
    payload = AccessLinkCreate(
        tenant_slug="nizhniy-novgorod-partner-a",
        contact_id="681",
        max_user_id=53364725,
        role=StudentAccessRole.PARENT,
        username="ImDoubleU",
        display_name="Дмитрий",
    )
    await create_contact_access_links(db_session, payload)
    await create_contact_access_links(
        db_session,
        payload.model_copy(update={"username": None, "display_name": None}),
    )

    account = await db_session.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == 53364725)
    )
    assert account is not None
    assert account.username == "ImDoubleU"
    assert account.display_name == "Дмитрий"


async def test_parent_max_account_cannot_accept_child_qr(db_session) -> None:
    await seed_two_students_for_one_contact(db_session)
    parent_links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
        ),
    )
    parent_link = parent_links[0]
    token = issue_student_invitation_token(
        parent_link.tenant_id,
        parent_link.student_id,
        parent_link.id,
    )

    with pytest.raises(AccessServiceError, match="уже используется родителем"):
        await create_invited_student_access_link(
            db_session,
            StudentInvitationLinkCreate(
                tenant_slug="nizhniy-novgorod-partner-a",
                token=token,
                max_user_id=53364725,
            ),
        )


async def test_revoked_parent_account_can_be_relinked_as_student(db_session) -> None:
    await seed_two_students_for_one_contact(db_session)
    former_parent_links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364725,
            role=StudentAccessRole.PARENT,
        ),
    )
    sponsor_links = await create_contact_access_links(
        db_session,
        AccessLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            contact_id="681",
            max_user_id=53364726,
            role=StudentAccessRole.PARENT,
        ),
    )
    for link in former_parent_links:
        link.status = StudentAccessStatus.REVOKED
        link.revoked_reason = "admin"
    await db_session.commit()

    sponsor_link = sponsor_links[0]
    token = issue_student_invitation_token(
        sponsor_link.tenant_id,
        sponsor_link.student_id,
        sponsor_link.id,
    )
    _, _, student_link = await create_invited_student_access_link(
        db_session,
        StudentInvitationLinkCreate(
            tenant_slug="nizhniy-novgorod-partner-a",
            token=token,
            max_user_id=53364725,
        ),
    )

    assert student_link.role == StudentAccessRole.STUDENT
    assert student_link.status == StudentAccessStatus.ACTIVE
