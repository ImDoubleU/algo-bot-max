from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    build_miniapp_url,
    inline_keyboard_with_main_menu,
    miniapp_button,
)
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.communication import SchoolBroadcast
from app.models.enums import (
    OrderStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.store import Order
from app.models.student import Student, StudentAccessLink, Wallet
from app.models.tenant import Tenant
from app.schemas.broadcasts import (
    BroadcastAudiencePreviewRead,
    BroadcastAudienceRequest,
    SchoolBroadcastRead,
)
from app.services.max_notifications import schedule_staff_notification
from app.services.staff import active_staff_roles_for_tenant

logger = logging.getLogger(__name__)

BROADCAST_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
}
ACTIVE_ORDER_STATUSES = {
    OrderStatus.CREATED,
    OrderStatus.RESERVED,
    OrderStatus.TRANSFERRED_TO_TEACHER,
    OrderStatus.PROBLEM,
}


class BroadcastServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class BroadcastContext:
    tenant: Tenant
    account: MaxAccount


@dataclass(frozen=True)
class BroadcastRecipients:
    max_user_ids: set[int]
    student_ids: set[UUID]
    unavailable_student_ids: set[UUID]


async def _load_context(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> BroadcastContext:
    tenant = await db.scalar(
        select(Tenant).where(Tenant.slug == tenant_slug.strip().lower())
    )
    if tenant is None:
        raise BroadcastServiceError("Партнёр не найден", status_code=404)

    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == max_user_id)
    )
    if account is None:
        raise BroadcastServiceError("MAX-аккаунт не найден", status_code=404)

    roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=UUID(str(tenant.id)),
        account_id=UUID(str(account.id)),
        allowed_roles=BROADCAST_ROLES,
    )
    if not roles:
        raise BroadcastServiceError(
            "Рассылки доступны администратору, куратору, директору и суперадмину",
            status_code=403,
        )
    return BroadcastContext(tenant=tenant, account=account)


async def _resolve_recipients(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    payload: BroadcastAudienceRequest,
) -> BroadcastRecipients:
    recipient_query = (
        select(Student.id, MaxAccount.max_user_id)
        .select_from(StudentAccessLink)
        .join(Student, Student.id == StudentAccessLink.student_id)
        .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
        .where(
            StudentAccessLink.tenant_id == tenant_id,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            Student.tenant_id == tenant_id,
            Student.status == StudentStatus.ACTIVE,
        )
    )

    if payload.recipient_category == "parents":
        recipient_query = recipient_query.where(
            StudentAccessLink.role == StudentAccessRole.PARENT
        )
    elif payload.recipient_category == "students":
        recipient_query = recipient_query.where(
            StudentAccessLink.role == StudentAccessRole.STUDENT
        )

    eligible_query = select(Student.id).where(
        Student.tenant_id == tenant_id,
        Student.status == StudentStatus.ACTIVE,
    )

    if payload.group_names:
        recipient_query = recipient_query.where(
            Student.group_name.in_(payload.group_names)
        )
        eligible_query = eligible_query.where(
            Student.group_name.in_(payload.group_names)
        )

    if payload.venue_names:
        recipient_query = recipient_query.where(
            Student.venue_name.in_(payload.venue_names)
        )
        eligible_query = eligible_query.where(
            Student.venue_name.in_(payload.venue_names)
        )

    if payload.audience_filter == "low_balance":
        threshold = payload.balance_threshold if payload.balance_threshold is not None else 300
        audience_condition = exists(
            select(Wallet.id).where(
                Wallet.tenant_id == tenant_id,
                Wallet.student_id == Student.id,
                Wallet.balance <= threshold,
            )
        )
        recipient_query = recipient_query.where(audience_condition)
        eligible_query = eligible_query.where(audience_condition)
    elif payload.audience_filter == "active_orders":
        audience_condition = exists(
            select(Order.id).where(
                Order.tenant_id == tenant_id,
                Order.student_id == Student.id,
                Order.status.in_(ACTIVE_ORDER_STATUSES),
            )
        )
        recipient_query = recipient_query.where(audience_condition)
        eligible_query = eligible_query.where(audience_condition)
    elif payload.audience_filter == "no_orders":
        audience_condition = ~exists(
            select(Order.id).where(
                Order.tenant_id == tenant_id,
                Order.student_id == Student.id,
            )
        )
        recipient_query = recipient_query.where(audience_condition)
        eligible_query = eligible_query.where(audience_condition)

    rows = (await db.execute(recipient_query)).all()
    linked_student_ids = {UUID(str(row.id)) for row in rows}
    eligible_student_ids = {
        UUID(str(student_id)) for student_id in (await db.scalars(eligible_query)).all()
    }
    return BroadcastRecipients(
        max_user_ids={int(row.max_user_id) for row in rows},
        student_ids=linked_student_ids,
        unavailable_student_ids=eligible_student_ids - linked_student_ids,
    )


def _preview_read(
    recipients: BroadcastRecipients,
    payload: BroadcastAudienceRequest,
) -> BroadcastAudiencePreviewRead:
    return BroadcastAudiencePreviewRead(
        recipient_count=len(recipients.max_user_ids),
        matched_students=len(recipients.student_ids),
        unavailable_students=len(recipients.unavailable_student_ids),
        selected_groups=payload.group_names,
        selected_venues=payload.venue_names,
    )


