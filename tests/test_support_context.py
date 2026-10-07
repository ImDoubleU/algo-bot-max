# ruff: noqa: F811
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import event, select

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.enums import AssignmentStatus, StaffRole, StudentAccessRole, StudentAccessStatus
from app.models.student import Student, StudentAccessLink
from app.services.support_context import ticket_user_contexts
from tests.test_miniapp_store import db_session, seed_linked_student  # noqa: F401
from tests.test_support import auth, support_client, ticket  # noqa: F401


async def test_ticket_context_uses_verified_max_links_and_keeps_revoked_family_profiles(db_session):
    first = await seed_linked_student(db_session)
    parent = await db_session.scalar(select(MaxAccount).where(MaxAccount.max_user_id == 53364725))
    parent.display_name = "Мой MAX"
    parent.username = "parent_name"
    parent.phone = "+79990000000"
    parent.staff_first_name = "Дмитрий"
    parent.staff_last_name = "Олейник"
    parent.staff_profile_completed_at = datetime.now(UTC)
    second = Student(tenant_id=first.tenant_id, first_name="Дмитрий", last_name="Петров",
                     student_access_code="secret-other-child", lms_student_id="ST-002",
                     group_name="Scratch", teacher_name="Другой преподаватель")
    unrelated = Student(tenant_id=first.tenant_id, first_name=first.first_name,
                        last_name=first.last_name, student_access_code="secret-same-name")
    child = MaxAccount(max_user_id=111, display_name="Child MAX")
    db_session.add_all([second, unrelated, child])
    await db_session.flush()
    db_session.add_all([
        StaffRoleAssignment(tenant_id=first.tenant_id, account_id=parent.id,
                            role=StaffRole.TEACHER, status=AssignmentStatus.ACTIVE),
        StudentAccessLink(tenant_id=first.tenant_id, student_id=first.id,
                          account_id=child.id, role=StudentAccessRole.STUDENT),
        StudentAccessLink(tenant_id=first.tenant_id, student_id=second.id,
                          account_id=parent.id, role=StudentAccessRole.PARENT,
                          status=StudentAccessStatus.REVOKED, revoked_reason="parent_required"),
    ])
    await db_session.commit()
    cases = [SimpleNamespace(id=7, max_user_id=parent.max_user_id, tenant_slug="test-city"),
             SimpleNamespace(id=8, max_user_id=999, tenant_slug="test-city")]
    contexts = await ticket_user_contexts(db_session, cases)
    context = contexts[7]
    assert context["account"]["name"] == "Мой MAX"
    assert context["account"]["username"] == "parent_name"
    assert context["account"]["phone"] == "+79990000000"
    assert context["account"]["staff_name"] == "Олейник Дмитрий"
    pupils = {item["id"]: item for item in context["students"]}
    assert set(pupils) == {str(first.id), str(second.id)}
    assert pupils[str(first.id)]["lms_id"] == "ST-001"
    assert pupils[str(first.id)]["school"]["city"] == "Нижний Новгород"
    assert pupils[str(first.id)]["teacher_max_id"] == str(parent.max_user_id)
    assert pupils[str(first.id)]["parent_connected"]
    assert pupils[str(first.id)]["contacts"][0]["name"] == "Мама Алисы"
    assert any(item["max_id"] == "111" for item in pupils[str(first.id)]["accounts"])
    assert pupils[str(second.id)]["links"][0]["status"] == "revoked"
    assert context["staff"][0]["groups"][0]["name"] == first.group_name
    assert context["staff"][0]["groups"][0]["students"] == 1
    assert contexts[8]["account"] is None and contexts[8]["students"] == []
    assert "secret-other-child" not in str(contexts)
    assert "secret-same-name" not in str(contexts)
    # Context is current data, not a copy retained alongside the ticket.
    first.group_name = "Новая группа"
    await db_session.commit()
    fresh = await ticket_user_contexts(db_session, cases)
    updated_student = next(item for item in fresh[7]["students"] if item["id"] == str(first.id))
    assert updated_student["group"] == "Новая группа"


async def test_user_context_query_count_is_constant_for_ticket_page(db_session):
    student = await seed_linked_student(db_session)
    cases = [
        SimpleNamespace(id=i, max_user_id=53364725, tenant_slug="test-city") for i in range(30)
    ]
    queries = []

    def capture(*args):
        queries.append(args[2])

    engine = db_session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        await ticket_user_contexts(db_session, cases[:1])
        single = len(queries)
        queries.clear()
        contexts = await ticket_user_contexts(db_session, cases)
        assert len(queries) == single
        assert len(contexts) == 30
        assert all(item["students"][0]["id"] == str(student.id) for item in contexts.values())
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_enriched_ticket_context_is_owner_only_and_role_claim_is_not_identity(support_client):
    client, _ = support_client
    response = client.post("/api/v1/support/tickets", headers=auth(), json=ticket(role="staff"))
    assert response.status_code == 201
    assert client.get("/api/v1/support/tickets", headers=auth()).status_code == 403
    item = client.get("/api/v1/support/tickets", headers=auth(4242)).json()["items"][0]
    assert item["role"] == "staff"
    assert item["user_context"]["account"] is None
    assert item["user_context"]["staff"] == []
    assert item["user_context"]["students"] == []
