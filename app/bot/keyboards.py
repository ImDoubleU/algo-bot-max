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
        schedule_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="teaching",
        )
        rows.append([link_button("Расписание преподавателя", schedule_url)])
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
    role: str | None = None,
) -> list[dict[str, Any]]:
    if role:
        return role_menu_keyboard(
            role,
            user_id=user_id,
            tenant_slug=tenant_slug,
            compact=True,
        )
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
        schedule_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="teaching",
        )
        rows.insert(0, [link_button("Расписание преподавателя", schedule_url)])
        rows.insert(0, [link_button("Открыть mini app", miniapp_url)])
    else:
        rows.insert(0, [callback_button("Открыть mini app", CALLBACK_MINIAPP)])
    return inline_keyboard(rows)


def role_menu_keyboard(
    role: str,
    *,
    user_id: int | None,
    tenant_slug: str | None,
    compact: bool,
) -> list[dict[str, Any]]:
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    schedule_url = build_miniapp_url(
        user_id=user_id,
        tenant_slug=tenant_slug,
        view="teaching",
    )
    normalized = role.casefold()
    rows: list[list[dict[str, str]]] = []
    if miniapp_url:
        if normalized == "teacher" and schedule_url:
            rows.append([link_button("Открыть расписание", schedule_url)])
        else:
            rows.append([link_button("Открыть mini app", miniapp_url)])

    if normalized == "student":
        rows.extend(
            [
                [
                    callback_button("Баланс", CALLBACK_BALANCE),
                    callback_button("Магазин", CALLBACK_CATALOG),
                ],
                [
                    callback_button("Мои заказы", CALLBACK_ORDERS),
                    callback_button("История AC", CALLBACK_LEDGER),
                ],
            ]
        )
    elif normalized == "parent":
        rows.extend(
            [
                [
                    callback_button("Мои дети", CALLBACK_STUDENTS),
                    callback_button("Балансы", CALLBACK_BALANCE),
                ],
                [
                    callback_button("Магазин", CALLBACK_CATALOG),
                    callback_button("Заказы", CALLBACK_ORDERS),
                ],
                [callback_button("История AC", CALLBACK_LEDGER)],
            ]
        )
    elif normalized == "teacher":
        rows.extend(
            [
                [
                    callback_button("Ученики", CALLBACK_STUDENTS),
                    callback_button("Группы", CALLBACK_GROUPS),
                ],
                [
                    callback_button("К выдаче", CALLBACK_TODO),
                    callback_button("Заказы", CALLBACK_OPEN_ORDERS),
                ],
                [
                    callback_button("Топ AC", CALLBACK_LEADERBOARD),
                    callback_button("Операции", CALLBACK_OPS),
                ],
            ]
        )
    else:
        rows.extend(
            [
                [
                    callback_button("Сводка", CALLBACK_OPS),
                    callback_button("К выдаче", CALLBACK_TODO),
                ],
                [
                    callback_button("Остатки", CALLBACK_STOCK),
                    callback_button("Заказы", CALLBACK_OPEN_ORDERS),
                ],
                [
                    callback_button("Ученики", CALLBACK_STUDENTS),
                    callback_button("Группы", CALLBACK_GROUPS),
                ],
            ]
        )
    rows.append(
        [
            callback_button("Помощь", CALLBACK_HELP),
            callback_button(
                "Главное меню" if compact else "Статус",
                CALLBACK_MENU if compact else CALLBACK_STATUS,
            ),
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
