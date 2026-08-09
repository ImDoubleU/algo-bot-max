"""broadcast filters for venues and lesson modes

Revision ID: 20260809_0013
Revises: 20260801_0012
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_0013"
down_revision: str | None = "20260801_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("school_broadcasts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "venue_names",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "lesson_modes",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("school_broadcasts") as batch_op:
        batch_op.drop_column("lesson_modes")
        batch_op.drop_column("venue_names")
