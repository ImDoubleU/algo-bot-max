"""Add teacher-issued student QR access source.

Revision ID: 20260908_0029
Revises: 20260906_0028
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260908_0029"
down_revision: str | None = "20260906_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE studentaccesssource ADD VALUE IF NOT EXISTS 'TEACHER_QR'"
        )


def downgrade() -> None:
    op.execute(
        "UPDATE student_access_links "
        "SET source = 'ID_ENTRY' WHERE source = 'TEACHER_QR'"
    )
    # PostgreSQL enum values are retained because removing one requires
    # replacing the enum type and can break newer application rows.
