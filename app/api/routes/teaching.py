from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.schemas.teaching import (
    FeedbackDeliveryRead,
    FeedbackDeliveryRequest,
    FeedbackGenerateRequest,
    FeedbackOutputRead,
    TeachingScheduleRead,
    TeachingScheduleUpsert,
    TeachingWorkspaceRead,
)
from app.services.teaching import (
    TeachingServiceError,
    generate_schedule_feedback,
    get_teaching_workspace,
    send_feedback_to_parents,
    upsert_teaching_schedule,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/workspace", response_model=TeachingWorkspaceRead)
async def teaching_workspace(
    db: DbSession,
    max_user_id: Annotated[int, Query(gt=0)],
    tenant_slug: str | None = None,
) -> TeachingWorkspaceRead:
    settings = get_settings()
    try:
        return await get_teaching_workspace(
            db,
            max_user_id=max_user_id,
            tenant_slug=tenant_slug or settings.default_tenant_slug,
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
) -> TeachingScheduleRead:
    settings = get_settings()
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
) -> FeedbackOutputRead:
    settings = get_settings()
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
) -> FeedbackDeliveryRead:
    settings = get_settings()
    try:
        return await send_feedback_to_parents(
            db,
            output_id=output_id,
            payload=payload,
            default_tenant_slug=settings.default_tenant_slug,
        )
    except TeachingServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
