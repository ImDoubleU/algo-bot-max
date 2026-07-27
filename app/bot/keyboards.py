from __future__ import annotations

import os
from typing import Any
from urllib import parse

from app.core.miniapp_auth import issue_miniapp_token

CALLBACK_HELP = "help"
CALLBACK_MENU = "menu"
CALLBACK_MINIAPP = "miniapp:open"
CALLBACK_STATUS = "status"
CALLBACK_BALANCE = "balance"
CALLBACK_LEDGER = "ledger"
CALLBACK_STUDENTS = "students"
CALLBACK_GROUPS = "groups"
CALLBACK_LEADERBOARD = "leaderboard"
CALLBACK_CATALOG = "catalog"
CALLBACK_CATEGORIES = "categories"
CALLBACK_ORDERS = "orders"
CALLBACK_OPEN_ORDERS = "orders:open"
CALLBACK_OPS = "ops"
CALLBACK_STOCK = "stock"
CALLBACK_TODO = "todo"
CALLBACK_FEEDBACK = "feedback"
CALLBACK_FEEDBACK_PREFIX = "feedback"
CALLBACK_ROLE_PARENT = "role:parent"
CALLBACK_ROLE_STUDENT = "role:student"
CALLBACK_ORDER_ACTION_PREFIX = "order:action"
CALLBACK_ORDER_CONFIRM_PREFIX = "order:confirm"


def callback_button(text: str, payload: str) -> dict[str, str]:
    return {
        "type": "callback",
        "text": text,
        "payload": payload,
    }


def link_button(text: str, url: str) -> dict[str, str]:
    return {
        "type": "link",
        "text": text,
        "url": url,
    }


def inline_keyboard(rows: list[list[dict[str, str]]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": rows,
            },
        }
    ]


def inline_keyboard_with_main_menu(
    rows: list[list[dict[str, str]]],
) -> list[dict[str, Any]]:
    has_main_menu = any(
        button.get("type") == "callback" and button.get("payload") == CALLBACK_MENU
        for row in rows
        for button in row
    )
    navigation_rows = list(rows)
    if not has_main_menu:
        navigation_rows.append([callback_button("Главное меню", CALLBACK_MENU)])
    return inline_keyboard(navigation_rows)


def order_action_payload(action: str, order_ref: str | int) -> str:
    encoded_ref = parse.quote(str(order_ref), safe="")
    return f"{CALLBACK_ORDER_ACTION_PREFIX}:{action}:{encoded_ref}"


def order_confirm_payload(action: str, order_ref: str | int) -> str:
    encoded_ref = parse.quote(str(order_ref), safe="")
    return f"{CALLBACK_ORDER_CONFIRM_PREFIX}:{action}:{encoded_ref}"


def parse_order_action_payload(payload: str) -> tuple[str, str] | None:
    prefix = f"{CALLBACK_ORDER_ACTION_PREFIX}:"
    if not payload.startswith(prefix):
        return None
    rest = payload[len(prefix) :]
    action, separator, encoded_ref = rest.partition(":")
    if not separator or not action or not encoded_ref:
        return None
    return action, parse.unquote(encoded_ref)


def parse_order_confirm_payload(payload: str) -> tuple[str, str] | None:
    prefix = f"{CALLBACK_ORDER_CONFIRM_PREFIX}:"
    if not payload.startswith(prefix):
        return None
    rest = payload[len(prefix) :]
    action, separator, encoded_ref = rest.partition(":")
    if not separator or not action or not encoded_ref:
        return None
    return action, parse.unquote(encoded_ref)


def feedback_payload(action: str, value: str | int | None = None) -> str:
    if value is None:
        return f"{CALLBACK_FEEDBACK_PREFIX}:{action}"
    return f"{CALLBACK_FEEDBACK_PREFIX}:{action}:{parse.quote(str(value), safe='')}"


def parse_feedback_payload(payload: str) -> tuple[str, str | None] | None:
    prefix = f"{CALLBACK_FEEDBACK_PREFIX}:"
    if not payload.startswith(prefix):
        return None
    action, separator, encoded_value = payload[len(prefix) :].partition(":")
    if not action:
        return None
    return action, parse.unquote(encoded_value) if separator and encoded_value else None


def _button_label(text: str, *, limit: int = 54) -> str:
    normalized = " ".join(str(text).split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1]}…"


def build_miniapp_url(
    user_id: int | None = None,
    tenant_slug: str | None = None,
    view: str | None = None,
) -> str:
    miniapp_url = os.getenv("MAX_MINIAPP_URL", "").strip()
    if not miniapp_url:
        return ""

    parts = parse.urlsplit(miniapp_url)
    query = dict(parse.parse_qsl(parts.query, keep_blank_values=True))
    if user_id is not None:
        query["max_user_id"] = str(user_id)
    if tenant_slug:
        query["tenant_slug"] = tenant_slug
    if user_id is not None and tenant_slug:
        query["miniapp_token"] = issue_miniapp_token(
            max_user_id=user_id,
            tenant_slug=tenant_slug,
        )
    if view:
        query["view"] = view

    return parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            parse.urlencode(query),
            parts.fragment,
        )
    )


