import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.enums import (
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.models.tenant import Tenant
from app.schemas.access import (
    AccessLinkCreate,
    BotStoppedAccessRevoke,
    StudentInvitationLinkCreate,
    StudentResolveRequest,
)
from app.services.student_invitations import (
    StudentInvitationError,
    verify_student_invitation_token,
)


class AccessServiceError(RuntimeError):
    pass


def normalize_contact_id(value: str) -> str:
    return "".join(value.strip().upper().split())


def normalize_student_code(value: str) -> str:
    """Backward-compatible alias for older tests and transitional code."""
    return normalize_contact_id(value)


def hash_contact_id(value: str) -> str:
    settings = get_settings()
    normalized = normalize_contact_id(value)
    material = f"{settings.app_secret_key}:{normalized}".encode()
    return hashlib.sha256(material).hexdigest()


def hash_student_code(value: str) -> str:
    """Backward-compatible alias for older tests and transitional code."""
    return hash_contact_id(value)


def build_rate_limit_key(payload: StudentResolveRequest | AccessLinkCreate) -> str:
    actor = getattr(payload, "max_user_id", None) or "anonymous"
    tenant = payload.tenant_slug.strip().lower()
    return f"contact-id-entry:{tenant}:{actor}"


async def get_tenant_by_slug(db: AsyncSession, tenant_slug: str) -> Tenant | None:
    stmt = select(Tenant).where(Tenant.slug == tenant_slug.strip().lower())
    return await db.scalar(stmt)


async def resolve_contact_by_id(
    db: AsyncSession,
    payload: StudentResolveRequest,
) -> Contact | None:
    tenant = await get_tenant_by_slug(db, payload.tenant_slug)
    if tenant is None:
        return None

    contact_id = normalize_contact_id(payload.contact_id)
    stmt = select(Contact).where(
        Contact.tenant_id == tenant.id,
        Contact.external_contact_id == contact_id,
    )
    return await db.scalar(stmt)


async def resolve_students_by_contact_id(
    db: AsyncSession,
    payload: StudentResolveRequest,
) -> tuple[Contact, list[Student]] | None:
    contact = await resolve_contact_by_id(db, payload)
    if contact is None:
        return None

    stmt = (
        select(Student)
        .join(ContactStudentLink, ContactStudentLink.student_id == Student.id)
        .where(
            ContactStudentLink.tenant_id == contact.tenant_id,
            ContactStudentLink.contact_id == contact.id,
            Student.status == StudentStatus.ACTIVE,
        )
        .order_by(Student.first_name, Student.last_name)
    )
    return contact, list((await db.scalars(stmt)).all())


async def record_student_access_attempt(
    db: AsyncSession,
    *,
    payload: StudentResolveRequest | AccessLinkCreate,
    action: str,
    result: str,
    tenant: Tenant | None = None,
    tenant_id: UUID | None = None,
    account: MaxAccount | None = None,
    student: Student | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        AuditLog(
            tenant_id=tenant_id or (tenant.id if tenant else None),
            actor_account_id=account.id if account else None,
            action=action,
            entity_type="contact_access",
            entity_id=str(student.id) if student else None,
            payload={
                "result": result,
                "tenant_slug": payload.tenant_slug.strip().lower(),
                "contact_id_hash": hash_contact_id(payload.contact_id),
                "max_user_id": getattr(payload, "max_user_id", None),
                "reason": reason,
            },
        ),
    )


async def get_or_create_max_account(
    db: AsyncSession,
    payload: AccessLinkCreate | StudentInvitationLinkCreate,
) -> MaxAccount:
    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id),
    )
    if account is not None:
        if payload.username is not None:
            account.username = payload.username
        if payload.display_name is not None:
            account.display_name = payload.display_name
        return account

    account = MaxAccount(
        max_user_id=payload.max_user_id,
        username=payload.username,
        display_name=payload.display_name,
    )
    db.add(account)
    await db.flush()
    return account


