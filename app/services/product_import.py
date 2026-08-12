from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import ProductStatus, StockMovementType, WarehouseType
from app.models.store import Product, ProductCategory, Warehouse, WarehouseInventory
from app.models.tenant import Tenant
from app.services.crm_sync import slugify
from app.services.warehouse import build_stock_movement

HEADER_ALIASES = {
    "sku": "sku",
    "артикул": "sku",
    "код": "sku",
    "product_sku": "sku",
    "name": "name",
    "название": "name",
    "товар": "name",
    "product_name": "name",
    "category": "category_name",
    "категория": "category_name",
    "category_name": "category_name",
    "category_slug": "category_slug",
    "price": "price_astrocoins",
    "цена": "price_astrocoins",
    "price_astrocoins": "price_astrocoins",
    "астрокоины": "price_astrocoins",
    "quantity": "quantity",
    "остаток": "quantity",
    "количество": "quantity",
    "stock": "quantity",
    "warehouse": "warehouse_name",
    "склад": "warehouse_name",
    "warehouse_name": "warehouse_name",
    "warehouse_slug": "warehouse_slug",
    "description": "description",
    "описание": "description",
    "photo_url": "photo_url",
    "фото": "photo_url",
    "status": "status",
    "статус": "status",
}


class ProductImportError(RuntimeError):
    pass


@dataclass
class ProductImportResult:
    tenant_slug: str
    created_products: int = 0
    updated_products: int = 0
    created_categories: int = 0
    created_warehouses: int = 0
    updated_inventory: int = 0
    skipped_rows: int = 0
    errors: list[str] = field(default_factory=list)
    new_active_products: list[Product] = field(default_factory=list, repr=False)
    low_stock_items: list[tuple[Product, WarehouseInventory]] = field(
        default_factory=list,
        repr=False,
    )


@dataclass(frozen=True)
class ProductImportRow:
    row_number: int
    sku: str
    name: str
    category_name: str
    category_slug: str
    price_astrocoins: int
    quantity: int
    warehouse_name: str
    warehouse_slug: str
    description: str | None = None
    photo_url: str | None = None
    status: ProductStatus = ProductStatus.ACTIVE


def parse_product_rows(filename: str, content: bytes) -> list[ProductImportRow]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix not in {"csv", "xlsx"}:
        raise ProductImportError("Поддерживаются только файлы CSV и XLSX")
    try:
        raw_rows = _read_xlsx(content) if suffix == "xlsx" else _read_csv(content)
    except (BadZipFile, InvalidFileException, OSError, ValueError, csv.Error) as exc:
        raise ProductImportError(f"Не удалось прочитать файл {suffix.upper()}") from exc
    return _normalize_rows(raw_rows)


def _read_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return [dict(row) for row in reader]


def _read_xlsx(content: bytes) -> list[dict[str, Any]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    try:
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(value or "").strip() for value in rows[0]]
        result: list[dict[str, Any]] = []
        for values in rows[1:]:
            result.append({headers[index]: values[index] for index in range(len(headers))})
        return result
    finally:
        workbook.close()


def _normalize_header(value: str) -> str:
    return HEADER_ALIASES.get(value.strip().lower(), value.strip().lower())


def _cell(row: dict[str, Any], key: str) -> Any:
    normalized = {_normalize_header(str(header)): value for header, value in row.items()}
    return normalized.get(key)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _int(value: Any, *, default: int | None = None) -> int:
    text = _text(value).replace(" ", "").replace(",", ".")
    if not text:
        if default is None:
            raise ValueError("empty number")
        return default
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"неверное число: {value}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"ожидается целое число: {value}")
    return int(number)


def _status(value: Any) -> ProductStatus:
    text = _text(value).lower()
    if text in {"", "active", "активен", "активный", "да", "1"}:
        return ProductStatus.ACTIVE
    if text in {"hidden", "скрыт", "скрытый", "нет", "0"}:
        return ProductStatus.HIDDEN
    if text in {"archived", "архив", "архивный"}:
        return ProductStatus.ARCHIVED
    raise ValueError(f"unknown status: {value}")


def _normalize_rows(raw_rows: list[dict[str, Any]]) -> list[ProductImportRow]:
    rows: list[ProductImportRow] = []
    seen_inventory_rows: dict[tuple[str, str], int] = {}
    for index, raw_row in enumerate(raw_rows, start=2):
        sku = _text(_cell(raw_row, "sku")).upper()
        name = _text(_cell(raw_row, "name"))
        if not sku and not name:
            continue
        if not sku:
            raise ProductImportError(f"Строка {index}: не указан sku/артикул")
        if not name:
            raise ProductImportError(f"Строка {index}: не указано название товара")

        category_name = _text(_cell(raw_row, "category_name")) or "Без категории"
        category_slug = _text(_cell(raw_row, "category_slug")) or slugify(category_name)
        warehouse_name = _text(_cell(raw_row, "warehouse_name")) or "Общий склад"
        warehouse_slug = _text(_cell(raw_row, "warehouse_slug")) or slugify(warehouse_name)
        inventory_key = (sku, warehouse_slug)
        if inventory_key in seen_inventory_rows:
            first_row = seen_inventory_rows[inventory_key]
            raise ProductImportError(
                f"Строки {first_row} и {index}: повторяется товар {sku} на складе "
                f"«{warehouse_name}»"
            )
        seen_inventory_rows[inventory_key] = index

        try:
            price = _int(_cell(raw_row, "price_astrocoins"))
            quantity = _int(_cell(raw_row, "quantity"), default=0)
            status = _status(_cell(raw_row, "status"))
        except ValueError as exc:
            raise ProductImportError(f"Строка {index}: {exc}") from exc

        if price < 0:
            raise ProductImportError(f"Строка {index}: цена не может быть отрицательной")
        if quantity < 0:
            raise ProductImportError(f"Строка {index}: остаток не может быть отрицательным")

        rows.append(
            ProductImportRow(
                row_number=index,
                sku=sku,
                name=name,
                category_name=category_name,
                category_slug=category_slug,
                price_astrocoins=price,
                quantity=quantity,
                warehouse_name=warehouse_name,
                warehouse_slug=warehouse_slug,
                description=_text(_cell(raw_row, "description")) or None,
                photo_url=_text(_cell(raw_row, "photo_url")) or None,
                status=status,
            )
        )
    return rows


