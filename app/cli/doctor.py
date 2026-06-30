from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

STATIC_ROOT = Path(__file__).resolve().parents[1] / "web" / "static"
PLACEHOLDER_VALUES = {
    "",
    "...",
    "replace_me",
    "your_token_here",
    "replace_with_local_xlsx_path",
    "replace_with_local_json_path",
}


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def ok(name: str, message: str, **details: Any) -> DoctorCheck:
    return DoctorCheck(name=name, status="ok", message=message, details=details)


def warning(name: str, message: str, **details: Any) -> DoctorCheck:
    return DoctorCheck(name=name, status="warning", message=message, details=details)


def error(name: str, message: str, **details: Any) -> DoctorCheck:
    return DoctorCheck(name=name, status="error", message=message, details=details)


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in PLACEHOLDER_VALUES


def load_settings() -> tuple[Any | None, DoctorCheck | None]:
    try:
        from app.core.config import get_settings
    except ImportError as exc:
        return None, error(
            "python_dependencies",
            "Не установлены Python-зависимости проекта",
            missing_package=getattr(exc, "name", "") or str(exc),
            install_command=(
                "max_bot_venv\\Scripts\\python.exe -m pip install -r requirements.txt"
            ),
        )

    try:
        return get_settings(), None
    except Exception as exc:  # noqa: BLE001
        return None, error("config", "Не удалось загрузить конфигурацию", reason=str(exc))


def skipped_without_settings(name: str, subject: str) -> DoctorCheck:
    return warning(
        name,
        f"{subject} пропущена: сначала установите зависимости и загрузите конфигурацию",
    )


def database_connection_details(database_url: str) -> dict[str, str]:
    try:
        parsed = urlsplit(database_url)
    except ValueError:
        return {}

    details: dict[str, str] = {}
    if parsed.hostname:
        details["host"] = parsed.hostname
    if parsed.port:
        details["port"] = str(parsed.port)
    database = parsed.path.lstrip("/")
    if database:
        details["database"] = database
    return details


def check_config(settings: Any) -> DoctorCheck:
    report = settings.safe_config_report()
    if report["errors"]:
        return error("config", "Конфигурация содержит ошибки", errors=report["errors"])
    if report["warnings"]:
        return warning(
            "config",
            "Конфигурация рабочая, но есть предупреждения",
            warnings=report["warnings"],
        )
    return ok("config", "Конфигурация выглядит рабочей")


