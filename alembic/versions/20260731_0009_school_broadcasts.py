"""school broadcasts

Revision ID: 20260731_0009
Revises: 20260730_0008
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0009"
down_revision: str | None = "20260730_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "school_broadcasts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("creator_account_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("recipient_category", sa.String(length=24), nullable=False),
        sa.Column("audience_filter", sa.String(length=32), nullable=False),
        sa.Column("group_names", sa.JSON(), nullable=False),
        sa.Column("balance_threshold", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("recipient_count", sa.Integer(), nullable=False),
        sa.Column("delivered_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
            ["creator_account_id"],
            ["max_accounts.id"],
            name=op.f(
                "fk_school_broadcasts_creator_account_id_max_accounts"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_school_broadcasts_tenant_id_tenants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_school_broadcasts")),
    )
    op.create_index(
        op.f("ix_school_broadcasts_creator_account_id"),
        "school_broadcasts",
        ["creator_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_school_broadcasts_tenant_id"),
        "school_broadcasts",
        ["tenant_id"],
        unique=False,
    )
    op.execute(
        "UPDATE teaching_schedules SET parent_delivery_enabled = false"
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_school_broadcasts_tenant_id"),
        table_name="school_broadcasts",
    )
    op.drop_index(
        op.f("ix_school_broadcasts_creator_account_id"),
        table_name="school_broadcasts",
    )
    op.drop_table("school_broadcasts")
