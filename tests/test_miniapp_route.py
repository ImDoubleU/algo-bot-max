import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.db.session import get_db_session
from app.main import create_app
from app.models.base import Base


def test_miniapp_route_serves_html() -> None:
    client = TestClient(create_app())

    response = client.get("/miniapp")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Алгоритмика" in response.text
    assert "Расписание" not in response.text


def test_teaching_api_is_not_exposed() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/teaching/workspace")

    assert response.status_code == 404


def test_miniapp_static_serves_assets() -> None:
    client = TestClient(create_app())

    response = client.get("/miniapp/static/app.js")

    assert response.status_code == 200
    assert "state" in response.text


def test_ready_route_returns_safe_config_report() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def init_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init_db())
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def override_db_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    response = client.get("/api/v1/ready")

    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "max_bot_token" in payload
    assert "errors" in payload
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["app_data"]["status"] == "warning"
    assert "seed_command" in payload["checks"]["app_data"]
    asyncio.run(engine.dispose())
