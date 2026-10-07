import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from functools import wraps
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.binding_diagnostics import binding_request_id
from app.core.config import get_settings
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.enums import (
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
)
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.models.tenant import Tenant
from app.schemas.access import (
    AccessLinkCreate,
    BotStoppedAccessRevoke,
    StudentInvitationLinkCreate,
    StudentResolveRequest,
)
from app.services.student_access_policy import student_access_window
from app.services.student_invitations import (
    StudentInvitationError,
    StudentInvitationIssuer,
    verify_student_invitation_details,
)

logger = logging.getLogger(__name__)


class AccessServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "binding_failed"):
        super().__init__(message)
        self.code = code


def audited_binding(function):
    """Undo incomplete family writes before persisting a rejected binding."""

    @wraps(function)
    async def wrapped(db, payload):
        try:
            return await function(db, payload)
        except AccessServiceError as exc:
            await db.rollback()
            tenant = await get_tenant_by_slug(db, payload.tenant_slug)
            fields = {
                "request_id": binding_request_id(),
                "result": "failed",
                "reason": exc.code,
                "max_user_id": payload.max_user_id,
                "tenant_slug": payload.tenant_slug.strip().lower(),
                "role": getattr(payload, "role", StudentAccessRole.STUDENT).value,
            }
            contact_binding = isinstance(payload, AccessLinkCreate)
            if contact_binding:
                fields["contact_id_hash"] = hash_contact_id(payload.contact_id)
            else:
                fields["invitation_hash"] = hashlib.sha256(
                    f"{get_settings().app_secret_key}:invitation:{payload.token}".encode()
                ).hexdigest()
                try:
                    invitation = verify_student_invitation_details(payload.token)
                except StudentInvitationError:
                    pass
                else:
                    fields["student_id"] = str(invitation.student_id)
                    fields["invitation_tenant_id"] = str(invitation.tenant_id)
                    fields["issuer"] = invitation.issuer.value
            db.add(
                AuditLog(
                    tenant_id=tenant.id if tenant else None,
                    action="contact_access_link.failed"
                    if contact_binding
                    else "student_qr_access_link.failed",
                    entity_type="contact_access" if contact_binding else "student_access",
                    payload=fields,
                )
            )
            await db.commit()
            logger.info("binding_failed %s", json.dumps(fields, ensure_ascii=False))
            raise

    return wrapped


PARENT_REQUIRED_MESSAGE = (
    "Сначала должен подключиться родитель. Попросите родителя открыть "
    "письмо школы "
    "и перейти по персональной ссылке."
)


