"""Add student bank deposits and ledger categories.

Revision ID: 20260906_0028
Revises: 20260904_0027
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260906_0028"
down_revision: str | None = "20260904_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def upgrade() -> None:
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.add_column(
            sa.Column(
                "bank_annual_rate_bps",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
            )
        )
        batch_op.create_check_constraint(
            "ck_tenants_bank_rate_range",
            "bank_annual_rate_bps >= 0 AND bank_annual_rate_bps <= 10000",
        )

    with op.batch_alter_table("astrocoin_ledger_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "category",
                sa.String(length=20),
                server_default="accrual",
                nullable=False,
            )
        )
    op.execute(
        sa.text(
            """
            UPDATE astrocoin_ledger_entries
            SET category = 'purchase'
            WHERE idempotency_key LIKE 'order:%'
               OR idempotency_key LIKE '%:order:%'
            """
        )
    )
    with op.batch_alter_table("astrocoin_ledger_entries") as batch_op:
        batch_op.create_check_constraint(
            "ck_astrocoin_ledger_entries_astrocoin_ledger_entries_category_values",
            "category IN ('accrual', 'purchase', 'bank')",
        )
        batch_op.create_index(
            op.f("ix_astrocoin_ledger_entries_category"),
            ["category"],
            unique=False,
        )
        batch_op.alter_column("category", server_default=None)

    op.create_table(
        "bank_rate_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("annual_rate_bps", sa.Integer(), nullable=False),
        sa.Column("effective_on", sa.Date(), nullable=False),
        sa.Column("changed_by_account_id", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "annual_rate_bps >= 0 AND annual_rate_bps <= 10000",
            name=op.f("ck_bank_rate_history_bank_rate_history_rate_range"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_bank_rate_history_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_bank_rate_history_changed_by_account_id_max_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_rate_history")),
        sa.UniqueConstraint(
            "tenant_id",
            "effective_on",
            name="uq_bank_rate_history_tenant_effective_on",
        ),
    )
    op.create_index(
        op.f("ix_bank_rate_history_tenant_id"),
        "bank_rate_history",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_rate_history_effective_on"),
        "bank_rate_history",
        ["effective_on"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_rate_history_changed_by_account_id"),
        "bank_rate_history",
        ["changed_by_account_id"],
        unique=False,
    )

    op.create_table(
        "bank_deposits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column(
            "opened_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("opened_on", sa.Date(), nullable=False),
        sa.Column("maturity_on", sa.Date(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.String(length=80), nullable=True),
        sa.Column("principal_amount", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "capitalized_interest",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "pending_interest",
            sa.Numeric(precision=28, scale=12),
            server_default="0",
            nullable=False,
        ),
        sa.Column("last_processed_on", sa.Date(), nullable=False),
        sa.Column("minimum_balance_on", sa.Date(), nullable=True),
        sa.Column("minimum_balance_amount", sa.Integer(), nullable=True),
        sa.Column("returned_amount", sa.Integer(), server_default="0", nullable=False),
        sa.Column("forfeited_interest", sa.Integer(), server_default="0", nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "principal_amount >= 0",
            name=op.f("ck_bank_deposits_bank_deposits_principal_nonnegative"),
        ),
        sa.CheckConstraint(
            "capitalized_interest >= 0",
            name=op.f("ck_bank_deposits_bank_deposits_interest_nonnegative"),
        ),
        sa.CheckConstraint(
            "returned_amount >= 0",
            name=op.f("ck_bank_deposits_bank_deposits_returned_nonnegative"),
        ),
        sa.CheckConstraint(
            "forfeited_interest >= 0",
            name=op.f("ck_bank_deposits_bank_deposits_forfeited_nonnegative"),
        ),
        sa.CheckConstraint(
            "maturity_on > opened_on",
            name=op.f("ck_bank_deposits_bank_deposits_maturity_after_open"),
        ),
        sa.CheckConstraint(
            "last_processed_on >= opened_on AND last_processed_on < maturity_on",
            name=op.f("ck_bank_deposits_bank_deposits_processed_date_range"),
        ),
        sa.CheckConstraint(
            "minimum_balance_amount IS NULL OR minimum_balance_amount >= 0",
            name=op.f("ck_bank_deposits_bank_deposits_minimum_balance_nonnegative"),
        ),
        sa.CheckConstraint(
            "(minimum_balance_on IS NULL) = (minimum_balance_amount IS NULL)",
            name=op.f("ck_bank_deposits_bank_deposits_minimum_balance_pair"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'matured', 'early_closed', 'student_inactive_closed')",
            name=op.f("ck_bank_deposits_bank_deposits_status_values"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_bank_deposits_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_bank_deposits_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name=op.f("fk_bank_deposits_wallet_id_wallets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_deposits")),
    )
    op.create_index(
        op.f("ix_bank_deposits_tenant_id"),
        "bank_deposits",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_deposits_student_id"),
        "bank_deposits",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_deposits_wallet_id"),
        "bank_deposits",
        ["wallet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_deposits_maturity_on"),
        "bank_deposits",
        ["maturity_on"],
        unique=False,
    )
    op.create_index(
        "ix_bank_deposits_tenant_status",
        "bank_deposits",
        ["tenant_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_bank_deposits_active_student",
        "bank_deposits",
        ["student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "bank_daily_accruals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deposit_id", sa.Uuid(), nullable=False),
        sa.Column("accrual_date", sa.Date(), nullable=False),
        sa.Column("minimum_balance", sa.Integer(), nullable=False),
        sa.Column("annual_rate_bps", sa.Integer(), nullable=False),
        sa.Column("exact_interest", sa.Numeric(precision=28, scale=12), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "minimum_balance >= 0",
            name=op.f("ck_bank_daily_accruals_bank_daily_accruals_balance_nonnegative"),
        ),
        sa.CheckConstraint(
            "annual_rate_bps >= 0 AND annual_rate_bps <= 10000",
            name=op.f("ck_bank_daily_accruals_bank_daily_accruals_rate_range"),
        ),
        sa.CheckConstraint(
            "exact_interest >= 0",
            name=op.f("ck_bank_daily_accruals_bank_daily_accruals_interest_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_bank_daily_accruals_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deposit_id"],
            ["bank_deposits.id"],
            name=op.f("fk_bank_daily_accruals_deposit_id_bank_deposits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_daily_accruals")),
        sa.UniqueConstraint(
            "deposit_id",
            "accrual_date",
            name="uq_bank_daily_accruals_deposit_date",
        ),
    )
    op.create_index(
        op.f("ix_bank_daily_accruals_tenant_id"),
        "bank_daily_accruals",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_daily_accruals_deposit_id"),
        "bank_daily_accruals",
        ["deposit_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_daily_accruals_accrual_date"),
        "bank_daily_accruals",
        ["accrual_date"],
        unique=False,
    )

    op.create_table(
        "bank_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("deposit_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("operation_type", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False),
        sa.Column("correlation_key", sa.String(length=180), nullable=True),
        sa.Column("amount", sa.Integer(), server_default="0", nullable=False),
        sa.Column("principal_before", sa.Integer(), server_default="0", nullable=False),
        sa.Column("principal_after", sa.Integer(), server_default="0", nullable=False),
        sa.Column("interest_before", sa.Integer(), server_default="0", nullable=False),
        sa.Column("interest_after", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wallet_before", sa.Integer(), nullable=True),
        sa.Column("wallet_after", sa.Integer(), nullable=True),
        sa.Column("annual_rate_bps", sa.Integer(), nullable=True),
        sa.Column("effective_on", sa.Date(), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "amount >= 0",
            name=op.f("ck_bank_operations_bank_operations_amount_nonnegative"),
        ),
        sa.CheckConstraint(
            "principal_before >= 0 AND principal_after >= 0",
            name=op.f("ck_bank_operations_bank_operations_principal_nonnegative"),
        ),
        sa.CheckConstraint(
            "interest_before >= 0 AND interest_after >= 0",
            name=op.f("ck_bank_operations_bank_operations_interest_nonnegative"),
        ),
        sa.CheckConstraint(
            "annual_rate_bps IS NULL OR (annual_rate_bps >= 0 AND annual_rate_bps <= 10000)",
            name=op.f("ck_bank_operations_bank_operations_rate_range"),
        ),
        sa.CheckConstraint(
            "operation_type IN ("
            "'opened', 'topped_up', 'interest_capitalized', 'rate_changed', "
            "'matured', 'early_closed', 'student_inactive_closed'"
            ")",
            name=op.f("ck_bank_operations_bank_operations_type_values"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_bank_operations_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["deposit_id"],
            ["bank_deposits.id"],
            name=op.f("fk_bank_operations_deposit_id_bank_deposits"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
            name=op.f("fk_bank_operations_student_id_students"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_bank_operations_actor_account_id_max_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_operations")),
        sa.UniqueConstraint(
            "idempotency_key",
            name="uq_bank_operations_idempotency_key",
        ),
    )
    for column in ("tenant_id", "deposit_id", "student_id", "actor_account_id"):
        op.create_index(
            op.f(f"ix_bank_operations_{column}"),
            "bank_operations",
            [column],
            unique=False,
        )
    op.create_index(
        op.f("ix_bank_operations_operation_type"),
        "bank_operations",
        ["operation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_bank_operations_correlation_key"),
        "bank_operations",
        ["correlation_key"],
        unique=False,
    )
    op.create_index(
        "ix_bank_operations_student_created",
        "bank_operations",
        ["student_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_bank_operations_student_created", table_name="bank_operations")
    op.drop_table("bank_operations")
    op.drop_table("bank_daily_accruals")
    op.drop_index("uq_bank_deposits_active_student", table_name="bank_deposits")
    op.drop_index("ix_bank_deposits_tenant_status", table_name="bank_deposits")
    op.drop_table("bank_deposits")
    op.drop_table("bank_rate_history")
    with op.batch_alter_table("astrocoin_ledger_entries") as batch_op:
        batch_op.drop_index(op.f("ix_astrocoin_ledger_entries_category"))
        batch_op.drop_constraint(
            "ck_astrocoin_ledger_entries_astrocoin_ledger_entries_category_values",
            type_="check",
        )
        batch_op.drop_column("category")
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_constraint("ck_tenants_bank_rate_range", type_="check")
        batch_op.drop_column("bank_annual_rate_bps")
