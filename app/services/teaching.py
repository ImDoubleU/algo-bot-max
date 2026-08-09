from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings, is_placeholder
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.student import Student, StudentAccessLink
from app.models.teaching import (
    AttendanceRecord,
    Course,
    CourseLesson,
    FeedbackOutput,
    ManualFeedbackOutput,
    TeachingLessonOverride,
    TeachingSchedule,
)
from app.models.tenant import Tenant
from app.schemas.teaching import (
    AttendanceJournalRead,
    AttendanceJournalUpdateRequest,
    AttendanceLessonRead,
    AttendanceMarkRead,
    AttendanceMarkRequest,
    AttendanceStudentRead,
    CourseLessonSummaryRead,
    CourseSummaryRead,
    FeedbackGenerateRequest,
    FeedbackOutputRead,
    GroupAttendanceJournalRead,
    GroupAttendanceStudentRead,
    ManualFeedbackCreate,
    ManualFeedbackOutputRead,
    ManualFeedbackSendRead,
    ManualFeedbackSendRequest,
    TeachingGroupOptionRead,
    TeachingScheduleRead,
    TeachingScheduleUpsert,
    TeachingWorkspaceRead,
)
from app.services.feedback_notifications import deliver_feedback_to_parents
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


def schedule_has_lesson_at_position(
    schedule: TeachingSchedule,
    position: int,
) -> bool:
    return lesson_for_number(
        schedule.course,
        lesson_number_for_position(schedule, position),
    ) is not None


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
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
        .order_by(TeachingSchedule.weekday, TeachingSchedule.lesson_time)
    )
    if role not in MANAGER_ROLES:
        accessible_group_names = {
            student.group_name
            for student in group_students
            if student.group_name
        }
        schedule_query = schedule_query.where(
            TeachingSchedule.group_name.in_(accessible_group_names)
        )
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


