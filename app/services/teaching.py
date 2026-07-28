from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.enums import StaffRole, StudentStatus
from app.models.student import Student
from app.models.teaching import (
    Course,
    CourseLesson,
    FeedbackOutput,
    ManualFeedbackOutput,
    TeachingSchedule,
)
from app.models.tenant import Tenant
from app.schemas.teaching import (
    CourseLessonSummaryRead,
    CourseSummaryRead,
    FeedbackDeliveryRead,
    FeedbackDeliveryRequest,
    FeedbackGenerateRequest,
    FeedbackOutputRead,
    ManualFeedbackCreate,
    ManualFeedbackOutputRead,
    TeachingGroupOptionRead,
    TeachingScheduleRead,
    TeachingScheduleUpsert,
    TeachingWorkspaceRead,
)
from app.services.staff import (
    active_staff_roles_for_tenant,
    normalize_staff_name,
    staff_names_match,
)

TEACHING_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
    StaffRole.TEACHER,
}
MANAGER_ROLES = {
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
}
STAFF_ROLE_PRIORITY = (
    StaffRole.SUPERADMIN,
    StaffRole.PARTNER_DIRECTOR,
    StaffRole.ADMIN,
    StaffRole.CURATOR,
    StaffRole.TEACHER,
)


class TeachingServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


async def load_teaching_context(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> tuple[Tenant, MaxAccount, StaffRole]:
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug.strip().lower()))
    if tenant is None:
        raise TeachingServiceError("Tenant не найден", status_code=404)
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if account is None:
        raise TeachingServiceError("MAX-аккаунт не найден", status_code=403)
    roles = await active_staff_roles_for_tenant(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        allowed_roles=TEACHING_ROLES,
    )
    role = next((candidate for candidate in STAFF_ROLE_PRIORITY if candidate in roles), None)
    if role is None:
        raise TeachingServiceError("Раздел доступен преподавателям и сотрудникам", status_code=403)
    return tenant, account, role


def next_lesson_date(schedule: TeachingSchedule) -> date:
    return schedule.first_lesson_date + timedelta(days=7 * (schedule.current_lesson_number - 1))


def lesson_for_number(course: Course, lesson_number: int) -> CourseLesson | None:
    return next(
        (lesson for lesson in course.lessons if lesson.lesson_number == lesson_number),
        None,
    )


def schedule_to_read(schedule: TeachingSchedule) -> TeachingScheduleRead:
    lesson = lesson_for_number(schedule.course, schedule.current_lesson_number)
    return TeachingScheduleRead(
        id=UUID(str(schedule.id)),
        group_name=schedule.group_name,
        course_id=UUID(str(schedule.course_id)),
        course_name=schedule.course.name,
        lesson_count=len(schedule.course.lessons),
        first_lesson_date=schedule.first_lesson_date,
        weekday=schedule.weekday,
        lesson_time=schedule.lesson_time,
        duration_minutes=schedule.duration_minutes,
        lesson_mode=schedule.lesson_mode,
        lesson_place=schedule.lesson_place,
        current_lesson_number=schedule.current_lesson_number,
        lesson_offset=schedule.lesson_offset,
        auto_feedback_enabled=schedule.auto_feedback_enabled,
        parent_delivery_enabled=schedule.parent_delivery_enabled,
        is_active=schedule.is_active,
        last_generated_lesson_date=schedule.last_generated_lesson_date,
        next_lesson_date=next_lesson_date(schedule),
        next_lesson_title=lesson.title if lesson else None,
    )


def feedback_to_read(output: FeedbackOutput) -> FeedbackOutputRead:
    return FeedbackOutputRead(
        id=UUID(str(output.id)),
        schedule_id=UUID(str(output.schedule_id)),
        group_name=output.schedule.group_name,
        course_name=output.schedule.course.name,
        lesson_date=output.lesson_date,
        lesson_number=output.lesson_number,
        lesson_title=output.lesson_title,
        feedback_text=output.feedback_text,
        status=output.status,
        sent_at=output.sent_at,
        created_at=output.created_at,
    )


def manual_feedback_to_read(output: ManualFeedbackOutput) -> ManualFeedbackOutputRead:
    return ManualFeedbackOutputRead(
        id=UUID(str(output.id)),
        group_name=output.group_name,
        course_id=UUID(str(output.course_id)),
        course_name=output.course.name,
        lesson_date=output.lesson_date,
        lesson_number=output.lesson_number,
        lesson_title=output.lesson_title,
        lesson_mode=output.lesson_mode,
        lesson_place=output.lesson_place,
        feedback_text=output.feedback_text,
        status=output.status,
        sent_at=output.sent_at,
        created_at=output.created_at,
    )


