"""Persist missing-profile attempts and deliver confirmation invitations."""

import sqlalchemy as sa

from alembic import op

revision = "20261007_0035"
down_revision = "20261007_0034"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pending_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("max_user_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("target_id", sa.String(120), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("issuer", sa.String(16)),
        sa.Column("sponsor_link_id", sa.Uuid()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(80), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("notification_attempts", sa.Integer(), nullable=False),
        sa.Column("notification_attempted_at", sa.DateTime(timezone=True)),
        sa.Column("notification_error", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.UniqueConstraint("tenant_id", "max_user_id", "fingerprint",
                            name="uq_pending_binding_actor_target"),
    )
    for field in ("tenant_id", "max_user_id", "status", "expires_at"):
        op.create_index(f"ix_pending_bindings_{field}", "pending_bindings", [field])


def downgrade():
    op.drop_table("pending_bindings")
