"""Add optimized product image variants and crop metadata.

Revision ID: 20260921_0030
Revises: 20260908_0029
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260921_0030"
down_revision: str | None = "20260908_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("photo_thumbnail_url", sa.String(length=500)))
    op.add_column("products", sa.Column("photo_master_url", sa.String(length=500)))
    op.add_column("products", sa.Column("photo_crop_x", sa.Float()))
    op.add_column("products", sa.Column("photo_crop_y", sa.Float()))
    op.add_column("products", sa.Column("photo_crop_width", sa.Float()))
    op.add_column("products", sa.Column("photo_crop_height", sa.Float()))


def downgrade() -> None:
    op.drop_column("products", "photo_crop_height")
    op.drop_column("products", "photo_crop_width")
    op.drop_column("products", "photo_crop_y")
    op.drop_column("products", "photo_crop_x")
    op.drop_column("products", "photo_master_url")
    op.drop_column("products", "photo_thumbnail_url")
