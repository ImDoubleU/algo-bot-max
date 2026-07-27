from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import build_miniapp_url, inline_keyboard_with_main_menu, link_button
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder
from app.models.account import MaxAccount
from app.models.enums import StudentAccessRole, StudentAccessStatus
from app.models.student import Student, StudentAccessLink
from app.models.teaching import FeedbackOutput, TeachingSchedule

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FeedbackDeliveryResult:
    eligible: int
    sent: int


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
        rows = [[link_button("Открыть mini app", url)]] if url else []
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


async def parent_recipient_ids(
    db: AsyncSession,
    *,
    schedule: TeachingSchedule,
) -> set[int]:
    return set(
        (
            await db.scalars(
                select(MaxAccount.max_user_id)
                .join(StudentAccessLink, StudentAccessLink.account_id == MaxAccount.id)
                .join(Student, Student.id == StudentAccessLink.student_id)
                .where(
                    StudentAccessLink.tenant_id == schedule.tenant_id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                    StudentAccessLink.role == StudentAccessRole.PARENT,
                    Student.group_name == schedule.group_name,
                )
                .distinct()
            )
        ).all()
    )


async def deliver_feedback_to_parents(
    db: AsyncSession,
    *,
    output: FeedbackOutput,
    tenant_slug: str,
) -> FeedbackDeliveryResult:
    user_ids = await parent_recipient_ids(db, schedule=output.schedule)
    sent = await _send_max_messages(
        user_ids=user_ids,
        tenant_slug=tenant_slug,
        text=output.feedback_text,
    )
    if sent:
        output.status = "sent_to_parents"
        output.sent_at = datetime.now(UTC)
        await db.commit()
    return FeedbackDeliveryResult(eligible=len(user_ids), sent=sent)
