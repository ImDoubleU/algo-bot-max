from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class FeedbackSchedule(TimestampMixin, Base):
    __tablename__ = "feedback_schedules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "teacher_account_id",
            "group_name",
            name="uq_feedback_schedules_teacher_group",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    teacher_account_id: Mapped[UUID] = mapped_column(ForeignKey("max_accounts.id"), nullable=False)
    group_name: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
