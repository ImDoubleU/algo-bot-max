from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.store import Product, Warehouse, WarehouseInventory, WarehouseTenantLink
from app.models.tenant import Partner, Tenant


def normalize_warehouse_name(value: str) -> str:
    return " ".join(value.casefold().replace("ё", "е").replace("\u00a0", " ").split())


def accessible_warehouse_ids_query(tenant_id: UUID):
    linked_ids = select(WarehouseTenantLink.warehouse_id).where(
        WarehouseTenantLink.tenant_id == tenant_id
    )
    return select(Warehouse.id).where(
        or_(Warehouse.tenant_id == tenant_id, Warehouse.id.in_(linked_ids))
    )


def accessible_product_filter(tenant_id: UUID):
    return or_(
        Product.tenant_id == tenant_id,
        exists(
            select(WarehouseInventory.id).where(
                WarehouseInventory.product_id == Product.id,
                WarehouseInventory.warehouse_id.in_(
                    accessible_warehouse_ids_query(tenant_id)
                ),
                WarehouseInventory.is_active.is_(True),
            )
        ),
    )


async def accessible_warehouse_ids(db: AsyncSession, *, tenant_id: UUID) -> set[UUID]:
    return {
        UUID(str(warehouse_id))
        for warehouse_id in await db.scalars(accessible_warehouse_ids_query(tenant_id))
    }


async def list_accessible_warehouses(
    db: AsyncSession,
    *,
    tenant_id: UUID,
) -> list[Warehouse]:
    return list(
        await db.scalars(
            select(Warehouse)
            .where(Warehouse.id.in_(accessible_warehouse_ids_query(tenant_id)))
            .order_by(Warehouse.name, Warehouse.id)
        )
    )


async def get_accessible_warehouse(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    warehouse_id: UUID,
    for_update: bool = False,
) -> Warehouse | None:
    query = select(Warehouse).where(
        Warehouse.id == warehouse_id,
        Warehouse.id.in_(accessible_warehouse_ids_query(tenant_id)),
    )
    if for_update:
        query = query.with_for_update()
    return await db.scalar(query)


async def ensure_warehouse_link(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    warehouse_id: UUID,
) -> tuple[WarehouseTenantLink, bool]:
    link = await db.scalar(
        select(WarehouseTenantLink).where(
            WarehouseTenantLink.tenant_id == tenant_id,
            WarehouseTenantLink.warehouse_id == warehouse_id,
        )
    )
    if link is not None:
        return link, False

    link = WarehouseTenantLink(tenant_id=tenant_id, warehouse_id=warehouse_id)
    db.add(link)
    await db.flush()
    return link, True


async def find_partner_warehouse_by_name(
    db: AsyncSession,
    *,
    tenant: Tenant,
    name: str,
    exclude_warehouse_id: UUID | None = None,
) -> Warehouse | None:
    # Locking the shared partner row serializes same-name warehouse creation
    # from two different cities of that partner.
    await db.scalar(select(Partner.id).where(Partner.id == tenant.partner_id).with_for_update())
    query = (
        select(Warehouse)
        .join(Tenant, Tenant.id == Warehouse.tenant_id)
        .where(Tenant.partner_id == tenant.partner_id)
        .order_by(Warehouse.created_at, Warehouse.id)
    )
    if exclude_warehouse_id is not None:
        query = query.where(Warehouse.id != exclude_warehouse_id)
    candidates = list(await db.scalars(query))
    name_key = normalize_warehouse_name(name)
    return next(
        (
            candidate
            for candidate in candidates
            if normalize_warehouse_name(candidate.name) == name_key
        ),
        None,
    )
