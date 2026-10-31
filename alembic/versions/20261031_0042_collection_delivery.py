"""Durable collection notice delivery and retries."""

import sqlalchemy as sa

from alembic import op

revision = "20261031_0042"
down_revision = "20261031_0041"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("attempted_at", "next_attempt_at", "cancelled_at"):
        op.add_column("pizza_notices", sa.Column(name, sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "pizza_notices", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("pizza_notices", sa.Column("last_error", sa.String(120), nullable=True))
    op.create_index("ix_pizza_notices_next_attempt_at", "pizza_notices", ["next_attempt_at"])


def downgrade():
    op.drop_index("ix_pizza_notices_next_attempt_at", "pizza_notices")
    for name in ("last_error", "attempts", "cancelled_at", "next_attempt_at", "attempted_at"):
        op.drop_column("pizza_notices", name)
