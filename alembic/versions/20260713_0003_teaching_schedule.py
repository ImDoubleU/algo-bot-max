"""teaching courses, schedules and feedback

Revision ID: 20260713_0003
Revises: 20260616_0002
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_0003"
down_revision: str | None = "20260616_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamp_columns() -> tuple[sa.Column, sa.Column]:
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
    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_courses_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_courses")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_courses_tenant_name"),
    )
    op.create_index(op.f("ix_courses_tenant_id"), "courses", ["tenant_id"], unique=False)

    op.create_table(
        "course_lessons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=260), nullable=False),
        sa.Column("educational_results", sa.Text(), nullable=False),
        sa.Column("image_path", sa.String(length=500), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_course_lessons_course_id_courses"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_course_lessons_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_lessons")),
        sa.UniqueConstraint(
            "tenant_id",
            "course_id",
            "lesson_number",
            name="uq_course_lessons_tenant_course_number",
        ),
    )
    op.create_index(
        op.f("ix_course_lessons_course_id"),
        "course_lessons",
        ["course_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_course_lessons_tenant_id"),
        "course_lessons",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "teaching_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("teacher_account_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("group_name", sa.String(length=200), nullable=False),
        sa.Column("first_lesson_date", sa.Date(), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("lesson_time", sa.Time(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), server_default="90", nullable=False),
        sa.Column("lesson_mode", sa.String(length=40), server_default="group", nullable=False),
        sa.Column("lesson_place", sa.String(length=200), server_default="offline", nullable=False),
        sa.Column("current_lesson_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("lesson_offset", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "auto_feedback_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "parent_delivery_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_generated_lesson_date", sa.Date(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name=op.f("fk_teaching_schedules_course_id_courses"),
        ),
        sa.ForeignKeyConstraint(
            ["teacher_account_id"],
            ["max_accounts.id"],
            name=op.f("fk_teaching_schedules_teacher_account_id_max_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_teaching_schedules_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teaching_schedules")),
        sa.UniqueConstraint(
            "tenant_id",
            "teacher_account_id",
            "group_name",
            name="uq_teaching_schedules_tenant_teacher_group",
        ),
    )
    for column in ("course_id", "teacher_account_id", "tenant_id"):
        op.create_index(
            op.f(f"ix_teaching_schedules_{column}"),
            "teaching_schedules",
            [column],
            unique=False,
        )

    op.create_table(
        "feedback_outputs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_date", sa.Date(), nullable=False),
        sa.Column("lesson_number", sa.Integer(), nullable=False),
        sa.Column("lesson_title", sa.String(length=260), nullable=False),
        sa.Column("feedback_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="generated", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["teaching_schedules.id"],
            name=op.f("fk_feedback_outputs_schedule_id_teaching_schedules"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_feedback_outputs_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_outputs")),
        sa.UniqueConstraint(
            "schedule_id",
            "lesson_date",
            name="uq_feedback_outputs_schedule_lesson_date",
        ),
    )
    op.create_index(
        op.f("ix_feedback_outputs_schedule_id"),
        "feedback_outputs",
        ["schedule_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_outputs_tenant_id"),
        "feedback_outputs",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_feedback_outputs_tenant_id"), table_name="feedback_outputs")
    op.drop_index(op.f("ix_feedback_outputs_schedule_id"), table_name="feedback_outputs")
    op.drop_table("feedback_outputs")
    for column in ("tenant_id", "teacher_account_id", "course_id"):
        op.drop_index(
            op.f(f"ix_teaching_schedules_{column}"),
            table_name="teaching_schedules",
        )
    op.drop_table("teaching_schedules")
    op.drop_index(op.f("ix_course_lessons_tenant_id"), table_name="course_lessons")
    op.drop_index(op.f("ix_course_lessons_course_id"), table_name="course_lessons")
    op.drop_table("course_lessons")
    op.drop_index(op.f("ix_courses_tenant_id"), table_name="courses")
    op.drop_table("courses")
