from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.store import Product, Warehouse
from app.models.student import Contact, Student
from app.models.tenant import Tenant


async def check_database_session(db: AsyncSession) -> dict[str, Any]:
    try:
        await db.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "message": "Не удалось подключиться к базе данных",
            "reason": str(exc),
        }
    return {"status": "ok", "message": "База данных отвечает на SELECT 1"}


async def check_app_data_session(db: AsyncSession, settings: Settings) -> dict[str, Any]:
    tenant_slug = settings.default_tenant_slug.strip().lower()
    local_environment = settings.app_env.strip().lower() in {
        "local",
        "dev",
        "development",
        "test",
    }
    guidance_key = "seed_command" if local_environment else "next_step"
    next_step = (
        "python -m app.cli.seed_store --max-user-id <MAX_USER_ID>"
        if local_environment
        else (
            "Import students into the selected tenant, then create a warehouse "
            "and import products in miniapp"
        )
    )
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is None:
        return {
            "status": "warning",
            "message": "Default tenant не найден",
            "tenant_slug": tenant_slug,
            guidance_key: next_step,
        }

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
    details: dict[str, Any] = {
        "status": "ok",
        "message": "Default tenant содержит базовые данные для miniapp",
        "tenant_slug": tenant.slug,
        "products": product_count or 0,
        "warehouses": warehouse_count or 0,
        "students": student_count or 0,
        "contacts": contact_count or 0,
    }
    missing = [
        key
        for key in ("products", "warehouses", "students", "contacts")
        if details[key] == 0
    ]
    if missing:
        details["status"] = "warning"
        details["message"] = "Default tenant найден, но данных недостаточно для miniapp"
        details["missing"] = missing
        details[guidance_key] = next_step
    return details