async def get_attendance_journal(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    schedule_id: UUID,
    lesson_date: date,
) -> AttendanceJournalRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    schedule = await db.scalar(
        select(TeachingSchedule)
        .where(
            TeachingSchedule.tenant_id == tenant.id,
            TeachingSchedule.id == schedule_id,
        )
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
    )
    if schedule is None:
        raise TeachingServiceError("Расписание не найдено", status_code=404)
    if role == StaffRole.TEACHER and not await teacher_has_group_access(
        db,
        tenant_id=UUID(str(tenant.id)),
        account=account,
        group_name=schedule.group_name,
    ):
        raise TeachingServiceError("Нельзя редактировать журнал чужой группы", status_code=403)

    students = (
        await db.scalars(
            select(Student)
            .where(
                Student.tenant_id == tenant.id,
                Student.group_name == schedule.group_name,
                Student.status == StudentStatus.ACTIVE,
            )
            .order_by(Student.last_name, Student.first_name)
        )
    ).all()
    records = (
        await db.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.schedule_id == schedule.id,
                AttendanceRecord.lesson_date == lesson_date,
            )
        )
    ).all()
    scheduled_dates = {item.lesson_date for item in _attendance_lessons(schedule)}
    if lesson_date not in scheduled_dates and not records:
        raise TeachingServiceError(
            "Дата занятия отсутствует в журнале группы",
            status_code=404,
        )
    records_by_student = {record.student_id: record for record in records}
    lesson = next(
        (
            item
            for item in _attendance_lessons(schedule)
            if item.lesson_date == lesson_date
        ),
        None,
    )
    lesson_number = lesson.lesson_number if lesson else max(
        1,
        ((lesson_date - schedule.first_lesson_date).days // 7) + 1,
    )
    return AttendanceJournalRead(
        schedule_id=UUID(str(schedule.id)),
        group_name=schedule.group_name,
        lesson_date=lesson_date,
        lesson_number=lesson_number,
        students=[
            AttendanceStudentRead(
                student_id=UUID(str(student.id)),
                student_name=student.display_name,
                group_name=schedule.group_name,
                present=(
                    records_by_student[student.id].present
                    if student.id in records_by_student
                    else None
                ),
                makeup_completed=(
                    records_by_student[student.id].makeup_completed
                    if student.id in records_by_student
                    else False
                ),
                comment=(
                    records_by_student[student.id].comment
                    if student.id in records_by_student
                    else None
                ),
            )
            for student in students
        ],
    )


async def mark_attendance(
    db: AsyncSession,
    *,
    schedule_id: UUID,
    payload: AttendanceMarkRequest,
    default_tenant_slug: str,
) -> AttendanceJournalRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
    )
    schedule = await db.scalar(
        select(TeachingSchedule)
        .where(
            TeachingSchedule.tenant_id == tenant.id,
            TeachingSchedule.id == schedule_id,
        )
        .with_for_update()
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
    )
    if schedule is None:
        raise TeachingServiceError("Расписание не найдено", status_code=404)
    if role == StaffRole.TEACHER and not await teacher_has_group_access(
        db,
        tenant_id=UUID(str(tenant.id)),
        account=account,
        group_name=schedule.group_name,
    ):
        raise TeachingServiceError("Нельзя редактировать журнал чужой группы", status_code=403)

    existing_lesson_date = await db.scalar(
        select(AttendanceRecord.id).where(
            AttendanceRecord.schedule_id == schedule.id,
            AttendanceRecord.lesson_date == payload.lesson_date,
        )
    )
    scheduled_dates = {lesson.lesson_date for lesson in _attendance_lessons(schedule)}
    if payload.lesson_date not in scheduled_dates and existing_lesson_date is None:
        raise TeachingServiceError(
            "Дата занятия отсутствует в журнале группы",
            status_code=409,
        )

    student_ids = list(dict.fromkeys(item.student_id for item in payload.items))
    students = (
        await db.scalars(
            select(Student).where(
                Student.tenant_id == tenant.id,
                Student.id.in_(student_ids),
                Student.group_name == schedule.group_name,
                Student.status == StudentStatus.ACTIVE,
            )
        )
    ).all()
    if len(students) != len(student_ids):
        raise TeachingServiceError("В списке есть ученик из другой группы", status_code=409)
    existing = (
        await db.scalars(
            select(AttendanceRecord).where(
                AttendanceRecord.schedule_id == schedule.id,
                AttendanceRecord.lesson_date == payload.lesson_date,
                AttendanceRecord.student_id.in_(student_ids),
            )
        )
    ).all()
    records = {record.student_id: record for record in existing}
    for item in payload.items:
        if item.makeup_completed and item.present:
            raise TeachingServiceError(
                "Отработку можно отметить только для пропущенного урока",
                status_code=409,
            )
        record = records.get(item.student_id)
        if record is None:
            record = AttendanceRecord(
                tenant_id=tenant.id,
                schedule_id=schedule.id,
                student_id=item.student_id,
                lesson_date=payload.lesson_date,
                present=item.present,
                makeup_completed=item.makeup_completed,
                marked_by_account_id=account.id,
                comment=item.comment,
            )
            db.add(record)
        else:
            record.present = item.present
            record.makeup_completed = item.makeup_completed
            record.comment = item.comment
            record.marked_by_account_id = account.id
    await db.commit()
    return await get_attendance_journal(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
        schedule_id=schedule.id,
        lesson_date=payload.lesson_date,
    )


async def _load_attendance_schedule(
    db: AsyncSession,
    *,
    tenant: Tenant,
    account: MaxAccount,
    role: StaffRole,
    schedule_id: UUID,
    for_update: bool = False,
) -> TeachingSchedule:
    query = (
        select(TeachingSchedule)
        .where(
            TeachingSchedule.tenant_id == tenant.id,
            TeachingSchedule.id == schedule_id,
        )
        .options(selectinload(TeachingSchedule.course).selectinload(Course.lessons))
        .options(selectinload(TeachingSchedule.lesson_overrides))
    )
    if for_update:
        query = query.with_for_update()
    schedule = await db.scalar(query)
    if schedule is None:
        raise TeachingServiceError("Расписание не найдено", status_code=404)
    if role not in MANAGER_ROLES and not await teacher_has_group_access(
        db,
        tenant_id=UUID(str(tenant.id)),
        account=account,
        group_name=schedule.group_name,
    ):
        raise TeachingServiceError("Нельзя редактировать журнал чужой группы", status_code=403)
    return schedule


async def _attendance_students(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    group_name: str,
) -> list[Student]:
    return list(
        (
            await db.scalars(
                select(Student)
                .where(
                    Student.tenant_id == tenant_id,
                    Student.group_name == group_name,
                    Student.status == StudentStatus.ACTIVE,
                )
                .order_by(Student.last_name, Student.first_name)
            )
        ).all()
    )


