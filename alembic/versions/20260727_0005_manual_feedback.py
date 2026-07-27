"""manual feedback outputs

Revision ID: 20260727_0005
Revises: 20260727_0004
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0005"
down_revision: str | None = "20260727_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "manual_feedback_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("author_account_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("group_name", sa.String(length=200), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("lesson_title", sa.String(length=260), nullable=False),
        sa.Column("lesson_mode", sa.String(length=40), server_default="group", nullable=False),
        sa.Column("lesson_place", sa.String(length=200), server_default="offline", nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="generated", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            ["author_account_id"],
            ["max_accounts.id"],
            name=op.f(
                "fk_manual_feedback_outputs_author_account_id_max_accounts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_manual_feedback_outputs_course_id_courses"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_manual_feedback_outputs_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_manual_feedback_outputs")),
    )
    for column in ("author_account_id", "course_id", "tenant_id"):
        op.create_index(
            op.f(f"ix_manual_feedback_outputs_{column}"),
            "manual_feedback_outputs",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in ("tenant_id", "course_id", "author_account_id"):
        op.drop_index(
            op.f(f"ix_manual_feedback_outputs_{column}"),
            table_name="manual_feedback_outputs",
        )
    op.drop_table("manual_feedback_outputs")
