from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, exists, false, func, or_, select
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
from app.models.tenant import Tenant, Venue
from app.schemas.broadcasts import (
    BroadcastAudiencePreviewRead,
    BroadcastAudienceRequest,
    BroadcastTargetOptionsRead,
    BroadcastVenueRuleRead,
    BroadcastVenueRuleUpsert,
    SchoolBroadcastRead,
)
from app.services.crm_sync import slugify
from app.services.max_notifications import schedule_staff_notification
from app.services.staff import active_staff_roles_for_tenant

logger = logging.getLogger(__name__)

BROADCAST_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
}
BROADCAST_VENUE_MANAGEMENT_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
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
    roles: frozenset[StaffRole]


@dataclass(frozen=True)
class BroadcastRecipients:
    max_user_ids: set[int]
    student_ids: set[UUID]
    unavailable_student_ids: set[UUID]


def normalize_broadcast_target_text(value: str | None) -> str:
    return " ".join((value or "").strip().casefold().replace("ё", "е").split())


def classify_broadcast_group(group_name: str | None) -> str:
    normalized = normalize_broadcast_target_text(group_name)
    if "индивид" in normalized:
        return "individual"
    if "общ" in normalized:
        return "online"
    return "offline"


def _normalized_sql(column):
    return func.replace(func.lower(func.coalesce(column, "")), "ё", "е")


def _lesson_mode_condition(lesson_modes: list[str]):
    if not lesson_modes:
        return None
    group_name = _normalized_sql(Student.group_name)
    is_individual = group_name.contains("индивид")
    contains_online_marker = group_name.contains("общ")
    conditions = []
    if "individual" in lesson_modes:
        conditions.append(is_individual)
    if "online" in lesson_modes:
        conditions.append(and_(~is_individual, contains_online_marker))
    if "offline" in lesson_modes:
        conditions.append(and_(~is_individual, ~contains_online_marker))
    return or_(*conditions) if conditions else false()


def _venue_matches_group(
    *,
    group_name: str,
    imported_venue_name: str,
    venue: Venue,
    explicit_group_owners: dict[str, set[UUID]],
) -> bool:
    normalized_group = normalize_broadcast_target_text(group_name)
    explicit_owners = explicit_group_owners.get(normalized_group)
    if explicit_owners:
        return UUID(str(venue.id)) in explicit_owners
    if normalize_broadcast_target_text(
        imported_venue_name
    ) == normalize_broadcast_target_text(venue.name):
        return True
    return any(
        normalize_broadcast_target_text(keyword) in normalized_group
        for keyword in (venue.broadcast_keywords or [])
        if normalize_broadcast_target_text(keyword)
    )


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
    return BroadcastContext(
        tenant=tenant,
        account=account,
        roles=frozenset(roles),
    )


async def _venue_condition(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    venue_names: list[str],
):
    if not venue_names:
        return None
    venues = list(
        (
            await db.scalars(
                select(Venue).where(Venue.tenant_id == tenant_id)
            )
        ).all()
    )
    selected_names = {
        normalize_broadcast_target_text(name) for name in venue_names
    }
    selected = [
        venue
        for venue in venues
        if normalize_broadcast_target_text(venue.name) in selected_names
    ]
    all_explicit_groups = {
        normalize_broadcast_target_text(group_name)
        for venue in venues
        for group_name in (venue.broadcast_group_names or [])
        if normalize_broadcast_target_text(group_name)
    }
    selected_explicit_groups = {
        normalize_broadcast_target_text(group_name)
        for venue in selected
        for group_name in (venue.broadcast_group_names or [])
        if normalize_broadcast_target_text(group_name)
    }
    normalized_group = _normalized_sql(Student.group_name)
    fallback_conditions = [
        Student.venue_id.in_([venue.id for venue in selected]),
        Student.venue_name.in_(venue_names),
        _normalized_sql(Student.venue_name).in_(selected_names),
    ]
    fallback_conditions.extend(
        normalized_group.contains(normalize_broadcast_target_text(keyword))
        for venue in selected
        for keyword in (venue.broadcast_keywords or [])
        if normalize_broadcast_target_text(keyword)
    )
    fallback = or_(*fallback_conditions)
    if all_explicit_groups:
        fallback = and_(~normalized_group.in_(all_explicit_groups), fallback)
    if selected_explicit_groups:
        return or_(normalized_group.in_(selected_explicit_groups), fallback)
    return fallback


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

    lesson_mode_condition = _lesson_mode_condition(payload.lesson_modes)
    if lesson_mode_condition is not None:
        recipient_query = recipient_query.where(lesson_mode_condition)
        eligible_query = eligible_query.where(lesson_mode_condition)

    venue_condition = await _venue_condition(
        db,
        tenant_id=tenant_id,
        venue_names=payload.venue_names,
    )
    if venue_condition is not None:
        recipient_query = recipient_query.where(venue_condition)
        eligible_query = eligible_query.where(venue_condition)

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
        selected_lesson_modes=payload.lesson_modes,
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
        lesson_modes=list(broadcast.lesson_modes or []),
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
        lesson_modes=payload.lesson_modes,
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
                "lesson_modes": payload.lesson_modes,
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


