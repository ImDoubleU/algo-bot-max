"""Collection artwork and versioned director-managed variants."""

import sqlalchemy as sa

from alembic import op

revision = "20261031_0041"
down_revision = "20261031_0040"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "pizza_offers", sa.Column("kind", sa.String(20), nullable=False, server_default="pizza")
    )
    op.add_column(
        "pizza_offers", sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.add_column(
        "pizza_campaigns", sa.Column("kind", sa.String(20), nullable=False, server_default="pizza")
    )


def downgrade():
    if op.get_bind().scalar(
        sa.text(
            "SELECT (SELECT COUNT(*) FROM pizza_offers WHERE kind <> 'pizza') + "
            "(SELECT COUNT(*) FROM pizza_campaigns WHERE kind <> 'pizza')"
        )
    ):
        raise RuntimeError("Cannot discard non-pizza collection types")
    op.drop_column("pizza_campaigns", "kind")
    op.drop_column("pizza_offers", "revision")
    op.drop_column("pizza_offers", "kind")
