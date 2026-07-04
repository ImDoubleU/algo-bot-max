from __future__ import annotations

import os
from typing import Any
from urllib import parse

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
CALLBACK_ROLE_PARENT = "role:parent"
CALLBACK_ROLE_STUDENT = "role:student"


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


def build_miniapp_url(user_id: int | None = None, tenant_slug: str | None = None) -> str:
    miniapp_url = os.getenv("MAX_MINIAPP_URL", "").strip()
    if not miniapp_url:
        return ""

    parts = parse.urlsplit(miniapp_url)
    query = dict(parse.parse_qsl(parts.query, keep_blank_values=True))
    if user_id is not None:
        query["max_user_id"] = str(user_id)
    if tenant_slug:
        query["tenant_slug"] = tenant_slug

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
) -> list[dict[str, Any]]:
    rows = [
        [
            callback_button("Помощь", CALLBACK_HELP),
            callback_button("Статус", CALLBACK_STATUS),
        ],
        [
            callback_button("Каталог", CALLBACK_CATALOG),
            callback_button("Баланс", CALLBACK_BALANCE),
        ],
        [
            callback_button("Заказы", CALLBACK_ORDERS),
            callback_button("Открытые", CALLBACK_OPEN_ORDERS),
        ],
        [
            callback_button("Ученики", CALLBACK_STUDENTS),
            callback_button("История AC", CALLBACK_LEDGER),
        ],
        [
            callback_button("Группы", CALLBACK_GROUPS),
            callback_button("Топ AC", CALLBACK_LEADERBOARD),
        ],
    ]
    rows.append(
        [
            callback_button("Категории", CALLBACK_CATEGORIES),
            callback_button("Операции", CALLBACK_OPS),
        ]
    )
    rows.append(
        [
            callback_button("К выдаче", CALLBACK_TODO),
            callback_button("Остатки", CALLBACK_STOCK),
        ]
    )
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    if miniapp_url:
        rows.append([link_button("Открыть mini app", miniapp_url)])
    return inline_keyboard(rows)


def role_selection_keyboard() -> list[dict[str, Any]]:
    return inline_keyboard(
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
) -> list[dict[str, Any]]:
    rows = [
        [
            callback_button("Баланс", CALLBACK_BALANCE),
            callback_button("Заказы", CALLBACK_ORDERS),
        ],
        [callback_button("Открытые заказы", CALLBACK_OPEN_ORDERS)],
        [
            callback_button("Каталог", CALLBACK_CATALOG),
            callback_button("История AC", CALLBACK_LEDGER),
        ],
        [
            callback_button("Ученики", CALLBACK_STUDENTS),
            callback_button("Группы", CALLBACK_GROUPS),
        ],
        [
            callback_button("Топ AC", CALLBACK_LEADERBOARD),
        ],
        [callback_button("В меню", CALLBACK_MENU)],
    ]
    rows.insert(
        -1,
        [
            callback_button("Операции", CALLBACK_OPS),
            callback_button("К выдаче", CALLBACK_TODO),
        ],
    )
    rows.insert(-1, [callback_button("Остатки", CALLBACK_STOCK)])
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    if miniapp_url:
        rows.insert(0, [link_button("Открыть mini app", miniapp_url)])
    else:
        rows.insert(0, [callback_button("Открыть mini app", CALLBACK_MINIAPP)])
    return inline_keyboard(rows)
