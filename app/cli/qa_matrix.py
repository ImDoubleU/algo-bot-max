from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import re
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import parse
from uuid import UUID, uuid5

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, is_local_environment, is_placeholder
from app.db.session import AsyncSessionLocal
from app.models.account import (
    MaxAccount,
    StaffNotificationPreference,
    StaffRoleAssignment,
    StaffWarehousePreference,
)
from app.models.audit import AuditLog
from app.models.communication import SchoolBroadcast
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    OrderStatus,
    ProductStatus,
    StaffRole,
    StockMovementType,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
    StudentStatus,
    TenantStatus,
    WarehouseType,
)
from app.models.store import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductCategory,
    StockMovement,
    StudentCartItem,
    Warehouse,
    WarehouseInventory,
)
from app.models.student import (
    AstrocoinLedgerEntry,
    Contact,
    ContactStudentLink,
    Student,
    StudentAccessLink,
    StudentHistoryEvent,
    Wallet,
)
from app.models.teaching import (
    AttendanceRecord,
    Course,
    CourseLesson,
    FeedbackOutput,
    ManualFeedbackOutput,
    TeachingLessonOverride,
    TeachingSchedule,
)
from app.models.tenant import City, Partner, Tenant, Venue
from app.services.miniapp import MiniAppStoreError, get_miniapp_session
from app.services.staff import configured_superadmin_max_user_id
from app.services.staff_notifications import STAFF_NOTIFICATION_CATALOG

DEFAULT_RUN_ID = "QA-20260811"
QA_NAMESPACE = UUID("2bd2d30e-b18d-4e8f-bfcc-c13eed84f013")
QA_MAX_ID_BASE = 920_260_811_000

ACCOUNT_SPECS: tuple[tuple[str, int, str], ...] = (
    ("superadmin", 1, "Суперадминистратор QA"),
    ("director", 2, "Директор QA"),
    ("admin", 3, "Администратор QA"),
    ("curator", 4, "Куратор QA"),
    ("teacher_one", 5, "Анна Петрова"),
    ("teacher_two", 6, "Илья Смирнов"),
    ("parent", 7, "Родитель двух учеников QA"),
    ("student", 8, "Ученик QA"),
    ("direct_student", 9, "Самостоятельный ученик QA"),
    ("revoked_staff", 10, "Бывший администратор QA"),
    ("limited_director", 11, "Директор ограниченного филиала QA"),
    ("limited_teacher", 12, "Ольга Кузнецова"),
    ("empty_director", 13, "Директор пустого филиала QA"),
    ("revoked_parent", 14, "Родитель с отозванной связью QA"),
    ("limited_parent", 15, "Родитель ограниченного филиала QA"),
)

STUDENT_NAMES: tuple[tuple[str, str], ...] = (
    ("Александра", "Воронова"),
    ("Михаил", "Соколов"),
    ("Екатерина", "Орлова"),
    ("Даниил", "Морозов"),
    ("София", "Лебедева"),
    ("Артем", "Козлов"),
    ("Мария", "Новикова"),
    ("Иван", "Федоров"),
    ("Полина", "Волкова"),
    ("Максим", "Семенов"),
    ("Виктория", "Павлова"),
    ("Кирилл", "Голубев"),
    ("Алиса", "Васильева"),
    ("Роман", "Захаров"),
    ("Есения", "Писарева"),
    ("Степан", "Макаренков"),
    ("Надежда", "Белова"),
    ("Лев", "Комаров"),
)

ORDER_STATES: tuple[OrderStatus, ...] = (
    OrderStatus.CREATED,
    OrderStatus.RESERVED,
    OrderStatus.AWAITING_DELIVERY,
    OrderStatus.DELIVERED_TO_VENUE,
    OrderStatus.TRANSFERRED_TO_TEACHER,
    OrderStatus.ISSUED_TO_STUDENT,
    OrderStatus.CANCELLED,
    OrderStatus.RETURNED,
    OrderStatus.COINS_REFUNDED,
    OrderStatus.PROBLEM,
)


