from __future__ import annotations

import os
from typing import Any
from urllib import parse

from app.core.config import get_settings, is_placeholder
from app.services.knowledge_base import clean_knowledge_label

CALLBACK_HELP = "help"
CALLBACK_MENU = "menu"
CALLBACK_MINIAPP = "miniapp:open"
CALLBACK_KNOWLEDGE = "knowledge"
CALLBACK_KNOWLEDGE_PREFIX = "knowledge"
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
CALLBACK_STAFF_JOIN_PREFIX = "staff_join"
CALLBACK_ROLE_PARENT = "role:parent"
CALLBACK_ROLE_STUDENT = "role:student"
CALLBACK_ONBOARDING_RESTART = "onboarding:restart"
CALLBACK_ONBOARDING_CANCEL = "onboarding:cancel"
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


def open_app_button(text: str, web_app: str) -> dict[str, str]:
    return {
        "type": "open_app",
        "text": text,
        "web_app": web_app,
    }


def miniapp_button(text: str, url: str) -> dict[str, str]:
    configured_username = os.getenv("MAX_BOT_USERNAME", "").strip()
    if not configured_username:
        configured_username = (get_settings().max_bot_username or "").strip()
    bot_username = configured_username.removeprefix("@")
    if bot_username:
        return open_app_button(text, bot_username)
    return link_button(text, url)


def inline_keyboard(rows: list[list[dict[str, str]]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": rows,
            },
        }
    ]


def without_open_app_buttons(
    attachments: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if not attachments:
        return attachments

    filtered_attachments: list[dict[str, Any]] = []
    changed = False
    for attachment in attachments:
        if attachment.get("type") != "inline_keyboard":
            filtered_attachments.append(attachment)
            continue

        payload = attachment.get("payload") or {}
        rows = payload.get("buttons") or []
        filtered_rows = []
        for row in rows:
            filtered_row = [button for button in row if button.get("type") != "open_app"]
            changed = changed or len(filtered_row) != len(row)
            if filtered_row:
                filtered_rows.append(filtered_row)

        if filtered_rows:
            filtered_attachments.append(
                {
                    **attachment,
                    "payload": {
                        **payload,
                        "buttons": filtered_rows,
                    },
                }
            )

    return filtered_attachments if changed else attachments


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


def staff_join_payload(action: str, value: str | None = None) -> str:
    if value is None:
        return f"{CALLBACK_STAFF_JOIN_PREFIX}:{action}"
    return f"{CALLBACK_STAFF_JOIN_PREFIX}:{action}:{parse.quote(value, safe='')}"


def parse_staff_join_payload(payload: str) -> tuple[str, str | None] | None:
    prefix = f"{CALLBACK_STAFF_JOIN_PREFIX}:"
    if not payload.startswith(prefix):
        return None
    action, separator, encoded_value = payload[len(prefix) :].partition(":")
    if not action:
        return None
    return action, parse.unquote(encoded_value) if separator and encoded_value else None


def knowledge_payload(section_id: str) -> str:
    return f"{CALLBACK_KNOWLEDGE_PREFIX}:{parse.quote(section_id, safe='')}"


def parse_knowledge_payload(payload: str) -> str | None:
    prefix = f"{CALLBACK_KNOWLEDGE_PREFIX}:"
    if not payload.startswith(prefix):
        return None
    section_id = parse.unquote(payload[len(prefix) :]).strip()
    return section_id or None


def _button_label(text: str, *, limit: int = 54) -> str:
    normalized = " ".join(str(text).split())
    return normalized if len(normalized) <= limit else f"{normalized[: limit - 1]}…"


def build_miniapp_url(
    user_id: int | None = None,
    tenant_slug: str | None = None,
    view: str | None = None,
    product_id: str | None = None,
) -> str:
    # Keep the configured site URL exact for the external-link fallback.
    # User and tenant context come from signed WebApp init data after launch.
    _ = user_id, tenant_slug
    configured_url = os.getenv("MAX_MINIAPP_URL", "").strip()
    settings_url = get_settings().max_miniapp_url
    base_url = configured_url or (
        "" if is_placeholder(settings_url) else str(settings_url).strip()
    )
    return base_url


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
        rows.append([miniapp_button("Открыть личный кабинет", miniapp_url)])
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
            [callback_button("Отменить вход", CALLBACK_ONBOARDING_CANCEL)],
        ]
    )


def onboarding_contact_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard_with_main_menu(
        [
            [callback_button("Изменить роль", CALLBACK_ONBOARDING_RESTART)],
            [callback_button("Отменить вход", CALLBACK_ONBOARDING_CANCEL)],
        ]
    )


