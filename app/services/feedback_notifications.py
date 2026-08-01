from __future__ import annotations

import asyncio
import logging

from app.bot.keyboards import (
    build_miniapp_url,
    inline_keyboard_with_main_menu,
    miniapp_button,
)
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder

logger = logging.getLogger(__name__)


async def _send_max_messages(
    *,
    user_ids: set[int],
    text: str,
    tenant_slug: str,
    view: str | None = None,
) -> int:
    settings = get_settings()
    if not user_ids or is_placeholder(settings.max_bot_token):
        return 0
    client = MaxApiClient(
        settings.max_bot_token or "",
        settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )

    async def send(user_id: int) -> bool:
        url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug, view=view)
        rows = [[miniapp_button("Открыть кабинет", url)]] if url else []
        attachments = inline_keyboard_with_main_menu(rows)
        try:
            await asyncio.to_thread(
                client.send_message,
                text=text,
                attachments=attachments,
                user_id=user_id,
            )
        except Exception as exc:
            logger.warning("Не удалось отправить ОС пользователю %s: %s", user_id, exc)
            return False
        return True

    results = await asyncio.gather(*(send(user_id) for user_id in user_ids))
    return sum(results)


async def deliver_feedback_to_teacher(
    *,
    max_user_id: int,
    tenant_slug: str,
    group_name: str,
    feedback_text: str,
) -> int:
    return await _send_max_messages(
        user_ids={max_user_id},
        tenant_slug=tenant_slug,
        view="teaching",
        text=f"ОС готова · {group_name}\n\n{feedback_text}",
    )