def check_miniapp_assets(static_root: Path = STATIC_ROOT) -> DoctorCheck:
    required = [
        static_root / "miniapp" / "index.html",
        static_root / "miniapp" / "app.js",
        static_root / "miniapp" / "styles.css",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        return error("miniapp_assets", "Не найдены статические файлы miniapp", missing=missing)
    return ok("miniapp_assets", "Статические файлы miniapp найдены")


def check_miniapp_js_syntax(static_root: Path = STATIC_ROOT) -> DoctorCheck:
    app_js = static_root / "miniapp" / "app.js"
    if not app_js.exists():
        return error("miniapp_js", "Файл miniapp app.js не найден", path=str(app_js))

    node = shutil.which("node")
    if node is None:
        return warning(
            "miniapp_js",
            "Node.js не найден: проверка синтаксиса miniapp пропущена",
            command=f"node --check {app_js}",
        )

    try:
        result = subprocess.run(
            [node, "--check", str(app_js)],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return error(
            "miniapp_js",
            "Не удалось запустить проверку синтаксиса miniapp",
            reason=str(exc),
        )

    if result.returncode != 0:
        return error(
            "miniapp_js",
            "JavaScript miniapp содержит синтаксическую ошибку",
            stderr=result.stderr.strip(),
        )

    return ok("miniapp_js", "JavaScript miniapp прошел node --check")


def check_google_sheets_config(settings: Any | None) -> DoctorCheck:
    if settings is None:
        return skipped_without_settings("google_sheets", "Проверка Google Sheets")

    if is_placeholder(settings.google_service_account_file) or is_placeholder(
        settings.google_sheets_orders_spreadsheet_id
    ):
        return ok("google_sheets", "Google Sheets экспорт выключен")

    service_account_file = Path(str(settings.google_service_account_file))
    if not service_account_file.exists():
        return error(
            "google_sheets",
            "Файл service account для Google Sheets не найден",
            path=str(service_account_file),
        )
    return ok("google_sheets", "Google Sheets экспорт настроен", path=str(service_account_file))


def check_redis(settings: Any | None) -> DoctorCheck:
    if settings is None:
        return skipped_without_settings("redis", "Проверка Redis")

    if settings.rate_limit_backend.lower() != "redis":
        return ok("redis", "Redis rate limit выключен")

    if is_placeholder(settings.redis_url):
        return error("redis", "RATE_LIMIT_BACKEND=redis требует REDIS_URL")

    try:
        import redis
    except ImportError as exc:
        return error("redis", "Python-пакет redis не установлен", reason=str(exc))

    try:
        client = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True,
        )
        client.ping()
    except Exception as exc:  # noqa: BLE001
        return error("redis", "Redis недоступен для rate limit", reason=str(exc))

    return ok("redis", "Redis отвечает на PING")


async def check_database(settings: Any | None) -> DoctorCheck:
    if settings is None:
        return error(
            "database",
            "Проверка базы данных невозможна без загруженной конфигурации",
        )

    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError as exc:
        return error("database", "Python-пакет SQLAlchemy не установлен", reason=str(exc))

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        return error(
            "database",
            "Не удалось подключиться к базе данных",
            reason=str(exc),
            **database_connection_details(settings.database_url),
            next_steps=[
                "docker compose up -d postgres",
                "или Copy-Item .env.sqlite.example .env для локального SQLite smoke",
                "max_bot_venv\\Scripts\\python.exe -m alembic upgrade head",
                (
                    "max_bot_venv\\Scripts\\python.exe -m app.cli.seed_store "
                    "--max-user-id <MAX_USER_ID>"
                ),
            ],
        )
    finally:
        await engine.dispose()
    return ok("database", "База данных отвечает на SELECT 1")


async def check_app_data_in_session(db: Any, settings: Any) -> DoctorCheck:
    from sqlalchemy import func, select

    import app.db.base  # noqa: F401
    from app.models.store import Product, Warehouse
    from app.models.student import Contact, Student
    from app.models.tenant import Tenant

    tenant_slug = settings.default_tenant_slug.strip().lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    seed_command = (
        "python -m app.cli.seed_store --max-user-id <MAX_USER_ID>"
    )
    if tenant is None:
        return warning(
            "app_data",
            "Default tenant не найден: miniapp будет пустой до импорта CRM или seed_store",
            tenant_slug=tenant_slug,
            seed_command=seed_command,
        )

    product_count = await db.scalar(
        select(func.count()).select_from(Product).where(Product.tenant_id == tenant.id)
    )
    warehouse_count = await db.scalar(
        select(func.count()).select_from(Warehouse).where(Warehouse.tenant_id == tenant.id)
    )
    student_count = await db.scalar(
        select(func.count()).select_from(Student).where(Student.tenant_id == tenant.id)
    )
    contact_count = await db.scalar(
        select(func.count()).select_from(Contact).where(Contact.tenant_id == tenant.id)
    )
    details = {
        "tenant_slug": tenant.slug,
        "products": product_count or 0,
        "warehouses": warehouse_count or 0,
        "students": student_count or 0,
        "contacts": contact_count or 0,
    }
    missing = [
        name
        for name, count in details.items()
        if name != "tenant_slug" and isinstance(count, int) and count == 0
    ]
    if missing:
        return warning(
            "app_data",
            "Default tenant найден, но данных недостаточно для рабочего miniapp",
            **details,
            missing=missing,
            seed_command=seed_command,
        )

    return ok("app_data", "Default tenant содержит базовые данные для miniapp", **details)


async def check_app_data(settings: Any | None) -> DoctorCheck:
    if settings is None:
        return skipped_without_settings("app_data", "Проверка данных приложения")

    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    except ImportError as exc:
        return error("app_data", "Python-пакет SQLAlchemy не установлен", reason=str(exc))

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
            return await check_app_data_in_session(db, settings)
    except Exception as exc:  # noqa: BLE001
        return error(
            "app_data",
            "Не удалось проверить данные приложения",
            reason=str(exc),
        )
    finally:
        await engine.dispose()


async def run_checks(
    *,
    settings: Any | None = None,
    include_db: bool = True,
    static_root: Path = STATIC_ROOT,
) -> list[DoctorCheck]:
    current_settings = settings
    settings_error: DoctorCheck | None = None
    if current_settings is None:
        current_settings, settings_error = load_settings()

    checks = [
        settings_error or check_config(current_settings),
        check_miniapp_assets(static_root),
        check_miniapp_js_syntax(static_root),
        check_google_sheets_config(current_settings),
        check_redis(current_settings),
    ]
    if include_db:
        database_check = await check_database(current_settings)
        checks.append(database_check)
        if database_check.status == "ok":
            checks.append(await check_app_data(current_settings))
    else:
        checks.append(ok("database", "Проверка базы данных пропущена"))
        checks.append(ok("app_data", "Проверка данных приложения пропущена"))
    return checks


def checks_failed(checks: list[DoctorCheck]) -> bool:
    return any(check.status == "error" for check in checks)


def render_text(checks: list[DoctorCheck]) -> str:
    lines: list[str] = []
    for check in checks:
        prefix = {"ok": "[ok]", "warning": "[warn]", "error": "[error]"}[check.status]
        lines.append(f"{prefix} {check.name}: {check.message}")
        for key, value in check.details.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Локальная диагностика запуска Algo MAX Bot")
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Не проверять подключение к базе данных",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести результат в JSON",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    checks = asyncio.run(run_checks(include_db=not args.skip_db))
    if args.json:
        print(json.dumps([asdict(check) for check in checks], ensure_ascii=False, indent=2))
    else:
        print(render_text(checks))
    return 1 if checks_failed(checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
