from datetime import date
from uuid import UUID

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import TenantStatus


class City(TimestampMixin, Base):
    __tablename__ = "cities"

    id: Mapped[UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    tenants = relationship("Tenant", back_populates="city")


class Partner(TimestampMixin, Base):
    __tablename__ = "partners"

    id: Mapped[UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    tenants = relationship("Tenant", back_populates="partner")


class Tenant(TimestampMixin, Base):
    __tablename__ = "tenants"
    __table_args__ = (UniqueConstraint("city_id", "partner_id", name="uq_tenants_city_partner"),)

    id: Mapped[UUID] = uuid_pk()
    city_id: Mapped[UUID] = mapped_column(ForeignKey("cities.id"), index=True, nullable=False)
    partner_id: Mapped[UUID] = mapped_column(ForeignKey("partners.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(default=TenantStatus.ACTIVE, nullable=False)
    departed_access_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    access_freeze_from: Mapped[date | None] = mapped_column(Date)
    access_freeze_until: Mapped[date | None] = mapped_column(Date)
    birthday_reward_amount: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    city = relationship("City", back_populates="tenants")
    partner = relationship("Partner", back_populates="tenants")
    venues = relationship("Venue", back_populates="tenant")
    students = relationship("Student", back_populates="tenant")
    staff_assignments = relationship("StaffRoleAssignment", back_populates="tenant")
    warehouses = relationship("Warehouse", back_populates="tenant")
    warehouse_links = relationship(
        "WarehouseTenantLink",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )
    accrual_rules = relationship(
        "AstrocoinAccrualRule",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class AstrocoinAccrualRule(TimestampMixin, Base):
    __tablename__ = "astrocoin_accrual_rules"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "reason",
            name="uq_astrocoin_accrual_rules_tenant_reason",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(160), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    tenant = relationship("Tenant", back_populates="accrual_rules")


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_venues_tenant_slug"),)

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    address: Mapped[str | None] = mapped_column(String(260))
    broadcast_keywords: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    broadcast_group_names: Mapped[list[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="venues")
    students = relationship("Student", back_populates="venue")
    warehouses = relationship("Warehouse", back_populates="venue")
