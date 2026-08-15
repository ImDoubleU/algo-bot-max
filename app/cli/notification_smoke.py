from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from urllib import parse

from app.bot.keyboards import (
    build_miniapp_url,
    cabinet_keyboard,
    inline_keyboard_with_main_menu,
    miniapp_button,
    staff_approval_keyboard,
)
from app.bot.max_client import MaxApiClient, MaxApiError
from app.core.config import get_settings, is_placeholder
from app.models.enums import OrderStatus
from app.models.store import Order
from app.models.student import Student
from app.services.max_notifications import _order_message

DEFAULT_DELAY_SECONDS = 0.7


@dataclass(frozen=True)
class NotificationCase:
    key: str
    label: str
    text: str
    attachments: list[dict[str, object]]


def _miniapp_attachments(
    *,
    user_id: int,
    tenant_slug: str,
    view: str | None,
    button_label: str,
    product_id: str | None = None,
    image_url: str | None = None,
) -> list[dict[str, object]]:
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
    return attachments


def _default_image_url(miniapp_url: str | None) -> str | None:
    if not miniapp_url or is_placeholder(miniapp_url):
        return None
    parsed = parse.urlsplit(str(miniapp_url))
    if not parsed.scheme or not parsed.netloc:
        return None
    return parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            "/miniapp/static/assets/dashboard-learning.png",
            "",
            "",
        )
    )


def _order_case(
    *,
    key: str,
    label: str,
    status: OrderStatus,
    user_id: int,
    tenant_slug: str,
    cancellation_reason: str | None = None,
) -> NotificationCase:
    order = Order(
        order_number=99001,
        status=status,
        total_astrocoins=350,
        cancellation_reason=cancellation_reason,
    )
    student = Student(first_name="Алиса", last_name="Тестова")
    return NotificationCase(
        key=key,
        label=label,
        text=_order_message(
            order=order,
            student=student,
            balance_after=1250,
        ),
        attachments=_miniapp_attachments(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="orders",
            button_label="Открыть заказ",
        ),
    )


def build_cases(
    *,
    user_id: int,
    tenant_slug: str,
    image_url: str | None,
    product_id: str | None,
) -> list[NotificationCase]:
    cases = [
        NotificationCase(
            key="school_broadcast",
            label="Ручная рассылка",
            text=(
                "Тестовая новость школы.\n\n"
                "Проверяем текст, изображение и кнопку перехода в раздел рассылок."
            ),
            attachments=_miniapp_attachments(
                user_id=user_id,
                tenant_slug=tenant_slug,
                view="broadcasts",
                button_label="Открыть Algo MAX",
                image_url=image_url,
            ),
        ),
        NotificationCase(
            key="new_product",
            label="Новый товар",
            text=(
                "В магазине появился новый товар!\n\n"
                "Тестовый набор для творчества\n"
                "Цена: 350 астрокоинов"
            ),
            attachments=_miniapp_attachments(
                user_id=user_id,
                tenant_slug=tenant_slug,
                view="store",
                button_label="Посмотреть товар",
                product_id=product_id,
                image_url=image_url,
            ),
        ),
        NotificationCase(
            key="low_stock",
            label="Низкий остаток",
            text=(
                "Низкий остаток товара.\n\n"
                "Тестовый набор для творчества\n"
                "Склад: Главный склад\n"
                "Доступно: 2 шт."
            ),
            attachments=_miniapp_attachments(
                user_id=user_id,
                tenant_slug=tenant_slug,
                view="admin",
                button_label="Проверить остатки",
            ),
        ),
        _order_case(
            key="order_reserved",
            label="Заказ зарезервирован",
            status=OrderStatus.RESERVED,
            user_id=user_id,
            tenant_slug=tenant_slug,
        ),
        _order_case(
            key="order_transferred",
            label="Заказ передан учителю",
            status=OrderStatus.TRANSFERRED_TO_TEACHER,
            user_id=user_id,
            tenant_slug=tenant_slug,
        ),
        _order_case(
            key="order_issued",
            label="Заказ выдан",
            status=OrderStatus.ISSUED_TO_STUDENT,
            user_id=user_id,
            tenant_slug=tenant_slug,
        ),
        _order_case(
            key="order_cancelled",
            label="Заказ отменен",
            status=OrderStatus.CANCELLED,
            user_id=user_id,
            tenant_slug=tenant_slug,
            cancellation_reason="Товар закончился",
        ),
        _order_case(
            key="order_returned",
            label="Возврат заказа",
            status=OrderStatus.RETURNED,
            user_id=user_id,
            tenant_slug=tenant_slug,
        ),
        NotificationCase(
            key="staff_request",
            label="Новая заявка сотрудника",
            text=(
                "Новая заявка сотрудника\n\n"
                "MAX ID: 00000000\n"
                "Сотрудник: Тестовый пользователь\n"
                "Город: Тестовый город\n"
                "Организация: Тестовый партнер\n"
                "Роль: Преподаватель"
            ),
            attachments=staff_approval_keyboard("notification-smoke"),
        ),
        NotificationCase(
            key="staff_approved",
            label="Доступ сотрудника подтвержден",
            text=(
                "Доступ сотрудника подтвержден.\n\n"
                "Город: Тестовый город\n"
                "Роль: Преподаватель\n\n"
                "Рабочий кабинет доступен в главном меню."
            ),
            attachments=cabinet_keyboard(
                user_id=user_id,
                tenant_slug=tenant_slug,
                role="teacher",
            ),
        ),
        NotificationCase(
            key="staff_rejected",
            label="Заявка сотрудника отклонена",
            text=(
                "Заявка на доступ отклонена.\n\n"
                "Город: Тестовый город\n"
                "Роль: Преподаватель"
            ),
            attachments=inline_keyboard_with_main_menu([]),
        ),
    ]
    return cases


