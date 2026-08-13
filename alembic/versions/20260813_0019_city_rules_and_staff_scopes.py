"""city accrual rules, staff venue scopes and student group history

Revision ID: 20260813_0019
Revises: 20260812_0018
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0019"
down_revision: str | None = "20260812_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "student_history_events",
        sa.Column("from_group_name", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "student_history_events",
        sa.Column("to_group_name", sa.String(length=160), nullable=True),
    )

    op.create_table(
        "staff_venue_scopes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["assignment_id"],
            ["staff_role_assignments.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assignment_id",
            "venue_id",
            name="uq_staff_venue_scopes_assignment_venue",
        ),
    )
    op.create_index(
        op.f("ix_staff_venue_scopes_assignment_id"),
        "staff_venue_scopes",
        ["assignment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_venue_scopes_venue_id"),
        "staff_venue_scopes",
        ["venue_id"],
        unique=False,
    )

    op.create_table(
        "astrocoin_accrual_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=160), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "reason",
            name="uq_astrocoin_accrual_rules_tenant_reason",
        ),
    )
    op.create_index(
        op.f("ix_astrocoin_accrual_rules_tenant_id"),
        "astrocoin_accrual_rules",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_astrocoin_accrual_rules_tenant_id"),
        table_name="astrocoin_accrual_rules",
    )
    op.drop_table("astrocoin_accrual_rules")
    op.drop_index(
        op.f("ix_staff_venue_scopes_venue_id"),
        table_name="staff_venue_scopes",
    )
    op.drop_index(
        op.f("ix_staff_venue_scopes_assignment_id"),
        table_name="staff_venue_scopes",
    )
    op.drop_table("staff_venue_scopes")
    op.drop_column("student_history_events", "to_group_name")
    op.drop_column("student_history_events", "from_group_name")
