"""Two-way support conversations and per-message read receipts."""

import sqlalchemy as sa

from alembic import op

revision = "20261012_0037"
down_revision = "20261010_0036"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("support_replies", sa.Column(
        "author", sa.String(16), nullable=False, server_default="staff"))
    op.add_column("support_replies", sa.Column(
        "photo_ids", sa.JSON(), nullable=False, server_default="[]"))
    for name in ("read_at", "notified_at", "notification_attempted_at"):
        op.add_column("support_replies", sa.Column(name, sa.DateTime(timezone=True)))
    op.create_table(
        "support_conversations",
        sa.Column("max_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("ticket_id", sa.Integer(),
                  sa.ForeignKey("support_tickets.id", ondelete="SET NULL")),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pending_messages", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_support_conversations_ticket_id", "support_conversations", ["ticket_id"])


def downgrade():
    op.drop_table("support_conversations")
    for name in ("notification_attempted_at", "notified_at", "read_at", "photo_ids", "author"):
        op.drop_column("support_replies", name)
    op.execute("UPDATE support_tickets SET status = 'in_progress' WHERE status = 'waiting'")
