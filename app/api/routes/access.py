from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_miniapp_identity,
    require_matching_miniapp_identity,
)
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.account import MaxAccount
from app.models.pending_binding import PendingBinding
from app.models.student import Contact, ContactStudentLink, Student
from app.models.support import SupportTicket
from app.models.tenant import City, Partner
from app.schemas.access import (
    AccessLinkBatchRead,
    AccessLinkCreate,
    AccessLinkRead,
    BotStoppedAccessRevoke,
    BotStoppedAccessRevokeRead,
    ContactResolveResponse,
    PendingBindingAction,
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
from app.services.staff import configured_superadmin_max_user_id

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
MiniAppIdentityDep = Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)]


@router.post("/resolve-contact", response_model=ContactResolveResponse)
async def resolve_contact(
    payload: StudentResolveRequest,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> ContactResolveResponse:
    if payload.max_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="MAX user_id is required",
        )
    require_matching_miniapp_identity(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
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
            detail="Слишком много попыток подключения подряд. Подождите минуту и "
            "откройте ссылку снова.",
            headers={
                "Retry-After": str(rate_limit.retry_after_seconds or 60),
                "X-Access-Error-Code": "too_many_attempts",
            },
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
        from app.services.pending_bindings import WAITING_MESSAGE, remember_missing_binding
        pending = await remember_missing_binding(db, payload, "contact_not_found")
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=WAITING_MESSAGE if pending else "Семья по этой ссылке не найдена. "
            "Проверьте выбранный город и "
            "откройте ссылку из последнего письма школы. Если не получается, "
            "обратитесь в школу.",
            headers={"X-Access-Error-Code": "pending_waiting" if pending else "contact_not_found"},
        )

    contact, students = resolved
    if not students:
        from app.services.pending_bindings import WAITING_MESSAGE, remember_missing_binding
        pending = await remember_missing_binding(db, payload, "contact_has_no_students")
        if pending:
            await db.commit()
            raise HTTPException(404, WAITING_MESSAGE,
                                headers={"X-Access-Error-Code": "pending_waiting"})
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
    identity: MiniAppIdentityDep,
) -> ContactResolveResponse:
    return await resolve_contact(payload, db, identity)


@router.post("/links", response_model=AccessLinkBatchRead, status_code=status.HTTP_201_CREATED)
async def create_link(
    payload: AccessLinkCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> AccessLinkBatchRead:
    require_matching_miniapp_identity(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    rate_limit = student_id_entry_limiter.check(f"{build_rate_limit_key(payload)}:create-link")
    if not rate_limit.allowed:
        tenant = await get_tenant_by_slug(db, payload.tenant_slug)
        await record_student_access_attempt(
            db,
            payload=payload,
            action="contact_access_link.rate_limited",
            result="rate_limited",
            tenant=tenant,
            reason="too_many_attempts",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток подключения подряд. Подождите минуту и "
            "откройте ссылку снова.",
            headers={
                "Retry-After": str(rate_limit.retry_after_seconds or 60),
                "X-Access-Error-Code": "too_many_attempts",
            },
        )
    try:
        links = await create_contact_access_links(db, payload)
    except AccessServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            headers={"X-Access-Error-Code": exc.code},
        ) from exc

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
    identity: MiniAppIdentityDep,
) -> StudentInvitationLinkRead:
    require_matching_miniapp_identity(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        tenant, student, link = await create_invited_student_access_link(db, payload)
    except AccessServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            headers={"X-Access-Error-Code": exc.code},
        ) from exc
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


