from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_miniapp_identity,
    require_matching_miniapp_identity,
)
from app.core.config import get_settings
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.schemas.teaching import (
    CourseLessonSummaryRead,
    TeachingScheduleRead,
    TeachingScheduleUpsert,
    TeachingWorkspaceRead,
)
from app.services.teaching import (
    TeachingServiceError,
    get_teaching_workspace,
    list_course_lessons,
    upsert_teaching_schedule,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
MiniAppIdentityDep = Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)]


def _authorize(
    identity: MiniAppIdentity | None,
    *,
    max_user_id: int,
    tenant_slug: str | None,
) -> str:
    resolved_tenant = tenant_slug or get_settings().default_tenant_slug
    require_matching_miniapp_identity(
        identity,
        max_user_id=max_user_id,
        tenant_slug=resolved_tenant,
    )
    return resolved_tenant


@router.get("/workspace", response_model=TeachingWorkspaceRead)
async def teaching_workspace(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> TeachingWorkspaceRead:
    resolved_tenant = _authorize(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_teaching_workspace(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/courses/{course_id}/lessons",
    response_model=list[CourseLessonSummaryRead],
)
async def teaching_course_lessons(
    course_id: UUID,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> list[CourseLessonSummaryRead]:
    resolved_tenant = _authorize(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_course_lessons(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            course_id=course_id,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/schedules",
    response_model=TeachingScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
async def teaching_schedule_upsert(
    payload: TeachingScheduleUpsert,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> TeachingScheduleRead:
    settings = get_settings()
    _authorize(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await upsert_teaching_schedule(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
