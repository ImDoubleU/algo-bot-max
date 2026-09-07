import asyncio
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.db.session import get_db_session
from app.main import create_app
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
)
from app.models.student import Student, StudentAccessLink, Wallet
from app.models.tenant import City, Partner, Tenant


async def _seed_bank_api_data(session_factory) -> tuple[str, str]:
    async with session_factory() as session:
        city = City(slug="api-city", name="API City")
        partner = Partner(slug="api-partner", name="API Partner")
        session.add_all([city, partner])
        await session.flush()
        tenant = Tenant(
            city_id=city.id,
            partner_id=partner.id,
            slug="api-city-partner",
            name="API City / Partner",
            bank_annual_rate_bps=3650,
        )
        student = Student(
            tenant=tenant,
            student_access_code="BANK-API-STUDENT",
            first_name="Alex",
            last_name="Student",
        )
        student_account = MaxAccount(max_user_id=91001, display_name="Alex")
        parent_account = MaxAccount(max_user_id=91002, display_name="Parent")
        admin_account = MaxAccount(max_user_id=91003, display_name="Admin")
        session.add_all([tenant, student, student_account, parent_account, admin_account])
        await session.flush()
        session.add_all(
            [
                Wallet(tenant_id=tenant.id, student_id=student.id, balance=1000),
                StudentAccessLink(
                    tenant_id=tenant.id,
                    account_id=student_account.id,
                    student_id=student.id,
                    role=StudentAccessRole.STUDENT,
                    status=StudentAccessStatus.ACTIVE,
                    source=StudentAccessSource.ADMIN,
                ),
                StudentAccessLink(
                    tenant_id=tenant.id,
                    account_id=parent_account.id,
                    student_id=student.id,
                    role=StudentAccessRole.PARENT,
                    status=StudentAccessStatus.ACTIVE,
                    source=StudentAccessSource.ADMIN,
                ),
                StaffRoleAssignment(
                    tenant_id=tenant.id,
                    account_id=admin_account.id,
                    role=StaffRole.ADMIN,
                    status=AssignmentStatus.ACTIVE,
                ),
            ]
        )
        await session.commit()
        return tenant.slug, str(student.id)


def test_bank_http_contract_and_role_permissions(tmp_path) -> None:
    database_path = tmp_path / "bank-api.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def initialize() -> tuple[str, str]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        return await _seed_bank_api_data(session_factory)

    tenant_slug, student_id = asyncio.run(initialize())
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    open_payload = {
        "max_user_id": 91001,
        "tenant_slug": tenant_slug,
        "student_id": student_id,
        "amount": 400,
        "maturity_on": (date.today() + timedelta(days=30)).isoformat(),
        "request_key": "api-open-request-01",
    }

    try:
        preview = client.post(
            "/api/v1/miniapp/bank/deposits/preview",
            json={key: value for key, value in open_payload.items() if key != "request_key"},
        )
        assert preview.status_code == 200
        assert preview.json()["amount"] == 400
        assert preview.json()["annual_rate_bps"] == 3650
        assert preview.json()["projected_interest"] > 0
        assert preview.json()["projected_balance"] == 400 + preview.json()["projected_interest"]

        opened = client.post("/api/v1/miniapp/bank/deposits", json=open_payload)
        assert opened.status_code == 201
        opened_data = opened.json()
        assert opened_data["personal_balance"] == 600
        assert opened_data["bank_balance"] == 400
        assert opened_data["total_balance"] == 1000

        repeated = client.post("/api/v1/miniapp/bank/deposits", json=open_payload)
        assert repeated.status_code == 201
        assert repeated.json()["personal_balance"] == 600

        parent_summary = client.get(
            "/api/v1/miniapp/bank",
            params={
                "max_user_id": 91002,
                "tenant_slug": tenant_slug,
                "student_id": student_id,
            },
        )
        assert parent_summary.status_code == 200
        assert parent_summary.json()["can_open"] is False
        assert parent_summary.json()["can_top_up"] is False
        assert parent_summary.json()["can_close_early"] is False

        parent_top_up = client.post(
            f"/api/v1/miniapp/bank/deposits/{opened_data['deposit']['id']}/top-ups",
            json={
                "max_user_id": 91002,
                "tenant_slug": tenant_slug,
                "amount": 10,
                "request_key": "api-parent-topup-1",
            },
        )
        assert parent_top_up.status_code == 403

        student_top_up = client.post(
            f"/api/v1/miniapp/bank/deposits/{opened_data['deposit']['id']}/top-ups",
            json={
                "max_user_id": 91001,
                "tenant_slug": tenant_slug,
                "amount": 50,
                "request_key": "api-student-topup-1",
            },
        )
        assert student_top_up.status_code == 200
        student_top_up_data = student_top_up.json()
        assert student_top_up_data["bank_balance"] == 450
        assert student_top_up_data["history"][0]["operation_type"] == "topped_up"
        assert student_top_up_data["history"][0]["title"] == "Пополнение вклада"
        assert student_top_up_data["history"][0]["amount"] == 50

        settings = client.put(
            "/api/v1/miniapp/bank/settings",
            json={
                "max_user_id": 91003,
                "tenant_slug": tenant_slug,
                "annual_rate_bps": 7300,
            },
        )
        assert settings.status_code == 200
        assert settings.json()["annual_rate_bps"] == 7300

        report = client.get(
            "/api/v1/miniapp/bank/report",
            params={"max_user_id": 91003, "tenant_slug": tenant_slug},
        )
        assert report.status_code == 200
        assert report.json()["active_deposits"] == 1
        assert report.json()["entries"][0]["bank_balance"] == 450
    finally:
        asyncio.run(engine.dispose())
