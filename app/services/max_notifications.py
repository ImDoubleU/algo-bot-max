from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import (
    build_miniapp_url,
    inline_keyboard_with_main_menu,
    miniapp_button,
)
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.enums import (
    AssignmentStatus,
    OrderStatus,
    StaffRole,
    StudentAccessStatus,
)
from app.models.store import Order, Product, WarehouseInventory
from app.models.student import Student, StudentAccessLink
from app.models.tenant import Tenant
from app.services.staff import staff_names_match
from app.services.staff_notifications import staff_notification_user_ids
from app.services.student_access_policy import student_access_window

logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task[None]] = set()


def _order_status_text(status: OrderStatus) -> str:
    return {
        OrderStatus.RESERVED: "Зарезервирован",
        OrderStatus.AWAITING_DELIVERY: "Ожидает доставки",
        OrderStatus.DELIVERED_TO_VENUE: "Доставлен на площадку",
        OrderStatus.TRANSFERRED_TO_TEACHER: "Учитель получил заказ",
        OrderStatus.CANCELLED: "Заказ отменен",
        OrderStatus.ISSUED_TO_STUDENT: "Заказ передан ученику",
        OrderStatus.RETURNED: "Возврат оформлен",
    }.get(status, status.value)


def _notification_text(
    title: str,
    *,
    facts: list[tuple[str, str]],
    message: str | None = None,
) -> str:
    lines = [title]
    if message:
        lines.extend(["", message])
    if facts:
        lines.append("")
        lines.extend(f"{label}: {value}" for label, value in facts if value)
    return "\n".join(lines)


def _order_message(
    *,
    order: Order,
    student: Student,
    balance_after: int | None,
    issued_codes: list[str] | None = None,
) -> str:
    is_digital_delivery = order.status == OrderStatus.ISSUED_TO_STUDENT and bool(issued_codes)
    title = (
        f"Заказ №{order.order_number}: цифровой товар готов"
        if is_digital_delivery
        else f"Заказ №{order.order_number}: {_order_status_text(order.status)}"
    )
    message = None
    if order.status == OrderStatus.CANCELLED:
        message = "Заказ отменен, астрокоины возвращены на баланс."
    if order.status == OrderStatus.AWAITING_DELIVERY:
        message = "Склад выбран. Заказ собирают и доставят на площадку."
    if order.status == OrderStatus.DELIVERED_TO_VENUE:
        message = "Заказ уже на площадке. Следующий этап — передача преподавателю."
    if order.status == OrderStatus.TRANSFERRED_TO_TEACHER:
        message = "Преподаватель получил заказ. Его можно забрать на занятии."
    if is_digital_delivery:
        message = (
            "Код находится в приложении. Откройте раздел «Заказы», выберите "
            "«Получены» и нажмите на заказ."
        )
    facts = [
        ("Ученик", student.display_name),
        ("Сумма", f"{order.total_astrocoins} AC"),
    ]
    if order.status == OrderStatus.CANCELLED and order.cancellation_reason:
        facts.append(("Причина", order.cancellation_reason))
    if balance_after is not None:
        facts.append(("Баланс", f"{balance_after} AC"))
    return _notification_text(title, facts=facts, message=message)


async def _recipient_user_ids(
    db: AsyncSession,
    *,
    tenant: Tenant,
    student: Student,
) -> set[int]:
    if not student_access_window(student, tenant).allowed:
        return set()
    account_ids = set(
        (
            await db.scalars(
                select(StudentAccessLink.account_id).where(
                    StudentAccessLink.tenant_id == tenant.id,
                    StudentAccessLink.student_id == student.id,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
            )
        ).all()
    )
    if not account_ids:
        return set()
    return set(
        (
            await db.scalars(select(MaxAccount.max_user_id).where(MaxAccount.id.in_(account_ids)))
        ).all()
    )


async def _deliver_order_notification(
    *,
    user_ids: set[int],
    tenant_slug: str,
    text: str,
    button_label: str,
) -> None:
    settings = get_settings()
    client = MaxApiClient(
        settings.max_bot_token or "",
        settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )

    async def send(user_id: int) -> None:
        miniapp_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="orders",
        )
        rows = [[miniapp_button(button_label, miniapp_url)]] if miniapp_url else []
        attachments = inline_keyboard_with_main_menu(rows)
        await asyncio.to_thread(
            client.send_message,
            text=text,
            attachments=attachments,
            user_id=user_id,
        )

    results = await asyncio.gather(*(send(user_id) for user_id in user_ids), return_exceptions=True)
    for user_id, result in zip(user_ids, results, strict=True):
        if isinstance(result, Exception):
            logger.warning(
                "Не удалось отправить MAX-уведомление пользователю %s: %s",
                user_id,
                result,
            )