async def get_broadcast_target_options(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> BroadcastTargetOptionsRead:
    context = await _load_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    tenant_id = UUID(str(context.tenant.id))
    student_rows = (
        await db.execute(
            select(Student.group_name, Student.venue_name).where(
                Student.tenant_id == tenant_id,
                Student.status == StudentStatus.ACTIVE,
                Student.group_name.is_not(None),
            )
        )
    ).all()
    group_names = sorted(
        {
            str(row.group_name).strip()
            for row in student_rows
            if str(row.group_name or "").strip()
        },
        key=lambda value: normalize_broadcast_target_text(value),
    )
    venues = list(
        (
            await db.scalars(
                select(Venue)
                .where(Venue.tenant_id == tenant_id)
                .order_by(Venue.name)
            )
        ).all()
    )
    explicit_group_owners: dict[str, set[UUID]] = {}
    for venue in venues:
        for group_name in venue.broadcast_group_names or []:
            normalized = normalize_broadcast_target_text(group_name)
            if normalized:
                explicit_group_owners.setdefault(normalized, set()).add(
                    UUID(str(venue.id))
                )

    venue_reads = []
    for venue in venues:
        matched_groups = {
            str(row.group_name).strip()
            for row in student_rows
            if _venue_matches_group(
                group_name=str(row.group_name or ""),
                imported_venue_name=str(row.venue_name or ""),
                venue=venue,
                explicit_group_owners=explicit_group_owners,
            )
        }
        venue_reads.append(
            BroadcastVenueRuleRead(
                id=UUID(str(venue.id)),
                name=venue.name,
                keywords=list(venue.broadcast_keywords or []),
                group_names=list(venue.broadcast_group_names or []),
                matched_group_count=len(matched_groups),
            )
        )
    return BroadcastTargetOptionsRead(
        groups=group_names,
        venues=venue_reads,
        can_manage_venues=bool(context.roles & BROADCAST_VENUE_MANAGEMENT_ROLES),
    )


async def upsert_broadcast_venue_rule(
    db: AsyncSession,
    *,
    payload: BroadcastVenueRuleUpsert,
    default_tenant_slug: str,
    venue_id: UUID | None = None,
) -> BroadcastVenueRuleRead:
    context = await _load_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    if not context.roles & BROADCAST_VENUE_MANAGEMENT_ROLES:
        raise BroadcastServiceError(
            "Настраивать площадки могут директор, администратор и суперадминистратор",
            status_code=403,
        )
    tenant_id = UUID(str(context.tenant.id))
    venues = list(
        (
            await db.scalars(select(Venue).where(Venue.tenant_id == tenant_id))
        ).all()
    )
    venue = next(
        (item for item in venues if venue_id is not None and UUID(str(item.id)) == venue_id),
        None,
    )
    if venue_id is not None and venue is None:
        raise BroadcastServiceError("Площадка не найдена", status_code=404)
    duplicate = next(
        (
            item
            for item in venues
            if normalize_broadcast_target_text(item.name)
            == normalize_broadcast_target_text(payload.name)
            and (venue is None or item.id != venue.id)
        ),
        None,
    )
    if duplicate is not None:
        raise BroadcastServiceError("Площадка с таким названием уже существует")

    if venue is None:
        used_slugs = {item.slug for item in venues}
        base_slug = slugify(payload.name) or "venue"
        slug = base_slug
        suffix = 2
        while slug in used_slugs:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        venue = Venue(
            tenant_id=tenant_id,
            slug=slug,
            name=payload.name,
        )
        db.add(venue)
        await db.flush()
        action = "broadcast_venue.created"
    else:
        venue.name = payload.name
        action = "broadcast_venue.updated"
    venue.broadcast_keywords = payload.keywords
    venue.broadcast_group_names = payload.group_names
    db.add(
        AuditLog(
            tenant_id=tenant_id,
            actor_account_id=context.account.id,
            action=action,
            entity_type="venue",
            entity_id=str(venue.id),
            payload={
                "name": venue.name,
                "keywords": payload.keywords,
                "group_names": payload.group_names,
            },
        )
    )
    await db.commit()
    options = await get_broadcast_target_options(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=context.tenant.slug,
    )
    return next(item for item in options.venues if item.id == UUID(str(venue.id)))
