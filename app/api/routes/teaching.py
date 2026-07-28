from datetime import date
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
    AttendanceJournalRead,
    AttendanceMarkRequest,
    CourseLessonSummaryRead,
    FeedbackDeliveryRead,
    FeedbackDeliveryRequest,
    FeedbackGenerateRequest,
    FeedbackOutputRead,
    ManualFeedbackCreate,
    ManualFeedbackOutputRead,
    TeachingScheduleRead,
    TeachingScheduleUpsert,
    TeachingWorkspaceRead,
)
from app.services.teaching import (
    TeachingServiceError,
    generate_manual_feedback,
    generate_schedule_feedback,
    get_attendance_journal,
    get_teaching_workspace,
    list_course_lessons,
    list_manual_feedback,
    mark_attendance,
    send_feedback_to_parents,
    send_manual_feedback_to_parents,
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


@router.get(
    "/schedules/{schedule_id}/attendance",
    response_model=AttendanceJournalRead,
)
async def teaching_attendance_journal(
    schedule_id: UUID,
    lesson_date: date,
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> AttendanceJournalRead:
    resolved_tenant = _authorize(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await get_attendance_journal(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
            schedule_id=schedule_id,
            lesson_date=lesson_date,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put(
    "/schedules/{schedule_id}/attendance",
    response_model=AttendanceJournalRead,
)
async def teaching_attendance_mark(
    schedule_id: UUID,
    payload: AttendanceMarkRequest,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> AttendanceJournalRead:
    settings = get_settings()
    _authorize(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await mark_attendance(
            db,
            schedule_id=schedule_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/manual-feedback",
    response_model=list[ManualFeedbackOutputRead],
)
async def teaching_manual_feedback_list(
    db: DbSession,
    identity: MiniAppIdentityDep,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> list[ManualFeedbackOutputRead]:
    resolved_tenant = _authorize(
        identity,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    try:
        return await list_manual_feedback(
            db,
            max_user_id=max_user_id,
            tenant_slug=resolved_tenant,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/manual-feedback",
    response_model=ManualFeedbackOutputRead,
    status_code=status.HTTP_201_CREATED,
)
async def teaching_manual_feedback_generate(
    payload: ManualFeedbackCreate,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> ManualFeedbackOutputRead:
    settings = get_settings()
    _authorize(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await generate_manual_feedback(
            db,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/manual-feedback/{output_id}/send",
    response_model=FeedbackDeliveryRead,
)
async def teaching_manual_feedback_send(
    output_id: UUID,
    payload: FeedbackDeliveryRequest,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> FeedbackDeliveryRead:
    settings = get_settings()
    _authorize(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await send_manual_feedback_to_parents(
            db,
            output_id=output_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
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


@router.post(
    "/schedules/{schedule_id}/feedback",
    response_model=FeedbackOutputRead,
    status_code=status.HTTP_201_CREATED,
)
async def teaching_feedback_generate(
    schedule_id: UUID,
    payload: FeedbackGenerateRequest,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> FeedbackOutputRead:
    settings = get_settings()
    _authorize(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await generate_schedule_feedback(
            db,
            schedule_id=schedule_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/feedback/{output_id}/send",
    response_model=FeedbackDeliveryRead,
)
async def teaching_feedback_send(
    output_id: UUID,
    payload: FeedbackDeliveryRequest,
    db: DbSession,
    identity: MiniAppIdentityDep,
) -> FeedbackDeliveryRead:
    settings = get_settings()
    _authorize(
        identity,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug,
    )
    try:
        return await send_feedback_to_parents(
            db,
            output_id=output_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
