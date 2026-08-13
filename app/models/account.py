from uuid import UUID

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import AssignmentStatus, StaffRole


class MaxAccount(TimestampMixin, Base):
    __tablename__ = "max_accounts"

    id: Mapped[UUID] = uuid_pk()
    max_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(120))
    display_name: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))

    staff_assignments = relationship("StaffRoleAssignment", back_populates="account")
    student_links = relationship("StudentAccessLink", back_populates="account")


class StaffRoleAssignment(TimestampMixin, Base):
    __tablename__ = "staff_role_assignments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "account_id",
            "role",
            name="uq_staff_role_assignments_tenant_account_role",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    role: Mapped[StaffRole] = mapped_column(nullable=False)
    status: Mapped[AssignmentStatus] = mapped_column(
        default=AssignmentStatus.ACTIVE,
        nullable=False,
    )

    tenant = relationship("Tenant", back_populates="staff_assignments")
    account = relationship("MaxAccount", back_populates="staff_assignments")
    venue_scopes = relationship(
        "StaffVenueScope",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class StaffVenueScope(TimestampMixin, Base):
    __tablename__ = "staff_venue_scopes"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "venue_id",
            name="uq_staff_venue_scopes_assignment_venue",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    assignment_id: Mapped[UUID] = mapped_column(
        ForeignKey("staff_role_assignments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    venue_id: Mapped[UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    assignment = relationship("StaffRoleAssignment", back_populates="venue_scopes")
    venue = relationship("Venue")


class StaffWarehousePreference(TimestampMixin, Base):
    __tablename__ = "staff_warehouse_preferences"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "account_id",
            name="uq_staff_warehouse_preferences_tenant_account",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id"),
        index=True,
        nullable=False,
    )

    account = relationship("MaxAccount")
    warehouse = relationship("Warehouse")


class StaffNotificationPreference(TimestampMixin, Base):
    __tablename__ = "staff_notification_preferences"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "account_id",
            "event_key",
            name="uq_staff_notification_preferences_tenant_account_event",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)

    account = relationship("MaxAccount")
