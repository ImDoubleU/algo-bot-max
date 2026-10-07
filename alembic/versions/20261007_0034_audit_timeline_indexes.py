"""Indexes for paginated activity audit."""

from alembic import op

revision = "20261007_0034"
down_revision = "20261007_0033"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_audit_tenant_time", "audit_logs", ["tenant_id", "created_at", "id"])
    op.create_index("ix_audit_time", "audit_logs", ["created_at", "id"])


def downgrade():
    op.drop_index("ix_audit_time", table_name="audit_logs")
    op.drop_index("ix_audit_tenant_time", table_name="audit_logs")