def normalize_contact_id(value: str) -> str:
    normalized = "".join(value.strip().upper().split())
    match = re.fullmatch(r"([0-9]+)[.]0+", normalized)
    return match.group(1) if match else normalized


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

    tenant = await db.scalar(select(Tenant).where(Tenant.id == contact.tenant_id))
    if tenant is None:
        return None

    stmt = (
        select(Student)
        .join(ContactStudentLink, ContactStudentLink.student_id == Student.id)
        .where(
            ContactStudentLink.tenant_id == contact.tenant_id,
            ContactStudentLink.contact_id == contact.id,
        )
        .order_by(Student.first_name, Student.last_name)
    )
    students = list((await db.scalars(stmt)).all())
    return contact, [
        student for student in students if student_access_window(student, tenant).allowed
    ]


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
    logger.info(
        "binding_attempt %s",
        json.dumps(
            {
                "request_id": binding_request_id(),
                "stage": action,
                "result": result,
                "reason": reason,
                "max_user_id": getattr(payload, "max_user_id", None),
                "tenant_slug": payload.tenant_slug.strip().lower(),
                "contact_id_hash": hash_contact_id(payload.contact_id),
            },
            ensure_ascii=False,
        ),
    )
    db.add(
        AuditLog(
            tenant_id=tenant_id or (tenant.id if tenant else None),
            actor_account_id=account.id if account else None,
            action=action,
            entity_type="contact_access",
            entity_id=str(student.id) if student else None,
            payload={
                "request_id": binding_request_id(),
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
    # A row lock cannot serialize a first-ever account lookup and insert.
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": -(payload.max_user_id % (2**63 - 1))},
        )
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


async def ensure_single_account_binding(
    db: AsyncSession,
    *,
    account_id: UUID,
    tenant_id: UUID,
    student_id: UUID,
    role: StudentAccessRole,
) -> None:
    # Serialize every binding writer for this MAX account, across all schools.
    await db.scalar(select(MaxAccount.id).where(MaxAccount.id == account_id).with_for_update())
    links = (
        await db.scalars(
            select(StudentAccessLink).where(
                StudentAccessLink.account_id == account_id,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
            )
        )
    ).all()
    for link in links:
        if link.role != role:
            if link.role == StudentAccessRole.STUDENT:
                raise AccessServiceError(
                    "Этот MAX-профиль уже используется учеником. "
                    "Для родительского кабинета откройте ссылку с профиля родителя",
                    code="account_role_conflict",
                )
            raise AccessServiceError(
                "Этот MAX-профиль уже используется родителем. Откройте QR-код с профиля ребенка",
                code="account_role_conflict",
            )
        if role == StudentAccessRole.STUDENT and (
            link.tenant_id != tenant_id or link.student_id != student_id
        ):
            raise AccessServiceError(
                "Этот MAX-аккаунт уже привязан к другому ученику. "
                "Сначала попросите школу снять прежнюю привязку.",
                code="student_already_bound",
            )


async def get_active_parent_access_link(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    student_id: UUID,
    sponsor_access_link_id: UUID | None = None,
) -> StudentAccessLink | None:
    query = select(StudentAccessLink).where(
        StudentAccessLink.tenant_id == tenant_id,
        StudentAccessLink.student_id == student_id,
        StudentAccessLink.role == StudentAccessRole.PARENT,
        StudentAccessLink.status == StudentAccessStatus.ACTIVE,
    )
    if sponsor_access_link_id is not None:
        query = query.where(StudentAccessLink.id == sponsor_access_link_id)
    return await db.scalar(query.order_by(StudentAccessLink.created_at).limit(1))


async def get_effective_customer_access_link(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account_id: UUID,
    student_id: UUID,
    required_role: StudentAccessRole | None = None,
) -> StudentAccessLink | None:
    query = select(StudentAccessLink).where(
        StudentAccessLink.tenant_id == tenant_id,
        StudentAccessLink.account_id == account_id,
        StudentAccessLink.student_id == student_id,
        StudentAccessLink.status == StudentAccessStatus.ACTIVE,
    )
    if required_role is not None:
        query = query.where(StudentAccessLink.role == required_role)
    links = list((await db.scalars(query.order_by(StudentAccessLink.created_at))).all())
    parent_link = next(
        (link for link in links if link.role == StudentAccessRole.PARENT),
        None,
    )
    if parent_link is not None:
        return parent_link

    student_link = next(
        (link for link in links if link.role == StudentAccessRole.STUDENT),
        None,
    )
    if student_link is None:
        return None
    active_parent = await get_active_parent_access_link(
        db,
        tenant_id=tenant_id,
        student_id=student_id,
        sponsor_access_link_id=student_link.sponsor_access_link_id,
    )
    return student_link if active_parent is not None else None


async def revoke_dependent_student_links(
    db: AsyncSession,
    *,
    parent_links: list[StudentAccessLink],
    revoked_at: datetime | None = None,
    reason: str = "sponsor_revoked",
) -> list[StudentAccessLink]:
    parents = [link for link in parent_links if link.role == StudentAccessRole.PARENT]
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
    affected_tenant_ids = {link.tenant_id for link in [*account_links, *child_links]}
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
                    "revoked_child_links": sum(link.tenant_id == tenant_id for link in child_links),
                },
            )
        )
    await db.commit()
    return len(account_links), len(child_links), len(affected_tenant_ids)


