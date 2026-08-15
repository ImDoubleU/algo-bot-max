"""student access grace period and freeze dates

Revision ID: 20260813_0020
Revises: 20260813_0019
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0020"
down_revision: str | None = "20260813_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "departed_access_days",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
    )
    op.add_column("tenants", sa.Column("access_freeze_from", sa.Date(), nullable=True))
    op.add_column("tenants", sa.Column("access_freeze_until", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "access_freeze_until")
    op.drop_column("tenants", "access_freeze_from")
    op.drop_column("tenants", "departed_access_days")
