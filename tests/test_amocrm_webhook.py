import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.base import Base
from app.models.enums import StudentStatus
from app.models.student import Student, StudentHistoryEvent, Wallet
from app.services.amocrm_webhook import (
    extract_amocrm_lead_ids,
    extract_amocrm_student_rows,
    sync_students_from_amocrm,
    update_student_status_from_amocrm,
)
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def test_extract_amocrm_status_lead_ids_from_form_payload() -> None:
    payload = {
        "leads[status][0][id]": "25399013",
        "leads[status][0][status_id]": "142",
        "leads[status][1][id]": "25399014",
    }

    assert extract_amocrm_lead_ids(payload) == ["25399013", "25399014"]


def test_extract_amocrm_lead_ids_from_json_payload() -> None:
    payload = {"leads": {"status": {"0": {"id": "9001"}}}}

    assert extract_amocrm_lead_ids(payload) == ["9001"]


def complete_student_payload(*, lead_id: str = "9100") -> dict[str, str]:
    fields = (
        ("ID ученика", "LMS-9100"),
        ("Фамилия ребенка", "Смирнова"),
        ("Имя ребенка", "Мария"),
        ("Группа", "Python Start"),
        ("Курс", "Python Start"),
        ("Площадка", "Учебный центр"),
        ("Преподаватель", "Анна Петрова"),
    )
    payload = {"leads[add][0][id]": lead_id}
    for index, (name, value) in enumerate(fields):
        prefix = f"leads[add][0][custom_fields][{index}]"
        payload[f"{prefix}[name]"] = name
        payload[f"{prefix}[values][0]"] = value
    return payload


def test_extract_amocrm_student_from_form_payload() -> None:
    rows = extract_amocrm_student_rows(complete_student_payload())

    assert len(rows) == 1
    assert rows[0].deal_id == "9100"
    assert rows[0].lms_student_id == "LMS-9100"
    assert rows[0].last_name == "Смирнова"
    assert rows[0].first_name == "Мария"
    assert rows[0].group_name == "Python Start"


async def test_amocrm_webhook_updates_student_status_and_history(db_session) -> None:
    await upsert_crm_student_rows(
        db_session,
        [
            CrmStudentRow(
                row_number=2,
                deal_id="9001",
                uuid="crm-9001",
                lms_student_id="LMS-9001",
                first_name="Анна",
                last_name="Иванова",
                group_name="Python Start",
                course_name="Python Start",
                venue_name="Учебный центр",
                teacher_name="Преподаватель",
                city="Нижний Новгород",
                status_name="Активен",
                contact_ids="",
                contact_names="",
            )
        ],
        defaults=CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A"),
    )

    result = await update_student_status_from_amocrm(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_status=StudentStatus.DEPARTED,
        lead_ids=["9001", "missing"],
    )

    student = await db_session.scalar(select(Student).where(Student.crm_deal_id == "9001"))
    history = (
        await db_session.scalars(
            select(StudentHistoryEvent).where(StudentHistoryEvent.student_id == student.id)
        )
    ).all()
    assert result.matched_students == 1
    assert result.updated_students == 1
    assert result.unmatched_lead_ids == ["missing"]
    assert student.status == StudentStatus.DEPARTED
    assert student.departed_at is not None
    assert history[-1].source == "amocrm_webhook"


async def test_amocrm_webhook_creates_complete_student_once(db_session) -> None:
    await upsert_crm_student_rows(
        db_session,
        [
            CrmStudentRow(
                row_number=2,
                deal_id="seed",
                uuid=None,
                lms_student_id="SEED",
                first_name="Тест",
                last_name="Существующий",
                group_name="Seed",
                course_name="Seed",
                venue_name="Учебный центр",
                teacher_name="Преподаватель",
                city="Нижний Новгород",
                status_name="Активен",
                contact_ids=None,
                contact_names=None,
            )
        ],
        defaults=CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A"),
    )
    rows = extract_amocrm_student_rows(complete_student_payload())

    first = await sync_students_from_amocrm(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_status=StudentStatus.ACTIVE,
        rows=rows,
    )
    second = await sync_students_from_amocrm(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_status=StudentStatus.ACTIVE,
        rows=rows,
    )

    students = (
        await db_session.scalars(select(Student).where(Student.crm_deal_id == "9100"))
    ).all()
    wallet = await db_session.scalar(select(Wallet).where(Wallet.student_id == students[0].id))
    history = (
        await db_session.scalars(
            select(StudentHistoryEvent).where(StudentHistoryEvent.student_id == students[0].id)
        )
    ).all()
    assert first.created_students == 1
    assert first.incomplete_leads == {}
    assert second.created_students == 0
    assert second.existing_students == 1
    assert len(students) == 1
    assert wallet is not None
    assert history[-1].source == "amocrm_webhook"


async def test_amocrm_webhook_skips_incomplete_student(db_session) -> None:
    await upsert_crm_student_rows(
        db_session,
        [
            CrmStudentRow(
                row_number=2,
                deal_id="seed",
                uuid=None,
                lms_student_id="SEED",
                first_name="Тест",
                last_name="Существующий",
                group_name="Seed",
                course_name="Seed",
                venue_name="Учебный центр",
                teacher_name="Преподаватель",
                city="Нижний Новгород",
                status_name="Активен",
                contact_ids=None,
                contact_names=None,
            )
        ],
        defaults=CrmSyncDefaults(partner_slug="partner-a", partner_name="Партнер A"),
    )
    rows = extract_amocrm_student_rows(
        {
            "leads[add][0][id]": "9200",
            "leads[add][0][custom_fields][0][name]": "Имя ребенка",
            "leads[add][0][custom_fields][0][values][0]": "Иван",
        }
    )

    result = await sync_students_from_amocrm(
        db_session,
        tenant_slug="nizhniy-novgorod-partner-a",
        student_status=StudentStatus.ACTIVE,
        rows=rows,
    )

    assert result.created_students == 0
    assert "9200" in result.incomplete_leads
    assert "Фамилия ребенка" in result.incomplete_leads["9200"]
    assert await db_session.scalar(select(Student).where(Student.crm_deal_id == "9200")) is None
