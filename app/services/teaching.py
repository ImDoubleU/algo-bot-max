from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import AssignmentStatus, StaffRole, StudentStatus
from app.models.student import Student
from app.models.teaching import Course, CourseLesson, TeachingLessonOverride, TeachingSchedule
from app.models.tenant import Tenant
from app.schemas.teaching import (
    CourseLessonSummaryRead,
    CourseSummaryRead,
    TeachingGroupOptionRead,
    TeachingScheduleRead,
    TeachingScheduleUpsert,
    TeachingWorkspaceRead,
)
from app.services.staff import (
    active_staff_roles_for_tenant,
    normalize_staff_name,
    staff_names_match,
    staff_venue_scope_ids,
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
        raise TeachingServiceError("Партнер не найден", status_code=404)
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


async def teacher_has_group_access(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    account: MaxAccount,
    group_name: str,
) -> bool:
    teacher_names = (
        await db.scalars(
            select(Student.teacher_name).where(
                Student.tenant_id == tenant_id,
                Student.status == StudentStatus.ACTIVE,
                Student.group_name == group_name,
            )
        )
    ).all()
    return any(
        staff_names_match(account.display_name, teacher_name)
        for teacher_name in teacher_names
    )


async def teacher_account_for_group(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    group_name: str,
) -> MaxAccount | None:
    teacher_names = set(
        (
            await db.scalars(
                select(Student.teacher_name).where(
                    Student.tenant_id == tenant_id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.group_name == group_name,
                    Student.teacher_name.is_not(None),
                )
            )
        ).all()
    )
    if not teacher_names:
        return None
    candidates = (
        await db.scalars(
            select(MaxAccount)
            .join(
                StaffRoleAssignment,
                StaffRoleAssignment.account_id == MaxAccount.id,
            )
            .where(
                StaffRoleAssignment.tenant_id == tenant_id,
                StaffRoleAssignment.role == StaffRole.TEACHER,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            )
            .order_by(MaxAccount.max_user_id)
        )
    ).unique().all()
    return next(
        (
            candidate
            for candidate in candidates
            if any(
                staff_names_match(candidate.display_name, teacher_name)
                for teacher_name in teacher_names
            )
        ),
        None,
    )


def lesson_override_for_position(
    schedule: TeachingSchedule,
    position: int,
) -> TeachingLessonOverride | None:
    return next(
        (item for item in schedule.lesson_overrides if item.position == position),
        None,
    )


def lesson_date_for_position(schedule: TeachingSchedule, position: int) -> date:
    override = lesson_override_for_position(schedule, position)
    if override is not None:
        return override.lesson_date
    return schedule.first_lesson_date + timedelta(days=7 * (position - 1))


def lesson_number_for_position(schedule: TeachingSchedule, position: int) -> int:
    override = lesson_override_for_position(schedule, position)
    return override.lesson_number if override is not None else position


def next_lesson_date(schedule: TeachingSchedule) -> date:
    return lesson_date_for_position(schedule, schedule.current_lesson_number)


def lesson_for_number(course: Course, lesson_number: int) -> CourseLesson | None:
    return next(
        (lesson for lesson in course.lessons if lesson.lesson_number == lesson_number),
        None,
    )


def schedule_to_read(schedule: TeachingSchedule) -> TeachingScheduleRead:
    next_lesson_number = lesson_number_for_position(
        schedule,
        schedule.current_lesson_number,
    )
    lesson = lesson_for_number(schedule.course, next_lesson_number)
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
        next_lesson_number=next_lesson_number,
        lesson_offset=schedule.lesson_offset,
        is_active=schedule.is_active,
        next_lesson_date=next_lesson_date(schedule),
        next_lesson_title=lesson.title if lesson else None,
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
    venue_scope_ids = await staff_venue_scope_ids(
        db,
        tenant_id=tenant.id,
        account_id=account.id,
        role=role,
    )
    if venue_scope_ids is not None:
        group_students = [
            student for student in group_students if student.venue_id in venue_scope_ids
        ]
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
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
        .order_by(TeachingSchedule.weekday, TeachingSchedule.lesson_time)
    )
    if role not in MANAGER_ROLES or venue_scope_ids is not None:
        accessible_group_names = {
            student.group_name
            for student in group_students
            if student.group_name
        }
        schedule_query = schedule_query.where(
            TeachingSchedule.group_name.in_(accessible_group_names)
        )
    schedules = (await db.scalars(schedule_query)).unique().all()

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
    group_name = payload.group_name.strip()
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
                    Student.group_name == group_name,
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

    resolved_teacher_account = (
        account
        if role == StaffRole.TEACHER
        else await teacher_account_for_group(
            db,
            tenant_id=UUID(str(tenant.id)),
            group_name=group_name,
        )
    )

    schedule = None
    if payload.schedule_id:
        schedule = await db.scalar(
            select(TeachingSchedule)
            .where(
                TeachingSchedule.tenant_id == tenant.id,
                TeachingSchedule.id == payload.schedule_id,
            )
            .with_for_update()
        )
        if schedule is None:
            raise TeachingServiceError("Расписание не найдено", status_code=404)
        if role not in MANAGER_ROLES and not await teacher_has_group_access(
            db,
            tenant_id=UUID(str(tenant.id)),
            account=account,
            group_name=schedule.group_name,
        ):
            raise TeachingServiceError(
                "Нельзя изменить чужое расписание",
                status_code=403,
            )
        if role not in MANAGER_ROLES and not await teacher_has_group_access(
            db,
            tenant_id=UUID(str(tenant.id)),
            account=account,
            group_name=group_name,
        ):
            raise TeachingServiceError("Нельзя изменить чужое расписание", status_code=403)
    else:
        schedule = await db.scalar(
            select(TeachingSchedule)
            .where(
                TeachingSchedule.tenant_id == tenant.id,
                TeachingSchedule.group_name == group_name,
            )
            .order_by(TeachingSchedule.updated_at.desc())
            .limit(1)
        )

    created = schedule is None
    if schedule is None:
        schedule = TeachingSchedule(
            tenant_id=tenant.id,
            teacher_account_id=(resolved_teacher_account or account).id,
            course_id=course.id,
            group_name=group_name,
            first_lesson_date=payload.first_lesson_date,
            weekday=payload.first_lesson_date.weekday(),
            lesson_time=payload.lesson_time,
        )
        db.add(schedule)

    schedule.course_id = course.id
    schedule.group_name = group_name
    schedule.first_lesson_date = payload.first_lesson_date
    schedule.weekday = payload.first_lesson_date.weekday()
    schedule.lesson_time = payload.lesson_time
    schedule.duration_minutes = payload.duration_minutes
    schedule.lesson_mode = payload.lesson_mode
    schedule.lesson_place = payload.lesson_place.strip()
    schedule.current_lesson_number = payload.current_lesson_number
    schedule.lesson_offset = payload.lesson_offset
    schedule.auto_feedback_enabled = False
    schedule.parent_delivery_enabled = False
    schedule.is_active = payload.is_active
    if resolved_teacher_account is not None:
        schedule.teacher_account_id = resolved_teacher_account.id
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
    saved_schedule = await db.scalar(
        select(TeachingSchedule)
        .where(TeachingSchedule.id == schedule.id)
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
    )
    if saved_schedule is None:
        raise TeachingServiceError("Расписание не найдено после сохранения", status_code=500)
    return schedule_to_read(saved_schedule)
