from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.student import Student
from app.models.teaching import AttendanceRecord, Course, TeachingSchedule
from app.models.tenant import Tenant
from app.schemas.teaching import FeedbackGenerateRequest
from app.services.feedback_notifications import deliver_feedback_to_teacher
from app.services.teaching import (
    generate_schedule_feedback,
    next_lesson_date,
    schedule_has_lesson_at_position,
)

logger = logging.getLogger(__name__)


async def process_due_feedback(db: AsyncSession, *, now: datetime | None = None) -> int:
    timezone = ZoneInfo(get_settings().app_timezone)
    if now is None:
        current = datetime.now(timezone).replace(tzinfo=None)
    elif now.tzinfo is not None:
        current = now.astimezone(timezone).replace(tzinfo=None)
    else:
        current = now
    schedule_ids = list(
        (
            await db.scalars(
                select(TeachingSchedule.id).where(
                    TeachingSchedule.is_active.is_(True),
                    TeachingSchedule.auto_feedback_enabled.is_(True),
                )
            )
        ).all()
    )
    generated = 0
    for schedule_id in schedule_ids:
        try:
            schedule = await db.scalar(
                select(TeachingSchedule)
                .where(TeachingSchedule.id == schedule_id)
                .with_for_update()
                .options(
                    selectinload(TeachingSchedule.course).selectinload(Course.lessons),
                    selectinload(TeachingSchedule.lesson_overrides),
                    selectinload(TeachingSchedule.teacher_account),
                )
            )
            if schedule is None or schedule.teacher_account is None:
                await db.rollback()
                continue
            lesson_date = next_lesson_date(schedule)
            stale_cutoff = current.date() - timedelta(days=1)
            if lesson_date < stale_cutoff:
                skipped_lessons = 0
                while lesson_date < stale_cutoff:
                    schedule.current_lesson_number += 1
                    skipped_lessons += 1
                    if not schedule_has_lesson_at_position(
                        schedule,
                        schedule.current_lesson_number,
                    ):
                        schedule.is_active = False
                        break
                    lesson_date = next_lesson_date(schedule)
                await db.commit()
                logger.info(
                    "Расписание %s продвинуто после простоя: пропущено занятий %s",
                    schedule.id,
                    skipped_lessons,
                )
                continue
            if lesson_date > current.date():
                await db.rollback()
                continue
            lesson_finished_at = datetime.combine(
                lesson_date,
                schedule.lesson_time,
            ) + timedelta(minutes=schedule.duration_minutes)
            if (
                current < lesson_finished_at
                or schedule.last_generated_lesson_date == lesson_date
            ):
                await db.rollback()
                continue
            tenant_slug = await db.scalar(
                select(Tenant.slug).where(Tenant.id == schedule.tenant_id)
            )
            if not tenant_slug:
                await db.rollback()
                continue
            absent_students = list(
                (
                    await db.scalars(
                        select(Student)
                        .join(
                            AttendanceRecord,
                            AttendanceRecord.student_id == Student.id,
                        )
                        .where(
                            AttendanceRecord.schedule_id == schedule.id,
                            AttendanceRecord.lesson_date == lesson_date,
                            AttendanceRecord.present.is_(False),
                        )
                        .order_by(Student.last_name, Student.first_name)
                    )
                ).all()
            )
            output = await generate_schedule_feedback(
                db,
                schedule_id=schedule.id,
                payload=FeedbackGenerateRequest(
                    max_user_id=schedule.teacher_account.max_user_id,
                    tenant_slug=tenant_slug,
                    lesson_date=lesson_date,
                    absent_students=[student.display_name for student in absent_students],
                    advance_lesson=True,
                ),
                default_tenant_slug=tenant_slug,
            )
            generated += 1
            try:
                await deliver_feedback_to_teacher(
                    max_user_id=schedule.teacher_account.max_user_id,
                    tenant_slug=tenant_slug,
                    group_name=schedule.group_name,
                    feedback_text=output.feedback_text,
                )
            except Exception:
                logger.exception(
                    "Не удалось отправить обратную связь для расписания %s",
                    schedule.id,
                )
        except Exception:
            await db.rollback()
            logger.exception("Не удалось обработать расписание %s", schedule_id)
    return generated
