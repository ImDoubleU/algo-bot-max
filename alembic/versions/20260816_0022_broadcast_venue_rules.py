"""Add broadcast targeting rules to venues.

Revision ID: 20260816_0022
Revises: 20260816_0021
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0022"
down_revision: str | None = "20260816_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_default = (
        sa.text("'[]'") if op.get_bind().dialect.name == "sqlite" else sa.text("'[]'::json")
    )
    op.add_column(
        "venues",
        sa.Column(
            "broadcast_keywords",
            sa.JSON(),
            server_default=json_default,
            nullable=False,
        ),
    )
    op.add_column(
        "venues",
        sa.Column(
            "broadcast_group_names",
            sa.JSON(),
            server_default=json_default,
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("venues", "broadcast_group_names")
    op.drop_column("venues", "broadcast_keywords")
