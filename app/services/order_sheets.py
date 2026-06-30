from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.models.account import MaxAccount
from app.models.store import Order
from app.models.student import Student
from app.services.google_sheets import GoogleSheetsClient, GoogleSheetsError

ORDERS_WORKSHEET = "orders"
ORDER_HEADERS = [
    "order_number",
    "created_at",
    "tenant_slug",
    "max_user_id",
    "student_id",
    "student_name",
    "status",
    "total_astrocoins",
    "items_json",
    "venue_name",
    "teacher_name",
    "comment",
]


def _created_at_value(order: Order) -> str:
    created_at = getattr(order, "created_at", None)
    return created_at.isoformat() if created_at else ""


def _items_json(items: Sequence[Mapping[str, Any]]) -> str:
    return json.dumps([dict(item) for item in items], ensure_ascii=False, sort_keys=True)


def order_item_mapping(
    *,
    product_id: str,
    product_name: str | None,
    quantity: int,
    warehouse_id: str | None,
    warehouse_name: str | None,
    unit_price_astrocoins: int,
    total_price_astrocoins: int,
) -> dict[str, Any]:
    return {
        "product_id": product_id,
        "product_name": product_name or "",
        "quantity": quantity,
        "warehouse_id": warehouse_id or "",
        "warehouse_name": warehouse_name or "",
        "unit_price_astrocoins": unit_price_astrocoins,
        "total_price_astrocoins": total_price_astrocoins,
    }


def order_sheet_row(
    *,
    tenant_slug: str,
    order: Order,
    student: Student,
    account: MaxAccount,
    items: Sequence[Mapping[str, Any]],
    comment: str | None = None,
) -> dict[str, Any]:
    return {
        "order_number": str(order.order_number),
        "created_at": _created_at_value(order),
        "tenant_slug": tenant_slug,
        "max_user_id": account.max_user_id,
        "student_id": str(order.student_id),
        "student_name": student.display_name,
        "status": order.status.value,
        "total_astrocoins": order.total_astrocoins,
        "items_json": _items_json(items),
        "venue_name": order.venue_name or "",
        "teacher_name": order.teacher_name or "",
        "comment": comment if comment is not None else order.comment or "",
    }


def upsert_order_sheet_row(
    *,
    client: GoogleSheetsClient,
    tenant_slug: str,
    order: Order,
    student: Student,
    account: MaxAccount,
    items: Sequence[Mapping[str, Any]],
    comment: str | None = None,
) -> None:
    row = order_sheet_row(
        tenant_slug=tenant_slug,
        order=order,
        student=student,
        account=account,
        items=items,
        comment=comment,
    )
    try:
        client.update_row_by_key(
            worksheet_name=ORDERS_WORKSHEET,
            key_column="order_number",
            key_value=str(order.order_number),
            updates=row,
        )
    except GoogleSheetsError as exc:
        if "не найдена строка" not in str(exc) and "нет колонки" not in str(exc):
            raise
        client.append_named_row(
            worksheet_name=ORDERS_WORKSHEET,
            headers=ORDER_HEADERS,
            row=row,
        )
