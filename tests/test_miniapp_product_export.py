from io import BytesIO

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from sqlalchemy import func, select
from test_miniapp_product_import import db_session as _db_session
from test_miniapp_product_import import seed_admin

from app.api.dependencies import get_miniapp_identity
from app.api.routes.miniapp import router
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.enums import (
    AssignmentStatus,
    ProductCodeStatus,
    ProductFulfillmentType,
    ProductStatus,
    StaffRole,
    WarehouseType,
)
from app.models.store import Product, ProductCategory, ProductCode, Warehouse, WarehouseInventory
from app.models.tenant import Tenant
from app.services.product_import import (
    PRODUCT_TEMPLATE_COLUMNS,
    import_products_for_tenant,
    parse_product_rows,
)

db_session = _db_session
SLUG = "nizhniy-novgorod-partner-a"


async def test_catalog_export_template_round_trip_and_permissions(db_session):
    await seed_admin(db_session)
    tenant = await db_session.scalar(select(Tenant))
    category = ProductCategory(tenant_id=tenant.id, slug="category", name="Категория")
    warehouses = [Warehouse(tenant_id=tenant.id, slug=f"stock-{i}", name=f"Склад {i}",
                            warehouse_type=WarehouseType.COMMON) for i in range(2)]
    db_session.add_all([category, *warehouses])
    await db_session.flush()
    physical = Product(tenant_id=tenant.id, category_id=category.id, sku="PHYSICAL",
                        name="=HYPERLINK(1)", description="Описание", price_astrocoins=150)
    hidden = Product(tenant_id=tenant.id, category_id=category.id, sku="DIGITAL",
                      name="80 Robux", price_astrocoins=740, status=ProductStatus.HIDDEN,
                      fulfillment_type=ProductFulfillmentType.DIGITAL_MANUAL,
                      recipient_field="roblox_username")
    archived = Product(tenant_id=tenant.id, category_id=category.id, sku="ARCHIVED",
                        name="Архивный товар", price_astrocoins=30, status=ProductStatus.ARCHIVED)
    instant = Product(tenant_id=tenant.id, category_id=category.id, sku="INSTANT",
                      name="Автовыдача", price_astrocoins=70,
                      fulfillment_type=ProductFulfillmentType.DIGITAL_CODE)
    db_session.add_all([physical, hidden, archived, instant])
    await db_session.flush()
    db_session.add(ProductCode(
        tenant_id=tenant.id, product_id=instant.id,
        code="PRIVATE-CODE-NEVER-EXPORT", status=ProductCodeStatus.AVAILABLE,
    ))
    for warehouse, stock, reserved in zip(warehouses, [5, 3], [2, 0], strict=True):
        db_session.add(WarehouseInventory(tenant_id=tenant.id, product_id=physical.id,
            warehouse_id=warehouse.id, available_quantity=stock, reserved_quantity=reserved))
    teacher = MaxAccount(max_user_id=777)
    db_session.add(teacher)
    await db_session.flush()
    db_session.add(StaffRoleAssignment(tenant_id=tenant.id, account_id=teacher.id,
        role=StaffRole.TEACHER, status=AssignmentStatus.ACTIVE))
    await db_session.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/miniapp")
    identity = {"id": 53364725}

    async def db_override():
        yield db_session

    app.dependency_overrides[get_db_session] = db_override
    app.dependency_overrides[get_miniapp_identity] = lambda: MiniAppIdentity(
        max_user_id=identity["id"], tenant_slug=SLUG, expires_at=9999999999,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/miniapp/products/export",
                                    params={"max_user_id": 53364725, "tenant_slug": SLUG})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "attachment" in response.headers["content-disposition"]
        content = response.content
        book = load_workbook(BytesIO(content), data_only=False)
        sheet = book["Товары"]
        assert tuple(cell.value for cell in sheet[1]) == PRODUCT_TEMPLATE_COLUMNS
        assert sheet.max_row == 6
        assert not any("PRIVATE-CODE-NEVER-EXPORT" in str(cell.value)
                       for row in sheet for cell in row)
        assert book.active.title == "Товары"
        physical_rows = [row for row in sheet.iter_rows(min_row=2) if row[0].value == "PHYSICAL"]
        assert sorted(row[5].value for row in physical_rows) == [3, 5]
        assert all(row[1].data_type == "s" for row in physical_rows)
        assert any(row[6].value == "Скрыт" for row in sheet.iter_rows(min_row=2))
        assert any(row[6].value == "Архив" for row in sheet.iter_rows(min_row=2))
        denied = await client.get("/api/v1/miniapp/products/export",
                                  params={"max_user_id": 777, "tenant_slug": SLUG})
        assert denied.status_code == 403
        identity["id"] = 777
        denied = await client.get("/api/v1/miniapp/products/export",
                                  params={"max_user_id": 777, "tenant_slug": SLUG})
        assert denied.status_code == 403
    warehouse_count = await db_session.scalar(select(func.count()).select_from(Warehouse))
    rows = parse_product_rows("export.xlsx", content)
    result = await import_products_for_tenant(db_session, tenant=tenant, rows=rows)
    await db_session.commit()
    assert result.created_products == result.created_warehouses == 0
    assert await db_session.scalar(select(func.count()).select_from(Warehouse)) == warehouse_count
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 4
    code = await db_session.scalar(select(ProductCode))
    assert code.code == "PRIVATE-CODE-NEVER-EXPORT" and code.status == ProductCodeStatus.AVAILABLE
    await db_session.refresh(hidden)
    assert hidden.fulfillment_type == ProductFulfillmentType.DIGITAL_MANUAL
    assert hidden.recipient_field == "roblox_username"
    inventory = list(await db_session.scalars(select(WarehouseInventory).order_by(
        WarehouseInventory.available_quantity,
    )))
    assert [(item.available_quantity, item.reserved_quantity) for item in inventory] == [
        (3, 0), (5, 2),
    ]
