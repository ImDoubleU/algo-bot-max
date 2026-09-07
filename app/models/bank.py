from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.enums import BankDepositStatus


class BankRateHistory(TimestampMixin, Base):
    __tablename__ = "bank_rate_history"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "effective_on",
            name="uq_bank_rate_history_tenant_effective_on",
        ),
        CheckConstraint(
            "annual_rate_bps >= 0 AND annual_rate_bps <= 10000",
            name="bank_rate_history_rate_range",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    annual_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    changed_by_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
    )

    tenant = relationship("Tenant", back_populates="bank_rate_history")
    changed_by = relationship("MaxAccount")


class BankDeposit(TimestampMixin, Base):
    __tablename__ = "bank_deposits"
    __table_args__ = (
        CheckConstraint("principal_amount >= 0", name="bank_deposits_principal_nonnegative"),
        CheckConstraint(
            "capitalized_interest >= 0",
            name="bank_deposits_interest_nonnegative",
        ),
        CheckConstraint("returned_amount >= 0", name="bank_deposits_returned_nonnegative"),
        CheckConstraint("forfeited_interest >= 0", name="bank_deposits_forfeited_nonnegative"),
        CheckConstraint("maturity_on > opened_on", name="bank_deposits_maturity_after_open"),
        CheckConstraint(
            "last_processed_on >= opened_on AND last_processed_on < maturity_on",
            name="bank_deposits_processed_date_range",
        ),
        CheckConstraint(
            "minimum_balance_amount IS NULL OR minimum_balance_amount >= 0",
            name="bank_deposits_minimum_balance_nonnegative",
        ),
        CheckConstraint(
            "(minimum_balance_on IS NULL) = (minimum_balance_amount IS NULL)",
            name="bank_deposits_minimum_balance_pair",
        ),
        CheckConstraint(
            "status IN ('active', 'matured', 'early_closed', 'student_inactive_closed')",
            name="bank_deposits_status_values",
        ),
        Index(
            "uq_bank_deposits_active_student",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index("ix_bank_deposits_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(40),
        default=BankDepositStatus.ACTIVE.value,
        nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    maturity_on: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(String(80))
    principal_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    capitalized_interest: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pending_interest: Mapped[Decimal] = mapped_column(
        Numeric(28, 12),
        default=Decimal("0"),
        nullable=False,
    )
    last_processed_on: Mapped[date] = mapped_column(Date, nullable=False)
    minimum_balance_on: Mapped[date | None] = mapped_column(Date)
    minimum_balance_amount: Mapped[int | None] = mapped_column(Integer)
    returned_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    forfeited_interest: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    tenant = relationship("Tenant", back_populates="bank_deposits")
    student = relationship("Student", back_populates="bank_deposits")
    wallet = relationship("Wallet", back_populates="bank_deposits")
    daily_accruals = relationship(
        "BankDailyAccrual",
        back_populates="deposit",
        cascade="all, delete-orphan",
    )
    operations = relationship(
        "BankOperation",
        back_populates="deposit",
        cascade="all, delete-orphan",
    )

    @property
    def bank_balance(self) -> int:
        if self.status != BankDepositStatus.ACTIVE.value:
            return 0
        return self.principal_amount + self.capitalized_interest


class BankDailyAccrual(TimestampMixin, Base):
    __tablename__ = "bank_daily_accruals"
    __table_args__ = (
        UniqueConstraint(
            "deposit_id",
            "accrual_date",
            name="uq_bank_daily_accruals_deposit_date",
        ),
        CheckConstraint(
            "minimum_balance >= 0",
            name="bank_daily_accruals_balance_nonnegative",
        ),
        CheckConstraint(
            "annual_rate_bps >= 0 AND annual_rate_bps <= 10000",
            name="bank_daily_accruals_rate_range",
        ),
        CheckConstraint(
            "exact_interest >= 0",
            name="bank_daily_accruals_interest_nonnegative",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    deposit_id: Mapped[UUID] = mapped_column(
        ForeignKey("bank_deposits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    accrual_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    minimum_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    annual_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_interest: Mapped[Decimal] = mapped_column(Numeric(28, 12), nullable=False)

    deposit = relationship("BankDeposit", back_populates="daily_accruals")


class BankOperation(TimestampMixin, Base):
    __tablename__ = "bank_operations"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_bank_operations_idempotency_key"),
        Index("ix_bank_operations_student_created", "student_id", "created_at"),
        CheckConstraint("amount >= 0", name="bank_operations_amount_nonnegative"),
        CheckConstraint(
            "principal_before >= 0 AND principal_after >= 0",
            name="bank_operations_principal_nonnegative",
        ),
        CheckConstraint(
            "interest_before >= 0 AND interest_after >= 0",
            name="bank_operations_interest_nonnegative",
        ),
        CheckConstraint(
            "annual_rate_bps IS NULL OR (annual_rate_bps >= 0 AND annual_rate_bps <= 10000)",
            name="bank_operations_rate_range",
        ),
        CheckConstraint(
            "operation_type IN ("
            "'opened', 'topped_up', 'interest_capitalized', 'rate_changed', "
            "'matured', 'early_closed', 'student_inactive_closed'"
            ")",
            name="bank_operations_type_values",
        ),
    )

    id: Mapped[UUID] = uuid_pk()
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    deposit_id: Mapped[UUID] = mapped_column(
        ForeignKey("bank_deposits.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    actor_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("max_accounts.id"),
        index=True,
    )
    operation_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False)
    correlation_key: Mapped[str | None] = mapped_column(String(180), index=True)
    amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    principal_before: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    principal_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interest_before: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    interest_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    wallet_before: Mapped[int | None] = mapped_column(Integer)
    wallet_after: Mapped[int | None] = mapped_column(Integer)
    annual_rate_bps: Mapped[int | None] = mapped_column(Integer)
    effective_on: Mapped[date | None] = mapped_column(Date)
    comment: Mapped[str | None] = mapped_column(String(500))
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    deposit = relationship("BankDeposit", back_populates="operations")
    student = relationship("Student")
    actor = relationship("MaxAccount")
