from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.enums import ProductStatus, TenantStatus, WarehouseType
from app.models.store import Product, ProductCategory, Warehouse, WarehouseInventory
from app.models.tenant import City, Partner, Tenant

DEMO_PRODUCTS: list[dict[str, Any]] = [
    {
        "category_slug": "games",
        "category_name": "Игры",
        "sku": "GAME-CYBERTOWN",
        "name": "Игра Кибертаун",
        "description": "Настольная игра для проектных занятий и домашних вечеров.",
        "price": 900,
        "quantity": 4,
    },
    {
        "category_slug": "stationery",
        "category_name": "Канцелярия",
        "sku": "PEN-LOGO",
        "name": "Ручка металл с лого",
        "description": "Приятный базовый подарок за первые достижения.",
        "price": 120,
        "quantity": 18,
    },
    {
        "category_slug": "accessories",
        "category_name": "Аксессуары",
        "sku": "BRACELET-SILICONE",
        "name": "Силиконовый браслет",
        "description": "Легкий фирменный браслет для учеников.",
        "price": 160,
        "quantity": 12,
    },
    {
        "category_slug": "mugs",
        "category_name": "Кружки",
        "sku": "MUG-PYTHON",
        "name": "Кружка Python. Be the best",
        "description": "Кружка для юных разработчиков.",
        "price": 520,
        "quantity": 6,
    },
    {
        "category_slug": "magnets",
        "category_name": "Магниты",
        "sku": "MAGNET-ROBLOX",
        "name": "Магнит Roblox",
        "description": "Небольшой сувенир для витрины астроcoins.",
        "price": 90,
        "quantity": 24,
    },
]


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Заполнить демо-каталог магазина MAX mini app")
    parser.add_argument("--tenant-slug", default=settings.default_tenant_slug)
    parser.add_argument("--tenant-name", default="Нижний Новгород / Партнер A")
    parser.add_argument("--city-slug", default="nizhniy-novgorod")
    parser.add_argument("--city-name", default="Нижний Новгород")
    parser.add_argument("--partner-slug", default="partner-a")
    parser.add_argument("--partner-name", default="Партнер A")
    parser.add_argument("--warehouse-slug", default="common")
    parser.add_argument("--warehouse-name", default="Общий склад")
    return parser.parse_args()


async def get_or_create_city(db, *, slug: str, name: str) -> City:
    city = await db.scalar(select(City).where(City.slug == slug))
    if city is not None:
        city.name = name
        return city

    city = City(slug=slug, name=name)
    db.add(city)
    await db.flush()
    return city


async def get_or_create_partner(db, *, slug: str, name: str) -> Partner:
    partner = await db.scalar(select(Partner).where(Partner.slug == slug))
    if partner is not None:
        partner.name = name
        return partner

    partner = Partner(slug=slug, name=name)
    db.add(partner)
    await db.flush()
    return partner


async def get_or_create_tenant(db, args: argparse.Namespace) -> Tenant:
    tenant_slug = args.tenant_slug.strip().lower()
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    if tenant is not None:
        tenant.name = args.tenant_name
        tenant.status = TenantStatus.ACTIVE
        return tenant

    city = await get_or_create_city(db, slug=args.city_slug, name=args.city_name)
    partner = await get_or_create_partner(
        db,
        slug=args.partner_slug,
        name=args.partner_name,
    )
    tenant = Tenant(
        city_id=city.id,
        partner_id=partner.id,
        slug=tenant_slug,
        name=args.tenant_name,
        status=TenantStatus.ACTIVE,
    )
    db.add(tenant)
    await db.flush()
    return tenant


async def get_or_create_category(
    db,
    *,
    tenant: Tenant,
    slug: str,
    name: str,
    sort_order: int,
) -> ProductCategory:
    category = await db.scalar(
        select(ProductCategory).where(
            ProductCategory.tenant_id == tenant.id,
            ProductCategory.slug == slug,
        )
    )
    if category is not None:
        category.name = name
        category.sort_order = sort_order
        return category

    category = ProductCategory(
        tenant_id=tenant.id,
        slug=slug,
        name=name,
        sort_order=sort_order,
    )
    db.add(category)
    await db.flush()
    return category


async def get_or_create_warehouse(db, *, tenant: Tenant, args: argparse.Namespace) -> Warehouse:
    warehouse = await db.scalar(
        select(Warehouse).where(
            Warehouse.tenant_id == tenant.id,
            Warehouse.slug == args.warehouse_slug,
        )
    )
    if warehouse is not None:
        warehouse.name = args.warehouse_name
        warehouse.warehouse_type = WarehouseType.COMMON
        return warehouse

    warehouse = Warehouse(
        tenant_id=tenant.id,
        slug=args.warehouse_slug,
        name=args.warehouse_name,
        warehouse_type=WarehouseType.COMMON,
    )
    db.add(warehouse)
    await db.flush()
    return warehouse


async def upsert_demo_store(args: argparse.Namespace) -> dict[str, int | str]:
    async with AsyncSessionLocal() as db:
        tenant = await get_or_create_tenant(db, args)
        warehouse = await get_or_create_warehouse(db, tenant=tenant, args=args)

        created_products = 0
        updated_products = 0
        for sort_order, item in enumerate(DEMO_PRODUCTS, start=10):
            category = await get_or_create_category(
                db,
                tenant=tenant,
                slug=item["category_slug"],
                name=item["category_name"],
                sort_order=sort_order,
            )
            product = await db.scalar(
                select(Product).where(
                    Product.tenant_id == tenant.id,
                    Product.sku == item["sku"],
                )
            )
            if product is None:
                product = Product(
                    tenant_id=tenant.id,
                    category_id=category.id,
                    sku=item["sku"],
                    name=item["name"],
                    description=item["description"],
                    price_astrocoins=item["price"],
                    status=ProductStatus.ACTIVE,
                )
                db.add(product)
                await db.flush()
                created_products += 1
            else:
                product.category_id = category.id
                product.name = item["name"]
                product.description = item["description"]
                product.price_astrocoins = item["price"]
                product.status = ProductStatus.ACTIVE
                updated_products += 1

            inventory = await db.scalar(
                select(WarehouseInventory).where(
                    WarehouseInventory.tenant_id == tenant.id,
                    WarehouseInventory.warehouse_id == warehouse.id,
                    WarehouseInventory.product_id == product.id,
                )
            )
            if inventory is None:
                inventory = WarehouseInventory(
                    tenant_id=tenant.id,
                    warehouse_id=warehouse.id,
                    product_id=product.id,
                )
                db.add(inventory)
            inventory.available_quantity = item["quantity"]
            inventory.reserved_quantity = 0
            inventory.issued_quantity = 0
            inventory.returned_quantity = 0

        await db.commit()
        return {
            "tenant_slug": tenant.slug,
            "warehouse_slug": warehouse.slug,
            "created_products": created_products,
            "updated_products": updated_products,
            "total_products": len(DEMO_PRODUCTS),
        }


def main() -> int:
    result = asyncio.run(upsert_demo_store(parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