async def get_teaching_workspace(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> TeachingWorkspaceRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    courses = (
        await db.scalars(
            select(Course)
            .where(Course.tenant_id == tenant.id, Course.is_active.is_(True))
            .options(selectinload(Course.lessons))
            .order_by(Course.name)
        )
    ).unique().all()
    group_students = (
        await db.scalars(
            select(Student)
            .where(
                Student.tenant_id == tenant.id,
                Student.status == StudentStatus.ACTIVE,
                Student.group_name.is_not(None),
            )
            .order_by(Student.group_name)
        )
    ).all()
    if role == StaffRole.TEACHER:
        group_students = [
            student
            for student in group_students
            if staff_names_match(account.display_name, student.teacher_name)
        ]
    group_counts: dict[tuple[str, str | None], int] = {}
    for student in group_students:
        key = (student.group_name or "", student.course_name)
        group_counts[key] = group_counts.get(key, 0) + 1
    schedule_query = (
        select(TeachingSchedule)
        .where(TeachingSchedule.tenant_id == tenant.id)
        .options(selectinload(TeachingSchedule.course).selectinload(Course.lessons))
        .order_by(TeachingSchedule.weekday, TeachingSchedule.lesson_time)
    )
    if role not in MANAGER_ROLES:
        schedule_query = schedule_query.where(TeachingSchedule.teacher_account_id == account.id)
    schedules = (await db.scalars(schedule_query)).unique().all()

    schedule_ids = [schedule.id for schedule in schedules]
    outputs: list[FeedbackOutput] = []
    if schedule_ids:
        outputs = (
            await db.scalars(
                select(FeedbackOutput)
                .where(FeedbackOutput.schedule_id.in_(schedule_ids))
                .options(
                    selectinload(FeedbackOutput.schedule).selectinload(TeachingSchedule.course)
                )
                .order_by(FeedbackOutput.created_at.desc())
                .limit(30)
            )
        ).unique().all()

    return TeachingWorkspaceRead(
        tenant_slug=tenant.slug,
        courses=[
            CourseSummaryRead(
                id=UUID(str(course.id)),
                name=course.name,
                lesson_count=len(course.lessons),
            )
            for course in courses
        ],
        groups=[
            TeachingGroupOptionRead(
                name=group_name,
                course_name=course_name,
                student_count=count,
            )
            for (group_name, course_name), count in sorted(
                group_counts.items(),
                key=lambda item: (
                    item[0][0].casefold(),
                    (item[0][1] or "").casefold(),
                ),
            )
            if group_name
        ],
        schedules=[schedule_to_read(schedule) for schedule in schedules],
        feedback_outputs=[feedback_to_read(output) for output in outputs],
    )


async def list_course_lessons(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    course_id: UUID,
) -> list[CourseLessonSummaryRead]:
    tenant, _, _ = await load_teaching_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    course = await db.scalar(
        select(Course)
        .where(
            Course.id == course_id,
            Course.tenant_id == tenant.id,
            Course.is_active.is_(True),
        )
        .options(selectinload(Course.lessons))
    )
    if course is None:
        raise TeachingServiceError("Курс не найден", status_code=404)
    return [
        CourseLessonSummaryRead(
            id=UUID(str(lesson.id)),
            lesson_number=lesson.lesson_number,
            title=lesson.title,
        )
        for lesson in course.lessons
    ]


async def list_manual_feedback(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
) -> list[ManualFeedbackOutputRead]:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    query = (
        select(ManualFeedbackOutput)
        .where(ManualFeedbackOutput.tenant_id == tenant.id)
        .options(selectinload(ManualFeedbackOutput.course))
        .order_by(ManualFeedbackOutput.created_at.desc())
        .limit(30)
    )
    if role not in MANAGER_ROLES:
        query = query.where(ManualFeedbackOutput.author_account_id == account.id)
    outputs = (await db.scalars(query)).unique().all()
    return [manual_feedback_to_read(output) for output in outputs]


async def upsert_teaching_schedule(
    db: AsyncSession,
    *,
    payload: TeachingScheduleUpsert,
    default_tenant_slug: str,
) -> TeachingScheduleRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    course = await db.scalar(
        select(Course)
        .where(Course.tenant_id == tenant.id, Course.id == payload.course_id)
        .options(selectinload(Course.lessons))
    )
    if course is None:
        raise TeachingServiceError("Курс не найден", status_code=404)
    if role == StaffRole.TEACHER:
        group_teachers = (
            await db.scalars(
                select(Student.teacher_name).where(
                    Student.tenant_id == tenant.id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.group_name == payload.group_name.strip(),
                )
            )
        ).all()
        account_teacher_name = normalize_staff_name(account.display_name)
        if not account_teacher_name or not any(
            staff_names_match(account.display_name, teacher_name)
            for teacher_name in group_teachers
        ):
            raise TeachingServiceError(
                "Группа не закреплена за текущим преподавателем в CRM",
                status_code=403,
            )
    if payload.current_lesson_number > len(course.lessons):
        raise TeachingServiceError(
            f"В курсе только {len(course.lessons)} уроков",
            status_code=409,
        )

    schedule = None
    if payload.schedule_id:
        schedule = await db.scalar(
            select(TeachingSchedule).where(
                TeachingSchedule.tenant_id == tenant.id,
                TeachingSchedule.id == payload.schedule_id,
            )
        )
        if schedule is None:
            raise TeachingServiceError("Расписание не найдено", status_code=404)
        if role not in MANAGER_ROLES and schedule.teacher_account_id != account.id:
            raise TeachingServiceError("Нельзя изменить чужое расписание", status_code=403)
    else:
        schedule = await db.scalar(
            select(TeachingSchedule).where(
                TeachingSchedule.tenant_id == tenant.id,
                TeachingSchedule.teacher_account_id == account.id,
                TeachingSchedule.group_name == payload.group_name.strip(),
            )
        )

    created = schedule is None
    if schedule is None:
        schedule = TeachingSchedule(
            tenant_id=tenant.id,
            teacher_account_id=account.id,
            course_id=course.id,
            group_name=payload.group_name.strip(),
            first_lesson_date=payload.first_lesson_date,
            weekday=payload.first_lesson_date.weekday(),
            lesson_time=payload.lesson_time,
        )
        db.add(schedule)

    schedule.course_id = course.id
    schedule.group_name = payload.group_name.strip()
    schedule.first_lesson_date = payload.first_lesson_date
    schedule.weekday = payload.first_lesson_date.weekday()
    schedule.lesson_time = payload.lesson_time
    schedule.duration_minutes = payload.duration_minutes
    schedule.lesson_mode = payload.lesson_mode
    schedule.lesson_place = payload.lesson_place.strip()
    schedule.current_lesson_number = payload.current_lesson_number
    schedule.lesson_offset = payload.lesson_offset
    schedule.auto_feedback_enabled = payload.auto_feedback_enabled
    schedule.parent_delivery_enabled = payload.parent_delivery_enabled
    schedule.is_active = payload.is_active
    await db.flush()
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="teaching_schedule.created" if created else "teaching_schedule.updated",
            entity_type="teaching_schedule",
            entity_id=str(schedule.id),
            payload={
                "group_name": schedule.group_name,
                "course_name": course.name,
                "lesson_time": schedule.lesson_time.strftime("%H:%M"),
                "current_lesson_number": schedule.current_lesson_number,
            },
        )
    )
    await db.commit()
    schedule = await db.scalar(
        select(TeachingSchedule)
        .where(TeachingSchedule.id == schedule.id)
        .options(selectinload(TeachingSchedule.course).selectinload(Course.lessons))
    )
    return schedule_to_read(schedule)