def main_menu_keyboard(
    user_id: int | None = None,
    tenant_slug: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    if role:
        return role_menu_keyboard(
            role,
            user_id=user_id,
            tenant_slug=tenant_slug,
            compact=False,
        )
    rows: list[list[dict[str, str]]] = []
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    if miniapp_url:
        rows.append([link_button("Открыть личный кабинет", miniapp_url)])
    else:
        rows.append([callback_button("Личный кабинет", CALLBACK_MINIAPP)])
    rows.append([callback_button("Помощь", CALLBACK_HELP)])
    return inline_keyboard(rows)


def role_selection_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard_with_main_menu(
        [
            [
                callback_button("Я родитель", CALLBACK_ROLE_PARENT),
                callback_button("Я ученик", CALLBACK_ROLE_STUDENT),
            ],
            [callback_button("Помощь", CALLBACK_HELP)],
        ]
    )


def cabinet_keyboard(
    user_id: int | None = None,
    tenant_slug: str | None = None,
    role: str | None = None,
) -> list[dict[str, Any]]:
    return main_menu_keyboard(
        user_id=user_id,
        tenant_slug=tenant_slug,
        role=role,
    )


def role_menu_keyboard(
    role: str,
    *,
    user_id: int | None,
    tenant_slug: str | None,
    compact: bool,
) -> list[dict[str, Any]]:
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    normalized = role.casefold()
    rows: list[list[dict[str, str]]] = []
    cabinet_label = {
        "student": "Открыть личный кабинет",
        "parent": "Открыть семейный кабинет",
        "teacher": "Открыть рабочий кабинет",
        "curator": "Открыть кабинет куратора",
        "admin": "Открыть рабочий кабинет",
        "partner_director": "Открыть кабинет директора",
        "superadmin": "Открыть кабинет суперадминистратора",
    }.get(normalized, "Открыть кабинет")
    if miniapp_url:
        rows.append([link_button(cabinet_label, miniapp_url)])
    else:
        rows.append([callback_button(cabinet_label, CALLBACK_MINIAPP)])
    if normalized in {
        "teacher",
        "curator",
        "admin",
        "partner_director",
        "superadmin",
    }:
        rows.append([callback_button("Обратная связь", CALLBACK_FEEDBACK)])
    rows.append([callback_button("Помощь", CALLBACK_HELP)])
    return inline_keyboard(rows)


def feedback_menu_keyboard(
    schedules: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    for schedule in schedules[:16]:
        label = (
            f"{schedule.get('group_name') or 'Группа'} · "
            f"урок {schedule.get('current_lesson_number') or 1}"
        )
        rows.append(
            [
                callback_button(
                    _button_label(label),
                    feedback_payload("schedule", str(schedule.get("id") or "")),
                )
            ]
        )
    unsent_outputs = [
        output for output in outputs if str(output.get("status") or "") != "sent_to_parents"
    ]
    if unsent_outputs:
        rows.append([callback_button("Готовые черновики", feedback_payload("drafts"))])
    rows.append([callback_button("Главное меню", CALLBACK_MENU)])
    return inline_keyboard(rows)


def feedback_drafts_keyboard(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    for output in outputs[:12]:
        label = (
            f"{output.get('group_name') or 'Группа'} · "
            f"{output.get('lesson_date') or 'без даты'}"
        )
        rows.append(
            [
                callback_button(
                    _button_label(label),
                    feedback_payload("output", str(output.get("id") or "")),
                )
            ]
        )
    rows.extend(
        [
            [callback_button("К группам", CALLBACK_FEEDBACK)],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_setup_keyboard(
    students: list[dict[str, Any]],
    *,
    absent_student_ids: set[str],
    is_repetition: bool,
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    for student in students[:24]:
        student_id = str(student.get("student_id") or "")
        selected = student_id in absent_student_ids
        prefix = "Отсутствовал" if selected else "Был на уроке"
        rows.append(
            [
                callback_button(
                    _button_label(f"{prefix} · {student.get('display_name') or 'Ученик'}"),
                    feedback_payload("absent", student_id),
                )
            ]
        )
    rows.extend(
        [
            [
                callback_button(
                    f"Повторение: {'да' if is_repetition else 'нет'}",
                    feedback_payload("repeat"),
                )
            ],
            [callback_button("Сформировать ОС", feedback_payload("generate"))],
            [callback_button("К группам", CALLBACK_FEEDBACK)],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_preview_keyboard(
    *,
    output_id: str,
    schedule_id: str,
    can_send: bool,
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    if can_send:
        rows.append(
            [callback_button("Отправить родителям", feedback_payload("send", output_id))]
        )
    rows.extend(
        [
            [callback_button("Настроить заново", feedback_payload("schedule", schedule_id))],
            [callback_button("К группам", CALLBACK_FEEDBACK)],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def order_actions_keyboard(
    order_ref: str | int,
    *,
    status: str,
    user_id: int | None = None,
    tenant_slug: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = [
        [callback_button("Повторить", order_action_payload("repeat", order_ref))]
    ]
    if status in {"created", "reserved", "transferred_to_teacher", "problem"}:
        rows.append(
            [
                callback_button("Выдать", order_action_payload("issue", order_ref)),
                callback_button("Отменить", order_action_payload("cancel", order_ref)),
            ]
        )
    elif status == "issued_to_student":
        rows.append([callback_button("Возврат", order_action_payload("return", order_ref))])

    rows.extend(
        [
            [
                callback_button("Открытые", CALLBACK_OPEN_ORDERS),
                callback_button("Заказы", CALLBACK_ORDERS),
            ],
            [callback_button("В меню", CALLBACK_MENU)],
        ]
    )
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    if miniapp_url:
        rows.insert(0, [link_button("Открыть mini app", miniapp_url)])
    return inline_keyboard(rows)


def order_confirmation_keyboard(action: str, order_ref: str | int) -> list[dict[str, Any]]:
    return inline_keyboard(
        [
            [callback_button("Подтвердить", order_confirm_payload(action, order_ref))],
            [
                callback_button("Открытые", CALLBACK_OPEN_ORDERS),
                callback_button("Заказы", CALLBACK_ORDERS),
            ],
            [callback_button("В меню", CALLBACK_MENU)],
        ]
    )