async def _tenant_customer_user_ids(db: AsyncSession, *, tenant_id: UUID) -> set[int]:
    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        return set()
    rows = (
        await db.execute(
            select(MaxAccount.max_user_id, Student)
            .join(StudentAccessLink, StudentAccessLink.account_id == MaxAccount.id)
            .join(Student, Student.id == StudentAccessLink.student_id)
            .where(
                StudentAccessLink.tenant_id == tenant_id,
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                Student.tenant_id == tenant_id,
            )
        )
    ).all()
    return {
        max_user_id
        for max_user_id, student in rows
        if student_access_window(student, tenant).allowed
    }


def _schedule_direct_notification(
    *,
    user_ids: set[int],
    tenant_slug: str,
    text: str,
    view: str,
    button_label: str,
    product_id: str | None = None,
    image_url: str | None = None,
) -> None:
    if not user_ids:
        return

    async def deliver() -> None:
        settings = get_settings()
        client = MaxApiClient(
            settings.max_bot_token or "",
            settings.max_api_base,
            timeout_seconds=settings.max_api_timeout_seconds,
            poll_timeout_seconds=settings.max_poll_timeout_seconds,
        )

        async def send(user_id: int) -> None:
            miniapp_url = build_miniapp_url(
                user_id=user_id,
                tenant_slug=tenant_slug,
                view=view,
                product_id=product_id,
            )
            rows = [[miniapp_button(button_label, miniapp_url)]] if miniapp_url else []
            attachments = inline_keyboard_with_main_menu(rows)
            if image_url:
                attachments.insert(0, {"type": "image", "payload": {"url": image_url}})
            await asyncio.to_thread(
                client.send_message,
                text=text,
                attachments=attachments,
                user_id=user_id,
            )

        results = await asyncio.gather(
            *(send(user_id) for user_id in user_ids),
            return_exceptions=True,
        )
        for user_id, result in zip(user_ids, results, strict=True):
            if isinstance(result, Exception):
                logger.warning(
                    "Не удалось отправить уведомление пользователю %s: %s",
                    user_id,
                    result,
                )

    task = asyncio.create_task(deliver())
    _background_tasks.add(task)
    task.add_done_callback(_log_notification_task_error)


async def schedule_staff_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    event_key: str,
    title: str,
    message: str | None = None,
    facts: list[tuple[str, str]] | None = None,
    view: str = "dashboard",
    button_label: str = "Открыть Algo MAX",
) -> None:
    settings = get_settings()
    if not settings.max_order_notifications_enabled or is_placeholder(settings.max_bot_token):
        return

    try:
        user_ids = await staff_notification_user_ids(
            db,
            tenant_id=UUID(str(tenant.id)),
            event_key=event_key,
        )
    except Exception as exc:
        logger.warning(
            "Не удалось определить сотрудников для уведомления %s: %s",
            event_key,
            exc,
        )
        return

    _schedule_direct_notification(
        user_ids=user_ids,
        tenant_slug=tenant.slug,
        text=_notification_text(title, message=message, facts=facts or []),
        view=view,
        button_label=button_label,
    )


async def schedule_staff_order_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    order: Order,
    student: Student,
    event_key: str,
    title: str,
    actor_name: str | None = None,
    message: str | None = None,
    extra_facts: list[tuple[str, str]] | None = None,
) -> None:
    facts = [
        ("Заказ", f"№{order.order_number}"),
        ("Ученик", student.display_name),
        ("Сумма", f"{order.total_astrocoins} AC"),
    ]
    if actor_name:
        facts.append(("Изменил", actor_name))
    if extra_facts:
        facts.extend(extra_facts)
    await schedule_staff_notification(
        db,
        tenant=tenant,
        event_key=event_key,
        title=title,
        message=message,
        facts=facts,
        view="orders",
        button_label="Открыть заказы",
    )