def absent_students_text(students: list[str]) -> str:
    names = [name.strip() for name in students if name.strip()]
    if not names:
        return ""
    joined = names[0] if len(names) == 1 else f"{', '.join(names[:-1])} и {names[-1]}"
    return f"{joined}, ждем на отработке за 30 минут до начала следующего занятия."


def format_feedback_text(
    *,
    lesson: CourseLesson,
    lesson_date: date,
    absent_students: list[str],
    is_repetition: bool,
    displayed_number: int,
    lesson_mode: str,
    lesson_place: str,
) -> str:
    educational_text = (
        "Сегодня мы с ребятами повторяли тему предыдущего занятия, чтобы укрепить знания по ней."
        if is_repetition
        else lesson.educational_results
    )
    now_hour = datetime.now().hour
    greeting = (
        "Доброе утро, уважаемые родители!"
        if 6 <= now_hour < 12
        else "Добрый день, уважаемые родители!"
        if now_hour < 18
        else "Добрый вечер, уважаемые родители!"
    )
    blocks = [
        f"Обратная связь урок №{displayed_number:02d} от {lesson_date:%d.%m.%Y}",
        greeting,
        educational_text,
    ]
    absent = absent_students_text(absent_students)
    if absent:
        blocks.append(absent)
    if lesson_mode != "individual" and lesson_place.lower() != "online":
        blocks.append(
            f"Начислены астрокоины за урок №{displayed_number:02d} от {lesson_date:%d.%m.%Y}."
        )
    blocks.extend(
        [
            "На онлайн-платформе «Алгоритмика» доступен материал урока и прогресс ребенка.",
            "Удачной недели!",
        ]
    )
    return "\n\n".join(blocks)


