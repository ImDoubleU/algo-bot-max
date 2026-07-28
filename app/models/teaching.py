from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk


class Course(TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_courses_tenant_name"),)

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lessons = relationship(
        "CourseLesson",
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="CourseLesson.lesson_number",
    )
    schedules = relationship("TeachingSchedule", back_populates="course")


class CourseLesson(TimestampMixin, Base):
    __tablename__ = "course_lessons"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "course_id",
            "lesson_number",
            name="uq_course_lessons_tenant_course_number",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(260), nullable=False)
    educational_results: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[str | None] = mapped_column(String(500))

    course = relationship("Course", back_populates="lessons")


class TeachingSchedule(TimestampMixin, Base):
    __tablename__ = "teaching_schedules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "teacher_account_id",
            "group_name",
            name="uq_teaching_schedules_tenant_teacher_group",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    teacher_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    first_lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_time: Mapped[time] = mapped_column(Time, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    lesson_mode: Mapped[str] = mapped_column(String(40), default="group", nullable=False)
    lesson_place: Mapped[str] = mapped_column(String(200), default="offline", nullable=False)
    current_lesson_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    lesson_offset: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    auto_feedback_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_generated_lesson_date: Mapped[date | None] = mapped_column(Date)

    course = relationship("Course", back_populates="schedules")
    teacher_account = relationship("MaxAccount")
    feedback_outputs = relationship(
        "FeedbackOutput",
        back_populates="schedule",
        cascade="all, delete-orphan",
    )


class FeedbackOutput(TimestampMixin, Base):
    __tablename__ = "feedback_outputs"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "lesson_date",
            name="uq_feedback_outputs_schedule_lesson_date",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("teaching_schedules.id"),
        index=True,
        nullable=False,
    )
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_title: Mapped[str] = mapped_column(String(260), nullable=False)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="generated", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    schedule = relationship("TeachingSchedule", back_populates="feedback_outputs")


class ManualFeedbackOutput(TimestampMixin, Base):
    __tablename__ = "manual_feedback_outputs"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    author_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    course_id: Mapped[UUID] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lesson_title: Mapped[str] = mapped_column(String(260), nullable=False)
    lesson_mode: Mapped[str] = mapped_column(String(40), default="group", nullable=False)
    lesson_place: Mapped[str] = mapped_column(String(200), default="offline", nullable=False)
    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="generated", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author_account = relationship("MaxAccount")
    course = relationship("Course")


class AttendanceRecord(TimestampMixin, Base):
    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id",
            "student_id",
            "lesson_date",
            name="uq_attendance_schedule_student_lesson_date",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    schedule_id: Mapped[UUID] = mapped_column(
        ForeignKey("teaching_schedules.id"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id"),
        index=True,
        nullable=False,
    )
    lesson_date: Mapped[date] = mapped_column(Date, nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    marked_by_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(String(300))

    schedule = relationship("TeachingSchedule")
    student = relationship("Student")
    marked_by = relationship("MaxAccount")
