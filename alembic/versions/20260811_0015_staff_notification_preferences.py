"""staff notification preferences

Revision ID: 20260811_0015
Revises: 20260809_0014
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_0015"
down_revision: str | None = "20260809_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "staff_notification_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("event_key", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "account_id",
            "event_key",
            name="uq_staff_notification_preferences_tenant_account_event",
        ),
    )
    op.create_index(
        op.f("ix_staff_notification_preferences_tenant_id"),
        "staff_notification_preferences",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_preferences_account_id"),
        "staff_notification_preferences",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_notification_preferences_event_key"),
        "staff_notification_preferences",
        ["event_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_staff_notification_preferences_event_key"),
        table_name="staff_notification_preferences",
    )
    op.drop_index(
        op.f("ix_staff_notification_preferences_account_id"),
        table_name="staff_notification_preferences",
    )
    op.drop_index(
        op.f("ix_staff_notification_preferences_tenant_id"),
        table_name="staff_notification_preferences",
    )
    op.drop_table("staff_notification_preferences")
