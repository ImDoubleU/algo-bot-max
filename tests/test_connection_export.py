from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import openpyxl
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from test_contact_access_service import db_session as _db_session
from test_contact_access_service import row

from app.api.dependencies import get_miniapp_identity
from app.api.routes.miniapp import router
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.account import MaxAccount, StaffRoleAssignment, StaffVenueScope
from app.models.enums import AssignmentStatus, StaffRole, StudentAccessRole, StudentAccessStatus
from app.models.student import Student, StudentAccessLink
from app.schemas.access import AccessLinkCreate
from app.schemas.miniapp import (
    MiniAppConnectionExportStudentRead,
    MiniAppConnectionsExportRequest,
)
from app.services.access import create_contact_access_links
from app.services.connection_export import build_connection_workbook, filter_connection_students
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows
from app.services.miniapp import MiniAppStoreError, list_miniapp_connection_export_students

db_session = _db_session
SLUG = "nizhniy-novgorod-partner-a"


def example_rows():
    return [MiniAppConnectionExportStudentRead(
        student_id=uuid4(), lms_student_id=f"0000{index + 1}", display_name=name,
        group_name=group, venue_name=venue, teacher_name=teacher, status=status,
        student_connected=child, parent_connected=parent,
    ) for index, (name, group, venue, teacher, child, parent, status) in enumerate([
        ("Васильева Алиса", "Python *", "Союзный 45", "Олейник Д", True, True, "active"),
        ("Петров Иван", "Python *", "Союзный 45", "Олейник Д", False, True, "active"),
        ("Иванова Мария", "Scratch", "Гагарина 64", "Петрова Анна", False, False, "active"),
        ('=HYPERLINK("https://invalid")', "Python ?", "Союзный 45", "Олейник Д",
         True, False, "departed"),
    ])]


async def seed_report(db):
    defaults = CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A")
    first = row(lms_student_id="00123", first_name="Алиса")
    second = replace(row(lms_student_id="00456", first_name="Иван"),
        group_name="Scratch", teacher_name="Петрова Анна", venue_name="Гагарина 64")
    third = replace(row(lms_student_id="00789", first_name="Мария"), contact_ids="682")
    await upsert_crm_student_rows(db, [first, second, third], defaults=defaults)
    links = await create_contact_access_links(db, AccessLinkCreate(
        tenant_slug=SLUG, max_user_id=70001, role=StudentAccessRole.PARENT, contact_id="681"))
    await create_contact_access_links(db, AccessLinkCreate(
        tenant_slug=SLUG, max_user_id=70002, role=StudentAccessRole.PARENT, contact_id="681"))
    pupil = await db.scalar(select(Student).where(Student.lms_student_id == "00123"))
    actor = MaxAccount(max_user_id=70003)
    child = MaxAccount(max_user_id=70004)
    db.add_all([actor, child])
    await db.flush()
    assignment = StaffRoleAssignment(tenant_id=pupil.tenant_id, account_id=actor.id,
        role=StaffRole.ADMIN, status=AssignmentStatus.ACTIVE)
    db.add_all([assignment, StudentAccessLink(tenant_id=pupil.tenant_id, student_id=pupil.id,
        account_id=child.id, role=StudentAccessRole.STUDENT, status=StudentAccessStatus.ACTIVE,
        source=links[0].source)])
    await db.commit()
    return pupil, assignment


async def test_report_includes_unconnected_students_without_duplicate_parents(db_session):
    await seed_report(db_session)
    report = await list_miniapp_connection_export_students(
        db_session, max_user_id=70003, tenant_slug=SLUG)
    assert len(report.students) == 3
    assert sum(s.parent_connected for s in report.students) == 2
    assert sum(s.student_connected for s in report.students) == 1
    assert {s.lms_student_id for s in report.students} == {"00123", "00456", "00789"}
    assert not next(s for s in report.students if s.lms_student_id == "00789").parent_connected


async def test_director_export_obeys_venue_scope_even_with_teacher_role(db_session):
    pupil, assignment = await seed_report(db_session)
    assignment.role = StaffRole.PARTNER_DIRECTOR
    db_session.add(StaffVenueScope(assignment_id=assignment.id, venue_id=pupil.venue_id))
    db_session.add(StaffRoleAssignment(tenant_id=pupil.tenant_id, account_id=assignment.account_id,
        role=StaffRole.TEACHER, status=AssignmentStatus.ACTIVE))
    await db_session.commit()
    report = await list_miniapp_connection_export_students(
        db_session, max_user_id=70003, tenant_slug=SLUG)
    assert {s.lms_student_id for s in report.students} == {"00123", "00789"}
    assignment.role = StaffRole.CURATOR
    await db_session.commit()
    with pytest.raises(MiniAppStoreError) as exc:
        await list_miniapp_connection_export_students(
            db_session, max_user_id=70003, tenant_slug=SLUG)
    assert exc.value.status_code == 403


