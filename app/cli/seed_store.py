from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.enums import ProductStatus, StudentAccessRole, TenantStatus, WarehouseType
from app.models.store import Product, ProductCategory, Warehouse, WarehouseInventory
from app.models.student import Student, Wallet
from app.models.tenant import City, Partner, Tenant
from app.schemas.access import AccessLinkCreate
from app.services.access import AccessServiceError, create_contact_access_links
from app.services.course_import import import_courses_for_tenant
from app.services.crm_import import CrmStudentRow
from app.services.crm_sync import CrmSyncDefaults, upsert_crm_student_rows

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

DEMO_CONTACT_ID = "681"
DEMO_STUDENT_BALANCE = 1000


def demo_student_rows(args: argparse.Namespace) -> list[CrmStudentRow]:
    return [
        CrmStudentRow(
            row_number=2,
            deal_id="1357",
            uuid="demo-alisa",
            lms_student_id="ST-001",
            first_name="Алиса",
            last_name="Васильева",
            group_name="Python Start, вс 10:00",
            course_name="Python Start",
            venue_name="Союзный 45",
            teacher_name="Олейник Д",
            city=args.city_name,
            status_name="Активен",
            contact_ids=DEMO_CONTACT_ID,
            contact_names="Мама Алисы",
        ),
        CrmStudentRow(
            row_number=3,
            deal_id="1358",
            uuid="demo-ivan",
            lms_student_id="ST-002",
            first_name="Иван",
            last_name="Петров",
            group_name="Python Start, вс 10:00",
            course_name="Python Start",
            venue_name="Союзный 45",
            teacher_name="Олейник Д",
            city=args.city_name,
            status_name="Активен",
            contact_ids=DEMO_CONTACT_ID,
            contact_names="Мама Алисы",
        ),
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
    parser.add_argument(
        "--skip-students",
        action="store_true",
        help="Не создавать demo учеников, контакт 681 и кошельки.",
    )
    parser.add_argument(
        "--student-balance",
        type=int,
        default=DEMO_STUDENT_BALANCE,
        help="Стартовый баланс demo учеников в астрокоинах.",
    )
    parser.add_argument(
        "--max-user-id",
        type=int,
        default=None,
        help="Опционально сразу привязать demo Contact ID к MAX user_id.",
    )
    parser.add_argument(
        "--access-role",
        choices=[StudentAccessRole.PARENT.value, StudentAccessRole.STUDENT.value],
        default=StudentAccessRole.PARENT.value,
        help="Роль для --max-user-id.",
    )
    parser.add_argument("--username", default=None, help="Username MAX для --max-user-id.")
    parser.add_argument("--display-name", default=None, help="Имя MAX для --max-user-id.")
    parser.add_argument(
        "--skip-courses",
        action="store_true",
        help="Не импортировать каталог курсов и уроков.",
    )
    parser.add_argument(
        "--courses-source",
        type=Path,
        default=Path(settings.courses_json_path),
        help="JSON-файл курсов из предыдущего Telegram-бота.",
    )
    return parser.parse_args()


async def get_or_create_city(db: AsyncSession, *, slug: str, name: str) -> City:
    city = await db.scalar(select(City).where(City.slug == slug))
    if city is not None:
        city.name = name
        return city

    city = City(slug=slug, name=name)
    db.add(city)
    await db.flush()
    return city


async def get_or_create_partner(db: AsyncSession, *, slug: str, name: str) -> Partner:
    partner = await db.scalar(select(Partner).where(Partner.slug == slug))
    if partner is not None:
        partner.name = name
        return partner

    partner = Partner(slug=slug, name=name)
    db.add(partner)
    await db.flush()
    return partner


async def get_or_create_tenant(db: AsyncSession, args: argparse.Namespace) -> Tenant:
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
    db: AsyncSession,
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


async def get_or_create_warehouse(
    db: AsyncSession,
    *,
    tenant: Tenant,
    args: argparse.Namespace,
) -> Warehouse:
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


async def upsert_demo_store_in_session(
    db: AsyncSession,
    args: argparse.Namespace,
) -> dict[str, int | str]:
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

    crm_result = None
    wallet_balances_set = 0
    if not args.skip_students:
        crm_result = await upsert_crm_student_rows(
            db,
            demo_student_rows(args),
            defaults=CrmSyncDefaults(
                partner_slug=args.partner_slug,
                partner_name=args.partner_name,
                fallback_city_name=args.city_name,
            ),
            commit=False,
        )
        students = (
            await db.scalars(
                select(Student).where(
                    Student.tenant_id == tenant.id,
                    Student.lms_student_id.in_(["ST-001", "ST-002"]),
                )
            )
        ).all()
        for student in students:
            wallet = await db.scalar(select(Wallet).where(Wallet.student_id == student.id))
            if wallet is not None:
                wallet.balance = args.student_balance
                wallet_balances_set += 1

    course_result: dict[str, int | str] = {}
    if not getattr(args, "skip_courses", False):
        course_result = await import_courses_for_tenant(
            db,
            tenant=tenant,
            source_path=getattr(
                args,
                "courses_source",
                Path(get_settings().courses_json_path),
            ),
            commit=False,
        )

    await db.commit()

    access_links = 0
    if args.max_user_id and not args.skip_students:
        try:
            links = await create_contact_access_links(
                db,
                AccessLinkCreate(
                    tenant_slug=tenant.slug,
                    contact_id=DEMO_CONTACT_ID,
                    max_user_id=args.max_user_id,
                    role=StudentAccessRole(args.access_role),
                    username=args.username,
                    display_name=args.display_name,
                ),
            )
            access_links = len(links)
        except AccessServiceError as exc:
            raise SystemExit(f"Не удалось создать demo access links: {exc}") from exc

    return {
        "tenant_slug": tenant.slug,
        "warehouse_slug": warehouse.slug,
        "created_products": created_products,
        "updated_products": updated_products,
        "total_products": len(DEMO_PRODUCTS),
        "created_students": crm_result.created_students if crm_result else 0,
        "updated_students": crm_result.updated_students if crm_result else 0,
        "created_contacts": crm_result.created_contacts if crm_result else 0,
        "created_contact_student_links": (
            crm_result.created_contact_student_links if crm_result else 0
        ),
        "wallet_balances_set": wallet_balances_set,
        "demo_contact_id": DEMO_CONTACT_ID if not args.skip_students else "",
        "access_links": access_links,
        "courses": int(course_result.get("created_courses", 0))
        + int(course_result.get("updated_courses", 0)),
        "course_lessons": int(course_result.get("created_lessons", 0))
        + int(course_result.get("updated_lessons", 0)),
    }


async def upsert_demo_store(args: argparse.Namespace) -> dict[str, int | str]:
    async with AsyncSessionLocal() as db:
        return await upsert_demo_store_in_session(db, args)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    result = asyncio.run(upsert_demo_store(parse_args()))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
