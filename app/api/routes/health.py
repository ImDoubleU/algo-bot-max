from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.readiness import check_app_data_session, check_database_session

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/health")
async def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.app_env,
        "service": settings.app_name,
    }


@router.get("/ready")
async def readiness(db: DbSession) -> dict[str, object]:
    settings = get_settings()
    report = settings.safe_config_report()
    database = await check_database_session(db)
    checks = {"database": database}
    if database["status"] == "ok":
        checks["app_data"] = await check_app_data_session(db, settings)
    else:
        checks["app_data"] = {
            "status": "skipped",
            "message": "Проверка данных приложения пропущена из-за ошибки БД",
        }
    report["checks"] = checks
    if database["status"] == "error":
        report["status"] = "degraded"
        report["errors"].append("database is not ready")
    elif any(check["status"] == "warning" for check in checks.values()):
        report["status"] = "warning" if report["status"] == "ok" else report["status"]
    return report
