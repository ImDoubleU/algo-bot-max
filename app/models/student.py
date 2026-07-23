from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    LedgerDirection,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
)


class Student(TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("tenant_id", "lms_student_id", name="uq_students_tenant_lms_student"),
        UniqueConstraint("tenant_id", "student_access_code", name="uq_students_tenant_access_code"),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    venue_id: Mapped[UUID | None] = mapped_column(ForeignKey("venues.id"), index=True)
    lms_student_id: Mapped[str | None] = mapped_column(String(120), index=True)
    student_access_code: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(120))
    group_name: Mapped[str | None] = mapped_column(String(160))
    course_name: Mapped[str | None] = mapped_column(String(160))
    venue_name: Mapped[str | None] = mapped_column(String(160))
    teacher_name: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[StudentStatus] = mapped_column(default=StudentStatus.ACTIVE, nullable=False)

    tenant = relationship("Tenant", back_populates="students")
    venue = relationship("Venue", back_populates="students")
    contact_links = relationship("ContactStudentLink", back_populates="student")
    access_links = relationship("StudentAccessLink", back_populates="student")
    wallet = relationship("Wallet", back_populates="student", uselist=False)

    @property
    def display_name(self) -> str:
        return " ".join(
            part.strip() for part in (self.last_name, self.first_name) if part and part.strip()
        )


class Contact(TimestampMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_contact_id", name="uq_contacts_tenant_external_id"),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    external_contact_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160))

    student_links = relationship("ContactStudentLink", back_populates="contact")


class ContactStudentLink(TimestampMixin, Base):
    __tablename__ = "contact_student_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "contact_id",
            "student_id",
            name="uq_contact_student_links_tenant_contact_student",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    contact_id: Mapped[UUID] = mapped_column(ForeignKey("contacts.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)

    contact = relationship("Contact", back_populates="student_links")
    student = relationship("Student", back_populates="contact_links")


class StudentAccessLink(TimestampMixin, Base):
    __tablename__ = "student_access_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "account_id",
            "student_id",
            "role",
            name="uq_student_access_links_tenant_account_student_role",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    role: Mapped[StudentAccessRole] = mapped_column(nullable=False)
    status: Mapped[StudentAccessStatus] = mapped_column(
        default=StudentAccessStatus.ACTIVE,
        nullable=False,
    )
    source: Mapped[StudentAccessSource] = mapped_column(
        default=StudentAccessSource.ID_ENTRY,
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    account = relationship("MaxAccount", back_populates="student_links")
    student = relationship("Student", back_populates="access_links")


class Wallet(TimestampMixin, Base):
    __tablename__ = "wallets"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    balance: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    student = relationship("Student", back_populates="wallet")
    ledger_entries = relationship("AstrocoinLedgerEntry", back_populates="wallet")


class AstrocoinLedgerEntry(TimestampMixin, Base):
    __tablename__ = "astrocoin_ledger_entries"

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"), index=True, nullable=False)
    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id"), index=True, nullable=False)
    actor_account_id: Mapped[UUID | None] = mapped_column(ForeignKey("max_accounts.id"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    direction: Mapped[LedgerDirection] = mapped_column(nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(240), nullable=False)
    comment: Mapped[str | None] = mapped_column(String(500))

    wallet = relationship("Wallet", back_populates="ledger_entries")
