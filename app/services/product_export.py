"""Export a catalog using the same nine columns as the product import template."""

from copy import copy
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.styles import Alignment

from app.models.enums import ProductStatus
from app.schemas.miniapp import MiniAppProductRead
from app.services.product_import import PRODUCT_TEMPLATE_SHEET_NAME, build_product_import_template


def build_product_export_workbook(products: list[MiniAppProductRead]) -> bytes:
    workbook = load_workbook(BytesIO(build_product_import_template()))
    sheet = workbook[PRODUCT_TEMPLATE_SHEET_NAME]
    status_names = {ProductStatus.ACTIVE: "Активен", ProductStatus.HIDDEN: "Скрыт",
                    ProductStatus.ARCHIVED: "Архив"}
    instruction = workbook["Инструкция"]
    instruction.append([
        "8. Электронные товары выгружаются без склада и с остатком 0. При повторной загрузке "
        "в этот же каталог способ выдачи и данные получателя сохраняются по артикулу. "
        "Коды товаров в выгрузку не входят."
    ])
    for product in products:
        inventories = product.warehouses or [None]
        for inventory in inventories:
            values = [product.sku, product.name, product.category_name or "Без категории",
                      product.price_astrocoins, inventory.warehouse_name if inventory else "",
                      inventory.stock_quantity if inventory else 0, status_names[product.status],
                      product.description or "", product.photo_url or ""]
            sheet.append(values)
            for cell in sheet[sheet.max_row]:
                # Spreadsheet text must stay text even if it begins with =, +, - or @.
                if isinstance(cell.value, str):
                    cell.data_type = "s"
                cell.alignment = Alignment(vertical="top", wrap_text=True)
                font = copy(cell.font)
                font.size = 11
                cell.font = font
            sheet.row_dimensions[sheet.max_row].height = 44
    sheet.auto_filter.ref = f"A1:I{max(sheet.max_row, 1)}"
    workbook.active = workbook.sheetnames.index(PRODUCT_TEMPLATE_SHEET_NAME)
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()
