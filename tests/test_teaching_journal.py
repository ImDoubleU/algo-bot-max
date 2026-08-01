from datetime import date, time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import AssignmentStatus, StaffRole, StudentStatus
from app.models.student import Student
from app.models.teaching import Course, CourseLesson, TeachingSchedule
from app.models.tenant import City, Partner, Tenant
from app.schemas.teaching import (
    AttendanceJournalUpdateItem,
    AttendanceJournalUpdateRequest,
    AttendanceLessonUpdateItem,
)
from app.services.teaching import (
    get_group_attendance_journal,
    get_teaching_workspace,
    update_group_attendance_journal,
)


@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_teacher_opens_group_journal_and_marks_makeup(db_session) -> None:
    city = City(slug="city-a", name="Город")
    partner = Partner(slug="partner-a", name="Партнер")
    db_session.add_all([city, partner])
    await db_session.flush()
    tenant = Tenant(
        city_id=city.id,
        partner_id=partner.id,
        slug="city-a-partner-a",
        name="Город · Партнер",
    )
    db_session.add(tenant)
    await db_session.flush()

    administrator = MaxAccount(max_user_id=1001, display_name="Администратор")
    teacher = MaxAccount(max_user_id=1002, display_name="Иванова Анна")
    db_session.add_all([administrator, teacher])
    await db_session.flush()
    db_session.add(
        StaffRoleAssignment(
            tenant_id=tenant.id,
            account_id=teacher.id,
            role=StaffRole.TEACHER,
            status=AssignmentStatus.ACTIVE,
        )
    )
    student = Student(
        tenant_id=tenant.id,
        student_access_code="student-1",
        first_name="Алиса",
        last_name="Смирнова",
        group_name="Python, ср 18:00",
        teacher_name="Иванова Анна",
        status=StudentStatus.ACTIVE,
    )
    course = Course(tenant_id=tenant.id, name="Python", is_active=True)
    db_session.add_all([student, course])
    await db_session.flush()
    lessons = [
        CourseLesson(
            tenant_id=tenant.id,
            course_id=course.id,
            lesson_number=number,
            title=f"Урок {number}",
            educational_results="Результат",
        )
        for number in range(1, 4)
    ]
    db_session.add_all(lessons)
    schedule = TeachingSchedule(
        tenant_id=tenant.id,
        teacher_account_id=administrator.id,
        course_id=course.id,
        group_name=student.group_name,
        first_lesson_date=date(2026, 7, 1),
        weekday=2,
        lesson_time=time(18, 0),
        current_lesson_number=3,
    )
    db_session.add(schedule)
    await db_session.commit()

    workspace = await get_teaching_workspace(
        db_session,
        max_user_id=teacher.max_user_id,
        tenant_slug=tenant.slug,
    )
    assert [item.group_name for item in workspace.schedules] == [student.group_name]

    journal = await get_group_attendance_journal(
        db_session,
        max_user_id=teacher.max_user_id,
        tenant_slug=tenant.slug,
        schedule_id=schedule.id,
    )
    assert len(journal.lessons) == 3
    assert journal.students[0].student_name == "Смирнова Алиса"

    updated = await update_group_attendance_journal(
        db_session,
        schedule_id=schedule.id,
        payload=AttendanceJournalUpdateRequest(
            max_user_id=teacher.max_user_id,
            tenant_slug=tenant.slug,
            items=[
                AttendanceJournalUpdateItem(
                    student_id=student.id,
                    lesson_date=date(2026, 7, 1),
                    present=False,
                    makeup_completed=True,
                )
            ],
        ),
        default_tenant_slug=tenant.slug,
    )
    mark = updated.students[0].marks[0]
    assert mark.present is False
    assert mark.makeup_completed is True

    await update_group_attendance_journal(
        db_session,
        schedule_id=schedule.id,
        payload=AttendanceJournalUpdateRequest(
            max_user_id=teacher.max_user_id,
            tenant_slug=tenant.slug,
            items=[
                AttendanceJournalUpdateItem(
                    student_id=student.id,
                    lesson_date=date(2026, 7, 8),
                    present=False,
                )
            ],
        ),
        default_tenant_slug=tenant.slug,
    )
    moved = await update_group_attendance_journal(
        db_session,
        schedule_id=schedule.id,
        payload=AttendanceJournalUpdateRequest(
            max_user_id=teacher.max_user_id,
            tenant_slug=tenant.slug,
            lessons=[
                AttendanceLessonUpdateItem(
                    position=2,
                    lesson_date=date(2026, 7, 10),
                    lesson_number=1,
                )
            ],
        ),
        default_tenant_slug=tenant.slug,
    )
    repeated_lesson = next(item for item in moved.lessons if item.position == 2)
    assert repeated_lesson.lesson_date == date(2026, 7, 10)
    assert repeated_lesson.lesson_number == 1
    assert date(2026, 7, 10) in {item.lesson_date for item in moved.students[0].marks}