def _message_id(response: dict[str, object]) -> str | None:
    message = response.get("message")
    if not isinstance(message, dict):
        return None
    body = message.get("body")
    if isinstance(body, dict) and body.get("mid"):
        return str(body["mid"])
    for key in ("id", "message_id", "mid"):
        if message.get(key):
            return str(message[key])
    return None


def _message_summary(response: dict[str, object]) -> dict[str, object]:
    message = response.get("message")
    if not isinstance(message, dict):
        message = response
    body = message.get("body")
    if not isinstance(body, dict):
        body = {}
    text = str(body.get("text") or message.get("text") or "")
    attachments = body.get("attachments") or message.get("attachments") or []
    attachment_types = [
        str(attachment.get("type"))
        for attachment in attachments
        if isinstance(attachment, dict)
    ]
    return {
        "message_id": (
            body.get("mid")
            or message.get("id")
            or message.get("message_id")
            or message.get("mid")
        ),
        "first_line": text.splitlines()[0] if text else "",
        "attachment_types": attachment_types,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Отправить изолированный набор тестовых MAX-уведомлений",
    )
    parser.add_argument("--max-user-id", type=int, required=True)
    parser.add_argument("--tenant-slug")
    parser.add_argument("--image-url")
    parser.add_argument("--product-id")
    parser.add_argument(
        "--verify-message-id",
        action="append",
        help="Прочитать ранее отправленное сообщение; параметр можно повторять",
    )
    parser.add_argument(
        "--only",
        action="append",
        help="Ключ уведомления; параметр можно повторять",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Пауза между сообщениями в секундах",
    )
    parser.add_argument(
        "--confirm-send",
        action="store_true",
        help="Обязательное подтверждение реальной отправки",
    )
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    settings = get_settings()
    if is_placeholder(settings.max_bot_token):
        print("MAX_BOT_TOKEN не настроен.", file=sys.stderr)
        return 2
    if args.max_user_id <= 0:
        print("MAX user_id должен быть положительным.", file=sys.stderr)
        return 2
    if args.delay < 0.55:
        print("Пауза должна быть не меньше 0.55 секунды.", file=sys.stderr)
        return 2

    tenant_slug = (args.tenant_slug or settings.default_tenant_slug).strip().lower()
    client = MaxApiClient(
        str(settings.max_bot_token),
        settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )
    if args.verify_message_id:
        results: list[dict[str, object]] = []
        for message_id in args.verify_message_id:
            try:
                response = client._request(
                    "GET",
                    f"/messages/{parse.quote(message_id, safe='')}",
                )
            except MaxApiError as exc:
                results.append(
                    {
                        "message_id": message_id,
                        "status": "error",
                        "error": str(exc),
                    }
                )
            else:
                results.append(
                    {
                        "status": "found",
                        **_message_summary(response),
                    }
                )
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 1 if any(result["status"] == "error" for result in results) else 0

    image_url = args.image_url or _default_image_url(settings.max_miniapp_url)
    cases = build_cases(
        user_id=args.max_user_id,
        tenant_slug=tenant_slug,
        image_url=image_url,
        product_id=args.product_id,
    )
    if args.only:
        requested = set(args.only)
        known = {case.key for case in cases}
        unknown = sorted(requested - known)
        if unknown:
            print(f"Неизвестные типы: {', '.join(unknown)}", file=sys.stderr)
            return 2
        cases = [case for case in cases if case.key in requested]

    if not args.confirm_send:
        print(
            json.dumps(
                {
                    "target_max_user_id": args.max_user_id,
                    "tenant_slug": tenant_slug,
                    "image_url": image_url,
                    "cases": [
                        {"key": case.key, "label": case.label}
                        for case in cases
                    ],
                    "send": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    results: list[dict[str, object]] = []
    total = len(cases)
    for index, case in enumerate(cases, start=1):
        text = f"ТЕСТ {index}/{total} · {case.label}\n\n{case.text}"
        try:
            response = client.send_message(
                text=text,
                attachments=case.attachments,
                user_id=args.max_user_id,
            )
        except MaxApiError as exc:
            results.append(
                {
                    "key": case.key,
                    "label": case.label,
                    "status": "error",
                    "error": str(exc),
                }
            )
        else:
            results.append(
                {
                    "key": case.key,
                    "label": case.label,
                    "status": "sent",
                    "message_id": _message_id(response),
                }
            )
        if index < total:
            time.sleep(args.delay)

    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 1 if any(result["status"] == "error" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
