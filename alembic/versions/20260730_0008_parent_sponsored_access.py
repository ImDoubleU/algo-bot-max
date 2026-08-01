"""parent-sponsored student access

Revision ID: 20260730_0008
Revises: 20260729_0007
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_0008"
down_revision: str | None = "20260729_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE studentaccesssource ADD VALUE IF NOT EXISTS 'PARENT_QR'"
        )

    with op.batch_alter_table("student_access_links") as batch_op:
        batch_op.add_column(
            sa.Column("sponsor_access_link_id", sa.Uuid(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("revoked_reason", sa.String(length=40), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_student_access_links_sponsor_link",
            "student_access_links",
            ["sponsor_access_link_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_student_access_links_sponsor_access_link_id",
            ["sponsor_access_link_id"],
            unique=False,
        )


def downgrade() -> None:
    op.execute(
        "UPDATE student_access_links "
        "SET source = 'ID_ENTRY' WHERE source = 'PARENT_QR'"
    )
    with op.batch_alter_table("student_access_links") as batch_op:
        batch_op.drop_index("ix_student_access_links_sponsor_access_link_id")
        batch_op.drop_constraint(
            "fk_student_access_links_sponsor_link",
            type_="foreignkey",
        )
        batch_op.drop_column("revoked_reason")
        batch_op.drop_column("sponsor_access_link_id")

    # PostgreSQL enum values are intentionally retained: removing one requires
    # replacing the enum type and can break rows created by newer application code.
