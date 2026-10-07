"""Missing-profile attempts. Matching never creates access without confirmation."""

import asyncio
import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update

from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.enums import StudentAccessRole, StudentAccessStatus, TenantStatus
from app.models.pending_binding import PendingBinding
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.models.tenant import Tenant
from app.schemas.access import AccessLinkCreate, StudentInvitationLinkCreate, StudentResolveRequest
from app.services.student_access_policy import student_access_window
from app.services.student_invitations import (
    StudentInvitationError,
    StudentInvitationIssuer,
    issue_student_invitation_token,
    issue_teacher_student_invitation_token,
    verify_student_invitation_details,
)

logger = logging.getLogger(__name__)
OPEN_STATUSES = ("pending", "ready", "review")
WAITING_MESSAGE = (
    "Профиль ребёнка пока не найден. Мы сохранили вашу попытку и сообщим, "
    "когда можно будет подключиться. Проверьте, что открыли ссылку из письма вашей школы."
)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def fingerprint(kind, target):
    if kind == "contact":
        from app.services.access import hash_contact_id
        target = target[7:] if target.startswith("sha256:") else hash_contact_id(target)
    return hashlib.sha256(f"{kind}:{target}".encode()).hexdigest()


def record_event(db, item, action, *, account_id=None):
    payload = {"max_user_id": item.max_user_id, "role": item.role,
               "status": item.status, "reason": item.reason, "attempts": item.attempts,
               "result": "pending" if action in {"saved", "ready", "waiting"} else
               "partial" if action in {"review", "expired"} else "success"}
    if item.kind == "contact":
        from app.services.access import hash_contact_id
        payload["contact_id_hash"] = (item.target_id[7:] if item.target_id.startswith("sha256:")
                                      else hash_contact_id(item.target_id))
    else:
        payload["student_id"] = item.target_id
    db.add(AuditLog(
        tenant_id=item.tenant_id, actor_account_id=account_id, action=f"pending_binding.{action}",
        entity_type="pending_binding", entity_id=str(item.id),
        payload=payload,
    ))


async def remember_missing_binding(db, payload, reason):
    from app.services.access import (
        get_or_create_max_account,
        get_tenant_by_slug,
        normalize_contact_id,
    )

    if not payload.max_user_id:
        return None
    issuer = sponsor = None
    if isinstance(payload, (AccessLinkCreate, StudentResolveRequest)):
        if reason not in {"contact_not_found", "contact_id_not_found", "contact_has_no_students"}:
            return None
        if getattr(payload, "role", StudentAccessRole.PARENT) != StudentAccessRole.PARENT:
            return None
        target = normalize_contact_id(payload.contact_id)
        if not re.fullmatch(r"[A-Z0-9_-]{1,120}", target):
            return None
        tenant = await get_tenant_by_slug(db, payload.tenant_slug)
        if tenant is None:
            return None
        existing_children = await db.scalar(
            select(ContactStudentLink.id).join(Contact, Contact.id == ContactStudentLink.contact_id)
            .where(Contact.tenant_id == tenant.id, Contact.external_contact_id == target).limit(1)
        )
        if existing_children:
            return None  # An existing family with closed access is not awaiting import.
        kind, role = "contact", "parent"
    else:
        if reason != "student_not_found":
            return None
        try:
            invitation = verify_student_invitation_details(payload.token)
        except StudentInvitationError:
            return None
        if invitation.issuer == StudentInvitationIssuer.LEGACY:
            return None
        tenant = await db.get(Tenant, invitation.tenant_id)
        target = str(invitation.student_id)
        issuer, sponsor = invitation.issuer.value, invitation.sponsor_access_link_id
        kind, role = "student", "student"
    if tenant is None or tenant.status != TenantStatus.ACTIVE:
        return None
    account = await get_or_create_max_account(db, payload)  # Serializes duplicate first attempts.
    now = datetime.now(UTC)
    key = fingerprint(kind, target)
    item = await db.scalar(select(PendingBinding).where(
        PendingBinding.tenant_id == tenant.id, PendingBinding.max_user_id == payload.max_user_id,
        PendingBinding.fingerprint == key,
    ).with_for_update())
    if item is None:
        item = PendingBinding(tenant_id=tenant.id, max_user_id=payload.max_user_id, role=role,
                              kind=kind, target_id=target, fingerprint=key, issuer=issuer,
                              sponsor_link_id=sponsor, status="pending", reason=reason, attempts=1,
                              last_attempt_at=now, expires_at=now + timedelta(days=30),
                              notification_attempts=0)
        db.add(item)
        await db.flush()
        record_event(db, item, "saved", account_id=account.id)
    else:
        item.target_id = target
        item.attempts += 1
        item.last_attempt_at = now
        item.last_checked_at = None
        item.reason = reason
        item.issuer, item.sponsor_link_id = issuer, sponsor
        if item.status not in OPEN_STATUSES or utc(item.expires_at) <= now:
            item.expires_at = now + timedelta(days=30)
        item.status = "pending"
        item.notified_at = None
        item.notification_attempts = 0
        item.notification_attempted_at = None
        item.notification_error = None
    return item


