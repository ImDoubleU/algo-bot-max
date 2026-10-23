"""Allow electronic products delivered manually after purchase.

Revision ID: 20261021_0039
Revises: 20261017_0038
"""

from alembic import op

revision = "20261021_0039"
down_revision = "20261017_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE productfulfillmenttype ADD VALUE IF NOT EXISTS 'DIGITAL_MANUAL'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed without rebuilding dependent columns.
    # Refuse to downgrade while data still requires the new fulfillment mode.
    bind = op.get_bind()
    value = "DIGITAL_MANUAL"
    from sqlalchemy import text

    if bind.execute(text("SELECT 1 FROM products WHERE fulfillment_type = :value LIMIT 1"),
                    {"value": value}).first():
        raise RuntimeError("Remove manual electronic products before downgrading")
