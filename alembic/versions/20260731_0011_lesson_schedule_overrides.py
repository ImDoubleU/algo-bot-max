"""lesson schedule overrides

Revision ID: 20260731_0011
Revises: 20260731_0010
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0011"
down_revision: str | None = "20260731_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "teaching_lesson_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["teaching_schedules.id"],
            name=op.f("fk_teaching_lesson_overrides_schedule_id_teaching_schedules"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_teaching_lesson_overrides_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teaching_lesson_overrides")),
        sa.UniqueConstraint(
            "schedule_id",
            "position",
            name="uq_teaching_lesson_overrides_schedule_position",
        ),
    )
    op.create_index(
        op.f("ix_teaching_lesson_overrides_schedule_id"),
        "teaching_lesson_overrides",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_teaching_lesson_overrides_tenant_id"),
        "teaching_lesson_overrides",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_teaching_lesson_overrides_tenant_id"),
        table_name="teaching_lesson_overrides",
    )
    op.drop_index(
        op.f("ix_teaching_lesson_overrides_schedule_id"),
        table_name="teaching_lesson_overrides",
    )
    op.drop_table("teaching_lesson_overrides")
