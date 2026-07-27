import hashlib
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.enums import StudentAccessSource, StudentAccessStatus, StudentStatus
from app.models.student import Contact, ContactStudentLink, Student, StudentAccessLink
from app.models.tenant import Tenant
from app.schemas.access import AccessLinkCreate, StudentResolveRequest


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


async def get_or_create_max_account(db: AsyncSession, payload: AccessLinkCreate) -> MaxAccount:
    account = await db.scalar(
        select(MaxAccount).where(MaxAccount.max_user_id == payload.max_user_id),
    )
    if account is not None:
        account.username = payload.username
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


async def create_contact_access_links(
    db: AsyncSession,
    payload: AccessLinkCreate,
) -> list[StudentAccessLink]:
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
        raise AccessServiceError("Contact ID was not found for this tenant")

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
        raise AccessServiceError("Contact ID has no linked students")

    account = await get_or_create_max_account(db, payload)
    links: list[StudentAccessLink] = []
    created = 0

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


async def create_student_access_link(
    db: AsyncSession,
    payload: AccessLinkCreate,
) -> StudentAccessLink:
    """Backward-compatible helper returning the first link from a contact binding."""
    links = await create_contact_access_links(db, payload)
    return links[0]
