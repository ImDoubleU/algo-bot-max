"""Make the birthday reward amount configurable per tenant.

Revision ID: 20260904_0027
Revises: 20260903_0026
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_0027"
down_revision: str | None = "20260903_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "birthday_reward_amount",
            sa.Integer(),
            server_default=sa.text("50"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "birthday_reward_amount")