@router.get("/pending")
async def pending_bindings_inbox(
    db: DbSession, identity: MiniAppIdentityDep, response: Response,
    tenant_slug: str = Query(min_length=2, max_length=80),
    search: str = Query(default="", max_length=100),
    filter_status: str = Query(
        default="open", pattern="^(open|ready|review|expired|completed|cancelled)$",
    ),
    offset: int = Query(default=0, ge=0), limit: int = Query(default=30, ge=1, le=100),
):
    if identity is None:
        raise HTTPException(401, "Откройте приложение из MAX")
    if identity.max_user_id != configured_superadmin_max_user_id():
        raise HTTPException(403, "Ожидающие подключения доступны суперадминистратору")
    response.headers["Cache-Control"] = "private, no-store"
    tenant = await get_tenant_by_slug(db, tenant_slug)
    if tenant is None:
        raise HTTPException(404, "Школа не найдена")
    from app.services.pending_bindings import OPEN_STATUSES
    conditions = [PendingBinding.tenant_id == tenant.id]
    conditions.append(PendingBinding.status.in_(OPEN_STATUSES) if filter_status == "open"
                      else PendingBinding.status == filter_status)
    if search.strip():
        needle = f"%{search.strip()}%"
        conditions.append(or_(PendingBinding.target_id.ilike(needle),
                              cast(PendingBinding.max_user_id, String).ilike(needle),
                              MaxAccount.display_name.ilike(needle),
                              MaxAccount.username.ilike(needle)))
    joined = select(PendingBinding, MaxAccount).outerjoin(
        MaxAccount, MaxAccount.max_user_id == PendingBinding.max_user_id,
    ).where(*conditions)
    total = await db.scalar(select(func.count()).select_from(joined.subquery()))
    rows = (await db.execute(joined.order_by(
        PendingBinding.last_attempt_at.desc(), PendingBinding.id,
    ).offset(offset).limit(limit))).all()
    ticket_names = {}
    for ticket in await db.scalars(select(SupportTicket).where(
        SupportTicket.max_user_id.in_([item.max_user_id for item, _ in rows]),
    ).order_by(SupportTicket.created_at.desc())):
        ticket_names.setdefault(ticket.max_user_id, f"{ticket.last_name} {ticket.first_name}")
    contact_targets = [item.target_id for item, _ in rows if item.kind == "contact"]
    student_targets = [UUID(item.target_id) for item, _ in rows if item.kind == "student"]
    related = {}
    for external_id, student in await db.execute(
        select(Contact.external_contact_id, Student)
        .join(ContactStudentLink, ContactStudentLink.contact_id == Contact.id)
        .join(Student, Student.id == ContactStudentLink.student_id)
        .where(Contact.tenant_id == tenant.id, Student.tenant_id == tenant.id,
               ContactStudentLink.tenant_id == tenant.id,
               Contact.external_contact_id.in_(contact_targets))
    ):
        related.setdefault(("contact", external_id), []).append(student)
    for student in await db.scalars(select(Student).where(
        Student.id.in_(student_targets), Student.tenant_id == tenant.id,
    )):
        related[("student", str(student.id))] = [student]
    school = (await db.execute(select(City.name, Partner.name).join(
        Partner, Partner.id == tenant.partner_id,
    ).where(City.id == tenant.city_id))).one()
    return {"total": total, "items": [{
        "id": str(item.id), "max_user_id": str(item.max_user_id), "role": item.role,
        "kind": item.kind,
        "target_id": None if item.target_id.startswith("sha256:") else item.target_id,
        "status": item.status, "reason": item.reason,
        "name": (account.display_name if account else None) or ticket_names.get(item.max_user_id),
        "name_source": "max" if account and account.display_name else "ticket",
        "username": account.username if account else None,
        "tenant_slug": tenant.slug, "school": " · ".join(school),
        "attempts": item.attempts, "created_at": item.created_at,
        "last_attempt_at": item.last_attempt_at, "expires_at": item.expires_at,
        "notified_at": item.notified_at, "notification_attempts": item.notification_attempts,
        "notification_error": item.notification_error,
        "students": [{"id": str(student.id), "name": student.display_name,
                      "group": student.group_name, "lms_id": student.lms_student_id}
                     for student in related.get((item.kind, item.target_id), [])],
    } for item, account in rows]}


@router.post("/pending/{pending_id}/confirm")
async def confirm_waiting_binding(
    pending_id: UUID, payload: PendingBindingAction, db: DbSession, identity: MiniAppIdentityDep,
):
    if identity is None:
        raise HTTPException(401, "Откройте приложение из MAX")
    require_matching_miniapp_identity(identity, max_user_id=payload.max_user_id,
                                     tenant_slug=payload.tenant_slug)
    rate_limit = student_id_entry_limiter.check(f"pending-confirm:{identity.max_user_id}")
    if not rate_limit.allowed:
        raise HTTPException(429, "Подождите минуту и попробуйте снова.")
    from app.services.pending_bindings import confirm_pending_binding
    try:
        return await confirm_pending_binding(db, pending_id, identity.max_user_id)
    except AccessServiceError as exc:
        raise HTTPException(400, str(exc), headers={"X-Access-Error-Code": exc.code}) from exc


@router.post("/pending/{pending_id}/cancel", status_code=204)
async def cancel_waiting_binding(
    pending_id: UUID, payload: PendingBindingAction, db: DbSession, identity: MiniAppIdentityDep,
):
    if identity is None:
        raise HTTPException(401, "Откройте приложение из MAX")
    require_matching_miniapp_identity(identity, max_user_id=payload.max_user_id,
                                     tenant_slug=payload.tenant_slug)
    from app.services.pending_bindings import cancel_pending_binding
    await cancel_pending_binding(db, pending_id, identity.max_user_id,
                                 owner=identity.max_user_id == configured_superadmin_max_user_id())


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
    account_links, child_links, affected_tenants = await revoke_access_for_stopped_bot(db, payload)
    return BotStoppedAccessRevokeRead(
        max_user_id=payload.max_user_id,
        revoked_account_links=account_links,
        revoked_child_links=child_links,
        affected_tenants=affected_tenants,
    )
