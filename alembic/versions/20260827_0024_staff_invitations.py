"""Add one-time staff invitations.

Revision ID: 20260827_0024
Revises: 20260822_0023
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260827_0024"
down_revision: str | None = "20260822_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

staff_role = postgresql.ENUM(
    "SUPERADMIN",
    "PARTNER_DIRECTOR",
    "ADMIN",
    "CURATOR",
    "TEACHER",
    name="staffrole",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "staff_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("role", staff_role, nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_account_id", sa.Uuid(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("redeemed_by_account_id", sa.Uuid(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["max_accounts.id"]),
        sa.ForeignKeyConstraint(["redeemed_by_account_id"], ["max_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_staff_invitations_token_hash"),
    )
    op.create_index(
        op.f("ix_staff_invitations_tenant_id"),
        "staff_invitations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_invitations_created_by_account_id"),
        "staff_invitations",
        ["created_by_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_invitations_redeemed_by_account_id"),
        "staff_invitations",
        ["redeemed_by_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_staff_invitations_expires_at"),
        "staff_invitations",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_staff_invitations_expires_at"), table_name="staff_invitations")
    op.drop_index(
        op.f("ix_staff_invitations_redeemed_by_account_id"),
        table_name="staff_invitations",
    )
    op.drop_index(
        op.f("ix_staff_invitations_created_by_account_id"),
        table_name="staff_invitations",
    )
    op.drop_index(op.f("ix_staff_invitations_tenant_id"), table_name="staff_invitations")
    op.drop_table("staff_invitations")
