"""operations workflows

Revision ID: 20260728_0006
Revises: 20260727_0005
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260728_0006"
down_revision: str | None = "20260727_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_warehouse_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["account_id"], ["max_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            name="uq_staff_warehouse_preferences_tenant_account",
        ),
    )
    for column in ("tenant_id", "account_id", "warehouse_id"):
        op.create_index(
            op.f(f"ix_staff_warehouse_preferences_{column}"),
            "staff_warehouse_preferences",
            [column],
            unique=False,
        )

    op.add_column("orders", sa.Column("cancellation_reason", sa.String(500), nullable=True))
    op.add_column(
        "warehouse_inventory",
        sa.Column(
            "low_stock_notified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column("present", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("marked_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("comment", sa.String(300), nullable=True),
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
        sa.ForeignKeyConstraint(["marked_by_account_id"], ["max_accounts.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["teaching_schedules.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "schedule_id",
            "student_id",
            "lesson_date",
            name="uq_attendance_schedule_student_lesson_date",
        ),
    )
    for column in ("tenant_id", "schedule_id", "student_id", "marked_by_account_id"):
        op.create_index(
            op.f(f"ix_attendance_records_{column}"),
            "attendance_records",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("marked_by_account_id", "student_id", "schedule_id", "tenant_id"):
        op.drop_index(op.f(f"ix_attendance_records_{column}"), table_name="attendance_records")
    op.drop_table("attendance_records")
    op.drop_column("warehouse_inventory", "low_stock_notified")
    op.drop_column("orders", "cancellation_reason")
    for column in ("warehouse_id", "account_id", "tenant_id"):
        op.drop_index(
            op.f(f"ix_staff_warehouse_preferences_{column}"),
            table_name="staff_warehouse_preferences",
        )
    op.drop_table("staff_warehouse_preferences")
