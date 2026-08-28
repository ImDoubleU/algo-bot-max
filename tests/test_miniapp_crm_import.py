from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import AssignmentStatus, StaffRole, StudentStatus
from app.models.student import Student
from app.models.tenant import City, Partner, Tenant
from app.services.miniapp import import_miniapp_crm_students


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def _crm_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Сделки"
    sheet.append(
        [
            "ID сделки",
            "ID ученика",
            "Имя ребенка из LMS",
            "Фамилия ребенка из LMS",
            "Название группы LMS",
            "Город",
        ]
    )
    sheet.append(
        [
            101,
            "NN-1",
            "Анна",
            "Иванова",
            "Группа НН",
            "Н.Новгород, Н.Новгород",
        ]
    )
    sheet.append([102, "BOR-1", "Илья", "Петров", "Группа Бор", "Бор"])
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


async def test_miniapp_crm_import_routes_rows_between_accessible_cities(db_session) -> None:
    partner = Partner(slug="algo-max", name="Algo MAX")
    nizhny = City(slug="nizhniy-novgorod", name="Нижний Новгород")
    bor = City(slug="bor", name="Бор")
    db_session.add_all([partner, nizhny, bor])
    await db_session.flush()

    nizhny_tenant = Tenant(
        city_id=nizhny.id,
        partner_id=partner.id,
        slug="n-novgorod",
        name="Нижний Новгород",
    )
    bor_tenant = Tenant(
        city_id=bor.id,
        partner_id=partner.id,
        slug="bor",
        name="Бор",
    )
    account = MaxAccount(max_user_id=53364725, display_name="Директор")
    db_session.add_all([nizhny_tenant, bor_tenant, account])
    await db_session.flush()
    db_session.add_all(
        [
            StaffRoleAssignment(
                tenant_id=tenant.id,
                account_id=account.id,
                role=StaffRole.ADMIN,
                status=AssignmentStatus.ACTIVE,
            )
            for tenant in (nizhny_tenant, bor_tenant)
        ]
    )
    await db_session.commit()

    preview = await import_miniapp_crm_students(
        db_session,
        max_user_id=account.max_user_id,
        tenant_slug=nizhny_tenant.slug,
        filename="active.xlsx",
        content=_crm_workbook(),
        sheet_name="Шаблон",
        dry_run=True,
        student_status=StudentStatus.ACTIVE,
    )

    assert preview.distinct_cities == 2
    assert {item.city_name: item.rows for item in preview.city_distribution} == {
        "Бор": 1,
        "Нижний Новгород": 1,
    }

    result = await import_miniapp_crm_students(
        db_session,
        max_user_id=account.max_user_id,
        tenant_slug=nizhny_tenant.slug,
        filename="active.xlsx",
        content=_crm_workbook(),
        sheet_name="Шаблон",
        dry_run=False,
        student_status=StudentStatus.ACTIVE,
    )

    students = list((await db_session.scalars(select(Student))).all())
    tenant_by_id = {nizhny_tenant.id: "Нижний Новгород", bor_tenant.id: "Бор"}
    assert result.created_students == 2
    assert {tenant_by_id[student.tenant_id] for student in students} == {
        "Бор",
        "Нижний Новгород",
    }
