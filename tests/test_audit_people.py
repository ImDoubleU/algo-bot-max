# ruff: noqa: F811
from datetime import UTC, datetime

from app.models.account import StaffRoleAssignment
from app.models.enums import AssignmentStatus, StaffRole
from app.services.audit_history import history_page
from tests.test_miniapp_store import (  # noqa: F401
    db_session,
    grant_store_admin,
    seed_linked_student,
)


async def test_parent_event_includes_child_group_teacher_and_account_ids(db_session):
    student = await seed_linked_student(db_session)
    account = await grant_store_admin(db_session, tenant_id=student.tenant_id)
    account.staff_first_name = "Дмитрий"
    account.staff_last_name = "Олейник"
    account.staff_profile_completed_at = datetime.now(UTC)
    student.teacher_name = "Олейник Дмитрий"
    db_session.add(
        StaffRoleAssignment(
            tenant_id=student.tenant_id,
            account_id=account.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    await db_session.commit()
    history = await history_page(
        db_session, max_user_id=53364725, tenant_slug="nizhniy-novgorod-partner-a", kind="bindings"
    )
    event = next(e for e in history.entries if e.action == "contact_access_links.created")
    assert event.actor_name == "Мама Алисы"
    assert event.actor_max_user_id == 53364725
    assert event.payload["actor_role"] == "parent"
    child = event.payload["students"][0]
    assert child["id"] == str(student.id) and child["name"] == student.display_name
    assert child["lms_id"] == "ST-001"
    assert child["teacher_max_user_id"] == 53364725
    assert child["accounts"][0]["role"] == "parent"
    assert child["accounts"][0]["max_user_id"] == 53364725