async def target_students(db, item):
    tenant = await db.get(Tenant, item.tenant_id)
    if tenant is None or tenant.status != TenantStatus.ACTIVE:
        return tenant, [], "school_inactive"
    if item.kind == "contact":
        if item.target_id.startswith("sha256:"):
            from app.services.access import hash_contact_id
            # Old logs intentionally retained only a hash. Resolve it against this school's IDs.
            contacts = list(await db.scalars(select(Contact).where(Contact.tenant_id == tenant.id)))
            matches = [contact for contact in contacts
                       if hash_contact_id(contact.external_contact_id) == item.target_id[7:]]
            if len(matches) != 1:
                return tenant, [], "contact_not_found"
            item.target_id = matches[0].external_contact_id
        contact = await db.scalar(select(Contact).where(
            Contact.tenant_id == tenant.id, Contact.external_contact_id == item.target_id,
        ))
        if contact is None:
            return tenant, [], "contact_not_found"
        students = list(await db.scalars(select(Student).join(
            ContactStudentLink, ContactStudentLink.student_id == Student.id,
        ).where(ContactStudentLink.contact_id == contact.id,
                ContactStudentLink.tenant_id == tenant.id, Student.tenant_id == tenant.id)))
        if not students:
            return tenant, [], "contact_has_no_students"
    else:
        student = await db.scalar(select(Student).where(
            Student.id == UUID(item.target_id), Student.tenant_id == tenant.id,
        ))
        if student is None:
            return tenant, [], "student_not_found"
        students = [student]
        if item.issuer == "parent":
            from app.services.access import get_active_parent_access_link
            parent = await get_active_parent_access_link(
                db, tenant_id=tenant.id, student_id=student.id,
                sponsor_access_link_id=item.sponsor_link_id,
            )
            if parent is None:
                return tenant, [], "parent_link_inactive"
    students = [student for student in students if student_access_window(student, tenant).allowed]
    if not students:
        return tenant, [], "student_access_closed"
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == item.max_user_id))
    if account:
        active_links = list(await db.scalars(select(StudentAccessLink).where(
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )))
        if any(link.role.value != item.role for link in active_links):
            return tenant, [], "account_role_conflict"
        if item.role == "student" and any(
            link.student_id != students[0].id or link.tenant_id != tenant.id
            for link in active_links
        ):
            return tenant, [], "student_already_bound"
        links = list(await db.scalars(select(StudentAccessLink).where(
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id.in_([student.id for student in students]),
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.role == StudentAccessRole(item.role),
        )))
        allowed_revocations = {"bot_stopped", "registration_reset"}
        if item.role == "student":
            allowed_revocations |= {
                "sponsor_bot_stopped", "sponsor_revoked", "parent_required_hotfix",
            }
        if any(link.status == StudentAccessStatus.DISPUTED or (
            link.status == StudentAccessStatus.REVOKED
            and link.revoked_reason not in allowed_revocations
        ) for link in links):
            return tenant, [], "access_revoked"
        if {link.student_id for link in links if link.status == StudentAccessStatus.ACTIVE} >= {
            student.id for student in students
        }:
            return tenant, students, "already_connected"
    return tenant, students, "ready"


