import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.base import Base
from app.models.student import Contact, ContactStudentLink, Student, Wallet
from app.models.tenant import City, Partner, Tenant, Venue
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import (
    CrmSyncDefaults,
    make_generated_access_code,
    slugify,
    split_contact_ids,
    upsert_crm_student_rows,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def row(**overrides):
    data = {
        "row_number": 2,
        "deal_id": "1357",
        "uuid": "uuid-1",
        "lms_student_id": "ST-001",
        "first_name": "\u0410\u043b\u0438\u0441\u0430",
        "last_name": "\u0412\u0430\u0441\u0438\u043b\u044c\u0435\u0432\u0430",
        "group_name": "\u0421\u043e\u044e\u0437\u043d\u044b\u0439 45, \u0432\u0441 10:00",
        "course_name": "Python Start",
        "venue_name": "\u0421\u043e\u044e\u0437\u043d\u044b\u0439 45",
        "teacher_name": "\u041e\u043b\u0435\u0439\u043d\u0438\u043a \u0414",
        "city": "\u041d\u0438\u0436\u043d\u0438\u0439 \u041d\u043e\u0432\u0433\u043e\u0440\u043e\u0434",  # noqa: E501
        "status_name": "\u0410\u043a\u0442\u0438\u0432\u0435\u043d",
        "contact_ids": "681",
        "contact_names": "\u041c\u0430\u043c\u0430 \u0410\u043b\u0438\u0441\u044b",
    }
    data.update(overrides)
    return CrmStudentRow(**data)


def test_slugify_transliterates_russian_text() -> None:
    assert (
        slugify(
            "\u041d\u0438\u0436\u043d\u0438\u0439 \u041d\u043e\u0432\u0433\u043e\u0440\u043e\u0434"
        )
        == "nizhniy-novgorod"
    )


def test_split_contact_ids() -> None:
    assert split_contact_ids("681, 682; abc") == ["681", "682", "ABC"]


def test_make_generated_access_code_is_stable() -> None:
    item = row(lms_student_id=None)

    first = make_generated_access_code(tenant_slug="nn-partner", row=item)
    second = make_generated_access_code(tenant_slug="nn-partner", row=item)

    assert first == second


async def test_upsert_crm_student_rows_creates_tenant_venue_student_contact_and_wallet(
    db_session,
) -> None:
    result = await upsert_crm_student_rows(
        db_session,
        [row()],
        defaults=CrmSyncDefaults(
            partner_slug="partner-a",
            partner_name="\u041f\u0430\u0440\u0442\u043d\u0435\u0440 A",
        ),
    )

    assert result.created_cities == 1
    assert result.created_partners == 1
    assert result.created_tenants == 1
    assert result.created_venues == 1
    assert result.created_students == 1
    assert result.created_wallets == 1
    assert result.created_contacts == 1
    assert result.created_contact_student_links == 1

    assert len((await db_session.scalars(select(City))).all()) == 1
    assert len((await db_session.scalars(select(Partner))).all()) == 1
    assert len((await db_session.scalars(select(Tenant))).all()) == 1
    assert len((await db_session.scalars(select(Venue))).all()) == 1
    assert len((await db_session.scalars(select(Student))).all()) == 1
    assert len((await db_session.scalars(select(Wallet))).all()) == 1
    assert len((await db_session.scalars(select(Contact))).all()) == 1
    assert len((await db_session.scalars(select(ContactStudentLink))).all()) == 1


async def test_upsert_crm_student_rows_links_one_contact_to_multiple_students(db_session) -> None:
    defaults = CrmSyncDefaults(
        partner_slug="partner-a",
        partner_name="\u041f\u0430\u0440\u0442\u043d\u0435\u0440 A",
    )
    await upsert_crm_student_rows(
        db_session,
        [
            row(lms_student_id="ST-001", first_name="\u0410\u043b\u0438\u0441\u0430"),
            row(lms_student_id="ST-002", first_name="\u0418\u0432\u0430\u043d"),
        ],
        defaults=defaults,
    )

    contacts = (await db_session.scalars(select(Contact))).all()
    students = (await db_session.scalars(select(Student))).all()
    links = (await db_session.scalars(select(ContactStudentLink))).all()

    assert len(contacts) == 1
    assert contacts[0].external_contact_id == "681"
    assert len(students) == 2
    assert len(links) == 2


async def test_upsert_crm_student_rows_updates_existing_student(db_session) -> None:
    defaults = CrmSyncDefaults(
        partner_slug="partner-a",
        partner_name="\u041f\u0430\u0440\u0442\u043d\u0435\u0440 A",
    )
    await upsert_crm_student_rows(db_session, [row()], defaults=defaults)

    result = await upsert_crm_student_rows(
        db_session,
        [row(group_name="\u0413\u0430\u0433\u0430\u0440\u0438\u043d\u0430 64, \u0441\u0431 18:00")],
        defaults=defaults,
    )

    students = (await db_session.scalars(select(Student))).all()
    assert result.updated_students == 1
    assert len(students) == 1
