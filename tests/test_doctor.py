import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.cli.doctor import (
    check_app_data_in_session,
    check_miniapp_assets,
    check_redis,
    checks_failed,
    render_text,
    run_checks,
)
from app.core.config import Settings
from app.models.base import Base


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


def make_static_root(tmp_path):
    miniapp = tmp_path / "miniapp"
    miniapp.mkdir()
    for filename in ("index.html", "app.js", "styles.css"):
        (miniapp / filename).write_text("", encoding="utf-8")
    return tmp_path


def test_check_miniapp_assets_reports_missing_files(tmp_path) -> None:
    result = check_miniapp_assets(tmp_path)

    assert result.status == "error"
    assert "missing" in result.details


def test_check_redis_is_ok_when_rate_limit_uses_memory() -> None:
    settings = Settings(
        MAX_BOT_TOKEN="real-token",
        DEFAULT_TENANT_SLUG="tenant-a",
        RATE_LIMIT_BACKEND="memory",
    )

    result = check_redis(settings)

    assert result.status == "ok"


async def test_doctor_run_checks_can_skip_database(tmp_path) -> None:
    settings = Settings(
        APP_SECRET_KEY="secret-value",
        MAX_BOT_TOKEN="real-token",
        DEFAULT_TENANT_SLUG="tenant-a",
        GOOGLE_SERVICE_ACCOUNT_FILE="",
        GOOGLE_SHEETS_ORDERS_SPREADSHEET_ID="",
    )

    checks = await run_checks(
        settings=settings,
        include_db=False,
        static_root=make_static_root(tmp_path),
    )

    assert checks_failed(checks) is False
    assert {check.name for check in checks} == {
        "config",
        "miniapp_assets",
        "miniapp_js",
        "google_sheets",
        "redis",
        "database",
        "app_data",
    }
    assert "Проверка базы данных пропущена" in render_text(checks)


async def test_app_data_check_warns_when_default_tenant_is_missing(db_session) -> None:
    settings = Settings(
        APP_SECRET_KEY="secret-value",
        MAX_BOT_TOKEN="real-token",
        DEFAULT_TENANT_SLUG="tenant-a",
    )

    result = await check_app_data_in_session(db_session, settings)

    assert result.status == "warning"
    assert result.name == "app_data"
    assert result.details["tenant_slug"] == "tenant-a"
    assert "seed_store" in result.details["seed_command"]