async def complete_matching_pending(db, *, tenant_id, max_user_id, kind, target):
    await db.execute(update(PendingBinding).where(
        PendingBinding.tenant_id == tenant_id, PendingBinding.max_user_id == max_user_id,
        PendingBinding.fingerprint == fingerprint(kind, target),
        PendingBinding.status.in_(OPEN_STATUSES),
    ).values(status="completed", reason="connected"))


async def recover_historical_missing_bindings(db):
    """One-time recovery from authenticated domain failures; never guesses a contact ID."""
    from app.services.access import get_or_create_max_account

    now = datetime.now(UTC)
    failures = list(await db.scalars(select(AuditLog).where(
        AuditLog.action.in_(("contact_access.resolve_failed", "contact_access_link.failed")),
        AuditLog.tenant_id.is_not(None), AuditLog.created_at >= now - timedelta(days=30),
    ).order_by(AuditLog.created_at)))
    grouped = {}
    for failure in failures:
        payload = failure.payload or {}
        if payload.get("reason") not in {"contact_id_not_found", "contact_not_found",
                                         "contact_has_no_students"}:
            continue
        if payload.get("role", "parent") != "parent":
            continue
        user_id, digest = payload.get("max_user_id"), payload.get("contact_id_hash")
        if not isinstance(user_id, int) or user_id <= 0 or not re.fullmatch(
            r"[0-9a-f]{64}", str(digest or ""),
        ):
            continue
        key = (failure.tenant_id, user_id, digest)
        _, attempts = grouped.get(key, (failure, 0))
        grouped[key] = failure, attempts + 1
    stopped = {}
    for event, actor_max_id in await db.execute(select(AuditLog, MaxAccount.max_user_id).outerjoin(
        MaxAccount, MaxAccount.id == AuditLog.actor_account_id,
    ).where(AuditLog.action.in_(("bot.interaction", "max_bot_access.revoked")),
            AuditLog.created_at >= now - timedelta(days=30))):
        payload = event.payload or {}
        if event.action == "bot.interaction" and payload.get("update_type") != "bot_stopped":
            continue
        user = actor_max_id or payload.get("actor_max_user_id") or payload.get("max_user_id")
        if user:
            stopped[int(user)] = max(stopped.get(int(user), utc(event.created_at)),
                                     utc(event.created_at))
    recovered = 0
    for (tenant_id, user_id, digest), (failure, attempts) in grouped.items():
        if user_id in stopped and stopped[user_id] >= utc(failure.created_at):
            continue
        tenant = await db.get(Tenant, tenant_id)
        if tenant is None or tenant.status != TenantStatus.ACTIVE:
            continue
        target = "sha256:" + digest
        key = fingerprint("contact", target)
        existing = await db.scalar(select(PendingBinding.id).where(
            PendingBinding.tenant_id == tenant_id, PendingBinding.max_user_id == user_id,
            PendingBinding.fingerprint == key,
        ))
        if existing:
            continue
        account = await get_or_create_max_account(db, AccessLinkCreate(
            tenant_slug=tenant.slug, contact_id="recovered", max_user_id=user_id,
            role=StudentAccessRole.PARENT,
        ))
        if await db.scalar(select(PendingBinding.id).where(
            PendingBinding.tenant_id == tenant_id, PendingBinding.max_user_id == user_id,
            PendingBinding.fingerprint == key,
        )):
            continue
        item = PendingBinding(
            tenant_id=tenant_id, max_user_id=user_id, kind="contact", role="parent",
            target_id=target, fingerprint=key, status="pending", reason="contact_not_found",
            attempts=attempts, last_attempt_at=failure.created_at, created_at=failure.created_at,
            expires_at=utc(failure.created_at) + timedelta(days=30), notification_attempts=0,
        )
        db.add(item)
        await db.flush()
        record_event(db, item, "saved", account_id=account.id)
        recovered += 1
    await db.commit()
    return recovered


