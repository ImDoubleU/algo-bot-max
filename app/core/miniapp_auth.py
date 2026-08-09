from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import time
from dataclasses import dataclass

from app.core.config import get_settings

TOKEN_VERSION = "v2"
TOKEN_AUDIENCE = "max-bot-backend"


class MiniAppAuthError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class MiniAppIdentity:
    max_user_id: int
    tenant_slug: str | None
    expires_at: int


def _normalized_tenant_slug(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise MiniAppAuthError("Город или партнер не указан")
    return normalized


def _signature(payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def issue_miniapp_token(
    *,
    max_user_id: int,
    tenant_slug: str,
    now: int | None = None,
) -> str:
    if max_user_id < 1:
        raise MiniAppAuthError("MAX user_id должен быть положительным")
    settings = get_settings()
    issued_at = int(time.time() if now is None else now)
    expires_at = issued_at + settings.miniapp_token_ttl_seconds
    normalized_tenant = _normalized_tenant_slug(tenant_slug)
    payload = (
        f"{TOKEN_VERSION}|{TOKEN_AUDIENCE}|"
        f"{max_user_id}|{normalized_tenant}|{expires_at}"
    )
    token = f"{payload}|{_signature(payload, settings.app_secret_key)}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii").rstrip("=")


def verify_miniapp_token(
    token: str,
    *,
    now: int | None = None,
) -> MiniAppIdentity:
    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(f"{token}{padding}").decode("utf-8")
        (
            version,
            audience,
            user_id_text,
            tenant_slug,
            expires_text,
            supplied_signature,
        ) = decoded.split(
            "|",
            5,
        )
        max_user_id = int(user_id_text)
        expires_at = int(expires_text)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise MiniAppAuthError("Не удалось проверить ссылку на приложение") from exc

    if (
        version != TOKEN_VERSION
        or audience != TOKEN_AUDIENCE
        or max_user_id < 1
    ):
        raise MiniAppAuthError("Не удалось проверить ссылку на приложение")

    normalized_tenant = _normalized_tenant_slug(tenant_slug)
    payload = f"{version}|{audience}|{max_user_id}|{normalized_tenant}|{expires_at}"
    expected_signature = _signature(payload, get_settings().app_secret_key)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise MiniAppAuthError("Не удалось проверить ссылку на приложение")

    current_time = int(time.time() if now is None else now)
    if expires_at < current_time:
        raise MiniAppAuthError("Ссылка устарела. Откройте личный кабинет из меню бота")

    return MiniAppIdentity(
        max_user_id=max_user_id,
        tenant_slug=normalized_tenant,
        expires_at=expires_at,
    )
