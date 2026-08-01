from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.teaching import Course, TeachingSchedule
from app.models.tenant import Tenant
from app.schemas.teaching import FeedbackGenerateRequest
from app.services.feedback_notifications import deliver_feedback_to_teacher
from app.services.teaching import generate_schedule_feedback, next_lesson_date

logger = logging.getLogger(__name__)


async def process_due_feedback(db: AsyncSession, *, now: datetime | None = None) -> int:
    current = now or datetime.now()
    schedules = (
        await db.scalars(
            select(TeachingSchedule)
            .where(
                TeachingSchedule.is_active.is_(True),
                TeachingSchedule.auto_feedback_enabled.is_(True),
            )
            .options(
                selectinload(TeachingSchedule.course).selectinload(Course.lessons),
                selectinload(TeachingSchedule.lesson_overrides),
                selectinload(TeachingSchedule.teacher_account),
            )
        )
    ).unique().all()
    generated = 0
    for schedule in schedules:
        lesson_date = next_lesson_date(schedule)
        if lesson_date < current.date() - timedelta(days=1) or lesson_date > current.date():
            continue
        lesson_finished_at = datetime.combine(lesson_date, schedule.lesson_time) + timedelta(
            minutes=schedule.duration_minutes
        )
        if current < lesson_finished_at or schedule.last_generated_lesson_date == lesson_date:
            continue
        tenant_slug = await db.scalar(
            select(Tenant.slug).where(Tenant.id == schedule.tenant_id)
        )
        output = await generate_schedule_feedback(
            db,
            schedule_id=schedule.id,
            payload=FeedbackGenerateRequest(
                max_user_id=schedule.teacher_account.max_user_id,
                tenant_slug=tenant_slug,
                lesson_date=lesson_date,
                advance_lesson=True,
            ),
            default_tenant_slug=tenant_slug,
        )
        generated += 1
        await deliver_feedback_to_teacher(
            max_user_id=schedule.teacher_account.max_user_id,
            tenant_slug=tenant_slug,
            group_name=schedule.group_name,
            feedback_text=output.feedback_text,
        )
    return generated
