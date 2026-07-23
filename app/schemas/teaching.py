from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, Field


class CourseSummaryRead(BaseModel):
    id: UUID
    name: str
    lesson_count: int


class TeachingGroupOptionRead(BaseModel):
    name: str
    course_name: str | None = None
    student_count: int


class TeachingScheduleRead(BaseModel):
    id: UUID
    group_name: str
    course_id: UUID
    course_name: str
    lesson_count: int
    first_lesson_date: date
    weekday: int
    lesson_time: time
    duration_minutes: int
    lesson_mode: str
    lesson_place: str
    current_lesson_number: int
    lesson_offset: int
    auto_feedback_enabled: bool
    parent_delivery_enabled: bool
    is_active: bool
    last_generated_lesson_date: date | None = None
    next_lesson_date: date
    next_lesson_title: str | None = None


class FeedbackOutputRead(BaseModel):
    id: UUID
    schedule_id: UUID
    group_name: str
    course_name: str
    lesson_date: date
    lesson_number: int
    lesson_title: str
    feedback_text: str
    status: str
    sent_at: datetime | None = None
    created_at: datetime


class TeachingWorkspaceRead(BaseModel):
    tenant_slug: str
    courses: list[CourseSummaryRead]
    groups: list[TeachingGroupOptionRead]
    schedules: list[TeachingScheduleRead]
    feedback_outputs: list[FeedbackOutputRead]


class TeachingScheduleUpsert(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    schedule_id: UUID | None = None
    group_name: str = Field(min_length=2, max_length=200)
    course_id: UUID
    first_lesson_date: date
    lesson_time: time
    duration_minutes: int = Field(default=90, ge=30, le=240)
    lesson_mode: str = Field(default="group", pattern="^(group|individual)$")
    lesson_place: str = Field(default="offline", min_length=2, max_length=200)
    current_lesson_number: int = Field(default=1, ge=1, le=1000)
    lesson_offset: int = Field(default=0, ge=-100, le=100)
    auto_feedback_enabled: bool = True
    parent_delivery_enabled: bool = False
    is_active: bool = True


class FeedbackGenerateRequest(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None
    lesson_date: date | None = None
    absent_students: list[str] = Field(default_factory=list, max_length=100)
    is_repetition: bool = False
    advance_lesson: bool = False


class FeedbackDeliveryRequest(BaseModel):
    max_user_id: int = Field(gt=0)
    tenant_slug: str | None = None


class FeedbackDeliveryRead(BaseModel):
    output_id: UUID
    parent_recipients: int
    sent_recipients: int
    status: str
