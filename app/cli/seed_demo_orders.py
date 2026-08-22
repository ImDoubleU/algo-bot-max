from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

import app.db.base  # noqa: F401
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.enums import (
    LedgerDirection,
    OrderStatus,
    ProductFulfillmentType,
    ProductStatus,
    StockMovementType,
    StudentStatus,
    WarehouseType,
)
from app.models.store import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    StockMovement,
    WarehouseInventory,
)
from app.models.student import AstrocoinLedgerEntry, Student, StudentHistoryEvent, Wallet
from app.models.tenant import Tenant
from app.services.warehouse import available_for_reservation, reserve_inventory

DEFAULT_RUN_ID = "DEMO-ORDERS-20260819"
DEMO_NAMESPACE = UUID("6fa2daf7-5090-48a6-bc09-60b2e1840a48")
MIN_STARTING_BALANCE = 10_000


def _run_slug(run_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", run_id.strip().lower()).strip("-")
    if not value:
        raise ValueError("run_id must contain letters or digits")
    return value[:40]


def _marker(run_id: str) -> str:
    return run_id.strip().upper()


def _id(run_id: str, key: str) -> UUID:
    return uuid5(DEMO_NAMESPACE, f"{_marker(run_id)}:{key}")


def _context_key(student: Student) -> tuple[str, str, str]:
    return (
        _student_venue_name(student).casefold(),
        (student.teacher_name or "").strip().casefold(),
        (student.group_name or "").strip().casefold(),
    )


def _student_venue_name(student: Student) -> str:
    explicit_name = (student.venue_name or "").strip()
    if explicit_name:
        return explicit_name

    group_name = " ".join((student.group_name or "").strip().casefold().split())
    if "индивид" in group_name:
        return "Индивидуальные занятия"
    if "общ" in group_name:
        return "Онлайн"
    if "бор" in group_name:
        if "окт бор" in group_name:
            return "Бор · Окт"
        if "м бор" in group_name:
            return "Бор · М"
        if "л бор" in group_name:
            return "Бор · Л"
        return "Бор"

    venue_markers = (
        ("союзн", "Союзный 45"),
        ("октябр", "Октября 13"),
        ("ванеева", "Ванеева 133"),
        ("гагарин", "Гагарина 64"),
        ("горная", "Горная 56а"),
        ("сормов", "Сормово"),
    )
    for marker, venue_name in venue_markers:
        if marker in group_name:
            return venue_name
    return "Очные занятия · площадка не указана"


def _usable_student_contexts(students: list[Student]) -> list[Student]:
    contexts: dict[tuple[str, str, str], Student] = {}
    for student in students:
        if not (student.teacher_name or "").strip():
            continue
        key = _context_key(student)
        contexts.setdefault(key, student)

    ordered = sorted(
        contexts.values(),
        key=lambda item: (
            (item.venue_name or "").casefold(),
            (item.teacher_name or "").casefold(),
            (item.group_name or "").casefold(),
        ),
    )
    primary: dict[tuple[str, str], Student] = {}
    for student in ordered:
        pair = (
            _student_venue_name(student).casefold(),
            (student.teacher_name or "").strip().casefold(),
        )
        primary.setdefault(pair, student)
    by_venue: defaultdict[str, list[Student]] = defaultdict(list)
    for student in primary.values():
        by_venue[_student_venue_name(student).casefold()].append(student)
    spread: list[Student] = []
    while any(by_venue.values()):
        for venue_name in sorted(by_venue):
            if by_venue[venue_name]:
                spread.append(by_venue[venue_name].pop(0))
    selected_ids = {student.id for student in primary.values()}
    return [*spread, *(student for student in ordered if student.id not in selected_ids)]


def _inventory_priority(
    inventory: WarehouseInventory,
    *,
    venue_id: UUID | None,
) -> tuple[int, str]:
    warehouse = inventory.warehouse
    if venue_id is not None and warehouse and warehouse.venue_id == venue_id:
        return (0, warehouse.name)
    if warehouse and warehouse.warehouse_type == WarehouseType.COMMON:
        return (1, warehouse.name)
    if warehouse and warehouse.warehouse_type == WarehouseType.PARTNER:
        return (2, warehouse.name)
    return (3, warehouse.name if warehouse else "")


async def seed_demo_orders(
    *,
    tenant_slug: str,
    count: int,
    run_id: str,
) -> dict[str, object]:
    if count < 1 or count > 250:
        raise ValueError("count must be between 1 and 250")

    marker = _marker(run_id)
    run_slug = _run_slug(run_id)
    async with AsyncSessionLocal() as db:
        tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_slug}")

        existing_orders = int(
            await db.scalar(
                select(func.count(Order.id)).where(
                    Order.tenant_id == tenant.id,
                    Order.comment.like(f"{marker}%"),
                )
            )
            or 0
        )
        if existing_orders:
            return {
                "run_id": marker,
                "tenant_slug": tenant_slug,
                "created": False,
                "existing_orders": existing_orders,
                "message": "Orders for this run already exist",
            }

        source_students = list(
            (
                await db.scalars(
                    select(Student)
                    .where(
                        Student.tenant_id == tenant.id,
                        Student.status == StudentStatus.ACTIVE,
                    )
                    .order_by(Student.venue_name, Student.teacher_name, Student.group_name)
                )
            ).all()
        )
        contexts = _usable_student_contexts(source_students)
        if not contexts:
            raise ValueError("No active students with both venue and teacher were found")

        products = list(
            (
                await db.scalars(
                    select(Product)
                    .where(
                        Product.tenant_id == tenant.id,
                        Product.status == ProductStatus.ACTIVE,
                        Product.fulfillment_type == ProductFulfillmentType.WAREHOUSE,
                        Product.name.ilike("QA-%"),
                    )
                    .order_by(Product.name)
                )
            ).all()
        )
        if not products:
            raise ValueError(
                "No active QA warehouse products were found. "
                "The command will not change stock of real products."
            )

        inventory_rows = list(
            (
                await db.scalars(
                    select(WarehouseInventory)
                    .where(
                        WarehouseInventory.tenant_id == tenant.id,
                        WarehouseInventory.product_id.in_([product.id for product in products]),
                        WarehouseInventory.is_active.is_(True),
                    )
                    .options(selectinload(WarehouseInventory.warehouse))
                    .order_by(WarehouseInventory.product_id, WarehouseInventory.warehouse_id)
                    .with_for_update()
                )
            )
            .unique()
            .all()
        )
        inventory_by_product: defaultdict[UUID, list[WarehouseInventory]] = defaultdict(list)
        for inventory in inventory_rows:
            inventory_by_product[UUID(str(inventory.product_id))].append(inventory)
        products = [product for product in products if inventory_by_product[UUID(str(product.id))]]
        if not products:
            raise ValueError("QA products do not have active warehouse inventory")

        context_count = min(len(contexts), count, 24)
        selected_contexts = contexts[:context_count]
        orders_per_student = (count + context_count - 1) // context_count
        starting_balance = max(
            MIN_STARTING_BALANCE,
            max(product.price_astrocoins for product in products) * orders_per_student + 1_000,
        )
        demo_students: list[Student] = []
        wallets: dict[UUID, Wallet] = {}
        for index, source in enumerate(selected_contexts, start=1):
            student = Student(
                id=_id(run_id, f"student:{index:03d}"),
                tenant_id=tenant.id,
                venue_id=source.venue_id,
                lms_student_id=f"{run_slug}-student-{index:03d}",
                student_access_code=f"{run_slug}-{index:03d}",
                first_name=f"Заказ {index:02d}",
                last_name="Демо",
                group_name=source.group_name,
                course_name=source.course_name,
                venue_name=_student_venue_name(source),
                teacher_name=source.teacher_name,
                status=StudentStatus.ACTIVE,
            )
            db.add(student)
            demo_students.append(student)

            wallet = Wallet(
                id=_id(run_id, f"wallet:{index:03d}"),
                tenant_id=tenant.id,
                student_id=student.id,
                balance=starting_balance,
            )
            db.add(wallet)
            wallets[student.id] = wallet
            db.add(
                AstrocoinLedgerEntry(
                    id=_id(run_id, f"ledger:initial:{index:03d}"),
                    tenant_id=tenant.id,
                    wallet_id=wallet.id,
                    student_id=student.id,
                    actor_account_id=None,
                    idempotency_key=f"demo:{run_slug}:initial:{index:03d}",
                    direction=LedgerDirection.CREDIT,
                    amount=starting_balance,
                    reason="Стартовый баланс для демонстрации заказов",
                    comment=marker,
                )
            )
            db.add(
                StudentHistoryEvent(
                    id=_id(run_id, f"student-history:{index:03d}"),
                    tenant_id=tenant.id,
                    student_id=student.id,
                    actor_account_id=None,
                    event_type="created",
                    from_status=None,
                    to_status=StudentStatus.ACTIVE.value,
                    from_group_name=None,
                    to_group_name=student.group_name,
                    changed_fields=[
                        "group_name",
                        "venue_name",
                        "teacher_name",
                    ],
                    source="demo_orders",
                )
            )

        await db.flush()

        last_order_number = int(
            await db.scalar(
                select(func.max(Order.order_number)).where(Order.tenant_id == tenant.id)
            )
            or 0
        )
        statuses: Counter[str] = Counter()
        venue_names: set[str] = set()
        teacher_names: set[str] = set()
        warehouse_names: set[str] = set()
        product_names: set[str] = set()
        stock_top_up = 0
        now = datetime.now(UTC)

        for index in range(1, count + 1):
            student = demo_students[(index - 1) % len(demo_students)]
            wallet = wallets[student.id]
            product = products[(index - 1) % len(products)]
            inventories = sorted(
                inventory_by_product[UUID(str(product.id))],
                key=lambda inventory: _inventory_priority(
                    inventory,
                    venue_id=student.venue_id,
                ),
            )
            inventory = inventories[((index - 1) // len(products)) % len(inventories)]
            if available_for_reservation(inventory) < 10:
                increment = 50
                inventory.available_quantity += increment
                stock_top_up += increment
                db.add(
                    StockMovement(
                        id=_id(run_id, f"stock-top-up:{index:03d}"),
                        tenant_id=tenant.id,
                        product_id=product.id,
                        from_warehouse_id=None,
                        to_warehouse_id=inventory.warehouse_id,
                        order_id=None,
                        actor_account_id=None,
                        movement_type=StockMovementType.ADJUSTMENT,
                        quantity=increment,
                        comment=f"{marker}: запас QA-товара для демонстрационных заказов",
                    )
                )

            reserve_inventory(inventory, 1)
            order_number = last_order_number + index
            mode = (index - 1) % 4
            warehouse_confirmed = mode in {2, 3}
            status = (
                OrderStatus.TRANSFERRED_TO_TEACHER
                if mode == 3
                else OrderStatus.RESERVED
            )
            created_at = now - timedelta(days=(count - index) % 8, minutes=index * 7)
            order = Order(
                id=_id(run_id, f"order:{index:03d}"),
                tenant_id=tenant.id,
                student_id=student.id,
                created_by_account_id=None,
                order_number=order_number,
                status=status,
                total_astrocoins=product.price_astrocoins,
                teacher_name=student.teacher_name,
                venue_name=student.venue_name,
                comment=f"{marker}: демонстрационный заказ",
                client_request_id=f"{run_slug}-order-{index:03d}",
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(order)
            db.add(
                OrderItem(
                    id=_id(run_id, f"order-item:{index:03d}"),
                    tenant_id=tenant.id,
                    order_id=order.id,
                    product_id=product.id,
                    quantity=1,
                    warehouse_id=inventory.warehouse_id if warehouse_confirmed else None,
                    reserved_warehouse_id=(
                        None if warehouse_confirmed else inventory.warehouse_id
                    ),
                    unit_price_astrocoins=product.price_astrocoins,
                    total_price_astrocoins=product.price_astrocoins,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            db.add(
                StockMovement(
                    id=_id(run_id, f"reserve:{index:03d}"),
                    tenant_id=tenant.id,
                    product_id=product.id,
                    from_warehouse_id=inventory.warehouse_id,
                    to_warehouse_id=None,
                    order_id=order.id,
                    actor_account_id=None,
                    movement_type=StockMovementType.RESERVE,
                    quantity=1,
                    comment=f"{marker}: резерв заказа №{order_number}",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            db.add(
                OrderStatusHistory(
                    id=_id(run_id, f"history:{index:03d}:reserved"),
                    tenant_id=tenant.id,
                    order_id=order.id,
                    actor_account_id=None,
                    from_status=None,
                    to_status=OrderStatus.RESERVED,
                    comment="Заказ создан и товар зарезервирован",
                    created_at=created_at,
                    updated_at=created_at,
                )
            )
            if warehouse_confirmed:
                assigned_at = created_at + timedelta(minutes=12)
                db.add(
                    OrderStatusHistory(
                        id=_id(run_id, f"history:{index:03d}:warehouse"),
                        tenant_id=tenant.id,
                        order_id=order.id,
                        actor_account_id=None,
                        from_status=OrderStatus.RESERVED,
                        to_status=OrderStatus.RESERVED,
                        comment=f"Склад подтвержден: {inventory.warehouse.name}",
                        created_at=assigned_at,
                        updated_at=assigned_at,
                    )
                )
            if status == OrderStatus.TRANSFERRED_TO_TEACHER:
                transferred_at = created_at + timedelta(minutes=25)
                db.add(
                    OrderStatusHistory(
                        id=_id(run_id, f"history:{index:03d}:transferred"),
                        tenant_id=tenant.id,
                        order_id=order.id,
                        actor_account_id=None,
                        from_status=OrderStatus.RESERVED,
                        to_status=OrderStatus.TRANSFERRED_TO_TEACHER,
                        comment=f"Передан преподавателю {student.teacher_name}",
                        created_at=transferred_at,
                        updated_at=transferred_at,
                    )
                )

            wallet.balance -= product.price_astrocoins
            db.add(
                AstrocoinLedgerEntry(
                    id=_id(run_id, f"ledger:order:{index:03d}"),
                    tenant_id=tenant.id,
                    wallet_id=wallet.id,
                    student_id=student.id,
                    actor_account_id=None,
                    idempotency_key=f"demo:{run_slug}:order:{index:03d}",
                    direction=LedgerDirection.DEBIT,
                    amount=product.price_astrocoins,
                    reason=f"Покупка в магазине, заказ №{order_number}",
                    comment=marker,
                    created_at=created_at,
                    updated_at=created_at,
                )
            )

            statuses[status.value] += 1
            venue_names.add(student.venue_name or "")
            teacher_names.add(student.teacher_name or "")
            warehouse_names.add(inventory.warehouse.name)
            product_names.add(product.name)

        db.add(
            AuditLog(
                id=_id(run_id, "audit"),
                tenant_id=tenant.id,
                actor_account_id=None,
                action="demo_orders.seeded",
                entity_type="tenant",
                entity_id=str(tenant.id),
                payload={
                    "run_id": marker,
                    "orders": count,
                    "students": len(demo_students),
                    "venues": len(venue_names),
                    "teachers": len(teacher_names),
                },
            )
        )
        await db.commit()

        return {
            "run_id": marker,
            "tenant_slug": tenant_slug,
            "created": True,
            "orders": count,
            "demo_students": len(demo_students),
            "venues": len(venue_names),
            "teachers": len(teacher_names),
            "warehouses": sorted(warehouse_names),
            "products": sorted(product_names),
            "statuses": dict(statuses),
            "qa_stock_added": stock_top_up,
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Seed many marked demo orders using student venue/teacher data"
    )
    parser.add_argument("--tenant-slug", default="n-novgorod")
    parser.add_argument("--count", type=int, default=48)
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = asyncio.run(
        seed_demo_orders(
            tenant_slug=args.tenant_slug,
            count=args.count,
            run_id=args.run_id,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