async def cancel_pending_binding(db, pending_id, max_user_id, *, owner=False):
    from fastapi import HTTPException
    await db.scalar(select(MaxAccount.id).where(
        MaxAccount.max_user_id == max_user_id,
    ).with_for_update())
    query = select(PendingBinding).where(PendingBinding.id == pending_id)
    if not owner:
        query = query.where(PendingBinding.max_user_id == max_user_id)
    item = await db.scalar(query.with_for_update())
    if item is None:
        raise HTTPException(404, "Ожидающее подключение не найдено")
    if item.status in OPEN_STATUSES:
        item.status, item.reason = "cancelled", "cancelled"
        actor_id = await db.scalar(select(MaxAccount.id).where(
            MaxAccount.max_user_id == max_user_id,
        ))
        record_event(db, item, "cancelled", account_id=actor_id)
        await db.commit()


async def confirm_pending_binding(db, pending_id, max_user_id):
    from app.services.access import (
        AccessServiceError,
        create_contact_access_links,
        create_invited_student_access_link,
        get_or_create_max_account,
    )

    # Binding writers lock the account before the pending row; preserve that order.
    existing = await db.scalar(select(PendingBinding.id).where(
        PendingBinding.id == pending_id, PendingBinding.max_user_id == max_user_id,
    ))
    if existing:
        await get_or_create_max_account(db, AccessLinkCreate(
            tenant_slug="pending", contact_id="pending", max_user_id=max_user_id,
            role=StudentAccessRole.PARENT,
        ))
    item = await db.scalar(select(PendingBinding).where(
        PendingBinding.id == pending_id, PendingBinding.max_user_id == max_user_id,
    ).with_for_update())
    if item is None:
        raise AccessServiceError("Это подключение не найдено для вашего аккаунта MAX.",
                                 code="pending_not_found")
    if item.status in {"cancelled", "expired"} or utc(item.expires_at) <= datetime.now(UTC):
        raise AccessServiceError("Время ожидания закончилось. Откройте свежую ссылку школы.",
                                 code="pending_expired")
    tenant, students, reason = await target_students(db, item)
    if reason not in {"ready", "already_connected"}:
        item.status = "pending" if reason in {
            "contact_not_found", "contact_has_no_students", "student_not_found",
        } else "review"
        item.reason = reason
        await db.commit()
        from app.services.audit_history import REASONS
        message = WAITING_MESSAGE if item.status == "pending" else (
            REASONS.get(reason, "Подключение требует проверки школы") + ". Обратитесь в школу."
        )
        raise AccessServiceError(
            message, code="pending_waiting" if item.status == "pending" else reason,
        )
    role, item_id = item.role, item.id
    if reason != "already_connected":
        if item.kind == "contact":
            await create_contact_access_links(db, AccessLinkCreate(
                tenant_slug=tenant.slug, contact_id=item.target_id, max_user_id=max_user_id,
                role=StudentAccessRole.PARENT,
            ))
        else:
            token = (issue_teacher_student_invitation_token(tenant.id, UUID(item.target_id))
                     if item.issuer == "teacher" else issue_student_invitation_token(
                         tenant.id, UUID(item.target_id), item.sponsor_link_id))
            await create_invited_student_access_link(db, StudentInvitationLinkCreate(
                tenant_slug=tenant.slug, token=token, max_user_id=max_user_id,
            ))
    await db.execute(update(PendingBinding).where(PendingBinding.id == item_id).values(
        status="completed", reason="connected",
    ))
    account_id = await db.scalar(select(MaxAccount.id).where(MaxAccount.max_user_id == max_user_id))
    db.add(AuditLog(tenant_id=tenant.id, actor_account_id=account_id,
                    action="pending_binding.confirmed", entity_type="pending_binding",
                    entity_id=str(item_id), payload={"max_user_id": max_user_id, "role": role,
                                                    "student_ids": [str(s.id) for s in students]}))
    await db.commit()
    return {"tenant_slug": tenant.slug, "role": role,
            "student_names": [student.display_name for student in students]}