async def import_products_for_tenant(
    db: AsyncSession,
    *,
    tenant: Tenant,
    rows: list[ProductImportRow],
    actor_account_id: UUID | None = None,
) -> ProductImportResult:
    result = ProductImportResult(tenant_slug=tenant.slug)
    categories: dict[str, ProductCategory] = {}
    warehouses: dict[str, Warehouse] = {}

    for row in rows:
        category = categories.get(row.category_slug)
        if category is None:
            category = await _get_or_create_category(db, tenant=tenant, row=row)
            categories[row.category_slug] = category
            if category.created_at is None:
                pass

        warehouse = warehouses.get(row.warehouse_slug)
        if warehouse is None:
            warehouse, created_warehouse = await _get_or_create_warehouse(
                db,
                tenant=tenant,
                row=row,
            )
            warehouses[row.warehouse_slug] = warehouse
            if created_warehouse:
                result.created_warehouses += 1

        category_created = getattr(category, "_import_created", False)
        if category_created:
            result.created_categories += 1
            category._import_created = False

        product = await db.scalar(
            select(Product).where(Product.tenant_id == tenant.id, Product.sku == row.sku)
        )
        product_created = product is None
        if product_created:
            product = Product(
                tenant_id=tenant.id,
                category_id=category.id,
                sku=row.sku,
                name=row.name,
                description=row.description,
                photo_url=row.photo_url,
                price_astrocoins=row.price_astrocoins,
                status=row.status,
            )
            db.add(product)
            await db.flush()
            result.created_products += 1
            if product.status == ProductStatus.ACTIVE:
                result.new_active_products.append(product)
        else:
            product.category_id = category.id
            product.name = row.name
            product.description = row.description
            product.photo_url = row.photo_url
            product.price_astrocoins = row.price_astrocoins
            product.status = row.status
            result.updated_products += 1

        inventory = await db.scalar(
            select(WarehouseInventory)
            .where(
                WarehouseInventory.tenant_id == tenant.id,
                WarehouseInventory.warehouse_id == warehouse.id,
                WarehouseInventory.product_id == product.id,
            )
            .with_for_update()
            .options(
                selectinload(WarehouseInventory.product),
                selectinload(WarehouseInventory.warehouse),
            )
        )
        if inventory is None:
            inventory = WarehouseInventory(
                tenant_id=tenant.id,
                warehouse_id=warehouse.id,
                product_id=product.id,
            )
            inventory.product = product
            inventory.warehouse = warehouse
            db.add(inventory)

        reserved_quantity = int(inventory.reserved_quantity or 0)
        if row.quantity < reserved_quantity:
            raise ProductImportError(
                f"Строка {row.row_number}: остаток {row.quantity} меньше уже "
                f"зарезервированного количества {reserved_quantity}"
            )
        previous_quantity = int(inventory.available_quantity or 0)
        inventory.is_active = True
        inventory.available_quantity = row.quantity
        quantity_delta = row.quantity - previous_quantity
        if quantity_delta:
            db.add(
                build_stock_movement(
                    inventory=inventory,
                    movement_type=StockMovementType.ADJUSTMENT,
                    quantity=abs(quantity_delta),
                    actor_account_id=actor_account_id,
                    from_warehouse_id=warehouse.id if quantity_delta < 0 else None,
                    to_warehouse_id=warehouse.id if quantity_delta > 0 else None,
                    comment=(
                        f"Импорт товаров: остаток изменен с {previous_quantity} "
                        f"на {row.quantity}"
                    ),
                )
            )
        free_quantity = row.quantity - reserved_quantity
        if free_quantity <= 5 and not inventory.low_stock_notified:
            inventory.low_stock_notified = True
            result.low_stock_items.append((product, inventory))
        elif free_quantity > 5:
            inventory.low_stock_notified = False
        result.updated_inventory += 1

    return result


async def _get_or_create_category(
    db: AsyncSession,
    *,
    tenant: Tenant,
    row: ProductImportRow,
) -> ProductCategory:
    category = await db.scalar(
        select(ProductCategory).where(
            ProductCategory.tenant_id == tenant.id,
            ProductCategory.slug == row.category_slug,
        )
    )
    if category is not None:
        category.name = row.category_name
        return category

    category = ProductCategory(
        tenant_id=tenant.id,
        slug=row.category_slug,
        name=row.category_name,
        sort_order=100,
    )
    category._import_created = True
    db.add(category)
    await db.flush()
    return category


async def _get_or_create_warehouse(
    db: AsyncSession,
    *,
    tenant: Tenant,
    row: ProductImportRow,
) -> tuple[Warehouse, bool]:
    warehouse = await db.scalar(
        select(Warehouse).where(
            Warehouse.tenant_id == tenant.id,
            Warehouse.slug == row.warehouse_slug,
        )
    )
    if warehouse is not None:
        warehouse.name = row.warehouse_name
        return warehouse, False

    warehouse = Warehouse(
        tenant_id=tenant.id,
        slug=row.warehouse_slug,
        name=row.warehouse_name,
        warehouse_type=WarehouseType.COMMON,
    )
    db.add(warehouse)
    await db.flush()
    return warehouse, True