def onboarding_cancelled_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard_with_main_menu(
        [
            [callback_button("Начать вход", CALLBACK_ONBOARDING_RESTART)],
            [callback_button("Помощь", CALLBACK_HELP)],
        ]
    )


STAFF_ROLE_LABELS = {
    "partner_director": "Директор",
    "admin": "Администратор",
    "curator": "Куратор",
    "teacher": "Преподаватель",
}


def staff_role_label(role: str) -> str:
    return STAFF_ROLE_LABELS.get(role, role)


def staff_tenant_keyboard(
    tenants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    city_counts: dict[str, int] = {}
    for tenant in tenants:
        city_name = str(tenant.get("city_name") or tenant.get("tenant_name") or "Город")
        city_counts[city_name] = city_counts.get(city_name, 0) + 1

    rows: list[list[dict[str, str]]] = []
    for tenant in tenants:
        tenant_slug = str(tenant.get("tenant_slug") or "").strip()
        if not tenant_slug:
            continue
        city_name = str(tenant.get("city_name") or tenant.get("tenant_name") or "Город")
        tenant_name = str(tenant.get("tenant_name") or city_name)
        label = (
            city_name
            if city_counts.get(city_name, 0) == 1
            else f"{city_name} · {tenant_name}"
        )
        rows.append(
            [
                callback_button(
                    _button_label(label),
                    staff_join_payload("tenant", tenant_slug),
                )
            ]
        )
    rows.append([callback_button("Отменить регистрацию", staff_join_payload("cancel"))])
    return inline_keyboard_with_main_menu(rows)


def staff_role_keyboard(roles: list[str]) -> list[dict[str, Any]]:
    rows = [
        [callback_button(staff_role_label(role), staff_join_payload("role", role))]
        for role in roles
        if role in STAFF_ROLE_LABELS
    ]
    rows.extend(
        [
            [callback_button("Назад к городам", staff_join_payload("cities"))],
            [callback_button("Отменить регистрацию", staff_join_payload("cancel"))],
        ]
    )
    return inline_keyboard_with_main_menu(rows)


def staff_approval_keyboard(request_id: str) -> list[dict[str, Any]]:
    return inline_keyboard_with_main_menu(
        [
            [
                callback_button(
                    "Подтвердить",
                    staff_join_payload("approve", request_id),
                ),
                callback_button(
                    "Отклонить",
                    staff_join_payload("reject", request_id),
                ),
            ]
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
        rows.append([miniapp_button(cabinet_label, miniapp_url)])
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
        rows.append([callback_button("База знаний", CALLBACK_KNOWLEDGE)])
    rows.append([callback_button("Помощь", CALLBACK_HELP)])
    return inline_keyboard(rows)


def knowledge_menu_keyboard(
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        [
            callback_button(
                _button_label(clean_knowledge_label(str(section.get("title") or "Раздел"))),
                knowledge_payload(str(section.get("id") or "")),
            )
        ]
        for section in sections
        if str(section.get("id") or "").strip()
    ]
    rows.append([callback_button("Главное меню", CALLBACK_MENU)])
    return inline_keyboard(rows)


def knowledge_section_keyboard(
    section: dict[str, Any],
    *,
    section_ids: set[str],
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    for item in section.get("buttons") or []:
        if not isinstance(item, dict):
            continue
        label = _button_label(
            clean_knowledge_label(str(item.get("text") or "Открыть"))
        )
        url = str(item.get("url") or "").strip()
        callback = str(item.get("callback") or "").strip()
        if url:
            rows.append([link_button(label, url)])
        elif callback in section_ids:
            rows.append([callback_button(label, knowledge_payload(callback))])
    rows.extend(
        [
            [callback_button("К разделам", CALLBACK_KNOWLEDGE)],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_menu_keyboard(outputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = [
        [callback_button("Создать ОС вручную", feedback_payload("manual"))]
    ]
    unsent_outputs = [
        output for output in outputs if str(output.get("status") or "") != "sent_to_parents"
    ]
    if unsent_outputs:
        rows.append(
            [
                callback_button(
                    f"Черновики · {len(unsent_outputs)}",
                    feedback_payload("drafts"),
                )
            ]
        )
    rows.append([callback_button("Главное меню", CALLBACK_MENU)])
    return inline_keyboard(rows)


def _feedback_page_rows(
    items: list[dict[str, Any]],
    *,
    page: int,
    action: str,
    page_action: str,
    label_builder: Any,
    page_size: int = 8,
) -> list[list[dict[str, str]]]:
    safe_page = max(page, 0)
    start = safe_page * page_size
    visible = items[start : start + page_size]
    rows = [
        [
            callback_button(
                _button_label(label_builder(item)),
                feedback_payload(action, start + index),
            )
        ]
        for index, item in enumerate(visible)
    ]
    navigation: list[dict[str, str]] = []
    if safe_page > 0:
        navigation.append(
            callback_button("Назад", feedback_payload(page_action, safe_page - 1))
        )
    if start + page_size < len(items):
        navigation.append(
            callback_button("Далее", feedback_payload(page_action, safe_page + 1))
        )
    if navigation:
        rows.append(navigation)
    return rows


def feedback_groups_keyboard(
    groups: list[dict[str, Any]],
    *,
    page: int,
) -> list[dict[str, Any]]:
    rows = _feedback_page_rows(
        groups,
        page=page,
        action="group",
        page_action="groups",
        label_builder=lambda item: (
            f"{item.get('name') or 'Группа'} · {item.get('student_count') or 0} уч."
        ),
    )
    rows.extend(
        [
            [callback_button("К разделу ОС", CALLBACK_FEEDBACK)],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_courses_keyboard(
    courses: list[dict[str, Any]],
    *,
    page: int,
) -> list[dict[str, Any]]:
    rows = _feedback_page_rows(
        courses,
        page=page,
        action="course",
        page_action="courses",
        label_builder=lambda item: (
            f"{item.get('name') or 'Курс'} · {item.get('lesson_count') or 0} ур."
        ),
    )
    rows.extend(
        [
            [callback_button("К группам", feedback_payload("groups", 0))],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_lessons_keyboard(
    lessons: list[dict[str, Any]],
    *,
    page: int,
) -> list[dict[str, Any]]:
    rows = _feedback_page_rows(
        lessons,
        page=page,
        action="lesson",
        page_action="lessons",
        label_builder=lambda item: (
            f"Урок {item.get('lesson_number') or 1} · {item.get('title') or 'Без названия'}"
        ),
    )
    rows.extend(
        [
            [callback_button("К курсам", feedback_payload("courses", 0))],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
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
                    feedback_payload("manual_output", str(output.get("id") or "")),
                )
            ]
        )
    rows.extend(
        [
            [callback_button("К разделу ОС", CALLBACK_FEEDBACK)],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_setup_keyboard(
    students: list[dict[str, Any]],
    *,
    absent_student_ids: set[str],
    is_repetition: bool,
    lesson_mode_label: str,
    attendance_page: int,
) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    page_size = 10
    safe_page = max(attendance_page, 0)
    start = safe_page * page_size
    for student in students[start : start + page_size]:
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
    attendance_navigation: list[dict[str, str]] = []
    if safe_page > 0:
        attendance_navigation.append(
            callback_button(
                "Ученики назад",
                feedback_payload("attendance", safe_page - 1),
            )
        )
    if start + page_size < len(students):
        attendance_navigation.append(
            callback_button(
                "Ученики далее",
                feedback_payload("attendance", safe_page + 1),
            )
        )
    if attendance_navigation:
        rows.append(attendance_navigation)
    rows.extend(
        [
            [
                callback_button("Дата −1 день", feedback_payload("date", -1)),
                callback_button("Дата +1 день", feedback_payload("date", 1)),
            ],
            [
                callback_button(
                    f"Формат: {lesson_mode_label}",
                    feedback_payload("mode"),
                )
            ],
            [
                callback_button(
                    f"Повторение: {'да' if is_repetition else 'нет'}",
                    feedback_payload("repeat"),
                )
            ],
            [callback_button("Сформировать ОС", feedback_payload("generate"))],
            [callback_button("К урокам", feedback_payload("lessons", 0))],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(rows)


def feedback_preview_keyboard(output_id: str | None = None) -> list[dict[str, Any]]:
    rows: list[list[dict[str, str]]] = []
    if output_id:
        rows.append(
            [callback_button("Отправить родителям", feedback_payload("manual_send", output_id))]
        )
    rows.extend(
        [
            [callback_button("Создать ещё", feedback_payload("manual"))],
            [callback_button("Черновики", feedback_payload("drafts"))],
            [callback_button("Главное меню", CALLBACK_MENU)],
        ]
    )
    return inline_keyboard(
        rows
    )


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
        rows.insert(0, [miniapp_button("Открыть приложение", miniapp_url)])
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