async def generate_schedule_feedback(
    db: AsyncSession,
    *,
    schedule_id: UUID,
    payload: FeedbackGenerateRequest,
    default_tenant_slug: str,
) -> FeedbackOutputRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    schedule = await db.scalar(
        select(TeachingSchedule)
        .where(TeachingSchedule.tenant_id == tenant.id, TeachingSchedule.id == schedule_id)
        .options(selectinload(TeachingSchedule.course).selectinload(Course.lessons))
    )
    if schedule is None:
        raise TeachingServiceError("Расписание не найдено", status_code=404)
    if role not in MANAGER_ROLES and schedule.teacher_account_id != account.id:
        raise TeachingServiceError("Нельзя сформировать ОС для чужой группы", status_code=403)
    lesson = lesson_for_number(schedule.course, schedule.current_lesson_number)
    if lesson is None:
        raise TeachingServiceError("Урок курса не найден", status_code=409)
    lesson_date = payload.lesson_date or next_lesson_date(schedule)
    output = await db.scalar(
        select(FeedbackOutput).where(
            FeedbackOutput.schedule_id == schedule.id,
            FeedbackOutput.lesson_date == lesson_date,
        )
    )
    feedback_text = format_feedback_text(
        lesson=lesson,
        lesson_date=lesson_date,
        absent_students=payload.absent_students,
        is_repetition=payload.is_repetition,
        displayed_number=lesson.lesson_number + schedule.lesson_offset,
        lesson_mode=schedule.lesson_mode,
        lesson_place=schedule.lesson_place,
    )
    if output is None:
        output = FeedbackOutput(
            tenant_id=tenant.id,
            schedule_id=schedule.id,
            lesson_date=lesson_date,
            lesson_number=lesson.lesson_number,
            lesson_title=lesson.title,
            feedback_text=feedback_text,
        )
        db.add(output)
    else:
        output.lesson_number = lesson.lesson_number
        output.lesson_title = lesson.title
        output.feedback_text = feedback_text
        output.status = "generated"
    if payload.advance_lesson:
        schedule.last_generated_lesson_date = lesson_date
        schedule.current_lesson_number += 1
    await db.commit()
    output = await db.scalar(
        select(FeedbackOutput)
        .where(FeedbackOutput.id == output.id)
        .options(selectinload(FeedbackOutput.schedule).selectinload(TeachingSchedule.course))
    )
    return feedback_to_read(output)