def _attendance_lessons(
    schedule: TeachingSchedule,
    *,
    extra_dates: set[date] | None = None,
) -> list[AttendanceLessonRead]:
    lessons_by_number = {lesson.lesson_number: lesson for lesson in schedule.course.lessons}
    override_positions = [item.position for item in schedule.lesson_overrides]
    lesson_count = max(
        len(schedule.course.lessons),
        schedule.current_lesson_number,
        max(override_positions, default=0),
        1,
    )
    today = date.today()
    result: list[AttendanceLessonRead] = []
    used_dates: set[date] = set()
    for position in range(1, lesson_count + 1):
        lesson_date = lesson_date_for_position(schedule, position)
        lesson_number = lesson_number_for_position(schedule, position)
        course_lesson = lessons_by_number.get(lesson_number)
        used_dates.add(lesson_date)
        result.append(
            AttendanceLessonRead(
                position=position,
                lesson_date=lesson_date,
                lesson_number=lesson_number,
                lesson_title=course_lesson.title if course_lesson else None,
                is_current=position == schedule.current_lesson_number,
                is_future=lesson_date > today,
            )
        )
    next_position = lesson_count + 1
    for lesson_date in sorted((extra_dates or set()) - used_dates):
        lesson_number = max(
            1,
            ((lesson_date - schedule.first_lesson_date).days // 7) + 1,
        )
        course_lesson = lessons_by_number.get(lesson_number)
        result.append(
            AttendanceLessonRead(
                position=next_position,
                lesson_date=lesson_date,
                lesson_number=lesson_number,
                lesson_title=course_lesson.title if course_lesson else None,
                is_current=False,
                is_future=lesson_date > today,
            )
        )
        next_position += 1
    result.sort(key=lambda item: (item.lesson_date, item.position))
    return result


async def get_group_attendance_journal(
    db: AsyncSession,
    *,
    max_user_id: int,
    tenant_slug: str,
    schedule_id: UUID,
) -> GroupAttendanceJournalRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=max_user_id,
        tenant_slug=tenant_slug,
    )
    schedule = await _load_attendance_schedule(
        db,
        tenant=tenant,
        account=account,
        role=role,
        schedule_id=schedule_id,
    )
    students = await _attendance_students(
        db,
        tenant_id=UUID(str(tenant.id)),
        group_name=schedule.group_name,
    )
    student_ids = [student.id for student in students]
    records: list[AttendanceRecord] = []
    if student_ids:
        records = list(
            (
                await db.scalars(
                    select(AttendanceRecord).where(
                        AttendanceRecord.schedule_id == schedule.id,
                        AttendanceRecord.student_id.in_(student_ids),
                    )
                )
            ).all()
        )
    records_by_student: dict[UUID, list[AttendanceRecord]] = {}
    for record in records:
        records_by_student.setdefault(record.student_id, []).append(record)
    lessons = _attendance_lessons(
        schedule,
        extra_dates={record.lesson_date for record in records},
    )
    return GroupAttendanceJournalRead(
        schedule_id=UUID(str(schedule.id)),
        group_name=schedule.group_name,
        course_name=schedule.course.name,
        lesson_time=schedule.lesson_time,
        current_lesson_number=schedule.current_lesson_number,
        lessons=lessons,
        students=[
            GroupAttendanceStudentRead(
                student_id=UUID(str(student.id)),
                student_name=student.display_name,
                group_name=schedule.group_name,
                marks=[
                    AttendanceMarkRead(
                        lesson_date=record.lesson_date,
                        present=record.present,
                        makeup_completed=record.makeup_completed,
                        comment=record.comment,
                    )
                    for record in sorted(
                        records_by_student.get(student.id, []),
                        key=lambda item: item.lesson_date,
                    )
                ],
            )
            for student in students
        ],
    )