@audited_binding
async def create_contact_access_links(
    db: AsyncSession,
    payload: AccessLinkCreate,
) -> list[StudentAccessLink]:
    if payload.role != StudentAccessRole.PARENT:
        raise AccessServiceError(
            "Contact ID используется только для входа родителя. "
            "Ученик входит по QR-коду из кабинета родителя или преподавателя.",
            code="student_qr_required",
        )

    resolved = await resolve_students_by_contact_id(
        db,
        StudentResolveRequest(tenant_slug=payload.tenant_slug, contact_id=payload.contact_id),
    )
    if resolved is None:
        raise AccessServiceError(
            "Семья по этой ссылке не найдена. Проверьте город и откройте ссылку "
            "из последнего письма школы. Если не получается, обратитесь в школу.",
            code="contact_not_found",
        )

    contact, students = resolved
    if not students:
        raise AccessServiceError(
            "По этой ссылке сейчас нет доступных учеников. Попросите школу "
            "проверить данные семьи и статус обучения.",
            code="contact_has_no_students",
        )

    account = await get_or_create_max_account(db, payload)
    await ensure_single_account_binding(
        db,
        account_id=account.id,
        tenant_id=contact.tenant_id,
        student_id=students[0].id,
        role=StudentAccessRole.PARENT,
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
                and existing.revoked_reason in {"bot_stopped", "registration_reset"}
            ):
                existing.status = StudentAccessStatus.ACTIVE
                existing.revoked_at = None
                existing.revoked_reason = None
                reactivated += 1
            elif existing.status == StudentAccessStatus.REVOKED:
                raise AccessServiceError(
                    "Связь была отозвана администратором. Обратитесь в школу", code="access_revoked"
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
                "request_id": binding_request_id(),
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
    logger.info(
        "binding_completed %s",
        json.dumps(
            {
                "binding": {
                    "request_id": binding_request_id(),
                    "max_user_id": payload.max_user_id,
                    "tenant_slug": payload.tenant_slug,
                    "role": payload.role.value,
                    "created_links": created,
                    "reactivated_links": reactivated,
                    "total_links": len(links),
                }
            },
            ensure_ascii=False,
        ),
    )
    for link in links:
        await db.refresh(link)
    return links


@audited_binding
async def create_invited_student_access_link(
    db: AsyncSession,
    payload: StudentInvitationLinkCreate,
) -> tuple[Tenant, Student, StudentAccessLink]:
    try:
        invitation = verify_student_invitation_details(payload.token)
    except StudentInvitationError as exc:
        raise AccessServiceError(
            "Ссылка ученика повреждена или не подходит для подключения. Попросите "
            "родителя или преподавателя показать новый QR-код и отсканируйте его "
            "снова.",
            code="invitation_invalid",
        ) from exc
    if invitation.issuer == StudentInvitationIssuer.LEGACY:
        raise AccessServiceError(
            "QR-код устарел. Попросите преподавателя или родителя получить новый код.",
            code="invitation_legacy",
        )
    tenant = await db.scalar(select(Tenant).where(Tenant.id == invitation.tenant_id))
    if tenant is None:
        raise AccessServiceError(
            "Школа по этой ссылке не найдена. Попросите школу прислать актуальную ссылку.",
            code="school_not_found",
        )
    student = await db.scalar(
        select(Student).where(
            Student.id == invitation.student_id,
            Student.tenant_id == tenant.id,
        )
    )
    if student is None:
        raise AccessServiceError(
            "Ученик по этой ссылке не найден. Попросите преподавателя проверить "
            "профиль и показать новый QR-код.",
            code="student_not_found",
        )
    if not student_access_window(student, tenant).allowed:
        raise AccessServiceError(
            "Срок доступа после завершения обучения истек. Обратитесь в школу.",
            code="student_access_closed",
        )

    sponsor_link: StudentAccessLink | None = None
    if invitation.issuer == StudentInvitationIssuer.PARENT:
        sponsor_link = await get_active_parent_access_link(
            db,
            tenant_id=UUID(str(tenant.id)),
            student_id=UUID(str(student.id)),
            sponsor_access_link_id=invitation.sponsor_access_link_id,
        )
        if sponsor_link is None:
            raise AccessServiceError(
                "Родительская связь больше не активна. Родителю нужно открыть "
                "персональную ссылку из письма школы, затем показать новый QR-код "
                "ученику.",
                code="parent_link_inactive",
            )
    else:
        sponsor_link = await get_active_parent_access_link(
            db,
            tenant_id=UUID(str(tenant.id)),
            student_id=UUID(str(student.id)),
        )

    account = await get_or_create_max_account(db, payload)
    await ensure_single_account_binding(
        db,
        account_id=account.id,
        tenant_id=tenant.id,
        student_id=student.id,
        role=StudentAccessRole.STUDENT,
    )
    link_source = (
        StudentAccessSource.PARENT_QR
        if invitation.issuer == StudentInvitationIssuer.PARENT
        else StudentAccessSource.TEACHER_QR
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
            source=link_source,
            sponsor_access_link_id=sponsor_link.id if sponsor_link else None,
        )
        db.add(link)
        await db.flush()
    else:
        if link.status == StudentAccessStatus.REVOKED and link.revoked_reason not in {
            "bot_stopped",
            "registration_reset",
            "sponsor_bot_stopped",
            "sponsor_revoked",
            "parent_required_hotfix",
        }:
            raise AccessServiceError(
                "Связь ученика была отключена школой. Попросите школу проверить "
                "привязку перед повторным подключением.",
                code="access_revoked",
            )
        link.status = StudentAccessStatus.ACTIVE
        link.source = link_source
        link.sponsor_access_link_id = sponsor_link.id if sponsor_link else None
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
                "request_id": binding_request_id(),
                "created": created,
                "max_user_id": payload.max_user_id,
                "source": link_source.value,
                "sponsor_access_link_id": str(sponsor_link.id) if sponsor_link else None,
            },
        )
    )
    await db.commit()
    await db.refresh(link)
    logger.info(
        "binding_completed %s",
        json.dumps(
            {
                "binding": {
                    "request_id": binding_request_id(),
                    "max_user_id": payload.max_user_id,
                    "tenant_slug": tenant.slug,
                    "role": "student",
                    "student_id": str(student.id),
                    "created": created,
                    "source": link_source.value,
                    "parent_connected": sponsor_link is not None,
                }
            },
            ensure_ascii=False,
        ),
    )
    return tenant, student, link


async def create_student_access_link(
    db: AsyncSession,
    payload: AccessLinkCreate,
) -> StudentAccessLink:
    """Backward-compatible helper returning the first link from a contact binding."""
    links = await create_contact_access_links(db, payload)
    return links[0]
