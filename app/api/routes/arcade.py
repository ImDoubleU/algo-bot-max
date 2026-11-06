"""Private staff pilot. Verified MAX identity owns an isolated test-game account."""

import asyncio
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.api.dependencies import get_miniapp_identity
from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.enums import AssignmentStatus
from app.models.tenant import Tenant


@lru_cache(maxsize=1)
def pilot_store():
    from app.services.arcade import ArcadeStore

    settings = get_settings()
    return ArcadeStore(Path(settings.arcade_pilot_db_path).expanduser().resolve())


async def authenticate(request: Request):
    settings = get_settings()
    if not settings.arcade_pilot_enabled:
        raise HTTPException(404, "Раздел пока недоступен")
    identity = await get_miniapp_identity(
        token=request.headers.get("X-Miniapp-Token"),
        max_webapp_data=request.headers.get("X-Max-WebApp-Data"),
        request=request,
    )
    if identity is None:
        raise HTTPException(401, "Откройте приложение из MAX")
    if identity.max_user_id not in settings.arcade_pilot_max_ids:
        raise HTTPException(403, "Игры пока доступны только участникам тестирования")
    async with AsyncSessionLocal() as db:
        query = (
            select(MaxAccount)
            .join(StaffRoleAssignment, StaffRoleAssignment.account_id == MaxAccount.id)
            .join(Tenant, Tenant.id == StaffRoleAssignment.tenant_id)
            .where(
                MaxAccount.max_user_id == identity.max_user_id,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
        if identity.tenant_slug:
            query = query.where(Tenant.slug == identity.tenant_slug)
        account = (await db.execute(query)).scalars().first()
        if account is None:
            raise HTTPException(403, "Доступ сотрудника не подтверждён")
        name = " ".join(filter(None, [account.staff_first_name, account.staff_last_name]))
        player = {
            "id": f"pilot:{identity.max_user_id}",
            "name": name or account.display_name or "Участник тестирования",
            "group": "Тестирование игр",
        }
    # Do not consult child/parent links or change school wallets in this pilot.
    await asyncio.to_thread(pilot_store().register, [player])
    return dict(player=player["id"])


def make_pilot_router():
    from app.api.routes.arcade_preview import make_router

    return make_router(pilot_store(), authenticate)
