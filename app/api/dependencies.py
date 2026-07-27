from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings, is_local_environment
from app.core.miniapp_auth import (
    MiniAppAuthError,
    MiniAppIdentity,
    verify_miniapp_token,
)


async def get_miniapp_identity(
    token: Annotated[str | None, Header(alias="X-Miniapp-Token")] = None,
) -> MiniAppIdentity | None:
    settings = get_settings()
    if not token:
        if is_local_environment(settings.app_env):
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Откройте mini-app из актуального меню MAX-бота",
        )
    try:
        return verify_miniapp_token(token)
    except MiniAppAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def require_matching_miniapp_identity(
    identity: MiniAppIdentity | None,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> None:
    if identity is None:
        return
    if (
        identity.max_user_id != max_user_id
        or identity.tenant_slug != tenant_slug.strip().lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ссылка открыта для другого пользователя или филиала",
        )
