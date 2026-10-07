from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class SupportTicket(TimestampMixin, Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    max_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    tenant_slug: Mapped[str | None] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False, index=True)
    private_note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notification_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupportDraft(TimestampMixin, Base):
    __tablename__ = "support_drafts"

    max_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[UUID] = mapped_column(nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str | None] = mapped_column(String(16))
    first_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    photo_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    event_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class SupportPhoto(TimestampMixin, Base):
    __tablename__ = "support_photos"

    id: Mapped[UUID] = uuid_pk()
    owner_max_user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    ticket_id: Mapped[int | None] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)


class SupportReply(TimestampMixin, Base):
    __tablename__ = "support_replies"

    id: Mapped[UUID] = uuid_pk()
    request_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("support_tickets.id"), index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="queued", nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
