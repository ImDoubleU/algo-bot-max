"""student CRM identity fields

Revision ID: 20260727_0004
Revises: 20260713_0003
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0004"
down_revision: str | None = "20260713_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("students", sa.Column("crm_deal_id", sa.String(length=120), nullable=True))
    op.add_column("students", sa.Column("crm_uuid", sa.String(length=180), nullable=True))
    op.create_index(op.f("ix_students_crm_deal_id"), "students", ["crm_deal_id"], unique=False)
    op.create_index(op.f("ix_students_crm_uuid"), "students", ["crm_uuid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_students_crm_uuid"), table_name="students")
    op.drop_index(op.f("ix_students_crm_deal_id"), table_name="students")
    op.drop_column("students", "crm_uuid")
    op.drop_column("students", "crm_deal_id")
