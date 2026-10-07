"""Persistent support tickets, private images, and bot forms."""

import sqlalchemy as sa

from alembic import op

revision = "20261007_0032"
down_revision = "20261004_0031"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
    ]


def upgrade():
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("max_user_id", sa.BigInteger(), nullable=False),
        sa.Column("tenant_slug", sa.String(160)),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("private_note", sa.Text(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("notification_attempts", sa.Integer(), nullable=False),
        sa.Column("notification_attempted_at", sa.DateTime(timezone=True)),
        *timestamps(),
    )
    op.create_index("ix_support_tickets_max_user_id", "support_tickets", ["max_user_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])
    op.create_table(
        "support_drafts",
        sa.Column("max_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("role", sa.String(16)),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("photo_ids", sa.JSON(), nullable=False),
        sa.Column("event_ids", sa.JSON(), nullable=False),
        *timestamps(),
    )
    op.create_table(
        "support_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_max_user_id", sa.BigInteger(), nullable=False),
        sa.Column("ticket_id", sa.Integer(), sa.ForeignKey("support_tickets.id")),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_support_photos_owner_max_user_id", "support_photos", ["owner_max_user_id"])
    op.create_index("ix_support_photos_ticket_id", "support_photos", ["ticket_id"])


def downgrade():
    op.drop_table("support_photos")
    op.drop_table("support_drafts")
    op.drop_table("support_tickets")
