from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, status

from app.bot.max_webhook import WebhookQueueFull, get_webhook_runtime
from app.core.config import get_settings, is_placeholder

router = APIRouter()


@router.post("/webhook")
def receive_max_webhook(
    update: dict[str, Any],
    max_secret: Annotated[str | None, Header(alias="X-Max-Bot-Api-Secret")] = None,
) -> dict[str, bool]:
    settings = get_settings()
    if settings.bot_mode.strip().lower() != "webhook":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MAX webhook processing is disabled",
        )
    expected_secret = settings.max_webhook_secret
    if is_placeholder(expected_secret) or max_secret is None or not hmac.compare_digest(
        str(expected_secret), max_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid MAX webhook secret",
        )
    if not isinstance(update.get("update_type"), str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="update_type is required",
        )
    try:
        get_webhook_runtime().submit(update)
    except WebhookQueueFull as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook queue is full",
        ) from exc
    return {"ok": True}