async def _active_account_role_link_id(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    role: StudentAccessRole,
) -> UUID | None:
    link_id = await db.scalar(
        select(StudentAccessLink.id)
        .where(
            StudentAccessLink.tenant_id == tenant_id,
            StudentAccessLink.account_id == account_id,
            StudentAccessLink.role == role,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
        .limit(1)
    )
    return UUID(str(link_id)) if link_id is not None else None


async def revoke_dependent_student_links(
    db: AsyncSession,
    *,
    parent_links: list[StudentAccessLink],
    revoked_at: datetime | None = None,
    reason: str = "sponsor_revoked",
) -> list[StudentAccessLink]:
    parents = [
        link for link in parent_links if link.role == StudentAccessRole.PARENT
    ]
    if not parents:
        return []

    revoked_at = revoked_at or datetime.now(UTC)
    parent_ids = [link.id for link in parents]
    dependent_by_id: dict[UUID, StudentAccessLink] = {}

    sponsored_links = (
        await db.scalars(
            select(StudentAccessLink).where(
                StudentAccessLink.sponsor_access_link_id.in_(parent_ids),
                StudentAccessLink.role == StudentAccessRole.STUDENT,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            )
        )
    ).all()
    for link in sponsored_links:
        dependent_by_id[UUID(str(link.id))] = link

    # Links created by older QR codes have no sponsor reference. Revoke them
    # only when the student has no other active parent connection.
    scopes = {(link.tenant_id, link.student_id) for link in parents}
    for tenant_id, student_id in scopes:
        other_parent_id = await db.scalar(
            select(StudentAccessLink.id)
            .where(
                StudentAccessLink.tenant_id == tenant_id,
                StudentAccessLink.student_id == student_id,
                StudentAccessLink.role == StudentAccessRole.PARENT,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                ~StudentAccessLink.id.in_(parent_ids),
            )
            .limit(1)
        )
        if other_parent_id is not None:
            continue
        legacy_links = (
            await db.scalars(
                select(StudentAccessLink).where(
                    StudentAccessLink.tenant_id == tenant_id,
                    StudentAccessLink.student_id == student_id,
                    StudentAccessLink.role == StudentAccessRole.STUDENT,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                    StudentAccessLink.sponsor_access_link_id.is_(None),
                )
            )
        ).all()
        for link in legacy_links:
            dependent_by_id[UUID(str(link.id))] = link

    for link in dependent_by_id.values():
        link.status = StudentAccessStatus.REVOKED
        link.revoked_at = revoked_at
        link.revoked_reason = reason
    return list(dependent_by_id.values())


async def revoke_access_for_stopped_bot(
    db: AsyncSession,
    payload: BotStoppedAccessRevoke,
) -> tuple[int, int, int]:
    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id)
    )
    if account is None:
        return 0, 0, 0

    account_links = list(
        (
            await db.scalars(
                select(StudentAccessLink).where(
                    StudentAccessLink.account_id == account.id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
            )
        ).all()
    )
    if not account_links:
        return 0, 0, 0

    revoked_at = datetime.now(UTC)
    for link in account_links:
        link.status = StudentAccessStatus.REVOKED
        link.revoked_at = revoked_at
        link.revoked_reason = payload.reason

    child_links = await revoke_dependent_student_links(
        db,
        parent_links=account_links,
        revoked_at=revoked_at,
        reason="sponsor_bot_stopped",
    )
    affected_tenant_ids = {
        link.tenant_id for link in [*account_links, *child_links]
    }
    for tenant_id in affected_tenant_ids:
        db.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_account_id=account.id,
                action="max_bot_access.revoked",
                entity_type="max_account",
                entity_id=str(account.id),
                payload={
                    "max_user_id": payload.max_user_id,
                    "reason": payload.reason,
                    "revoked_account_links": sum(
                        link.tenant_id == tenant_id for link in account_links
                    ),
                    "revoked_child_links": sum(
                        link.tenant_id == tenant_id for link in child_links
                    ),
                },
            )
        )
    await db.commit()
    return len(account_links), len(child_links), len(affected_tenant_ids)


async def create_contact_access_links(
    db: AsyncSession,
    payload: AccessLinkCreate,
) -> list[StudentAccessLink]:
    if payload.role != StudentAccessRole.PARENT:
        raise AccessServiceError(
            "Contact ID используется только для входа родителя. "
            "Ученик входит по QR-коду из кабинета родителя"
        )

    resolved = await resolve_students_by_contact_id(
        db,
        StudentResolveRequest(tenant_slug=payload.tenant_slug, contact_id=payload.contact_id),
    )
    if resolved is None:
        tenant = await get_tenant_by_slug(db, payload.tenant_slug)
        await record_student_access_attempt(
            db,
            payload=payload,
            action="contact_access_link.failed",
            result="not_found",
            tenant=tenant,
            reason="contact_id_not_found",
        )
        await db.commit()
        raise AccessServiceError("ID из письма не найден для выбранного города")

    contact, students = resolved
    if not students:
        await record_student_access_attempt(
            db,
            payload=payload,
            action="contact_access_link.failed",
            result="no_students",
            tenant_id=contact.tenant_id,
            reason="contact_has_no_students",
        )
        await db.commit()
        raise AccessServiceError("К этому ID не привязаны ученики")

    account = await get_or_create_max_account(db, payload)
    active_student_link_id = await _active_account_role_link_id(
        db,
        tenant_id=UUID(str(contact.tenant_id)),
        account_id=UUID(str(account.id)),
        role=StudentAccessRole.STUDENT,
    )
    if active_student_link_id is not None:
        raise AccessServiceError(
            "Этот MAX-профиль уже используется учеником. "
            "Для родительского кабинета откройте ссылку с профиля родителя"
        )
    links: list[StudentAccessLink] = []
    created = 0
    reactivated = 0

    for student in students:
        existing = await db.scalar(
            select(StudentAccessLink).where(
                StudentAccessLink.tenant_id == student.tenant_id,
                StudentAccessLink.account_id == account.id,
                StudentAccessLink.student_id == student.id,
                StudentAccessLink.role == payload.role,
            ),
        )
        if existing is not None:
            if (
                payload.role == StudentAccessRole.PARENT
                and existing.status == StudentAccessStatus.REVOKED
                and existing.revoked_reason == "bot_stopped"
            ):
                existing.status = StudentAccessStatus.ACTIVE
                existing.revoked_at = None
                existing.revoked_reason = None
                reactivated += 1
            elif existing.status == StudentAccessStatus.REVOKED:
                raise AccessServiceError(
                    "Связь была отозвана администратором. Обратитесь в школу"
                )
            links.append(existing)
            continue

        link = StudentAccessLink(
            tenant_id=student.tenant_id,
            account_id=account.id,
            student_id=student.id,
            role=payload.role,
            status=StudentAccessStatus.ACTIVE,
            source=StudentAccessSource.ID_ENTRY,
        )
        db.add(link)
        await db.flush()
        links.append(link)
        created += 1

    db.add(
        AuditLog(
            tenant_id=contact.tenant_id,
            actor_account_id=account.id,
            action="contact_access_links.created",
            entity_type="contact_access",
            entity_id=str(contact.id),
            payload={
                "contact_id_hash": hash_contact_id(payload.contact_id),
                "student_ids": [str(student.id) for student in students],
                "created_links": created,
                "reactivated_links": reactivated,
                "total_links": len(links),
                "role": payload.role.value,
                "source": StudentAccessSource.ID_ENTRY.value,
            },
        ),
    )
    await db.commit()
    for link in links:
        await db.refresh(link)
    return links