async def test_export_api_validates_identity_and_returns_scoped_xlsx(db_session):
    await seed_report(db_session)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/miniapp")
    identity = {"user": 70003}

    async def db_override():
        yield db_session

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[get_miniapp_identity] = lambda: MiniAppIdentity(
        max_user_id=identity["user"], tenant_slug=SLUG, expires_at=9999999999)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        params = {"max_user_id": 70003, "tenant_slug": SLUG}
        options = await client.get("/api/v1/miniapp/access-links/export-options", params=params)
        assert options.status_code == 200 and len(options.json()["students"]) == 3
        assert options.headers["cache-control"] == "no-store"
        payload = {**params, "teachers": ["Олейник Д"]}
        exported = await client.post("/api/v1/miniapp/access-links/export", json=payload)
        assert exported.status_code == 200
        assert exported.headers["cache-control"] == "no-store"
        assert "attachment" in exported.headers["content-disposition"]
        book = openpyxl.load_workbook(BytesIO(exported.content), data_only=True)
        assert book["Сводка"]["B7"].value == 2
        assert book["Ученики"].max_row == 8
        denied = await client.post("/api/v1/miniapp/access-links/export",
                                  json={**payload, "max_user_id": 70001})
        assert denied.status_code == 403
        identity["user"] = 70001
        denied = await client.get("/api/v1/miniapp/access-links/export-options",
                                  params={**params, "max_user_id": 70001})
        assert denied.status_code == 403


def test_export_filters_use_intersection_and_exclude_inactive_by_default():
    students = example_rows()
    payload = MiniAppConnectionsExportRequest(max_user_id=70003, teachers=["Олейник Д"],
        venues=["Союзный 45"], groups=["Python *", "Python ?"])
    assert len(filter_connection_students(students, payload)) == 2
    payload.include_inactive = True
    assert len(filter_connection_students(students, payload)) == 3
    payload.teachers = []
    with pytest.raises(MiniAppStoreError, match="нет учеников"):
        filter_connection_students(students, payload)
    payload.teachers = ["Чужой преподаватель"]
    with pytest.raises(MiniAppStoreError, match="фильтров изменился"):
        filter_connection_students(students, payload)


def test_workbook_has_native_checkboxes_formulas_text_ids_and_no_formula_injection():
    content = build_connection_workbook(example_rows(), tenant_name="Тестовый город",
        include_inactive=True, generated_at=datetime(2026, 10, 24, 9, tzinfo=UTC))
    book = openpyxl.load_workbook(BytesIO(content), data_only=True)
    assert book.sheetnames == ["Сводка", "Ученики"]
    detail, summary = book["Ученики"], book["Сводка"]
    assert detail["B7"].value == "00001" and detail["B7"].data_type == "s"
    assert detail["D7"].value is True and detail["D8"].value is False
    assert detail["C10"].data_type == "s" and detail["C10"].value.startswith("=HYPERLINK")
    assert [summary[f"{col}7"].value for col in "BCDE"] == [4, 2, 2, .5]
    assert [summary[f"{col}8"].value for col in "BCDE"] == [4, 2, 2, .5]
    assert summary["B10"].value == 1 and summary["B11"].value == 1
    assert detail["D6"].value == "Ребёнок подключён"
    assert summary["C6"].value == "Подключены"
    assert summary["D6"].value == "Не подключены"
    assert summary["E14"].value == "Дети" and summary["G14"].value == "Родители"
    assert summary["C7"].font.sz == 18
    assert detail["A5"].value is None and summary["A5"].value is None
    assert detail.freeze_panes == "D7"
    formulas = openpyxl.load_workbook(BytesIO(content), data_only=False)
    assert formulas["Сводка"]["C7"].value.startswith("=SUMPRODUCT(")
    assert formulas["Сводка"]["D16"].value.startswith("=SUMPRODUCT(")
    with ZipFile(BytesIO(content)) as archive:
        assert any("featurePropertyBag" in name for name in archive.namelist())
        assert b"Checkbox" in b"".join(archive.read(name) for name in archive.namelist()
                                      if "featurePropertyBag" in name)
