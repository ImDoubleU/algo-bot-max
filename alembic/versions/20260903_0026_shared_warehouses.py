"""Allow one physical warehouse to be used by several partner cities.

Revision ID: 20260903_0026
Revises: 20260901_0025
Create Date: 2026-09-03
"""

from collections import defaultdict
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_0026"
down_revision: str | None = "20260901_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _name_key(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").replace("\u00a0", " ").split())


def upgrade() -> None:
    op.create_table(
        "warehouse_tenant_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_warehouse_tenant_links_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
            name=op.f("fk_warehouse_tenant_links_warehouse_id_warehouses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_warehouse_tenant_links")),
        sa.UniqueConstraint(
            "tenant_id",
            "warehouse_id",
            name="uq_warehouse_tenant_links_tenant_warehouse",
        ),
    )
    op.create_index(
        op.f("ix_warehouse_tenant_links_tenant_id"),
        "warehouse_tenant_links",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_warehouse_tenant_links_warehouse_id"),
        "warehouse_tenant_links",
        ["warehouse_id"],
        unique=False,
    )

    bind = op.get_bind()
    warehouse_rows = bind.execute(
        sa.text(
            """
            SELECT w.id, w.tenant_id, w.name, w.created_at, t.partner_id,
                   (SELECT count(*) FROM warehouse_inventory wi WHERE wi.warehouse_id = w.id)
                 + (SELECT count(*) FROM order_items oi
                    WHERE oi.warehouse_id = w.id OR oi.reserved_warehouse_id = w.id)
                 + (SELECT count(*) FROM stock_movements sm
                    WHERE sm.from_warehouse_id = w.id OR sm.to_warehouse_id = w.id)
                 + (SELECT count(*) FROM staff_warehouse_preferences swp
                    WHERE swp.warehouse_id = w.id) AS reference_count
            FROM warehouses w
            JOIN tenants t ON t.id = w.tenant_id
            """
        )
    ).mappings().all()

    groups: dict[tuple[object, str], list[dict[str, object]]] = defaultdict(list)
    for row in warehouse_rows:
        groups[(row["partner_id"], _name_key(str(row["name"])))].append(dict(row))

    removed_ids: set[object] = set()
    extra_links: set[tuple[object, object]] = set()
    for rows in groups.values():
        if len(rows) < 2:
            continue
        rows.sort(
            key=lambda row: (
                -int(row["reference_count"] or 0),
                row["created_at"],
                str(row["id"]),
            )
        )
        canonical = rows[0]
        for duplicate in rows[1:]:
            if int(duplicate["reference_count"] or 0) != 0:
                continue
            extra_links.add((duplicate["tenant_id"], canonical["id"]))
            removed_ids.add(duplicate["id"])

    link_rows = {
        (row["tenant_id"], row["id"])
        for row in warehouse_rows
        if row["id"] not in removed_ids
    }
    link_rows.update(extra_links)
    if link_rows:
        sqlite = bind.dialect.name == "sqlite"

        def uuid_param(value: object) -> str:
            text = str(value)
            return text.replace("-", "") if sqlite else text

        bind.execute(
            sa.text(
                """
                INSERT INTO warehouse_tenant_links (id, tenant_id, warehouse_id)
                VALUES (:id, :tenant_id, :warehouse_id)
                """
            ),
            [
                {
                    "id": uuid_param(uuid4()),
                    "tenant_id": uuid_param(tenant_id),
                    "warehouse_id": uuid_param(warehouse_id),
                }
                for tenant_id, warehouse_id in link_rows
            ],
        )
    if removed_ids:
        bind.execute(
            sa.text("DELETE FROM warehouses WHERE id IN :warehouse_ids").bindparams(
                sa.bindparam("warehouse_ids", expanding=True)
            ),
            {"warehouse_ids": list(removed_ids)},
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_warehouse_tenant_links_warehouse_id"),
        table_name="warehouse_tenant_links",
    )
    op.drop_index(
        op.f("ix_warehouse_tenant_links_tenant_id"),
        table_name="warehouse_tenant_links",
    )
    op.drop_table("warehouse_tenant_links")
