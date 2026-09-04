import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.api.routes.miniapp import _product_validation_message
from app.db.session import get_db_session
from app.main import create_app
from app.models.base import Base
from app.schemas.miniapp import MiniAppProductUpsert


def test_miniapp_route_serves_html() -> None:
    client = TestClient(create_app())

    response = client.get("/miniapp")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["pragma"] == "no-cache"
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


def test_product_import_template_is_publicly_downloadable() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/miniapp/products/import-template")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert "algo-max-products-template.xlsx" in response.headers["content-disposition"]
    assert response.content.startswith(b"PK")


def test_product_validation_names_the_invalid_field() -> None:
    with pytest.raises(ValidationError) as error:
        MiniAppProductUpsert(
            max_user_id=1,
            sku="X" * 121,
            name="Товар",
            price_astrocoins=100,
        )

    assert _product_validation_message(error.value) == "Проверьте поле «Артикул»"


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
