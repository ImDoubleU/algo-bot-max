"""Durable personal replies to support tickets."""

import sqlalchemy as sa

from alembic import op

revision = "20261007_0033"
down_revision = "20261007_0032"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_replies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id"), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    )
    op.create_index("ix_support_replies_ticket_id", "support_replies", ["ticket_id"])


def downgrade():
    op.drop_table("support_replies")
