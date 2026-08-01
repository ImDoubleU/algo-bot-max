from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_miniapp_identity,
    require_matching_miniapp_identity,
)
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.schemas.access import (
    AccessLinkBatchRead,
    AccessLinkCreate,
    AccessLinkRead,
    BotStoppedAccessRevoke,
    BotStoppedAccessRevokeRead,
    ContactResolveResponse,
    StudentAccessTarget,
    StudentInvitationLinkCreate,
    StudentInvitationLinkRead,
    StudentResolveRequest,
)
from app.services.access import (
    AccessServiceError,
    build_rate_limit_key,
    create_contact_access_links,
    create_invited_student_access_link,
    get_tenant_by_slug,
    record_student_access_attempt,
    resolve_students_by_contact_id,
    revoke_access_for_stopped_bot,
)
from app.services.rate_limit import student_id_entry_limiter

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
MiniAppIdentityDep = Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)]


@router.post("/resolve-contact", response_model=ContactResolveResponse)
async def resolve_contact(
    payload: StudentResolveRequest,
    db: DbSession,
) -> ContactResolveResponse:
    rate_limit = student_id_entry_limiter.check(build_rate_limit_key(payload))
    if not rate_limit.allowed:
        tenant = await get_tenant_by_slug(db, payload.tenant_slug)
        await record_student_access_attempt(
            db,
            payload=payload,
            action="contact_access.resolve_rate_limited",
            result="rate_limited",
            tenant=tenant,
            reason="too_many_attempts",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Try again later.",
            headers={"Retry-After": str(rate_limit.retry_after_seconds or 60)},
        )

    resolved = await resolve_students_by_contact_id(db, payload)
    if resolved is None:
        tenant = await get_tenant_by_slug(db, payload.tenant_slug)
        await record_student_access_attempt(
            db,
            payload=payload,
            action="contact_access.resolve_failed",
            result="not_found",
            tenant=tenant,
            reason="contact_id_not_found",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact ID was not found for this tenant",
        )

    contact, students = resolved
    await record_student_access_attempt(
        db,
        payload=payload,
        action="contact_access.resolve_success",
        result="success",
        tenant_id=contact.tenant_id,
    )
    await db.commit()
    return ContactResolveResponse(
        tenant_id=contact.tenant_id,
        contact_id=contact.external_contact_id,
        contact_display_name=contact.display_name,
        students=[
            StudentAccessTarget(
                student_id=student.id,
                display_name=student.display_name,
                group_name=student.group_name,
                venue_name=student.venue_name,
                teacher_name=student.teacher_name,
            )
            for student in students
        ],
    )


@router.post("/resolve-student", response_model=ContactResolveResponse)
async def resolve_student_legacy(
    payload: StudentResolveRequest,
    db: DbSession,
) -> ContactResolveResponse:
    return await resolve_contact(payload, db)


@router.post("/links", response_model=AccessLinkBatchRead, status_code=status.HTTP_201_CREATED)
async def create_link(
    payload: AccessLinkCreate,
    db: DbSession,
) -> AccessLinkBatchRead:
    try:
        links = await create_contact_access_links(db, payload)
    except AccessServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    tenant_id = UUID(str(links[0].tenant_id))
    return AccessLinkBatchRead(
        tenant_id=tenant_id,
        contact_id=payload.contact_id,
        links=[
            AccessLinkRead(
                id=UUID(str(link.id)),
                tenant_id=UUID(str(link.tenant_id)),
                account_id=UUID(str(link.account_id)),
                student_id=UUID(str(link.student_id)),
                role=link.role,
                status=link.status,
                source=link.source,
                sponsor_access_link_id=link.sponsor_access_link_id,
                revoked_reason=link.revoked_reason,
                created_at=link.created_at,
            )
            for link in links
        ],
    )


@router.post(
    "/student-invite",
    response_model=StudentInvitationLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_student_invite_link(
    payload: StudentInvitationLinkCreate,
    db: DbSession,
) -> StudentInvitationLinkRead:
    try:
        tenant, student, link = await create_invited_student_access_link(db, payload)
    except AccessServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return StudentInvitationLinkRead(
        tenant_slug=tenant.slug,
        student_id=UUID(str(student.id)),
        student_name=student.display_name,
        group_name=student.group_name,
        link=AccessLinkRead(
            id=UUID(str(link.id)),
            tenant_id=UUID(str(link.tenant_id)),
            account_id=UUID(str(link.account_id)),
            student_id=UUID(str(link.student_id)),
            role=link.role,
            status=link.status,
            source=link.source,
            sponsor_access_link_id=link.sponsor_access_link_id,
            revoked_reason=link.revoked_reason,
            created_at=link.created_at,
        ),
    )


@router.post("/bot-stopped", response_model=BotStoppedAccessRevokeRead)
async def revoke_stopped_bot_access(
    payload: BotStoppedAccessRevoke,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> BotStoppedAccessRevokeRead:
    require_matching_miniapp_identity(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    account_links, child_links, affected_tenants = (
        await revoke_access_for_stopped_bot(db, payload)
    )
    return BotStoppedAccessRevokeRead(
        max_user_id=payload.max_user_id,
        revoked_account_links=account_links,
        revoked_child_links=child_links,
        affected_tenants=affected_tenants,
    )
