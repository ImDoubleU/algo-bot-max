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
CALLBACK_STAFF_JOIN_PREFIX = "staff_join"
CALLBACK_ROLE_PARENT = "role:parent"
CALLBACK_ROLE_STUDENT = "role:student"
CALLBACK_ONBOARDING_RESTART = "onboarding:restart"
CALLBACK_ONBOARDING_CANCEL = "onboarding:cancel"


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
    base_url = configured_url or ("" if is_placeholder(settings_url) else str(settings_url).strip())
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
        label = city_name if city_counts.get(city_name, 0) == 1 else f"{city_name} · {tenant_name}"
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
        label = _button_label(clean_knowledge_label(str(item.get("text") or "Открыть")))
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