async def create_invited_student_access_link(
    db: AsyncSession,
    payload: StudentInvitationLinkCreate,
) -> tuple[Tenant, Student, StudentAccessLink]:
    try:
        (
            token_tenant_id,
            student_id,
            sponsor_access_link_id,
        ) = verify_student_invitation_token(payload.token)
    except StudentInvitationError as exc:
        raise AccessServiceError(str(exc)) from exc
    if sponsor_access_link_id is None:
        raise AccessServiceError(
            "QR-код устарел. Попросите родителя получить новый код в личном кабинете."
        )
    tenant = await db.scalar(select(Tenant).where(Tenant.id == token_tenant_id))
    if tenant is None:
        raise AccessServiceError("Школа из ссылки не найдена")
    student = await db.scalar(
        select(Student).where(
            Student.id == student_id,
            Student.tenant_id == tenant.id,
            Student.status == StudentStatus.ACTIVE,
        )
    )
    if student is None:
        raise AccessServiceError("Student was not found for this tenant")

    sponsor_link = await db.scalar(
        select(StudentAccessLink).where(
            StudentAccessLink.id == sponsor_access_link_id,
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.student_id == student.id,
            StudentAccessLink.role == StudentAccessRole.PARENT,
            StudentAccessLink.status == StudentAccessStatus.ACTIVE,
        )
    )
    if sponsor_link is None:
        raise AccessServiceError(
            "Родительская связь больше не активна. Получите новый QR-код."
        )

    account = await get_or_create_max_account(db, payload)
    active_parent_link_id = await _active_account_role_link_id(
        db,
        tenant_id=UUID(str(tenant.id)),
        account_id=UUID(str(account.id)),
        role=StudentAccessRole.PARENT,
    )
    if active_parent_link_id is not None:
        raise AccessServiceError(
            "Этот MAX-профиль уже используется родителем. "
            "Откройте QR-код с профиля ребенка"
        )
    link = await db.scalar(
        select(StudentAccessLink).where(
            StudentAccessLink.tenant_id == tenant.id,
            StudentAccessLink.account_id == account.id,
            StudentAccessLink.student_id == student.id,
            StudentAccessLink.role == StudentAccessRole.STUDENT,
        )
    )
    created = link is None
    if link is None:
        link = StudentAccessLink(
            tenant_id=tenant.id,
            account_id=account.id,
            student_id=student.id,
            role=StudentAccessRole.STUDENT,
            status=StudentAccessStatus.ACTIVE,
            source=StudentAccessSource.PARENT_QR,
            sponsor_access_link_id=sponsor_link.id,
        )
        db.add(link)
        await db.flush()
    else:
        link.status = StudentAccessStatus.ACTIVE
        link.source = StudentAccessSource.PARENT_QR
        link.sponsor_access_link_id = sponsor_link.id
        link.revoked_at = None
        link.revoked_reason = None

    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="student_qr_access_link.created",
            entity_type="student_access",
            entity_id=str(student.id),
            payload={
                "created": created,
                "max_user_id": payload.max_user_id,
                "source": StudentAccessSource.PARENT_QR.value,
                "sponsor_access_link_id": str(sponsor_link.id),
            },
        )
    )
    await db.commit()
    await db.refresh(link)
    return tenant, student, link


async def create_student_access_link(
    db: AsyncSession,
    payload: AccessLinkCreate,
) -> StudentAccessLink:
    """Backward-compatible helper returning the first link from a contact binding."""
    links = await create_contact_access_links(db, payload)
    return links[0]
