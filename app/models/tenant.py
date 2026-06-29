from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
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

    city = relationship("City", back_populates="tenants")
    partner = relationship("Partner", back_populates="tenants")
    venues = relationship("Venue", back_populates="tenant")
    students = relationship("Student", back_populates="tenant")
    staff_assignments = relationship("StaffRoleAssignment", back_populates="tenant")
    warehouses = relationship("Warehouse", back_populates="tenant")


class Venue(TimestampMixin, Base):
    __tablename__ = "venues"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_venues_tenant_slug"),)

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    address: Mapped[str | None] = mapped_column(String(260))

    tenant = relationship("Tenant", back_populates="venues")
    students = relationship("Student", back_populates="venue")
    warehouses = relationship("Warehouse", back_populates="venue")
