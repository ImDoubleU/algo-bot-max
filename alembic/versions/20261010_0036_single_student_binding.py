"""Limit active student bindings in both directions without modifying existing links."""

import sqlalchemy as sa

from alembic import op

revision = "20261010_0036"
down_revision = "20261007_0035"
branch_labels = None
depends_on = None


def upgrade():
    predicate = sa.text("role = 'STUDENT' AND status = 'ACTIVE'")
    for suffix, column in (("student", "student_id"), ("account", "account_id")):
        op.create_index(f"uq_student_access_active_{suffix}", "student_access_links",
                        [column], unique=True, postgresql_where=predicate, sqlite_where=predicate)


def downgrade():
    for suffix in ("account", "student"):
        op.drop_index(f"uq_student_access_active_{suffix}", table_name="student_access_links")
