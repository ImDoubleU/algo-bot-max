"""Group collections are separate from ordinary goods and warehouse orders."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class PizzaOffer(TimestampMixin, Base):
    __tablename__ = "pizza_offers"
    __table_args__ = (CheckConstraint("share > 0", name="pizza_offer_share_positive"),)

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("max_accounts.id"))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    share: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(default=True)


class PizzaCampaign(TimestampMixin, Base):
    __tablename__ = "pizza_campaigns"
    __table_args__ = (
        CheckConstraint("share > 0 AND target > 0", name="pizza_campaign_amount_positive"),
        CheckConstraint(
            "collected >= 0 AND collected <= target", name="pizza_campaign_amount_range"
        ),
        Index(
            "uq_pizza_live_group",
            "tenant_id",
            "group_name",
            unique=True,
            postgresql_where=text("status IN ('open','funded','paid','ordered')"),
            sqlite_where=text("status IN ('open','funded','paid','ordered')"),
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    offer_id: Mapped[UUID] = mapped_column(ForeignKey("pizza_offers.id"))
    teacher_id: Mapped[UUID] = mapped_column(ForeignKey("max_accounts.id"), index=True)
    group_name: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    roster: Mapped[list] = mapped_column(JSON)
    share: Mapped[int] = mapped_column(Integer)
    target: Mapped[int] = mapped_column(Integer)
    collected: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PizzaContribution(TimestampMixin, Base):
    __tablename__ = "pizza_contributions"
    __table_args__ = (
        UniqueConstraint("campaign_id", "student_id", name="uq_pizza_contribution_student"),
        CheckConstraint("amount > 0", name="pizza_contribution_positive"),
    )

    id: Mapped[UUID] = uuid_pk()
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("pizza_campaigns.id"), index=True)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"))
    account_id: Mapped[UUID] = mapped_column(ForeignKey("max_accounts.id"))
    amount: Mapped[int] = mapped_column(Integer)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PizzaNotice(TimestampMixin, Base):
    """Transactional outbox; local preview displays it without sending MAX messages."""

    __tablename__ = "pizza_notices"
    __table_args__ = (
        UniqueConstraint("campaign_id", "account_id", "event", name="uq_pizza_notice_recipient"),
    )

    id: Mapped[UUID] = uuid_pk()
    campaign_id: Mapped[UUID] = mapped_column(ForeignKey("pizza_campaigns.id"))
    account_id: Mapped[UUID] = mapped_column(ForeignKey("max_accounts.id"), index=True)
    event: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(700))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
