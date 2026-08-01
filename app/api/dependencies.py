from __future__ import annotations

from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings, is_local_environment, is_placeholder
from app.core.max_webapp_auth import MaxWebAppAuthError, verify_max_webapp_data
from app.core.miniapp_auth import (
    MiniAppAuthError,
    MiniAppIdentity,
    verify_miniapp_token,
)


async def get_miniapp_identity(
    token: Annotated[str | None, Header(alias="X-Miniapp-Token")] = None,
    max_webapp_data: Annotated[
        str | None,
        Header(alias="X-Max-WebApp-Data"),
    ] = None,
) -> MiniAppIdentity | None:
    settings = get_settings()
    if max_webapp_data:
        if is_placeholder(settings.max_bot_token):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MAX-авторизация временно недоступна",
            )
        try:
            identity = verify_max_webapp_data(
                max_webapp_data,
                bot_token=str(settings.max_bot_token),
                max_age_seconds=settings.max_webapp_auth_max_age_seconds,
            )
        except MaxWebAppAuthError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        return MiniAppIdentity(
            max_user_id=identity.max_user_id,
            tenant_slug=None,
            expires_at=identity.auth_date + settings.max_webapp_auth_max_age_seconds,
        )
    if not token:
        if is_local_environment(settings.app_env):
            return None
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Откройте личный кабинет из меню бота",
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
        or (
            identity.tenant_slug is not None
            and identity.tenant_slug != tenant_slug.strip().lower()
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ссылка открыта для другого пользователя или филиала",
        )