async def update_group_attendance_journal(
    db: AsyncSession,
    *,
    schedule_id: UUID,
    payload: AttendanceJournalUpdateRequest,
    default_tenant_slug: str,
) -> GroupAttendanceJournalRead:
    tenant_slug = (payload.tenant_slug or default_tenant_slug).strip().lower()
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant_slug,
    )
    schedule = await _load_attendance_schedule(
        db,
        tenant=tenant,
        account=account,
        role=role,
        schedule_id=schedule_id,
        for_update=True,
    )
    if not payload.items and not payload.lessons:
        raise TeachingServiceError("В журнале нет изменений")

    item_keys = [(item.student_id, item.lesson_date) for item in payload.items]
    if len(set(item_keys)) != len(item_keys):
        raise TeachingServiceError(
            "Один ученик и урок указаны в запросе несколько раз",
            status_code=409,
        )
    lesson_positions = [item.position for item in payload.lessons]
    if len(set(lesson_positions)) != len(lesson_positions):
        raise TeachingServiceError(
            "Один урок указан в запросе несколько раз",
            status_code=409,
        )
    course_lesson_numbers = {lesson.lesson_number for lesson in schedule.course.lessons}
    if any(
        item.lesson_number not in course_lesson_numbers
        for item in payload.lessons
    ):
        raise TeachingServiceError(
            "Выбранного номера урока нет в этом курсе",
            status_code=409,
        )

    all_schedule_records: list[AttendanceRecord] = []
    if payload.lessons:
        all_schedule_records = list(
            (
                await db.scalars(
                    select(AttendanceRecord).where(
                        AttendanceRecord.schedule_id == schedule.id,
                    )
                )
            ).all()
        )
        lessons_before = _attendance_lessons(
            schedule,
            extra_dates={record.lesson_date for record in all_schedule_records},
        )
        lessons_by_position = {item.position: item for item in lessons_before}
        lesson_updates = {item.position: item for item in payload.lessons}
        unknown_positions = set(lesson_updates) - set(lessons_by_position)
        if unknown_positions:
            raise TeachingServiceError("Занятие не найдено в расписании", status_code=404)

        proposed_dates = {
            position: item.lesson_date
            for position, item in lessons_by_position.items()
        }
        for position, item in lesson_updates.items():
            proposed_dates[position] = item.lesson_date
        if len(set(proposed_dates.values())) != len(proposed_dates):
            raise TeachingServiceError(
                "На одну дату нельзя поставить два занятия одной группы",
                status_code=409,
            )

        overrides_by_position = {
            item.position: item
            for item in schedule.lesson_overrides
        }
        date_moves: dict[date, date] = {}
        changed_lessons: list[dict[str, object]] = []
        for position, item in lesson_updates.items():
            previous = lessons_by_position[position]
            if previous.lesson_date != item.lesson_date:
                date_moves[previous.lesson_date] = item.lesson_date
            if (
                previous.lesson_date != item.lesson_date
                or previous.lesson_number != item.lesson_number
            ):
                changed_lessons.append(
                    {
                        "position": position,
                        "old_date": previous.lesson_date.isoformat(),
                        "new_date": item.lesson_date.isoformat(),
                        "old_number": previous.lesson_number,
                        "new_number": item.lesson_number,
                    }
                )

            default_date = schedule.first_lesson_date + timedelta(days=7 * (position - 1))
            override = overrides_by_position.get(position)
            if item.lesson_date == default_date and item.lesson_number == position:
                if override is not None:
                    await db.delete(override)
                    schedule.lesson_overrides.remove(override)
                continue
            if override is None:
                override = TeachingLessonOverride(
                    tenant_id=tenant.id,
                    schedule_id=schedule.id,
                    position=position,
                    lesson_date=item.lesson_date,
                    lesson_number=item.lesson_number,
                )
                db.add(override)
                schedule.lesson_overrides.append(override)
            else:
                override.lesson_date = item.lesson_date
                override.lesson_number = item.lesson_number

        if date_moves:
            used_dates = {record.lesson_date for record in all_schedule_records}
            conflicting_targets = {
                target_date
                for target_date in date_moves.values()
                if target_date in used_dates and target_date not in date_moves
            }
            if conflicting_targets:
                raise TeachingServiceError(
                    "На новую дату уже сохранены отметки другого занятия",
                    status_code=409,
                )
            temporary_dates: dict[date, date] = {}
            candidate = date(9999, 12, 31)
            for source_date in date_moves:
                while candidate in used_dates:
                    candidate -= timedelta(days=1)
                temporary_dates[source_date] = candidate
                used_dates.add(candidate)
                candidate -= timedelta(days=1)
            records_to_move = [
                record
                for record in all_schedule_records
                if record.lesson_date in date_moves
            ]
            for record in records_to_move:
                record.lesson_date = temporary_dates[record.lesson_date]
            await db.flush()
            reverse_temporary_dates = {
                temporary: date_moves[source]
                for source, temporary in temporary_dates.items()
            }
            for record in records_to_move:
                record.lesson_date = reverse_temporary_dates[record.lesson_date]

        if changed_lessons:
            db.add(
                AuditLog(
                    tenant_id=tenant.id,
                    actor_account_id=account.id,
                    action="teaching_journal.lessons_updated",
                    entity_type="teaching_schedule",
                    entity_id=str(schedule.id),
                    payload={"lessons": changed_lessons},
                )
            )

    items_by_key = dict(zip(item_keys, payload.items, strict=True))
    if all_schedule_records:
        existing_record_dates = {record.lesson_date for record in all_schedule_records}
    else:
        existing_record_dates = set(
            (
                await db.scalars(
                    select(AttendanceRecord.lesson_date)
                    .where(AttendanceRecord.schedule_id == schedule.id)
                    .distinct()
                )
            ).all()
        )
    allowed_lesson_dates = {
        lesson.lesson_date
        for lesson in _attendance_lessons(schedule, extra_dates=existing_record_dates)
    }
    if any(lesson_date not in allowed_lesson_dates for _, lesson_date in item_keys):
        raise TeachingServiceError(
            "Дата занятия отсутствует в журнале группы",
            status_code=409,
        )
    student_ids = list({student_id for student_id, _ in items_by_key})
    if student_ids:
        students = await db.scalars(
            select(Student).where(
                Student.tenant_id == tenant.id,
                Student.id.in_(student_ids),
                Student.group_name == schedule.group_name,
                Student.status == StudentStatus.ACTIVE,
            )
        )
        if len(students.all()) != len(student_ids):
            raise TeachingServiceError("В списке есть ученик из другой группы", status_code=409)

    lesson_dates = list({lesson_date for _, lesson_date in items_by_key})
    existing: list[AttendanceRecord] = []
    if student_ids and lesson_dates:
        existing = list(
            (
                await db.scalars(
                    select(AttendanceRecord).where(
                        AttendanceRecord.schedule_id == schedule.id,
                        AttendanceRecord.student_id.in_(student_ids),
                        AttendanceRecord.lesson_date.in_(lesson_dates),
                    )
                )
            ).all()
        )
    records = {
        (record.student_id, record.lesson_date): record
        for record in existing
    }
    for key, item in items_by_key.items():
        if item.makeup_completed and item.present is not False:
            raise TeachingServiceError(
                "Отработку можно отметить только для пропущенного урока",
                status_code=409,
            )
        record = records.get(key)
        if item.present is None:
            if record is not None:
                await db.delete(record)
            continue
        comment = item.comment.strip() if item.comment else None
        if record is None:
            db.add(
                AttendanceRecord(
                    tenant_id=tenant.id,
                    schedule_id=schedule.id,
                    student_id=item.student_id,
                    lesson_date=item.lesson_date,
                    present=item.present,
                    makeup_completed=item.makeup_completed,
                    marked_by_account_id=account.id,
                    comment=comment,
                )
            )
            continue
        record.present = item.present
        record.makeup_completed = item.makeup_completed
        record.comment = comment
        record.marked_by_account_id = account.id
    await db.commit()
    return await get_group_attendance_journal(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=tenant.slug,
        schedule_id=schedule.id,
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


async def send_manual_feedback_to_parents(
    db: AsyncSession,
    *,
    output_id: UUID,
    payload: ManualFeedbackSendRequest,
    default_tenant_slug: str,
) -> ManualFeedbackSendRead:
    tenant, account, role = await load_teaching_context(
        db,
        max_user_id=payload.max_user_id,
        tenant_slug=payload.tenant_slug or default_tenant_slug,
    )
    output = await db.scalar(
        select(ManualFeedbackOutput)
        .where(
            ManualFeedbackOutput.id == output_id,
            ManualFeedbackOutput.tenant_id == tenant.id,
        )
        .with_for_update()
    )
    if output is None:
        raise TeachingServiceError("Черновик не найден", status_code=404)
    if role not in MANAGER_ROLES and output.author_account_id != account.id:
        raise TeachingServiceError("Нет доступа к этому черновику", status_code=403)
    if role == StaffRole.TEACHER and not await teacher_has_group_access(
        db,
        tenant_id=UUID(str(tenant.id)),
        account=account,
        group_name=output.group_name,
    ):
        raise TeachingServiceError("Группа не закреплена за преподавателем", status_code=403)

    parent_user_ids = set(
        (
            await db.scalars(
                select(MaxAccount.max_user_id)
                .join(
                    StudentAccessLink,
                    StudentAccessLink.account_id == MaxAccount.id,
                )
                .join(Student, Student.id == StudentAccessLink.student_id)
                .where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.role == StudentAccessRole.PARENT,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                    Student.tenant_id == tenant.id,
                    Student.status == StudentStatus.ACTIVE,
                    Student.group_name == output.group_name,
                )
                .distinct()
            )
        ).all()
    )
    recipient_count = len(parent_user_ids)
    if not recipient_count:
        raise TeachingServiceError(
            "У учеников группы пока нет связанных родителей",
            status_code=409,
        )
    if output.status == "sent_to_parents":
        return ManualFeedbackSendRead(
            output_id=UUID(str(output.id)),
            parent_recipients=recipient_count,
            sent_recipients=recipient_count,
            failed_recipients=0,
            status="sent",
        )
    if output.status == "partial":
        raise TeachingServiceError(
            "Часть сообщений уже отправлена. Проверьте связи родителей перед повтором",
            status_code=409,
        )
    if is_placeholder(get_settings().max_bot_token):
        raise TeachingServiceError("Отправка MAX не настроена", status_code=503)

    sent_count = await deliver_feedback_to_parents(
        max_user_ids={int(user_id) for user_id in parent_user_ids},
        tenant_slug=tenant.slug,
        group_name=output.group_name,
        feedback_text=output.feedback_text,
    )
    failed_count = recipient_count - sent_count
    if sent_count == recipient_count:
        output.status = "sent_to_parents"
    elif sent_count:
        output.status = "partial"
    else:
        output.status = "failed"
    output.sent_at = datetime.now(UTC) if sent_count else None
    db.add(
        AuditLog(
            tenant_id=tenant.id,
            actor_account_id=account.id,
            action="manual_feedback.sent_to_parents",
            entity_type="manual_feedback_output",
            entity_id=str(output.id),
            payload={
                "group_name": output.group_name,
                "parent_recipients": recipient_count,
                "sent_recipients": sent_count,
                "failed_recipients": failed_count,
                "status": output.status,
            },
        )
    )
    await db.commit()
    return ManualFeedbackSendRead(
        output_id=UUID(str(output.id)),
        parent_recipients=recipient_count,
        sent_recipients=sent_count,
        failed_recipients=failed_count,
        status=("sent" if output.status == "sent_to_parents" else output.status),
    )


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

    resolved_teacher_account = (
        account
        if role == StaffRole.TEACHER
        else await teacher_account_for_group(
            db,
            tenant_id=UUID(str(tenant.id)),
            group_name=payload.group_name.strip(),
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
            group_name=payload.group_name.strip(),
        ):
            raise TeachingServiceError("Нельзя изменить чужое расписание", status_code=403)
    else:
        schedule = await db.scalar(
            select(TeachingSchedule)
            .where(
                TeachingSchedule.tenant_id == tenant.id,
                TeachingSchedule.group_name == payload.group_name.strip(),
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
    schedule.auto_feedback_enabled = (
        payload.auto_feedback_enabled and resolved_teacher_account is not None
    )
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
    schedule = await db.scalar(
        select(TeachingSchedule)
        .where(TeachingSchedule.id == schedule.id)
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
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
        .with_for_update()
        .options(
            selectinload(TeachingSchedule.course).selectinload(Course.lessons),
            selectinload(TeachingSchedule.lesson_overrides),
        )
    )
    if schedule is None:
        raise TeachingServiceError("Расписание не найдено", status_code=404)
    if role not in MANAGER_ROLES and schedule.teacher_account_id != account.id:
        raise TeachingServiceError("Нельзя сформировать ОС для чужой группы", status_code=403)
    lesson_number = lesson_number_for_position(
        schedule,
        schedule.current_lesson_number,
    )
    lesson = lesson_for_number(schedule.course, lesson_number)
    if lesson is None:
        raise TeachingServiceError("Урок курса не найден", status_code=409)
    lesson_date = payload.lesson_date or next_lesson_date(schedule)
    output = await db.scalar(
        select(FeedbackOutput)
        .where(
            FeedbackOutput.schedule_id == schedule.id,
            FeedbackOutput.lesson_date == lesson_date,
        )
        .options(
            selectinload(FeedbackOutput.schedule).selectinload(TeachingSchedule.course)
        )
    )
    if (
        payload.advance_lesson
        and schedule.last_generated_lesson_date == lesson_date
        and output is not None
    ):
        return feedback_to_read(output)
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
        if not schedule_has_lesson_at_position(
            schedule,
            schedule.current_lesson_number,
        ):
            schedule.is_active = False
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