async def process_pending_batch(db, *, client=None, now=None, tenant_ids=None):
    now = now or datetime.now(UTC)
    query = select(PendingBinding).where(
        PendingBinding.status.in_(OPEN_STATUSES),
        (PendingBinding.last_checked_at.is_(None)
         | (PendingBinding.last_checked_at < now - timedelta(seconds=30))),
    )
    if tenant_ids is not None:
        query = query.where(PendingBinding.tenant_id.in_(tenant_ids))
    rows = list(await db.scalars(query.order_by(
        func.coalesce(PendingBinding.last_checked_at, PendingBinding.created_at), PendingBinding.id,
    ).limit(1 if client else 50).with_for_update(skip_locked=True)))
    for item in rows:
        item.last_checked_at = now
        if utc(item.expires_at) <= now:
            item.status, item.reason = "expired", "pending_expired"
            record_event(db, item, "expired")
            continue
        tenant, _, reason = await target_students(db, item)
        if reason == "already_connected":
            item.status, item.reason = "completed", "connected"
            continue
        if reason != "ready":
            status = "pending" if reason in {
                "contact_not_found", "contact_has_no_students", "student_not_found",
            } else "review"
            changed = item.status != status or item.reason != reason
            if item.status == "ready":
                item.notified_at = None
            item.status = status
            item.reason = reason
            if changed:
                record_event(db, item, "waiting" if status == "pending" else "review")
            continue
        if item.status != "ready":
            item.status, item.reason = "ready", "ready"
            record_event(db, item, "ready")
        if client is None or item.notified_at or item.notification_attempts >= 10:
            continue
        backoff = min(3600, 60 * 2 ** min(item.notification_attempts, 6))
        if item.notification_attempted_at and utc(item.notification_attempted_at) > now - timedelta(
            seconds=backoff,
        ):
            continue
        from app.bot.keyboards import callback_button, inline_keyboard
        item.notification_attempts += 1
        item.notification_attempted_at = now
        attachments = inline_keyboard([
            [callback_button("Завершить подключение", f"pending:confirm:{item.id}")],
            [callback_button("Отменить ожидание", f"pending:cancel:{item.id}")],
        ])
        try:
            await asyncio.to_thread(client.send_message, user_id=item.max_user_id,
                                    text="Теперь можно завершить подключение к Algo MAX.\n\n"
                                    "Нажмите кнопку с аккаунта MAX, который хотите подключить.",
                                    attachments=attachments)
            item.notified_at, item.notification_error = now, None
            record_event(db, item, "notified")
        except Exception:
            item.notification_error = "Не удалось доставить уведомление в MAX"
            logger.warning("Pending binding notification failed: %s", item.id)
    await db.commit()
    return len(rows)


async def pending_binding_loop():
    from app.bot.max_client import MaxApiClient
    from app.core.config import get_settings, is_placeholder
    from app.db.session import AsyncSessionLocal

    settings = get_settings()
    client = None if is_placeholder(settings.max_bot_token) else MaxApiClient(
        token=str(settings.max_bot_token), base_url=settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
    )
    while True:
        count = 0
        try:
            async with AsyncSessionLocal() as db:
                count = await process_pending_batch(db, client=client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Pending binding worker failed")
        await asyncio.sleep(0.2 if count else 15)
