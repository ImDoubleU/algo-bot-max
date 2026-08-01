"""attendance makeups

Revision ID: 20260731_0010
Revises: 20260731_0009
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_0010"
down_revision: str | None = "20260731_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "attendance_records",
        sa.Column(
            "makeup_completed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("attendance_records", "makeup_completed")