def _broadcast_read(
    broadcast: SchoolBroadcast,
    *,
    creator_name: str | None,
) -> SchoolBroadcastRead:
    return SchoolBroadcastRead(
        id=UUID(str(broadcast.id)),
        title=broadcast.title,
        message=broadcast.message,
        image_url=broadcast.image_url,
        recipient_category=broadcast.recipient_category,
        audience_filter=broadcast.audience_filter,
        group_names=list(broadcast.group_names or []),
        venue_names=list(broadcast.venue_names or []),
        balance_threshold=broadcast.balance_threshold,
        status=broadcast.status,
        recipient_count=broadcast.recipient_count,
        delivered_count=broadcast.delivered_count,
        failed_count=broadcast.failed_count,
        creator_name=(creator_name or "Сотрудник").strip() or "Сотрудник",
        sent_at=broadcast.sent_at,
        created_at=broadcast.created_at,
    )


async def preview_school_broadcast(
    db: AsyncSession,
    *,
    payload: BroadcastAudienceRequest,
    default_tenant_slug: str,
) -> BroadcastAudiencePreviewRead:
    context = await _load_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    recipients = await _resolve_recipients(
        db,
        tenant_id=UUID(str(context.tenant.id)),
        payload=payload,
    )
    return _preview_read(recipients, payload)


async def send_school_broadcast(
    db: AsyncSession,
    *,
    payload: BroadcastAudienceRequest,
    title: str | None,
    message: str,
    image_url: str | None,
    default_tenant_slug: str,
) -> SchoolBroadcastRead:
    context = await _load_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    recipients = await _resolve_recipients(
        db,
        tenant_id=UUID(str(context.tenant.id)),
        payload=payload,
    )
    if not recipients.max_user_ids:
        raise BroadcastServiceError("По выбранным условиям получателей не найдено")

    settings = get_settings()
    if is_placeholder(settings.max_bot_token):
        raise BroadcastServiceError(
            "MAX_BOT_TOKEN не настроен, рассылка не отправлена",
            status_code=503,
        )

    clean_title = (title or "").strip() or None
    clean_message = message.strip()
    if not clean_message:
        raise BroadcastServiceError("Введите текст новости")
    text = f"{clean_title}\n\n{clean_message}" if clean_title else clean_message

    broadcast = SchoolBroadcast(
        tenant_id=context.tenant.id,
        creator_account_id=context.account.id,
        title=clean_title,
        message=clean_message,
        image_url=image_url,
        recipient_category=payload.recipient_category,
        audience_filter=payload.audience_filter,
        group_names=payload.group_names,
        venue_names=payload.venue_names,
        lesson_modes=[],
        balance_threshold=payload.balance_threshold,
        status="sending",
        recipient_count=len(recipients.max_user_ids),
    )
    db.add(broadcast)
    await db.flush()
    await db.commit()

    client = MaxApiClient(
        settings.max_bot_token or "",
        settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )
    semaphore = asyncio.Semaphore(6)

    async def send_one(user_id: int) -> bool:
        miniapp_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=context.tenant.slug,
            view="dashboard",
        )
        rows = [[miniapp_button("Открыть Algo MAX", miniapp_url)]] if miniapp_url else []
        attachments = inline_keyboard_with_main_menu(rows)
        if image_url:
            attachments.insert(0, {"type": "image", "payload": {"url": image_url}})
        try:
            async with semaphore:
                await asyncio.to_thread(
                    client.send_message,
                    text=text,
                    attachments=attachments,
                    user_id=user_id,
                )
        except Exception as exc:
            logger.warning(
                "Не удалось отправить школьную рассылку пользователю %s: %s",
                user_id,
                exc,
            )
            return False
        return True

    results = await asyncio.gather(
        *(send_one(user_id) for user_id in recipients.max_user_ids)
    )
    delivered = sum(results)
    failed = len(results) - delivered
    broadcast.delivered_count = delivered
    broadcast.failed_count = failed
    broadcast.sent_at = datetime.now(UTC)
    if delivered == len(results):
        broadcast.status = "sent"
    elif delivered:
        broadcast.status = "partial"
    else:
        broadcast.status = "failed"
    db.add(
        AuditLog(
            tenant_id=context.tenant.id,
            actor_account_id=context.account.id,
            action="school_broadcast.sent",
            entity_type="school_broadcast",
            entity_id=str(broadcast.id),
            payload={
                "recipient_category": payload.recipient_category,
                "audience_filter": payload.audience_filter,
                "group_names": payload.group_names,
                "venue_names": payload.venue_names,
                "recipient_count": len(results),
                "delivered_count": delivered,
                "failed_count": failed,
            },
        )
    )
    await db.commit()
    event_key = {
        "sent": "broadcasts.completed",
        "partial": "broadcasts.partial",
        "failed": "broadcasts.failed",
    }[broadcast.status]
    event_title = {
        "sent": "Рассылка завершена",
        "partial": "Рассылка выполнена частично",
        "failed": "Рассылка не отправлена",
    }[broadcast.status]
    await schedule_staff_notification(
        db,
        tenant=context.tenant,
        event_key=event_key,
        title=event_title,
        message=clean_title,
        facts=[
            ("Отправил", context.account.display_name),
            ("Получателей", str(len(results))),
            ("Доставлено", str(delivered)),
            ("Не доставлено", str(failed)),
        ],
        view="broadcasts",
        button_label="Открыть рассылки",
    )
    return _broadcast_read(
        broadcast,
        creator_name=context.account.display_name,
    )


async def list_school_broadcasts(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    limit: int = 20,
) -> list[SchoolBroadcastRead]:
    context = await _load_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    rows = (
        await db.execute(
            select(SchoolBroadcast, MaxAccount.display_name)
            .join(MaxAccount, MaxAccount.id == SchoolBroadcast.creator_account_id)
            .where(SchoolBroadcast.tenant_id == context.tenant.id)
            .order_by(SchoolBroadcast.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        _broadcast_read(broadcast, creator_name=creator_name)
        for broadcast, creator_name in rows
    ]
