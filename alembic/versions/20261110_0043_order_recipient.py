"""Store electronic product recipient requirements and order snapshots.

Revision ID: 20261110_0043
Revises: 20261031_0042
"""

import sqlalchemy as sa

from alembic import op

revision = "20261110_0043"
down_revision = "20261031_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("recipient_field", sa.String(32), nullable=True))
    op.add_column("order_items", sa.Column("recipient_field", sa.String(32), nullable=True))
    op.add_column("order_items", sa.Column("recipient_value", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "recipient_value")
    op.drop_column("order_items", "recipient_field")
    op.drop_column("products", "recipient_field")
