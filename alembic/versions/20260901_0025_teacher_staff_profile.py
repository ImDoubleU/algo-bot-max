"""Add the teacher staff profile used for automatic group matching.

Revision ID: 20260901_0025
Revises: 20260827_0024
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_0025"
down_revision: str | None = "20260827_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "max_accounts",
        sa.Column("staff_first_name", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "max_accounts",
        sa.Column("staff_last_name", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "max_accounts",
        sa.Column("staff_profile_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("max_accounts", "staff_profile_completed_at")
    op.drop_column("max_accounts", "staff_last_name")
    op.drop_column("max_accounts", "staff_first_name")