def _run_slug(run_id: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", run_id.strip().lower()).strip("-")
    if not value:
        raise ValueError("run_id must contain letters or digits")
    return value[:48]


def _marker(run_id: str) -> str:
    return run_id.strip().upper()


def _id(run_id: str, key: str) -> UUID:
    return uuid5(QA_NAMESPACE, f"{_marker(run_id)}:{key}")


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _photo_url() -> str:
    settings = get_settings()
    configured = str(settings.max_miniapp_url or "").strip()
    if configured and not is_placeholder(configured):
        parsed = parse.urlsplit(configured)
        if parsed.scheme and parsed.netloc:
            return parse.urlunsplit(
                (
                    parsed.scheme,
                    parsed.netloc,
                    "/miniapp/static/assets/dashboard-learning.png",
                    "",
                    "",
                )
            )
    return "/miniapp/static/assets/dashboard-learning.png"


async def _merge(db: AsyncSession, instance: Any) -> Any:
    return await db.merge(instance)


async def _merge_cart_item(db: AsyncSession, item: StudentCartItem) -> StudentCartItem:
    existing = await db.scalar(
        select(StudentCartItem).where(
            StudentCartItem.tenant_id == item.tenant_id,
            StudentCartItem.student_id == item.student_id,
            StudentCartItem.product_id == item.product_id,
        )
    )
    if existing is not None:
        existing.updated_by_account_id = item.updated_by_account_id
        existing.quantity = item.quantity
        return existing
    return await db.merge(item)


async def _account(
    db: AsyncSession,
    *,
    run_id: str,
    key: str,
    offset: int,
    display_name: str,
) -> MaxAccount:
    configured_superadmin_id = (
        configured_superadmin_max_user_id() if key == "superadmin" else None
    )
    max_user_id = configured_superadmin_id or QA_MAX_ID_BASE + offset
    expected_account_id = _id(run_id, f"account:{key}")
    existing = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if existing is not None and configured_superadmin_id is not None:
        return existing
    if existing is not None and UUID(str(existing.id)) != expected_account_id:
        raise RuntimeError(f"MAX ID {max_user_id} already belongs to a non-QA account")
    account_id = existing.id if existing is not None else expected_account_id
    return await _merge(
        db,
        MaxAccount(
            id=account_id,
            max_user_id=max_user_id,
            username=(
                get_settings().initial_superadmin_username
                if configured_superadmin_id is not None
                else f"{_marker(run_id)}:{key}"
            ),
            display_name=display_name,
        ),
    )


async def _seed_accounts(db: AsyncSession, run_id: str) -> dict[str, MaxAccount]:
    accounts: dict[str, MaxAccount] = {}
    for key, offset, display_name in ACCOUNT_SPECS:
        accounts[key] = await _account(
            db,
            run_id=run_id,
            key=key,
            offset=offset,
            display_name=display_name,
        )
    await db.flush()
    return accounts


async def _seed_qa_tenants(db: AsyncSession, run_id: str) -> dict[str, Tenant]:
    slug = _run_slug(run_id)
    specs = (
        ("full", "Полный филиал QA", "Нижний Новгород QA", "Партнер Полный QA"),
        ("limited", "Ограниченный филиал QA", "Казань QA", "Партнер Ограниченный QA"),
        ("empty", "Пустой филиал QA", "Томск QA", "Партнер Пустой QA"),
    )
    tenants: dict[str, Tenant] = {}
    for key, tenant_name, city_name, partner_name in specs:
        city = await _merge(
            db,
            City(
                id=_id(run_id, f"city:{key}"),
                slug=f"{slug}-{key}-city",
                name=f"{_marker(run_id)} · {city_name}",
            ),
        )
        partner = await _merge(
            db,
            Partner(
                id=_id(run_id, f"partner:{key}"),
                slug=f"{slug}-{key}-partner",
                name=f"{_marker(run_id)} · {partner_name}",
            ),
        )
        tenants[key] = await _merge(
            db,
            Tenant(
                id=_id(run_id, f"tenant:{key}"),
                city_id=city.id,
                partner_id=partner.id,
                slug=f"{slug}-{key}",
                name=f"{_marker(run_id)} · {tenant_name}",
                status=TenantStatus.ACTIVE,
            ),
        )
    await db.flush()
    return tenants


async def _seed_staff(
    db: AsyncSession,
    *,
    run_id: str,
    tenants: dict[str, Tenant],
    accounts: dict[str, MaxAccount],
) -> None:
    assignments = (
        ("full-superadmin", "full", "superadmin", StaffRole.SUPERADMIN, AssignmentStatus.ACTIVE),
        (
            "full-director",
            "full",
            "director",
            StaffRole.PARTNER_DIRECTOR,
            AssignmentStatus.ACTIVE,
        ),
        ("full-admin", "full", "admin", StaffRole.ADMIN, AssignmentStatus.ACTIVE),
        ("full-curator", "full", "curator", StaffRole.CURATOR, AssignmentStatus.ACTIVE),
        ("full-teacher-one", "full", "teacher_one", StaffRole.TEACHER, AssignmentStatus.ACTIVE),
        ("full-teacher-two", "full", "teacher_two", StaffRole.TEACHER, AssignmentStatus.ACTIVE),
        (
            "full-revoked-admin",
            "full",
            "revoked_staff",
            StaffRole.ADMIN,
            AssignmentStatus.REVOKED,
        ),
        (
            "limited-director",
            "limited",
            "limited_director",
            StaffRole.PARTNER_DIRECTOR,
            AssignmentStatus.ACTIVE,
        ),
        (
            "limited-teacher",
            "limited",
            "limited_teacher",
            StaffRole.TEACHER,
            AssignmentStatus.ACTIVE,
        ),
        (
            "empty-director",
            "empty",
            "empty_director",
            StaffRole.PARTNER_DIRECTOR,
            AssignmentStatus.ACTIVE,
        ),
    )
    for key, tenant_key, account_key, role, status in assignments:
        await _merge(
            db,
            StaffRoleAssignment(
                id=_id(run_id, f"assignment:{key}"),
                tenant_id=tenants[tenant_key].id,
                account_id=accounts[account_key].id,
                role=role,
                status=status,
            ),
        )


async def _seed_venues(
    db: AsyncSession,
    *,
    run_id: str,
    tenants: dict[str, Tenant],
) -> dict[str, Venue]:
    slug = _run_slug(run_id)
    specs = (
        ("full-central", "full", "Центральная площадка", "ул. Учебная, 1"),
        ("full-north", "full", "Северная площадка", "пр. Знаний, 12"),
        ("full-online", "full", "Онлайн", None),
        ("limited-main", "limited", "Единственная площадка", "ул. Тестовая, 5"),
    )
    venues: dict[str, Venue] = {}
    for key, tenant_key, name, address in specs:
        venues[key] = await _merge(
            db,
            Venue(
                id=_id(run_id, f"venue:{key}"),
                tenant_id=tenants[tenant_key].id,
                slug=f"{slug}-{key}",
                name=f"{_marker(run_id)} · {name}",
                address=address,
            ),
        )
    return venues


def _student_group(run_id: str, index: int) -> tuple[str, str, str, str]:
    marker = _marker(run_id)
    groups = (
        (f"{marker} Робототехника Пн 16:00", "Робототехника", "full-central", "Анна Петрова"),
        (f"{marker} Python Ср 18:00", "Python Start", "full-north", "Илья Смирнов"),
        (f"{marker} Онлайн Сб 12:00", "Minecraft", "full-online", "Анна Петрова"),
        (
            f"{marker} Индивидуально Вт 15:00",
            "Python Pro",
            "full-central",
            "Илья Смирнов",
        ),
    )
    return groups[index % len(groups)]


async def _seed_students(
    db: AsyncSession,
    *,
    run_id: str,
    tenants: dict[str, Tenant],
    venues: dict[str, Venue],
) -> list[Student]:
    now = _utcnow()
    students: list[Student] = []
    for index, (first_name, last_name) in enumerate(STUDENT_NAMES, start=1):
        if index <= 16:
            tenant_key = "full"
            group_name, course_name, venue_key, teacher_name = _student_group(run_id, index - 1)
        else:
            tenant_key = "limited"
            group_name = f"{_marker(run_id)} Ограниченная группа"
            course_name = "Цифровая грамотность"
            venue_key = "limited-main"
            teacher_name = "Ольга Кузнецова"
        status = StudentStatus.DEPARTED if index == 16 else StudentStatus.ACTIVE
        imported_at = now - timedelta(days=40 - index)
        status_updated_at = (
            now - timedelta(days=1) if status == StudentStatus.DEPARTED else imported_at
        )
        student = await _merge(
            db,
            Student(
                id=_id(run_id, f"student:{index:02d}"),
                tenant_id=tenants[tenant_key].id,
                venue_id=venues[venue_key].id,
                crm_deal_id=f"{_marker(run_id)}-DEAL-{index:02d}",
                crm_uuid=f"{_run_slug(run_id)}-student-{index:02d}",
                lms_student_id=f"{_marker(run_id)}-ST-{index:02d}",
                student_access_code=f"{_marker(run_id)}-ACCESS-{index:02d}",
                first_name=first_name,
                last_name=last_name,
                group_name=group_name,
                course_name=course_name,
                venue_name=f"{_marker(run_id)} · {venues[venue_key].name.split('·')[-1].strip()}",
                teacher_name=teacher_name,
                status=status,
                status_updated_at=status_updated_at,
                departed_at=now - timedelta(days=1) if status == StudentStatus.DEPARTED else None,
                created_at=imported_at,
                updated_at=now - timedelta(days=index % 5),
            ),
        )
        students.append(student)
        await _merge(
            db,
            StudentHistoryEvent(
                id=_id(run_id, f"student-history:{index:02d}:imported"),
                tenant_id=student.tenant_id,
                student_id=student.id,
                event_type="imported",
                from_status=None,
                to_status=StudentStatus.ACTIVE.value,
                changed_fields=["first_name", "last_name", "group_name"],
                source="qa_matrix",
                created_at=imported_at,
                updated_at=imported_at,
            ),
        )
        if index in {2, 7, 16}:
            await _merge(
                db,
                StudentHistoryEvent(
                    id=_id(run_id, f"student-history:{index:02d}:updated"),
                    tenant_id=student.tenant_id,
                    student_id=student.id,
                    event_type="departed" if index == 16 else "updated",
                    from_status=StudentStatus.ACTIVE.value,
                    to_status=status.value,
                    changed_fields=["status"] if index == 16 else ["group_name", "teacher_name"],
                    source="qa_matrix",
                    created_at=status_updated_at,
                    updated_at=status_updated_at,
                ),
            )
    await db.flush()
    return students


async def _seed_student_access(
    db: AsyncSession,
    *,
    run_id: str,
    tenants: dict[str, Tenant],
    accounts: dict[str, MaxAccount],
    students: list[Student],
) -> None:
    full_tenant = tenants["full"]
    parent_contact = await _merge(
        db,
        Contact(
            id=_id(run_id, "contact:parent-two"),
            tenant_id=full_tenant.id,
            external_contact_id=f"{_marker(run_id)}-CONTACT-PARENT",
            display_name="Елена Воронова",
        ),
    )
    for index in (0, 1):
        await _merge(
            db,
            ContactStudentLink(
                id=_id(run_id, f"contact-link:parent:{index + 1}"),
                tenant_id=full_tenant.id,
                contact_id=parent_contact.id,
                student_id=students[index].id,
            ),
        )
    parent_links: list[StudentAccessLink] = []
    for index in (0, 1):
        parent_links.append(
            await _merge(
                db,
                StudentAccessLink(
                    id=_id(run_id, f"access:parent:{index + 1}"),
                    tenant_id=full_tenant.id,
                    account_id=accounts["parent"].id,
                    student_id=students[index].id,
                    role=StudentAccessRole.PARENT,
                    status=StudentAccessStatus.ACTIVE,
                    source=StudentAccessSource.IMPORT,
                ),
            )
        )
    await db.flush()
    await _merge(
        db,
        StudentAccessLink(
            id=_id(run_id, "access:child-sponsored"),
            tenant_id=full_tenant.id,
            account_id=accounts["student"].id,
            student_id=students[0].id,
            role=StudentAccessRole.STUDENT,
            status=StudentAccessStatus.ACTIVE,
            source=StudentAccessSource.PARENT_QR,
            sponsor_access_link_id=parent_links[0].id,
        ),
    )
    await _merge(
        db,
        StudentAccessLink(
            id=_id(run_id, "access:direct-student"),
            tenant_id=full_tenant.id,
            account_id=accounts["direct_student"].id,
            student_id=students[2].id,
            role=StudentAccessRole.STUDENT,
            status=StudentAccessStatus.ACTIVE,
            source=StudentAccessSource.ID_ENTRY,
        ),
    )
    await _merge(
        db,
        StudentAccessLink(
            id=_id(run_id, "access:revoked-parent"),
            tenant_id=full_tenant.id,
            account_id=accounts["revoked_parent"].id,
            student_id=students[3].id,
            role=StudentAccessRole.PARENT,
            status=StudentAccessStatus.REVOKED,
            source=StudentAccessSource.ADMIN,
            revoked_at=_utcnow() - timedelta(days=2),
            revoked_reason="qa_matrix",
        ),
    )
    limited_contact = await _merge(
        db,
        Contact(
            id=_id(run_id, "contact:limited-parent"),
            tenant_id=tenants["limited"].id,
            external_contact_id=f"{_marker(run_id)}-CONTACT-LIMITED",
            display_name="Родитель ограниченного филиала QA",
        ),
    )
    await _merge(
        db,
        ContactStudentLink(
            id=_id(run_id, "contact-link:limited-parent"),
            tenant_id=tenants["limited"].id,
            contact_id=limited_contact.id,
            student_id=students[16].id,
        ),
    )
    await _merge(
        db,
        StudentAccessLink(
            id=_id(run_id, "access:limited-parent"),
            tenant_id=tenants["limited"].id,
            account_id=accounts["limited_parent"].id,
            student_id=students[16].id,
            role=StudentAccessRole.PARENT,
            status=StudentAccessStatus.ACTIVE,
            source=StudentAccessSource.IMPORT,
        ),
    )


async def _seed_store_for_tenant(
    db: AsyncSession,
    *,
    run_id: str,
    tenant: Tenant,
    venue: Venue | None,
    key: str,
) -> tuple[list[Product], list[Warehouse], dict[tuple[UUID, UUID], WarehouseInventory]]:
    marker = _marker(run_id)
    slug = _run_slug(run_id)
    categories = {
        "school": await _merge(
            db,
            ProductCategory(
                id=_id(run_id, f"category:{key}:school"),
                tenant_id=tenant.id,
                slug=f"{slug}-school",
                name=f"{marker} · Для учебы",
                sort_order=10,
            ),
        ),
        "gifts": await _merge(
            db,
            ProductCategory(
                id=_id(run_id, f"category:{key}:gifts"),
                tenant_id=tenant.id,
                slug=f"{slug}-gifts",
                name=f"{marker} · Подарки",
                sort_order=20,
            ),
        ),
    }
    product_specs = (
        ("PHOTO", "Набор для творчества", 350, ProductStatus.ACTIVE, _photo_url()),
        ("NO-PHOTO", "Фирменная ручка", 120, ProductStatus.ACTIVE, None),
        (
            "LONG-NAME",
            "Большой учебный набор для проектов, экспериментов и домашних занятий",
            780,
            ProductStatus.ACTIVE,
            _photo_url(),
        ),
        ("HIDDEN", "Скрытый товар", 90, ProductStatus.HIDDEN, None),
        ("ARCHIVED", "Архивный товар", 150, ProductStatus.ARCHIVED, None),
        ("OUT", "Товар без остатка", 200, ProductStatus.ACTIVE, _photo_url()),
        ("LOW", "Товар с малым остатком", 180, ProductStatus.ACTIVE, _photo_url()),
        ("NORMAL", "Обычный товар", 250, ProductStatus.ACTIVE, _photo_url()),
    )
    products: list[Product] = []
    for index, (sku_suffix, name, price, status, photo_url) in enumerate(product_specs):
        products.append(
            await _merge(
                db,
                Product(
                    id=_id(run_id, f"product:{key}:{sku_suffix.lower()}"),
                    tenant_id=tenant.id,
                    category_id=categories["school" if index % 2 == 0 else "gifts"].id,
                    sku=f"{marker}-{key.upper()}-{sku_suffix}",
                    name=f"{marker} · {name}",
                    description=f"Тестовая позиция {marker}: {name}.",
                    photo_url=photo_url,
                    price_astrocoins=price,
                    status=status,
                ),
            )
        )
    warehouses = [
        await _merge(
            db,
            Warehouse(
                id=_id(run_id, f"warehouse:{key}:common"),
                tenant_id=tenant.id,
                slug=f"{slug}-common",
                name=f"{marker} · Главный склад",
                warehouse_type=WarehouseType.COMMON,
                address="ул. Складская, 1",
            ),
        ),
        await _merge(
            db,
            Warehouse(
                id=_id(run_id, f"warehouse:{key}:venue"),
                tenant_id=tenant.id,
                venue_id=venue.id if venue is not None else None,
                slug=f"{slug}-venue",
                name=f"{marker} · Склад площадки",
                warehouse_type=WarehouseType.VENUE,
                address=venue.address if venue is not None else None,
            ),
        ),
        await _merge(
            db,
            Warehouse(
                id=_id(run_id, f"warehouse:{key}:partner"),
                tenant_id=tenant.id,
                slug=f"{slug}-partner",
                name=f"{marker} · Склад партнера",
                warehouse_type=WarehouseType.PARTNER,
                address="ул. Резервная, 7",
            ),
        ),
    ]
    inventory: dict[tuple[UUID, UUID], WarehouseInventory] = {}
    for product_index, product in enumerate(products):
        for warehouse_index, warehouse in enumerate(warehouses):
            if product_index == 5:
                quantity = 0
            elif product_index == 6:
                quantity = 2 if warehouse_index == 0 else 0
            elif product_index == 7:
                quantity = (30, 12, 8)[warehouse_index]
            else:
                quantity = (12, 5, 3)[warehouse_index]
            row = await _merge(
                db,
                WarehouseInventory(
                    id=_id(
                        run_id,
                        f"inventory:{key}:{product_index}:{warehouse_index}",
                    ),
                    tenant_id=tenant.id,
                    warehouse_id=warehouse.id,
                    product_id=product.id,
                    available_quantity=quantity,
                    reserved_quantity=0,
                    issued_quantity=0,
                    returned_quantity=0,
                    low_stock_notified=quantity <= 2,
                ),
            )
            inventory[(product.id, warehouse.id)] = row
            if quantity:
                await _merge(
                    db,
                    StockMovement(
                        id=_id(
                            run_id,
                            f"movement:{key}:initial:{product_index}:{warehouse_index}",
                        ),
                        tenant_id=tenant.id,
                        product_id=product.id,
                        to_warehouse_id=warehouse.id,
                        movement_type=StockMovementType.INITIAL,
                        quantity=quantity,
                        comment=f"{marker} начальное заполнение",
                    ),
                )
    if inventory[(products[0].id, warehouses[0].id)].available_quantity >= 3:
        inventory[(products[0].id, warehouses[0].id)].available_quantity -= 3
        inventory[(products[0].id, warehouses[2].id)].available_quantity += 3
        await _merge(
            db,
            StockMovement(
                id=_id(run_id, f"movement:{key}:transfer"),
                tenant_id=tenant.id,
                product_id=products[0].id,
                from_warehouse_id=warehouses[0].id,
                to_warehouse_id=warehouses[2].id,
                movement_type=StockMovementType.TRANSFER,
                quantity=3,
                comment=f"{marker} тестовое перемещение",
            ),
        )
    await db.flush()
    return products, warehouses, inventory


async def _seed_wallets_and_orders(
    db: AsyncSession,
    *,
    run_id: str,
    tenant: Tenant,
    accounts: dict[str, MaxAccount],
    students: list[Student],
    products: list[Product],
    warehouses: list[Warehouse],
    inventory: dict[tuple[UUID, UUID], WarehouseInventory],
) -> None:
    marker = _marker(run_id)
    balances: defaultdict[UUID, int] = defaultdict(int)
    wallets: dict[UUID, Wallet] = {}
    full_students = [student for student in students if student.tenant_id == tenant.id]
    for index, student in enumerate(full_students, start=1):
        wallet = await _merge(
            db,
            Wallet(
                id=_id(run_id, f"wallet:{index:02d}"),
                tenant_id=tenant.id,
                student_id=student.id,
                balance=0,
            ),
        )
        wallets[student.id] = wallet
        initial_amount = 1200 + index * 50
        balances[student.id] += initial_amount
        await _merge(
            db,
            AstrocoinLedgerEntry(
                id=_id(run_id, f"ledger:{index:02d}:initial"),
                tenant_id=tenant.id,
                wallet_id=wallet.id,
                student_id=student.id,
                actor_account_id=accounts["teacher_one"].id,
                idempotency_key=f"qa:{_run_slug(run_id)}:initial:{index:02d}",
                direction=LedgerDirection.CREDIT,
                amount=initial_amount,
                reason="Стартовый баланс QA",
                comment=marker,
            ),
        )

    limited_students = [student for student in students if student.tenant_id != tenant.id]
    for index, student in enumerate(limited_students, start=17):
        wallet = await _merge(
            db,
            Wallet(
                id=_id(run_id, f"wallet:{index:02d}"),
                tenant_id=student.tenant_id,
                student_id=student.id,
                balance=500,
            ),
        )
        await _merge(
            db,
            AstrocoinLedgerEntry(
                id=_id(run_id, f"ledger:{index:02d}:initial"),
                tenant_id=student.tenant_id,
                wallet_id=wallet.id,
                student_id=student.id,
                actor_account_id=accounts["limited_teacher"].id,
                idempotency_key=f"qa:{_run_slug(run_id)}:initial:{index:02d}",
                direction=LedgerDirection.CREDIT,
                amount=500,
                reason="Стартовый баланс QA",
                comment=marker,
            ),
        )

    normal_product = products[7]
    common, venue, _partner = warehouses
    order_inventory_changes = {
        "common_reserved": 0,
        "venue_reserved": 0,
        "common_issued": 0,
        "common_returned": 0,
    }
    for index, status in enumerate(ORDER_STATES, start=1):
        student = full_students[index - 1]
        wallet = wallets[student.id]
        order_id = _id(run_id, f"order:{index:02d}")
        total = normal_product.price_astrocoins
        cancellation_reason = "Товар закончился" if status == OrderStatus.CANCELLED else None
        reserved_warehouse_id: UUID | None = None
        warehouse_id: UUID | None = None
        if status == OrderStatus.RESERVED:
            reserved_warehouse_id = common.id
            order_inventory_changes["common_reserved"] += 1
        elif status in {
            OrderStatus.AWAITING_DELIVERY,
            OrderStatus.DELIVERED_TO_VENUE,
            OrderStatus.TRANSFERRED_TO_TEACHER,
        }:
            warehouse_id = venue.id
            order_inventory_changes["venue_reserved"] += 1
        elif status in {OrderStatus.ISSUED_TO_STUDENT, OrderStatus.RETURNED}:
            warehouse_id = common.id
            order_inventory_changes["common_issued"] += 1
            if status == OrderStatus.RETURNED:
                order_inventory_changes["common_returned"] += 1
        order = await _merge(
            db,
            Order(
                id=order_id,
                tenant_id=tenant.id,
                student_id=student.id,
                created_by_account_id=(
                    accounts["parent"].id if index <= 2 else accounts["direct_student"].id
                ),
                order_number=980000 + index,
                status=status,
                total_astrocoins=total,
                teacher_name=student.teacher_name,
                venue_name=student.venue_name,
                comment=f"{marker} заказ в статусе {status.value}",
                cancellation_reason=cancellation_reason,
                client_request_id=f"{_run_slug(run_id)}-order-{index:02d}",
            ),
        )
        await _merge(
            db,
            OrderItem(
                id=_id(run_id, f"order-item:{index:02d}"),
                tenant_id=tenant.id,
                order_id=order.id,
                product_id=normal_product.id,
                quantity=1,
                warehouse_id=warehouse_id,
                reserved_warehouse_id=reserved_warehouse_id,
                unit_price_astrocoins=total,
                total_price_astrocoins=total,
            ),
        )
        history_states: list[OrderStatus] = [status]
        if status in {
            OrderStatus.AWAITING_DELIVERY,
            OrderStatus.DELIVERED_TO_VENUE,
            OrderStatus.TRANSFERRED_TO_TEACHER,
            OrderStatus.ISSUED_TO_STUDENT,
            OrderStatus.CANCELLED,
            OrderStatus.RETURNED,
            OrderStatus.COINS_REFUNDED,
        }:
            history_states = [OrderStatus.RESERVED, status]
        if status == OrderStatus.DELIVERED_TO_VENUE:
            history_states = [
                OrderStatus.RESERVED,
                OrderStatus.AWAITING_DELIVERY,
                OrderStatus.DELIVERED_TO_VENUE,
            ]
        if status == OrderStatus.TRANSFERRED_TO_TEACHER:
            history_states = [
                OrderStatus.RESERVED,
                OrderStatus.AWAITING_DELIVERY,
                OrderStatus.DELIVERED_TO_VENUE,
                OrderStatus.TRANSFERRED_TO_TEACHER,
            ]
        if status == OrderStatus.ISSUED_TO_STUDENT:
            history_states = [
                OrderStatus.RESERVED,
                OrderStatus.AWAITING_DELIVERY,
                OrderStatus.DELIVERED_TO_VENUE,
                OrderStatus.TRANSFERRED_TO_TEACHER,
                OrderStatus.ISSUED_TO_STUDENT,
            ]
        if status == OrderStatus.RETURNED:
            history_states = [
                OrderStatus.RESERVED,
                OrderStatus.AWAITING_DELIVERY,
                OrderStatus.DELIVERED_TO_VENUE,
                OrderStatus.TRANSFERRED_TO_TEACHER,
                OrderStatus.ISSUED_TO_STUDENT,
                OrderStatus.RETURNED,
            ]
        if status == OrderStatus.COINS_REFUNDED:
            history_states = [
                OrderStatus.RESERVED,
                OrderStatus.CANCELLED,
                OrderStatus.COINS_REFUNDED,
            ]
        previous: OrderStatus | None = None
        for position, history_status in enumerate(history_states, start=1):
            await _merge(
                db,
                OrderStatusHistory(
                    id=_id(run_id, f"order-history:{index:02d}:{position}"),
                    tenant_id=tenant.id,
                    order_id=order.id,
                    actor_account_id=accounts["admin"].id,
                    from_status=previous,
                    to_status=history_status,
                    comment=f"{marker} шаг {position}",
                    created_at=_utcnow() - timedelta(days=9 - index, minutes=-position),
                    updated_at=_utcnow() - timedelta(days=9 - index, minutes=-position),
                ),
            )
            previous = history_status
        if status != OrderStatus.CREATED:
            balances[student.id] -= total
            await _merge(
                db,
                AstrocoinLedgerEntry(
                    id=_id(run_id, f"ledger:order:{index:02d}:debit"),
                    tenant_id=tenant.id,
                    wallet_id=wallet.id,
                    student_id=student.id,
                    actor_account_id=accounts["direct_student"].id,
                    idempotency_key=f"order:{order.id}:debit",
                    direction=LedgerDirection.DEBIT,
                    amount=total,
                    reason=f"Покупка в магазине, заказ №{order.order_number}",
                    comment=marker,
                ),
            )
        if status in {OrderStatus.CANCELLED, OrderStatus.RETURNED, OrderStatus.COINS_REFUNDED}:
            balances[student.id] += total
            await _merge(
                db,
                AstrocoinLedgerEntry(
                    id=_id(run_id, f"ledger:order:{index:02d}:refund"),
                    tenant_id=tenant.id,
                    wallet_id=wallet.id,
                    student_id=student.id,
                    actor_account_id=accounts["admin"].id,
                    idempotency_key=f"order:{order.id}:qa-refund",
                    direction=LedgerDirection.REVERSAL,
                    amount=total,
                    reason=f"Возврат по заказу №{order.order_number}",
                    comment=cancellation_reason or marker,
                ),
            )

    accrual_student = full_students[8]
    balances[accrual_student.id] += 100
    await _merge(
        db,
        AstrocoinLedgerEntry(
            id=_id(run_id, "ledger:accrual:active"),
            tenant_id=tenant.id,
            wallet_id=wallets[accrual_student.id].id,
            student_id=accrual_student.id,
            actor_account_id=accounts["teacher_one"].id,
            idempotency_key=f"qa:{_run_slug(run_id)}:accrual:active",
            direction=LedgerDirection.CREDIT,
            amount=100,
            reason="Активность на уроке",
            comment=marker,
            created_at=_utcnow() - timedelta(days=2),
            updated_at=_utcnow() - timedelta(days=2),
        ),
    )
    undone_student = full_students[9]
    for suffix, direction in (("credit", LedgerDirection.CREDIT), ("undo", LedgerDirection.DEBIT)):
        await _merge(
            db,
            AstrocoinLedgerEntry(
                id=_id(run_id, f"ledger:accrual:{suffix}"),
                tenant_id=tenant.id,
                wallet_id=wallets[undone_student.id].id,
                student_id=undone_student.id,
                actor_account_id=accounts["teacher_two"].id,
                idempotency_key=f"qa:{_run_slug(run_id)}:accrual:{suffix}",
                direction=direction,
                amount=50,
                reason="Проект" if suffix == "credit" else "Отмена начисления: Проект",
                comment=marker,
            ),
        )

    common_inventory = inventory[(normal_product.id, common.id)]
    venue_inventory = inventory[(normal_product.id, venue.id)]
    common_inventory.available_quantity -= (
        order_inventory_changes["common_issued"] - order_inventory_changes["common_returned"]
    )
    common_inventory.reserved_quantity = order_inventory_changes["common_reserved"]
    common_inventory.issued_quantity = order_inventory_changes["common_issued"]
    common_inventory.returned_quantity = order_inventory_changes["common_returned"]
    venue_inventory.reserved_quantity = order_inventory_changes["venue_reserved"]
    await _merge(db, common_inventory)
    await _merge(db, venue_inventory)

    for student_id, wallet in wallets.items():
        wallet.balance = balances[student_id]
        await _merge(db, wallet)

    await _merge_cart_item(
        db,
        StudentCartItem(
            id=_id(run_id, "cart:parent-child-one"),
            tenant_id=tenant.id,
            student_id=full_students[0].id,
            product_id=products[0].id,
            updated_by_account_id=accounts["parent"].id,
            quantity=1,
        ),
    )
    await _merge_cart_item(
        db,
        StudentCartItem(
            id=_id(run_id, "cart:parent-child-two"),
            tenant_id=tenant.id,
            student_id=full_students[1].id,
            product_id=products[1].id,
            updated_by_account_id=accounts["parent"].id,
            quantity=2,
        ),
    )


async def _seed_broadcasts_and_preferences(
    db: AsyncSession,
    *,
    run_id: str,
    tenant: Tenant,
    accounts: dict[str, MaxAccount],
    warehouses: list[Warehouse],
) -> None:
    marker = _marker(run_id)
    statuses = (
        ("sent", 8, 8, 0),
        ("partial", 8, 5, 3),
        ("failed", 8, 0, 8),
    )
    for index, (status, recipients, delivered, failed) in enumerate(statuses, start=1):
        await _merge(
            db,
            SchoolBroadcast(
                id=_id(run_id, f"broadcast:{index}"),
                tenant_id=tenant.id,
                creator_account_id=accounts["director"].id,
                title=f"{marker} · Рассылка {status}",
                message=f"Тестовая школьная новость: результат {status}.",
                image_url=_photo_url() if index == 1 else None,
                recipient_category=("all", "parents", "students")[index - 1],
                audience_filter=("all", "low_balance", "active_orders")[index - 1],
                group_names=[],
                venue_names=[],
                lesson_modes=[],
                balance_threshold=500 if index == 2 else None,
                status=status,
                recipient_count=recipients,
                delivered_count=delivered,
                failed_count=failed,
                sent_at=_utcnow() - timedelta(days=4 - index),
            ),
        )
    for account_key in ("director", "admin", "curator"):
        await _merge(
            db,
            StaffWarehousePreference(
                id=_id(run_id, f"warehouse-preference:{account_key}"),
                tenant_id=tenant.id,
                account_id=accounts[account_key].id,
                warehouse_id=warehouses[0 if account_key != "curator" else 1].id,
            ),
        )
    configurable_keys = {
        "orders.created",
        "orders.cancelled",
        "orders.transferred",
        "orders.issued",
        "orders.returned",
        "inventory.low_stock",
        "broadcasts.completed",
        "broadcasts.partial",
        "broadcasts.failed",
    }
    known_keys = {item.key for item in STAFF_NOTIFICATION_CATALOG}
    for account_key in ("admin", "curator"):
        for event_key in sorted(configurable_keys & known_keys):
            await _merge(
                db,
                StaffNotificationPreference(
                    id=_id(run_id, f"notification:{account_key}:{event_key}"),
                    tenant_id=tenant.id,
                    account_id=accounts[account_key].id,
                    event_key=event_key,
                    enabled=(account_key == "admin"),
                ),
            )


async def _reset_qa_runtime_state(
    db: AsyncSession,
    *,
    tenants: dict[str, Tenant],
) -> None:
    tenant_ids = [tenant.id for tenant in tenants.values()]
    runtime_models = (
        StockMovement,
        OrderStatusHistory,
        OrderItem,
        Order,
        StudentCartItem,
        AstrocoinLedgerEntry,
        AttendanceRecord,
        FeedbackOutput,
        ManualFeedbackOutput,
        TeachingLessonOverride,
        TeachingSchedule,
        CourseLesson,
        Course,
        SchoolBroadcast,
        StaffRoleAssignment,
        StaffNotificationPreference,
        StaffWarehousePreference,
    )
    for model in runtime_models:
        await db.execute(delete(model).where(model.tenant_id.in_(tenant_ids)))
    await db.flush()


async def seed_matrix(run_id: str, default_tenant_slug: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as db:
        default_tenant = await db.scalar(
            select(Tenant).where(Tenant.slug == default_tenant_slug.strip().lower())
        )
        if default_tenant is None:
            raise RuntimeError(f"Default tenant not found: {default_tenant_slug}")
        accounts = await _seed_accounts(db, run_id)
        tenants = await _seed_qa_tenants(db, run_id)
        await _reset_qa_runtime_state(db, tenants=tenants)
        await _seed_staff(
            db,
            run_id=run_id,
            tenants=tenants,
            accounts=accounts,
        )
        venues = await _seed_venues(db, run_id=run_id, tenants=tenants)
        students = await _seed_students(
            db,
            run_id=run_id,
            tenants=tenants,
            venues=venues,
        )
        await _seed_student_access(
            db,
            run_id=run_id,
            tenants=tenants,
            accounts=accounts,
            students=students,
        )
        full_products, full_warehouses, full_inventory = await _seed_store_for_tenant(
            db,
            run_id=run_id,
            tenant=tenants["full"],
            venue=venues["full-central"],
            key="full",
        )
        default_venue = await db.scalar(
            select(Venue).where(Venue.tenant_id == default_tenant.id).order_by(Venue.created_at)
        )
        await _seed_store_for_tenant(
            db,
            run_id=run_id,
            tenant=default_tenant,
            venue=default_venue,
            key="production",
        )
        await _seed_wallets_and_orders(
            db,
            run_id=run_id,
            tenant=tenants["full"],
            accounts=accounts,
            students=students,
            products=full_products,
            warehouses=full_warehouses,
            inventory=full_inventory,
        )
        await _seed_broadcasts_and_preferences(
            db,
            run_id=run_id,
            tenant=tenants["full"],
            accounts=accounts,
            warehouses=full_warehouses,
        )
        await _merge(
            db,
            AuditLog(
                id=_id(run_id, "audit:seed"),
                tenant_id=tenants["full"].id,
                actor_account_id=accounts["superadmin"].id,
                action="qa_matrix.seeded",
                entity_type="qa_run",
                entity_id=_marker(run_id),
                payload={"run_id": _marker(run_id)},
            ),
        )
        await db.commit()

        return {
            "run_id": _marker(run_id),
            "default_tenant": default_tenant.slug,
            "qa_tenants": {key: tenant.slug for key, tenant in tenants.items()},
            "accounts": {key: account.max_user_id for key, account in accounts.items()},
            "students": len(students),
            "products_full": len(full_products),
            "warehouses_full": len(full_warehouses),
            "orders": len(ORDER_STATES),
        }


def _check(
    checks: list[dict[str, Any]],
    *,
    key: str,
    passed: bool,
    actual: Any,
    expected: Any,
) -> None:
    checks.append(
        {
            "key": key,
            "status": "pass" if passed else "fail",
            "actual": actual,
            "expected": expected,
        }
    )


async def audit_matrix(run_id: str, default_tenant_slug: str) -> dict[str, Any]:
    slug = _run_slug(run_id)
    checks: list[dict[str, Any]] = []
    async with AsyncSessionLocal() as db:
        tenants = (await db.scalars(select(Tenant).where(Tenant.slug.like(f"{slug}-%")))).all()
        tenant_by_suffix = {tenant.slug.removeprefix(f"{slug}-"): tenant for tenant in tenants}
        _check(
            checks,
            key="qa_tenants",
            passed=set(tenant_by_suffix) == {"full", "limited", "empty"},
            actual=sorted(tenant_by_suffix),
            expected=["empty", "full", "limited"],
        )
        if "full" not in tenant_by_suffix:
            return {"run_id": _marker(run_id), "status": "failed", "checks": checks}
        full = tenant_by_suffix["full"]
        tenant_ids = [tenant.id for tenant in tenants]
        counts = {
            "students": await db.scalar(
                select(func.count()).select_from(Student).where(Student.tenant_id.in_(tenant_ids))
            ),
            "products": await db.scalar(
                select(func.count()).select_from(Product).where(Product.tenant_id == full.id)
            ),
            "warehouses": await db.scalar(
                select(func.count()).select_from(Warehouse).where(Warehouse.tenant_id == full.id)
            ),
            "orders": await db.scalar(
                select(func.count()).select_from(Order).where(Order.tenant_id == full.id)
            ),
            "broadcasts": await db.scalar(
                select(func.count())
                .select_from(SchoolBroadcast)
                .where(SchoolBroadcast.tenant_id == full.id)
            ),
        }
        expected_counts = {
            "students": 18,
            "products": 8,
            "warehouses": 3,
            "orders": 8,
            "broadcasts": 3,
        }
        for key, expected in expected_counts.items():
            actual = int(counts[key] or 0)
            _check(
                checks,
                key=f"count.{key}",
                passed=actual >= expected,
                actual=actual,
                expected={"minimum": expected},
            )

        order_statuses = set(
            (await db.scalars(select(Order.status).where(Order.tenant_id == full.id))).all()
        )
        _check(
            checks,
            key="orders.all_statuses",
            passed=set(ORDER_STATES).issubset(order_statuses),
            actual=sorted(status.value for status in order_statuses),
            expected=sorted(status.value for status in ORDER_STATES),
        )

        bad_inventory = (
            await db.scalars(
                select(WarehouseInventory).where(
                    WarehouseInventory.tenant_id == full.id,
                    (
                        (WarehouseInventory.available_quantity < 0)
                        | (WarehouseInventory.reserved_quantity < 0)
                        | (
                            WarehouseInventory.reserved_quantity
                            > WarehouseInventory.available_quantity
                        )
                    ),
                )
            )
        ).all()
        _check(
            checks,
            key="inventory.non_negative_and_reservable",
            passed=not bad_inventory,
            actual=[str(item.id) for item in bad_inventory],
            expected=[],
        )

        qa_students = (
            await db.scalars(select(Student).where(Student.tenant_id.in_(tenant_ids)))
        ).all()
        wallet_mismatches: list[dict[str, Any]] = []
        for student in qa_students:
            wallet = await db.scalar(select(Wallet).where(Wallet.student_id == student.id))
            if wallet is None:
                wallet_mismatches.append({"student": student.display_name, "error": "no_wallet"})
                continue
            entries = (
                await db.scalars(
                    select(AstrocoinLedgerEntry).where(
                        AstrocoinLedgerEntry.student_id == student.id
                    )
                )
            ).all()
            calculated = sum(
                entry.amount
                if entry.direction in {LedgerDirection.CREDIT, LedgerDirection.REVERSAL}
                else -entry.amount
                for entry in entries
            )
            if calculated != wallet.balance:
                wallet_mismatches.append(
                    {
                        "student": student.display_name,
                        "wallet": wallet.balance,
                        "ledger": calculated,
                    }
                )
        _check(
            checks,
            key="wallets.match_ledger",
            passed=not wallet_mismatches,
            actual=wallet_mismatches,
            expected=[],
        )

        configured_superadmin_id = configured_superadmin_max_user_id()
        account_ids = {
            key: (
                configured_superadmin_id
                if key == "superadmin" and configured_superadmin_id is not None
                else QA_MAX_ID_BASE + offset
            )
            for key, offset, _name in ACCOUNT_SPECS
        }
        session_expectations = (
            ("superadmin", "full", StaffRole.SUPERADMIN.value),
            ("director", "full", StaffRole.PARTNER_DIRECTOR.value),
            ("admin", "full", StaffRole.ADMIN.value),
            ("curator", "full", StaffRole.CURATOR.value),
            ("teacher_one", "full", StaffRole.TEACHER.value),
            ("parent", "full", StudentAccessRole.PARENT.value),
            ("student", "full", StudentAccessRole.STUDENT.value),
        )
        for account_key, tenant_key, expected_role in session_expectations:
            try:
                session = await get_miniapp_session(
                    db,
                    max_user_id=account_ids[account_key],
                    tenant_slug=tenant_by_suffix[tenant_key].slug,
                )
            except MiniAppStoreError as exc:
                _check(
                    checks,
                    key=f"session.{account_key}",
                    passed=False,
                    actual=str(exc),
                    expected=expected_role,
                )
                continue
            visible_roles = [role.value for role in session.staff_roles] + [
                role.value for role in session.student_roles
            ]
            _check(
                checks,
                key=f"session.{account_key}",
                passed=session.has_access and expected_role in visible_roles,
                actual={"access": session.has_access, "roles": visible_roles},
                expected=expected_role,
            )

        for account_key in ("revoked_staff", "revoked_parent"):
            revoked_session = await get_miniapp_session(
                db,
                max_user_id=account_ids[account_key],
                tenant_slug=tenant_by_suffix["full"].slug,
            )
            _check(
                checks,
                key=f"session.{account_key}",
                passed=(
                    not revoked_session.has_access
                    and not revoked_session.staff_roles
                    and not revoked_session.student_roles
                ),
                actual={
                    "access": revoked_session.has_access,
                    "staff_roles": [role.value for role in revoked_session.staff_roles],
                    "student_roles": [role.value for role in revoked_session.student_roles],
                },
                expected="access denied",
            )

        director_cross_tenant = "allowed"
        try:
            cross_session = await get_miniapp_session(
                db,
                max_user_id=account_ids["director"],
                tenant_slug=tenant_by_suffix["limited"].slug,
            )
            director_cross_tenant = {
                "has_access": cross_session.has_access,
                "tenant": cross_session.tenant_slug,
            }
            blocked = not cross_session.has_access
        except MiniAppStoreError as exc:
            director_cross_tenant = str(exc)
            blocked = exc.status_code in {403, 404}
        _check(
            checks,
            key="tenant_isolation.director",
            passed=blocked,
            actual=director_cross_tenant,
            expected="access denied",
        )

        default_products = int(
            await db.scalar(
                select(func.count())
                .select_from(Product)
                .join(Tenant, Tenant.id == Product.tenant_id)
                .where(
                    Tenant.slug == default_tenant_slug,
                    Product.sku.like(f"{_marker(run_id)}-%"),
                )
            )
            or 0
        )
        _check(
            checks,
            key="default_tenant.products",
            passed=default_products == 8,
            actual=default_products,
            expected=8,
        )

    failed = [item for item in checks if item["status"] == "fail"]
    return {
        "run_id": _marker(run_id),
        "status": "passed" if not failed else "failed",
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
        "checks": checks,
    }


def _signed_init_data(*, user_id: int, bot_token: str, auth_date: int) -> str:
    values = {
        "auth_date": str(auth_date),
        "query_id": f"qa-matrix-{user_id}",
        "user": json.dumps(
            {"id": user_id, "first_name": "QA", "last_name": "Matrix"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(values.items()))
    secret_key = hmac.new(
        b"WebAppData",
        bot_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    values["hash"] = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return parse.urlencode(values)


def build_auth_manifest(run_id: str) -> dict[str, Any]:
    settings = get_settings()
    if is_placeholder(settings.max_bot_token):
        raise RuntimeError("MAX_BOT_TOKEN is required to sign QA sessions")
    auth_date = int(time.time())
    tenants = {
        "full": f"{_run_slug(run_id)}-full",
        "limited": f"{_run_slug(run_id)}-limited",
        "empty": f"{_run_slug(run_id)}-empty",
    }
    role_tenant = {
        "superadmin": "full",
        "director": "full",
        "admin": "full",
        "curator": "full",
        "teacher_one": "full",
        "teacher_two": "full",
        "parent": "full",
        "student": "full",
        "direct_student": "full",
        "revoked_staff": "full",
        "limited_director": "limited",
        "limited_teacher": "limited",
        "empty_director": "empty",
        "revoked_parent": "full",
        "limited_parent": "limited",
    }
    roles = {}
    configured_superadmin_id = configured_superadmin_max_user_id()
    for key, offset, display_name in ACCOUNT_SPECS:
        user_id = (
            configured_superadmin_id
            if key == "superadmin" and configured_superadmin_id is not None
            else QA_MAX_ID_BASE + offset
        )
        roles[key] = {
            "max_user_id": user_id,
            "display_name": display_name,
            "tenant_slug": tenants[role_tenant[key]],
            "init_data": _signed_init_data(
                user_id=user_id,
                bot_token=str(settings.max_bot_token),
                auth_date=auth_date,
            ),
        }
    return {
        "run_id": _marker(run_id),
        "generated_at": datetime.fromtimestamp(auth_date, tz=UTC).isoformat(),
        "expires_after_seconds": settings.max_webapp_auth_max_age_seconds,
        "roles": roles,
    }


async def _delete_tenant_graph(db: AsyncSession, tenant_ids: list[UUID]) -> None:
    if not tenant_ids:
        return
    for model in (
        AuditLog,
        StaffNotificationPreference,
        AttendanceRecord,
        TeachingLessonOverride,
        FeedbackOutput,
        ManualFeedbackOutput,
        SchoolBroadcast,
        OrderStatusHistory,
        StockMovement,
        OrderItem,
        StudentCartItem,
        AstrocoinLedgerEntry,
        StudentHistoryEvent,
        ContactStudentLink,
        StaffWarehousePreference,
        WarehouseInventory,
    ):
        await db.execute(delete(model).where(model.tenant_id.in_(tenant_ids)))
    await db.execute(
        update(StudentAccessLink)
        .where(StudentAccessLink.tenant_id.in_(tenant_ids))
        .values(sponsor_access_link_id=None)
    )
    for model in (
        StudentAccessLink,
        StaffRoleAssignment,
        Order,
        Wallet,
        Contact,
        TeachingSchedule,
        CourseLesson,
        Course,
        Product,
        ProductCategory,
        Warehouse,
        Student,
        Venue,
    ):
        await db.execute(delete(model).where(model.tenant_id.in_(tenant_ids)))


async def cleanup_matrix(run_id: str, default_tenant_slug: str) -> dict[str, Any]:
    slug = _run_slug(run_id)
    marker = _marker(run_id)
    async with AsyncSessionLocal() as db:
        qa_tenants = (await db.scalars(select(Tenant).where(Tenant.slug.like(f"{slug}-%")))).all()
        tenant_ids = [tenant.id for tenant in qa_tenants]
        city_ids = [tenant.city_id for tenant in qa_tenants]
        partner_ids = [tenant.partner_id for tenant in qa_tenants]
        await _delete_tenant_graph(db, tenant_ids)
        if tenant_ids:
            await db.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
            await db.execute(delete(City).where(City.id.in_(city_ids)))
            await db.execute(delete(Partner).where(Partner.id.in_(partner_ids)))

        default_tenant = await db.scalar(
            select(Tenant).where(Tenant.slug == default_tenant_slug.strip().lower())
        )
        removed_default_products = 0
        if default_tenant is not None:
            product_ids = list(
                (
                    await db.scalars(
                        select(Product.id).where(
                            Product.tenant_id == default_tenant.id,
                            Product.sku.like(f"{marker}-%"),
                        )
                    )
                ).all()
            )
            warehouse_ids = list(
                (
                    await db.scalars(
                        select(Warehouse.id).where(
                            Warehouse.tenant_id == default_tenant.id,
                            Warehouse.slug.like(f"{slug}-%"),
                        )
                    )
                ).all()
            )
            removed_default_products = len(product_ids)
            if product_ids:
                await db.execute(
                    delete(StockMovement).where(
                        StockMovement.tenant_id == default_tenant.id,
                        StockMovement.product_id.in_(product_ids),
                    )
                )
                await db.execute(
                    delete(StudentCartItem).where(StudentCartItem.product_id.in_(product_ids))
                )
                await db.execute(
                    delete(WarehouseInventory).where(WarehouseInventory.product_id.in_(product_ids))
                )
                await db.execute(delete(Product).where(Product.id.in_(product_ids)))
            if warehouse_ids:
                await db.execute(delete(Warehouse).where(Warehouse.id.in_(warehouse_ids)))
            await db.execute(
                delete(ProductCategory).where(
                    ProductCategory.tenant_id == default_tenant.id,
                    ProductCategory.slug.like(f"{slug}-%"),
                )
            )

        qa_account_ids = list(
            (
                await db.scalars(
                    select(MaxAccount.id).where(MaxAccount.username.like(f"{marker}:%"))
                )
            ).all()
        )
        if qa_account_ids:
            await db.execute(delete(MaxAccount).where(MaxAccount.id.in_(qa_account_ids)))
        await db.commit()
        return {
            "run_id": marker,
            "removed_tenants": len(tenant_ids),
            "removed_accounts": len(qa_account_ids),
            "removed_default_products": removed_default_products,
        }


def _write_json(path: Path | None, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if path is None:
        print(text)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text + "\n", encoding="utf-8")
    print(str(path.resolve()))


def _assert_environment_allowed(*, allow_production: bool) -> None:
    settings = get_settings()
    if not is_local_environment(settings.app_env) and not allow_production:
        raise RuntimeError(
            "Production execution requires --allow-production. "
            "All generated records are marked with the QA run id."
        )


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Create and audit the Algo MAX QA matrix")
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("seed", "audit", "auth-manifest", "cleanup"):
        command = subparsers.add_parser(action)
        command.add_argument("--run-id", default=DEFAULT_RUN_ID)
        command.add_argument("--default-tenant-slug", default=settings.default_tenant_slug)
        command.add_argument("--output", type=Path)
        command.add_argument("--allow-production", action="store_true")
        if action == "cleanup":
            command.add_argument(
                "--confirm-cleanup",
                help=f"Must exactly match the run id, for example {DEFAULT_RUN_ID}",
            )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    try:
        _assert_environment_allowed(allow_production=args.allow_production)
        if args.action == "seed":
            result = asyncio.run(seed_matrix(args.run_id, args.default_tenant_slug))
        elif args.action == "audit":
            result = asyncio.run(audit_matrix(args.run_id, args.default_tenant_slug))
        elif args.action == "auth-manifest":
            result = build_auth_manifest(args.run_id)
        else:
            if args.confirm_cleanup != args.run_id:
                raise RuntimeError("cleanup requires --confirm-cleanup matching --run-id")
            result = asyncio.run(cleanup_matrix(args.run_id, args.default_tenant_slug))
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _write_json(args.output, result)
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
