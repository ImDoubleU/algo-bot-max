"""student import history and status dates

Revision ID: 20260809_0014
Revises: 20260809_0013
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0014"
down_revision: str | None = "20260809_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "students",
        sa.Column(
            "status_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "students",
        sa.Column("departed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE students
            SET status_updated_at = updated_at,
                departed_at = CASE
                    WHEN status = 'DEPARTED' THEN updated_at
                    ELSE NULL
                END
            """
        )
    )

    op.create_table(
        "student_history_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("actor_account_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("from_status", sa.String(length=20), nullable=True),
        sa.Column("to_status", sa.String(length=20), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=40),
            server_default="crm_import",
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["actor_account_id"], ["max_accounts.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("tenant_id", "student_id", "actor_account_id", "event_type"):
        op.create_index(
            op.f(f"ix_student_history_events_{column}"),
            "student_history_events",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("event_type", "actor_account_id", "student_id", "tenant_id"):
        op.drop_index(
            op.f(f"ix_student_history_events_{column}"),
            table_name="student_history_events",
        )
    op.drop_table("student_history_events")
    op.drop_column("students", "departed_at")
    op.drop_column("students", "status_updated_at")
