"""Store the city and child's name supplied in support forms."""

import sqlalchemy as sa

from alembic import op

revision = "20261017_0038"
down_revision = "20261012_0037"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("support_tickets", "support_drafts"):
        op.add_column(table, sa.Column("city_name", sa.String(120), nullable=True))
        op.add_column(table, sa.Column("child_full_name", sa.String(160), nullable=True))


def downgrade():
    for table in ("support_drafts", "support_tickets"):
        op.drop_column(table, "child_full_name")
        op.drop_column(table, "city_name")