async def generate_manual_feedback(
    db: AsyncSession,
    *,
    payload: ManualFeedbackCreate,
    default_tenant_slug: str,
) -> ManualFeedbackOutputRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    group_name = payload.group_name.strip()
    group_students = (
        await db.scalars(
            select(Student).where(
                Student.tenant_id == tenant.id,
                Student.status == StudentStatus.ACTIVE,
                Student.group_name == group_name,
            )
        )
    ).all()
    if not group_students:
        raise TeachingServiceError("Группа не найдена", status_code=404)
    if role == StaffRole.TEACHER and not any(
        staff_names_match(account.display_name, student.teacher_name)
        for student in group_students
    ):
        raise TeachingServiceError(
            "Группа не закреплена за текущим преподавателем в CRM",
            status_code=403,
        )

    course = await db.scalar(
        select(Course)
        .where(
            Course.id == payload.course_id,
            Course.tenant_id == tenant.id,
            Course.is_active.is_(True),
        )
        .options(selectinload(Course.lessons))
    )
    if course is None:
        raise TeachingServiceError("Курс не найден", status_code=404)
    lesson = lesson_for_number(course, payload.lesson_number)
    if lesson is None:
        raise TeachingServiceError("Урок курса не найден", status_code=404)

    output = ManualFeedbackOutput(
        tenant_id=tenant.id,
        author_account_id=account.id,
        course_id=course.id,
        group_name=group_name,
        lesson_date=payload.lesson_date,
        lesson_number=lesson.lesson_number,
        lesson_title=lesson.title,
        lesson_mode=payload.lesson_mode,
        lesson_place=payload.lesson_place.strip(),
        feedback_text=format_feedback_text(
            lesson=lesson,
            lesson_date=payload.lesson_date,
            absent_students=payload.absent_students,
            is_repetition=payload.is_repetition,
            displayed_number=lesson.lesson_number,
            lesson_mode=payload.lesson_mode,
            lesson_place=payload.lesson_place,
        ),
    )
    db.add(output)
    await db.flush()
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="manual_feedback.generated",
            entity_type="manual_feedback_output",
            entity_id=str(output.id),
            payload={
                "group_name": group_name,
                "course_name": course.name,
                "lesson_number": lesson.lesson_number,
                "lesson_date": payload.lesson_date.isoformat(),
            },
        )
    )
    await db.commit()
    output = await db.scalar(
        select(ManualFeedbackOutput)
        .where(ManualFeedbackOutput.id == output.id)
        .options(selectinload(ManualFeedbackOutput.course))
    )
    return manual_feedback_to_read(output)


async def send_manual_feedback_to_parents(
    db: AsyncSession,
    *,
    output_id: UUID,
    payload: FeedbackDeliveryRequest,
    default_tenant_slug: str,
) -> FeedbackDeliveryRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    output = await db.scalar(
        select(ManualFeedbackOutput).where(
            ManualFeedbackOutput.tenant_id == tenant.id,
            ManualFeedbackOutput.id == output_id,
        )
    )
    if output is None:
        raise TeachingServiceError("Ручная ОС не найдена", status_code=404)
    if role not in MANAGER_ROLES and output.author_account_id != account.id:
        raise TeachingServiceError("Нельзя отправить чужую ОС", status_code=403)

    from app.services.feedback_notifications import deliver_group_feedback_to_parents

    delivery = await deliver_group_feedback_to_parents(
        db,
        tenant_id=tenant.id,
        group_name=output.group_name,
        feedback_text=output.feedback_text,
        tenant_slug=tenant.slug,
    )
    if delivery.sent:
        output.status = "sent_to_parents"
        output.sent_at = datetime.now(UTC)
        await db.commit()
    if delivery.eligible == 0:
        delivery_status = "no_recipients"
    elif delivery.sent == delivery.eligible:
        delivery_status = "sent"
    elif delivery.sent == 0:
        delivery_status = "delivery_unavailable"
    else:
        delivery_status = "partial"
    return FeedbackDeliveryRead(
        output_id=UUID(str(output.id)),
        parent_recipients=delivery.eligible,
        sent_recipients=delivery.sent,
        status=delivery_status,
    )


async def send_feedback_to_parents(
    db: AsyncSession,
    *,
    output_id: UUID,
    payload: FeedbackDeliveryRequest,
    default_tenant_slug: str,
) -> FeedbackDeliveryRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    output = await db.scalar(
        select(FeedbackOutput)
        .where(FeedbackOutput.tenant_id == tenant.id, FeedbackOutput.id == output_id)
        .options(selectinload(FeedbackOutput.schedule))
    )
    if output is None:
        raise TeachingServiceError("Обратная связь не найдена", status_code=404)
    if role not in MANAGER_ROLES and output.schedule.teacher_account_id != account.id:
        raise TeachingServiceError("Нельзя отправить ОС чужой группы", status_code=403)

    from app.services.feedback_notifications import deliver_feedback_to_parents

    delivery = await deliver_feedback_to_parents(
        db,
        output=output,
        tenant_slug=tenant.slug,
    )
    if delivery.eligible == 0:
        delivery_status = "no_recipients"
    elif delivery.sent == delivery.eligible:
        delivery_status = "sent"
    elif delivery.sent == 0:
        delivery_status = "delivery_unavailable"
    else:
        delivery_status = "partial"
    return FeedbackDeliveryRead(
        output_id=UUID(str(output.id)),
        parent_recipients=delivery.eligible,
        sent_recipients=delivery.sent,
        status=delivery_status,
    )
