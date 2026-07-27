from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    build_miniapp_url,
    inline_keyboard_with_main_menu,
    open_app_button,
)
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder
from app.models.account import MaxAccount
from app.models.enums import OrderStatus, StudentAccessStatus
from app.models.store import Order
from app.models.student import Student, StudentAccessLink
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task[None]] = set()


def _order_status_text(status: OrderStatus) -> str:
    return {
        OrderStatus.RESERVED: "Зарезервировано",
        OrderStatus.CANCELLED: "Заказ отменен",
        OrderStatus.ISSUED_TO_STUDENT: "Заказ выдан ученику",
        OrderStatus.RETURNED: "Возврат оформлен",
    }.get(status, status.value)


def _order_message(
    *,
    order: Order,
    student: Student,
    balance_after: int | None,
) -> str:
    lines = [
        f"Заказ №{order.order_number}",
        f"Ученик: {student.display_name}",
        f"Статус: {_order_status_text(order.status)}",
        f"Сумма: {order.total_astrocoins} AC",
    ]
    if order.status in {OrderStatus.CANCELLED, OrderStatus.RETURNED}:
        lines.append(f"Возвращено: {order.total_astrocoins} AC")
    if balance_after is not None:
        lines.append(f"Баланс: {balance_after} AC")
    return "\n".join(lines)


async def _recipient_user_ids(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    creator_account_id: UUID | None,
) -> set[int]:
    account_ids = set(
        (
            await db.scalars(
                select(StudentAccessLink.account_id).where(
                    StudentAccessLink.tenant_id == tenant_id,
                    StudentAccessLink.student_id == student_id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
            )
        ).all()
    )
    if creator_account_id is not None:
        account_ids.add(creator_account_id)
    if not account_ids:
        return set()
    return set(
        (
            await db.scalars(
                select(MaxAccount.max_user_id).where(MaxAccount.id.in_(account_ids))
            )
        ).all()
    )


async def _deliver_order_notification(
    *,
    user_ids: set[int],
    tenant_slug: str,
    text: str,
) -> None:
    settings = get_settings()
    client = MaxApiClient(
        settings.max_bot_token or "",
        settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )

    async def send(user_id: int) -> None:
        miniapp_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="orders",
        )
        rows = [[open_app_button("Открыть заказ")]] if miniapp_url else []
        attachments = inline_keyboard_with_main_menu(rows)
        await asyncio.to_thread(
            client.send_message,
            text=text,
            attachments=attachments,
            user_id=user_id,
        )

    results = await asyncio.gather(*(send(user_id) for user_id in user_ids), return_exceptions=True)
    for user_id, result in zip(user_ids, results, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                "Не удалось отправить MAX-уведомление пользователю %s: %s",
                user_id,
                result,
            )


async def schedule_order_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    order: Order,
    student: Student,
    balance_after: int | None = None,
) -> None:
    settings = get_settings()
    if not settings.max_order_notifications_enabled or is_placeholder(settings.max_bot_token):
        return

    try:
        user_ids = await _recipient_user_ids(
            db,
            tenant_id=UUID(str(tenant.id)),
            student_id=UUID(str(student.id)),
            creator_account_id=(
                UUID(str(order.created_by_account_id)) if order.created_by_account_id else None
            ),
        )
    except Exception as exc:
        logger.warning("Не удалось определить получателей MAX-уведомления: %s", exc)
        return
    if not user_ids:
        return

    task = asyncio.create_task(
        _deliver_order_notification(
            user_ids=user_ids,
            tenant_slug=tenant.slug,
            text=_order_message(order=order, student=student, balance_after=balance_after),
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_log_notification_task_error)


def _log_notification_task_error(task: asyncio.Task[None]) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning("Ошибка фоновой отправки MAX-уведомления: %s", error)
