# ruff: noqa: F811
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.enums import AssignmentStatus, StaffRole
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.schemas.access import AccessLinkCreate
from app.services.access import create_contact_access_links
from app.services.deep_links import parse_shop_payload
from app.services.miniapp import (
    MiniAppStoreError,
    get_miniapp_student_invitation,
    list_miniapp_teacher_invitations,
)
from tests.test_contact_access_service import (  # noqa: F401
    db_session,
    seed_two_students_for_one_contact,
)

SCHOOL = "nizhniy-novgorod-partner-a"


@pytest.fixture
def configured_bot(monkeypatch):
    monkeypatch.setenv("MAX_BOT_USERNAME", "AlgoBot")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def teacher_context(db):
    await seed_two_students_for_one_contact(db)
    students = list(await db.scalars(select(Student).order_by(Student.lms_student_id)))
    students[1].teacher_name = "Другой преподаватель"
    teacher = MaxAccount(max_user_id=8801, display_name="Олейник Д")
    db.add(teacher)
    await db.flush()
    db.add(StaffRoleAssignment(
        tenant_id=students[0].tenant_id, account_id=teacher.id,
        role=StaffRole.TEACHER, status=AssignmentStatus.ACTIVE,
    ))
    await db.commit()
    return teacher, students


async def test_parent_links_use_imported_contacts_and_preserve_multiple_parents(
    db_session, configured_bot,
):
    teacher, students = await teacher_context(db_session)
    pupil = students[0]
    second = Contact(tenant_id=pupil.tenant_id, external_contact_id="682", display_name="Папа")
    db_session.add(second)
    await db_session.flush()
    db_session.add(ContactStudentLink(
        tenant_id=pupil.tenant_id, contact_id=second.id, student_id=pupil.id,
    ))
    await db_session.commit()
    links_before = await db_session.scalar(select(func.count()).select_from(StudentAccessLink))
    result = await list_miniapp_teacher_invitations(
        db_session, max_user_id=teacher.max_user_id, tenant_slug=SCHOOL,
    )
    assert len(result) == 1 and result[0].student_id == pupil.id
    invitation = result[0]
    assert not invitation.parent_connected and invitation.bot_url
    assert {item.parent_name for item in invitation.parent_invitations} == {"Мама", "Папа"}
    assert {
        parse_shop_payload(parse_qs(urlsplit(item.bot_url).query)["start"][0])
        for item in invitation.parent_invitations
    } == {(SCHOOL, "681"), (SCHOOL, "682")}
    assert all(urlsplit(item.bot_url).path == "/AlgoBot" for item in invitation.parent_invitations)
    single = await get_miniapp_student_invitation(
        db_session, max_user_id=teacher.max_user_id, tenant_slug=SCHOOL, student_id=pupil.id,
    )
    assert single.parent_invitations == invitation.parent_invitations
    links_after = await db_session.scalar(select(func.count()).select_from(StudentAccessLink))
    assert links_after == links_before


async def test_parent_links_do_not_bypass_teacher_scope_or_leak_to_parents(
    db_session, configured_bot,
):
    teacher, students = await teacher_context(db_session)
    with pytest.raises(MiniAppStoreError) as denied:
        await get_miniapp_student_invitation(
            db_session, max_user_id=teacher.max_user_id, tenant_slug=SCHOOL,
            student_id=students[1].id,
        )
    assert denied.value.status_code == 403
    await create_contact_access_links(db_session, AccessLinkCreate(
        tenant_slug=SCHOOL, contact_id="681", max_user_id=9901, role="parent",
    ))
    parent_view = await get_miniapp_student_invitation(
        db_session, max_user_id=9901, tenant_slug=SCHOOL, student_id=students[0].id,
    )
    teacher_view = await list_miniapp_teacher_invitations(
        db_session, max_user_id=teacher.max_user_id, tenant_slug=SCHOOL,
    )
    assert parent_view.parent_connected and not parent_view.parent_invitations
    assert teacher_view[0].parent_connected and not teacher_view[0].parent_invitations


async def test_missing_contact_keeps_child_qr_without_fabricating_parent_link(
    db_session, configured_bot,
):
    teacher, students = await teacher_context(db_session)
    await db_session.execute(delete(ContactStudentLink).where(
        ContactStudentLink.student_id == students[0].id,
    ))
    await db_session.commit()
    invitation = await get_miniapp_student_invitation(
        db_session, max_user_id=teacher.max_user_id, tenant_slug=SCHOOL,
        student_id=students[0].id,
    )
    assert not invitation.parent_connected and invitation.qr_data_url
    assert not invitation.parent_invitations
