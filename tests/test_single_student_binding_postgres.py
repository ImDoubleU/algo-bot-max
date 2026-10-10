"""Opt-in concurrency checks in an explicitly isolated PostgreSQL database."""

import asyncio
import os

import pytest
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.base import Base
from app.models.enums import StudentAccessRole, StudentAccessStatus
from app.models.student import Student, StudentAccessLink
from app.models.tenant import City, Partner, Tenant
from app.schemas.access import StudentInvitationLinkCreate
from app.services.access import AccessServiceError, create_invited_student_access_link
from app.services.student_invitations import issue_teacher_student_invitation_token


@pytest.fixture
async def postgres_bindings():
    configured = os.environ.get("BINDING_TEST_DATABASE_URL")
    if not configured:
        pytest.skip("BINDING_TEST_DATABASE_URL must name an isolated test database")
    url = make_url(configured)
    assert url.drivername == "postgresql+asyncpg"
    assert (url.database or "").startswith("algo_max_binding_test_")
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with factory() as db:
            city = City(slug="binding-test", name="Test")
            partner = Partner(slug="binding-test", name="Test")
            db.add_all([city, partner])
            await db.flush()
            tenant = Tenant(city_id=city.id, partner_id=partner.id,
                            slug="binding-test", name="Test")
            db.add(tenant)
            await db.flush()
            pupils = [Student(tenant_id=tenant.id, student_access_code=f"test-{i}",
                              first_name=f"{i}")
                      for i in range(2)]
            db.add_all(pupils)
            await db.commit()
            tokens = [issue_teacher_student_invitation_token(tenant.id, s.id) for s in pupils]
        yield factory, tokens
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.mark.parametrize("scenario", ["one_pupil", "one_account", "repeat"])
async def test_concurrent_bindings_preserve_both_uniqueness_rules(postgres_bindings, scenario):
    factory, tokens = postgres_bindings
    calls = [(41001, tokens[0]), (41002, tokens[0])]
    expected_error = "student_profile_already_bound"
    if scenario == "one_account":
        calls = [(41003, tokens[0]), (41003, tokens[1])]
        expected_error = "student_already_bound"
    elif scenario == "repeat":
        calls = [(41004, tokens[0]), (41004, tokens[0])]
    ready = asyncio.Event()

    async def bind(user_id, token):
        async with factory() as db:
            await ready.wait()
            try:
                _, _, link = await create_invited_student_access_link(db,
                    StudentInvitationLinkCreate(tenant_slug="binding-test", max_user_id=user_id,
                                                token=token))
                return {"link": link.id}
            except AccessServiceError as exc:
                return {"error": exc.code}

    tasks = [asyncio.create_task(bind(*call)) for call in calls]
    ready.set()
    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15)
    async with factory() as db:
        links = list(await db.scalars(select(StudentAccessLink).where(
            StudentAccessLink.role == StudentAccessRole.STUDENT,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )))
    assert len(links) == 1
    if scenario == "repeat":
        assert all(result == {"link": links[0].id} for result in results)
    else:
        assert sum(result == {"link": links[0].id} for result in results) == 1
        assert {"error": expected_error} in results