async def schedule_teacher_order_transfer_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    order: Order,
    student: Student,
) -> None:
    settings = get_settings()
    teacher_name = (order.teacher_name or student.teacher_name or "").strip()
    if (
        not teacher_name
        or not settings.max_order_notifications_enabled
        or is_placeholder(settings.max_bot_token)
    ):
        return

    teacher_accounts = (
        await db.scalars(
            select(MaxAccount)
            .join(StaffRoleAssignment, StaffRoleAssignment.account_id == MaxAccount.id)
            .where(
                StaffRoleAssignment.tenant_id == tenant.id,
                StaffRoleAssignment.role == StaffRole.TEACHER,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
    ).unique().all()
    user_ids = {
        account.max_user_id
        for account in teacher_accounts
        if staff_names_match(account.display_name, teacher_name)
    }
    if not user_ids:
        return

    product_totals: dict[str, int] = {}
    warehouse_totals: dict[str, dict[str, int]] = {}
    for item in order.items:
        product_name = item.product.name if item.product else "Товар"
        warehouse_name = item.warehouse.name if item.warehouse else "Склад не указан"
        product_totals[product_name] = product_totals.get(product_name, 0) + item.quantity
        warehouse_products = warehouse_totals.setdefault(warehouse_name, {})
        warehouse_products[product_name] = warehouse_products.get(product_name, 0) + item.quantity

    products_text = "; ".join(
        f"{name} — {quantity} шт." for name, quantity in sorted(product_totals.items())
    )
    pickup_text = "; ".join(
        f"{warehouse}: "
        + ", ".join(
            f"{name} — {quantity} шт."
            for name, quantity in sorted(products.items())
        )
        for warehouse, products in sorted(warehouse_totals.items())
    )
    facts = [
        ("Ученик", student.display_name),
        ("Площадка", order.venue_name or student.venue_name or "Не указана"),
        ("Состав", products_text or "Нет позиций"),
        ("Забрать", pickup_text or "Склад не указан"),
    ]
    _schedule_direct_notification(
        user_ids=user_ids,
        tenant_slug=tenant.slug,
        text=_notification_text(
            f"Вам передан заказ №{order.order_number}",
            message="Проверьте комплект и выдайте его ученику.",
            facts=facts,
        ),
        view="orders",
        button_label="Открыть заказы",
    )


async def schedule_new_product_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    product: Product,
) -> None:
    settings = get_settings()
    if not settings.max_order_notifications_enabled or is_placeholder(settings.max_bot_token):
        return
    user_ids = await _tenant_customer_user_ids(db, tenant_id=UUID(str(tenant.id)))
    text = _notification_text(
        "Новый товар в магазине",
        message=product.name,
        facts=[("Цена", f"{product.price_astrocoins} AC")],
    )
    _schedule_direct_notification(
        user_ids=user_ids,
        tenant_slug=tenant.slug,
        text=text,
        view="store",
        button_label="Посмотреть товар",
        product_id=str(product.id),
        image_url=product.photo_url,
    )


async def schedule_low_stock_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    product: Product,
    inventory: WarehouseInventory,
) -> None:
    settings = get_settings()
    if not settings.max_order_notifications_enabled or is_placeholder(settings.max_bot_token):
        return
    user_ids = await staff_notification_user_ids(
        db,
        tenant_id=UUID(str(tenant.id)),
        event_key="inventory.low_stock",
    )
    warehouse_name = inventory.warehouse.name if inventory.warehouse else "Склад"
    free_quantity = max(inventory.available_quantity - inventory.reserved_quantity, 0)
    _schedule_direct_notification(
        user_ids=user_ids,
        tenant_slug=tenant.slug,
        text=_notification_text(
            "Заканчивается товар",
            message=product.name,
            facts=[
                ("Склад", warehouse_name),
                ("Доступно", f"{free_quantity} шт."),
            ],
        ),
        view="admin",
        button_label="Товары и остатки",
        product_id=str(product.id),
    )


async def schedule_low_digital_codes_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    product: Product,
    available_codes: int,
) -> None:
    await schedule_staff_notification(
        db,
        tenant=tenant,
        event_key="inventory.digital_codes_low",
        title="Заканчиваются коды для автовыдачи",
        message=product.name,
        facts=[
            ("Осталось кодов", str(max(available_codes, 0))),
        ],
        view="admin",
        button_label="Добавить коды",
    )


async def schedule_order_notification(
    db: AsyncSession,
    *,
    tenant: Tenant,
    order: Order,
    student: Student,
    balance_after: int | None = None,
    issued_codes: list[str] | None = None,
) -> None:
    settings = get_settings()
    if not settings.max_order_notifications_enabled or is_placeholder(settings.max_bot_token):
        return

    try:
        user_ids = await _recipient_user_ids(
            db,
            tenant=tenant,
            student=student,
        )
    except Exception as exc:
        logger.warning("Не удалось определить получателей MAX-уведомления: %s", exc)
        return
    if not user_ids:
        return

    task = asyncio.create_task(
        _deliver_order_notification(
            user_ids=user_ids,
            tenant_slug=tenant.slug,
            text=_order_message(
                order=order,
                student=student,
                balance_after=balance_after,
                issued_codes=issued_codes,
            ),
            button_label=(
                "Открыть приложение"
                if order.status == OrderStatus.ISSUED_TO_STUDENT and issued_codes
                else "Открыть заказ"
            ),
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_log_notification_task_error)


def _log_notification_task_error(task: asyncio.Task[None]) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning("Ошибка фоновой отправки MAX-уведомления: %s", error)
