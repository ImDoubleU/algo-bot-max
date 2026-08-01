from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class SchoolBroadcast(TimestampMixin, Base):
    __tablename__ = "school_broadcasts"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id"),
        index=True,
        nullable=False,
    )
    creator_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500))
    recipient_category: Mapped[str] = mapped_column(String(24), nullable=False)
    audience_filter: Mapped[str] = mapped_column(String(32), nullable=False)
    group_names: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    balance_threshold: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="sending", nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
