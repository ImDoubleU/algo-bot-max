"""Teacher-owned feedback schedules."""

import sqlalchemy as sa

from alembic import op

revision = "20261004_0031"
down_revision = "20260921_0030"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feedback_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column(
            "teacher_account_id", sa.Uuid(), sa.ForeignKey("max_accounts.id"), nullable=False
        ),
        sa.Column("group_name", sa.String(200), nullable=False),
        sa.Column("schedule", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "teacher_account_id",
            "group_name",
            name="uq_feedback_schedules_teacher_group",
        ),
    )


def downgrade():
    op.drop_table("feedback_schedules")
