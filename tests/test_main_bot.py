from __future__ import annotations

from typing import Any

import app.bot.max_long_polling as max_bot
from app.bot.max_long_polling import (
    CALLBACK_BALANCE,
    CALLBACK_CATALOG,
    CALLBACK_ONBOARDING_CANCEL,
    CALLBACK_ONBOARDING_RESTART,
    CALLBACK_OPS,
    CALLBACK_ORDERS,
    CALLBACK_ROLE_PARENT,
    CALLBACK_ROLE_STUDENT,
    CALLBACK_STATUS,
    CALLBACK_STUDENTS,
)
from main_bot import LongPollingBot, simulate_command


class FakeMaxClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    def get_me(self) -> dict[str, Any]:
        return {
            "user_id": 999,
            "username": "AlgoDraftBot",
            "first_name": "Algo Draft",
        }

    def send_message(
        self,
        *,
        text: str,
        attachments: list[dict[str, Any]] | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append(
            {
                "text": text,
                "attachments": attachments,
                "user_id": user_id,
                "chat_id": chat_id,
            }
        )
        return {}


class FakeBackendClient:
    def __init__(self) -> None:
        self.resolve_calls: list[dict[str, Any]] = []
        self.link_calls: list[dict[str, Any]] = []
        self.session_calls: list[dict[str, Any]] = []
        self.catalog_calls: list[dict[str, Any]] = []
        self.ops_calls: list[dict[str, Any]] = []
        self.order_calls: list[dict[str, Any]] = []
        self.inventory_adjust_calls: list[dict[str, Any]] = []
        self.create_order_calls: list[dict[str, Any]] = []
        self.accrue_calls: list[dict[str, Any]] = []
        self.extra_products: list[dict[str, Any]] = []
        self.extra_session_students: list[dict[str, Any]] = []

    def resolve_contact(
        self,
        *,
        tenant_slug: str,
        contact_id: str,
        max_user_id: int | None,
    ) -> dict[str, Any]:
        self.resolve_calls.append(
            {
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
            }
        )
        return {
            "contact_id": "681",
            "contact_display_name": "Мама Алисы",
            "students": [
                {
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "display_name": "Алиса",
                    "group_name": "Python Start",
                    "venue_name": "Союзный 45",
                    "teacher_name": "Олейник Д",
                },
                {
                    "student_id": "22222222-2222-2222-2222-222222222222",
                    "display_name": "Иван",
                    "group_name": "Python Start",
                    "venue_name": "Союзный 45",
                    "teacher_name": "Олейник Д",
                },
            ],
        }

    def create_links(
        self,
        *,
        tenant_slug: str,
        contact_id: str,
        max_user_id: int,
        role: str,
        username: str | None,
        display_name: str | None,
    ) -> dict[str, Any]:
        self.link_calls.append(
            {
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
                "role": role,
                "username": username,
                "display_name": display_name,
            }
        )
        return {"links": [{"id": "link-1"}, {"id": "link-2"}]}

    def get_session(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        self.session_calls.append(
            {
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
            }
        )
        return {
            "tenant_slug": tenant_slug,
            "account": {
                "max_user_id": max_user_id,
                "username": "parent_user",
                "display_name": "Родитель",
            },
            "staff_roles": ["admin"],
            "student_roles": ["parent"],
            "students": [
                {
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "display_name": "Алиса",
                    "group_name": "Python Start",
                    "venue_name": "Союзный 45",
                    "role": "parent",
                    "balance": 760,
                },
                *self.extra_session_students,
            ],
            "access_links": [
                {
                    "id": "access-link-1",
                    "account_id": "account-1",
                    "max_user_id": max_user_id,
                    "username": "parent_user",
                    "display_name": "Родитель",
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "student_name": "Алиса",
                    "group_name": "Python Start",
                    "role": "parent",
                    "status": "active",
                }
            ],
            "staff_assignments": [
                {
                    "id": "staff-assignment-1",
                    "account_id": "account-1",
                    "max_user_id": max_user_id,
                    "username": "parent_user",
                    "display_name": "Родитель",
                    "role": "admin",
                    "status": "active",
                }
            ],
            "orders": [
                {
                    "id": "order-1",
                    "order_number": 1001,
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "student_name": "Алиса",
                    "status": "reserved",
                    "total_astrocoins": 240,
                    "teacher_name": "Олейник Д",
                    "venue_name": "Союзный 45",
                    "created_at": "2026-06-29T00:00:00Z",
                    "items": [
                        {
                            "product_id": "product-1",
                            "product_name": "Ручка",
                            "quantity": 2,
                            "unit_price_astrocoins": 120,
                            "total_price_astrocoins": 240,
                            "warehouse_id": "warehouse-1",
                            "warehouse_name": "Общий склад",
                        }
                    ],
                }
            ],
            "ledger": [
                {
                    "id": "ledger-1",
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "direction": "credit",
                    "amount": 120,
                    "reason": "Начисление за проект",
                    "comment": "Python Start",
                    "created_at": "2026-06-29T00:00:00Z",
                },
                {
                    "id": "ledger-2",
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "direction": "debit",
                    "amount": 240,
                    "reason": "Покупка в магазине",
                    "comment": None,
                    "created_at": "2026-06-28T00:00:00Z",
                },
            ],
        }

    def get_readiness(self) -> dict[str, Any]:
        return {
            "status": "warning",
            "environment": "local",
            "service": "Algo MAX Bot",
            "default_tenant_slug": "nn-partner-a",
            "errors": [],
            "warnings": ["APP_SECRET_KEY still uses a placeholder value"],
            "checks": {
                "database": {
                    "status": "ok",
                    "message": "База данных отвечает на SELECT 1",
                },
                "app_data": {
                    "status": "warning",
                    "message": "Default tenant найден, но данных недостаточно для miniapp",
                    "tenant_slug": "nn-partner-a",
                    "products": 1,
                    "warehouses": 0,
                    "students": 1,
                    "contacts": 1,
                    "missing": ["warehouses"],
                    "seed_command": "python -m app.cli.seed_store --max-user-id <MAX_USER_ID>",
                },
            },
        }

    def update_order(
        self,
        *,
        order_id: str,
        action: str,
        tenant_slug: str,
        max_user_id: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        self.order_calls.append(
            {
                "order_id": order_id,
                "action": action,
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "comment": comment,
            }
        )
        status = {"cancel": "cancelled", "issue": "issued_to_student", "return": "returned"}[
            action
        ]
        return {
            "order": {
                "id": order_id,
                "order_number": 1001,
                "student_id": "11111111-1111-1111-1111-111111111111",
                "student_name": "Алиса",
                "status": status,
                "total_astrocoins": 240,
                "created_at": "2026-06-29T00:00:00Z",
            },
            "balance_after": 1000 if action in {"cancel", "return"} else None,
        }

    def create_order(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        student_id: str,
        items: list[dict[str, Any]],
        comment: str | None = None,
    ) -> dict[str, Any]:
        self.create_order_calls.append(
            {
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "student_id": student_id,
                "items": items,
                "comment": comment,
            }
        )
        product_prices = {
            "product-1": 120,
            "product-3": 30,
        }
        total = sum(
            product_prices.get(str(item["product_id"]), 0) * int(item["quantity"])
            for item in items
        )
        return {
            "order": {
                "id": "order-2",
                "order_number": 1002,
                "student_id": student_id,
                "student_name": "РђР»РёСЃР°",
                "status": "reserved",
                "total_astrocoins": total,
                "created_at": "2026-06-29T00:00:00Z",
            },
            "items": [
                {
                    "product_id": item["product_id"],
                    "product_name": "Р СѓС‡РєР°",
                    "quantity": int(item["quantity"]),
                    "unit_price_astrocoins": product_prices.get(str(item["product_id"]), 0),
                    "total_price_astrocoins": (
                        product_prices.get(str(item["product_id"]), 0) * int(item["quantity"])
                    ),
                    "warehouse_id": "warehouse-1",
                    "warehouse_name": "РћР±С‰РёР№ СЃРєР»Р°Рґ",
                }
                for item in items
            ],
            "balance_after": 1000 - total,
        }

    def accrue_astrocoins(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        student_ids: list[str],
        amount: int,
        reason: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        self.accrue_calls.append(
            {
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "student_ids": student_ids,
                "amount": amount,
                "reason": reason,
                "comment": comment,
            }
        )
        return {
            "tenant_slug": tenant_slug,
            "credited_students": len(student_ids),
            "amount": amount,
            "total_astrocoins": amount * len(student_ids),
        }

    def get_catalog(
        self,
        *,
        tenant_slug: str,
        max_user_id: int | None = None,
        include_inactive: bool = False,
    ) -> dict[str, Any]:
        self.catalog_calls.append(
            {
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "include_inactive": include_inactive,
            }
        )
        products = [
            {
                "id": "product-1",
                "sku": "PEN-LOGO",
                "name": "Ручка",
                "category_name": "Канцелярия",
                "price_astrocoins": 120,
                "status": "active",
                "available_quantity": 2,
                "warehouses": [
                    {
                        "warehouse_id": "warehouse-1",
                        "warehouse_name": "Общий склад",
                        "warehouse_type": "common",
                        "stock_quantity": 2,
                        "reserved_quantity": 0,
                        "available_quantity": 2,
                    }
                ],
            }
        ]
        products.extend(self.extra_products)
        if include_inactive:
            products.append(
                {
                    "id": "product-2",
                    "sku": "MUG-PYTHON",
                    "name": "Кружка",
                    "category_name": "Кружки",
                    "price_astrocoins": 250,
                    "status": "hidden",
                    "available_quantity": 0,
                    "warehouses": [
                        {
                            "warehouse_id": "warehouse-1",
                            "warehouse_name": "Общий склад",
                            "warehouse_type": "common",
                            "stock_quantity": 0,
                            "reserved_quantity": 0,
                            "available_quantity": 0,
                        }
                    ],
                }
            )
        return {
            "tenant_slug": tenant_slug,
            "products": products,
            "warehouses": [],
        }

    def adjust_inventory(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        product_id: str,
        warehouse_id: str,
        available_quantity: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        self.inventory_adjust_calls.append(
            {
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "product_id": product_id,
                "warehouse_id": warehouse_id,
                "available_quantity": available_quantity,
                "comment": comment,
            }
        )
        return {
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "warehouse_name": "РћР±С‰РёР№ СЃРєР»Р°Рґ",
            "stock_quantity": available_quantity,
            "reserved_quantity": 0,
            "available_quantity": available_quantity,
        }

    def get_ops_summary(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        low_stock_threshold: int = 5,
    ) -> dict[str, Any]:
        self.ops_calls.append(
            {
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "low_stock_threshold": low_stock_threshold,
            }
        )
        return {
            "tenant_slug": tenant_slug,
            "staff_role": "admin",
            "total_orders": 3,
            "open_orders": 2,
            "pending_issue_orders": 1,
            "order_statuses": [
                {"status": "cancelled", "count": 1},
                {"status": "reserved", "count": 1},
                {"status": "problem", "count": 1},
            ],
            "recent_open_orders": [
                {
                    "id": "order-1",
                    "order_number": 1001,
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "student_name": "Алиса",
                    "status": "reserved",
                    "total_astrocoins": 240,
                    "created_at": "2026-06-29T00:00:00Z",
                }
            ],
            "low_stock": [
                {
                    "product_id": "product-1",
                    "sku": "PEN-LOGO",
                    "product_name": "Ручка",
                    "product_status": "active",
                    "warehouse_id": "warehouse-1",
                    "warehouse_name": "Общий склад",
                    "stock_quantity": 2,
                    "reserved_quantity": 1,
                    "available_quantity": 1,
                }
            ],
            "low_stock_threshold": low_stock_threshold,
            "active_products": 1,
            "warehouses": 1,
            "total_stock_quantity": 2,
            "total_reserved_quantity": 1,
        }


def test_build_miniapp_url_keeps_registered_url_exact(monkeypatch) -> None:
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/miniapp?source=max")
    monkeypatch.setenv("MAX_BOT_USERNAME", "example_bot")

    url = max_bot.build_miniapp_url(
        user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
        view="orders",
    )

    assert url == "https://example.test/miniapp?source=max"
    button = max_bot.main_menu_keyboard(
        user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )[0]["payload"]["buttons"][0][0]
    assert button["type"] == "open_app"
    assert button["web_app"] == "example_bot"


def test_simulate_command_returns_local_bot_response() -> None:
    response = simulate_command(
        command_text="/help",
        user_id=1,
        backend_client=None,
        default_tenant_slug="nn-partner-a",
    )

    assert "Добро пожаловать" in response["text"]
    assert response["user_id"] == 1
    assert response["chat_id"] == 1


def test_tenant_selection_changes_user_tenant() -> None:
    bot = LongPollingBot(FakeMaxClient(), default_tenant_slug="nn-partner-a")

    assert "Текущий tenant: nn-partner-a" in bot.handle_tenant_selection(
        user_id=1,
        tenant_slug="",
    )
    assert "Tenant выбран: kazan-partner-b" in bot.handle_tenant_selection(
        user_id=1,
        tenant_slug="Kazan-Partner-B",
    )
    assert bot.current_tenant_slug(1) == "kazan-partner-b"


def test_contact_payload_resolves_students_through_backend() -> None:
    backend = FakeBackendClient()
    bot = LongPollingBot(
        FakeMaxClient(),
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    response = bot.handle_contact_payload(payload="cid_681", user_id=1)

    assert response is not None
    assert "Найдены ученики:" in response
    assert "Алиса / Python Start / Союзный 45 / Олейник Д" in response
    assert bot.pending_contact_ids[1].contact_id == "681"
    assert backend.resolve_calls == [
        {"tenant_slug": "nn-partner-a", "contact_id": "681", "max_user_id": 1}
    ]


def test_role_selection_creates_backend_access_links() -> None:
    backend = FakeBackendClient()
    bot = LongPollingBot(
        FakeMaxClient(),
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )
    bot.handle_contact_payload(payload="cid_681", user_id=1)

    response = bot.handle_role_selection(
        user_id=1,
        role="parent",
        username="parent_user",
        display_name="Родитель",
    )

    assert "Связи доступа созданы." in response
    assert "Связанных учеников: 2" in response
    assert backend.link_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "contact_id": "681",
            "max_user_id": 1,
            "role": "parent",
            "username": "parent_user",
            "display_name": "Родитель",
        }
    ]


def test_plain_contact_message_sends_role_buttons() -> None:
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=FakeBackendClient(),
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "681"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Найдены ученики:" in sent["text"]
    buttons = sent["attachments"][0]["payload"]["buttons"]
    assert buttons[0][0]["payload"] == CALLBACK_ROLE_PARENT
    assert buttons[0][1]["payload"] == CALLBACK_ROLE_STUDENT


def test_status_command_reports_runtime_state() -> None:
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=FakeBackendClient(),
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/status"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Статус MAX-бота" in sent["text"]
    assert "Tenant: nn-partner-a" in sent["text"]
    assert "Backend API: подключен" in sent["text"]
    buttons = sent["attachments"][0]["payload"]["buttons"]
    assert buttons[0][1]["payload"] == CALLBACK_STATUS
    assert buttons[1][0]["payload"] == CALLBACK_CATALOG
    assert buttons[1][1]["payload"] == CALLBACK_BALANCE
    assert buttons[2][0]["payload"] == CALLBACK_ORDERS
    assert buttons[2][1]["payload"] == CALLBACK_STUDENTS
    assert buttons[3][0]["payload"] == CALLBACK_OPS


def test_ready_command_reports_backend_readiness() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/ready"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Readiness backend" in sent["text"]
    assert "Status: warning" in sent["text"]
    assert "Database: ok" in sent["text"]
    assert "App data: warning" in sent["text"]
    assert "missing: warehouses" in sent["text"]
    assert "seed: python -m app.cli.seed_store --max-user-id <MAX_USER_ID>" in sent["text"]


def test_help_command_lists_practical_commands() -> None:
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=FakeBackendClient(),
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/help"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "/catalog [поиск] - активные товары" in sent["text"]
    assert "/balance - балансы астрокоинов" in sent["text"]
    assert "/ledger - последние операции с астрокоинами." in sent["text"]
    assert "/students [поиск] - ученики, роли, группы и балансы." in sent["text"]
    assert "/access - связи доступа и staff-роли." in sent["text"]
    assert "/accrue <AC> <ученик> | <причина>" in sent["text"]
    assert "/order <номер> - детали конкретного заказа." in sent["text"]
    assert "/stock [порог] - проблемные остатки для staff/admin." in sent["text"]
    assert "/ready - readiness backend" in sent["text"]


def test_me_command_reports_backend_session() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/me"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Профиль MAX" in sent["text"]
    assert "Staff-роли: admin" in sent["text"]
    assert "Алиса / Python Start / Союзный 45" in sent["text"]
    assert "Открытые заказы: 1" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_balance_command_reports_student_balances() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/balance"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Баланс астрокоинов" in sent["text"]
    assert "Всего по профилю: 760 AC" in sent["text"]
    assert "Алиса / Python Start: 760 AC" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_ledger_command_reports_recent_astrocoin_entries() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/ledger"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "История астрокоинов" in sent["text"]
    assert "Алиса, начисление +120 AC - Начисление за проект (Python Start)" in sent["text"]
    assert "Алиса, списание -240 AC - Покупка в магазине" in sent["text"]
    assert "29.06.2026" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_students_command_reports_students_with_search() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/students python"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Ученики MAX" in sent["text"]
    assert "Поиск: python" in sent["text"]
    assert "Найдено учеников: 1" in sent["text"]
    assert "Алиса (parent, 760 AC) - Python Start / Союзный 45" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_access_command_reports_access_links_and_staff_roles() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/access"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Доступы MAX" in sent["text"]
    assert "Ваши staff-роли: admin" in sent["text"]
    assert "Алиса / Python Start: parent, active, MAX Родитель" in sent["text"]
    assert "Родитель: admin, active" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_accrue_command_credits_unique_student() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "teacher_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/accrue 75 алиса | За проект"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Астрокоины начислены." in sent["text"]
    assert "Ученик: Алиса" in sent["text"]
    assert "Сумма: +75 AC" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]
    assert backend.accrue_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "student_ids": ["11111111-1111-1111-1111-111111111111"],
            "amount": 75,
            "reason": "За проект",
            "comment": "MAX bot /accrue",
        }
    ]


def test_accrue_command_requires_reason_without_backend_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "teacher_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/accrue 75 алиса"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Добавьте причину после" in sent["text"]
    assert backend.session_calls == []
    assert backend.accrue_calls == []


def test_buy_command_creates_order_for_unique_student_and_sku() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {
                    "text": "/buy PEN-LOGO 2 | 11111111-1111-1111-1111-111111111111"
                },
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "1002" in sent["text"]
    assert "x2" in sent["text"]
    assert "240 AC" in sent["text"]
    assert "/order 1002" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "include_inactive": False}
    ]
    assert backend.create_order_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "student_id": "11111111-1111-1111-1111-111111111111",
            "items": [{"product_id": "product-1", "quantity": 2}],
            "comment": "MAX bot /buy",
        }
    ]


def test_buy_command_creates_multi_item_order() -> None:
    backend = FakeBackendClient()
    backend.extra_products.append(
        {
            "id": "product-3",
            "sku": "STICKER-PACK",
            "name": "Sticker pack",
            "category_name": "Merch",
            "price_astrocoins": 30,
            "status": "active",
            "available_quantity": 10,
            "warehouses": [
                {
                    "warehouse_id": "warehouse-1",
                    "warehouse_name": "Main warehouse",
                    "warehouse_type": "common",
                    "stock_quantity": 10,
                    "reserved_quantity": 0,
                    "available_quantity": 10,
                }
            ],
        }
    )
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {
                    "text": (
                        "/buy PEN-LOGO 2, STICKER-PACK 1 | "
                        "11111111-1111-1111-1111-111111111111"
                    )
                },
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "270 AC" in sent["text"]
    assert "Баланс после заказа: 730 AC" in sent["text"]
    assert backend.create_order_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "student_id": "11111111-1111-1111-1111-111111111111",
            "items": [
                {"product_id": "product-1", "quantity": 2},
                {"product_id": "product-3", "quantity": 1},
            ],
            "comment": "MAX bot /buy",
        }
    ]


def test_buy_command_uses_single_linked_student_without_separator() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/buy PEN-LOGO 2"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "1002" in sent["text"]
    assert "240 AC" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "include_inactive": False}
    ]
    assert backend.create_order_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "student_id": "11111111-1111-1111-1111-111111111111",
            "items": [{"product_id": "product-1", "quantity": 2}],
            "comment": "MAX bot /buy",
        }
    ]


def test_buy_command_requires_student_separator_for_multiple_students() -> None:
    backend = FakeBackendClient()
    backend.extra_session_students.append(
        {
            "student_id": "22222222-2222-2222-2222-222222222222",
            "display_name": "Ivan",
            "group_name": "Python Start",
            "venue_name": "Main venue",
            "role": "parent",
            "balance": 1000,
        }
    )
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/buy PEN-LOGO 2"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "/buy PEN-LOGO 2 |" in sent["text"]
    assert "Ivan" in sent["text"]
    assert backend.catalog_calls == []
    assert backend.create_order_calls == []


def test_buy_command_rejects_insufficient_stock_without_order_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {
                    "text": "/buy PEN-LOGO 3 | 11111111-1111-1111-1111-111111111111"
                },
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "3" in sent["text"]
    assert "2" in sent["text"]
    assert backend.create_order_calls == []


def test_buy_command_aggregates_duplicate_products_before_stock_check() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {
                    "text": (
                        "/buy PEN-LOGO 1, PEN-LOGO 2 | "
                        "11111111-1111-1111-1111-111111111111"
                    )
                },
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "3" in sent["text"]
    assert "2" in sent["text"]
    assert backend.create_order_calls == []


def test_catalog_command_reports_active_products() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/catalog"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Каталог магазина" in sent["text"]
    assert "Найдено товаров: 1" in sent["text"]
    assert "Ручка (PEN-LOGO): 120 AC, остаток 2 шт., Канцелярия" in sent["text"]
    assert "Кружка" not in sent["text"]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": None, "include_inactive": False}
    ]


def test_shop_alias_opens_catalog() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/shop pen"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Каталог магазина" in sent["text"]
    assert "Поиск: pen" in sent["text"]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": None, "include_inactive": False}
    ]


def test_catalog_command_filters_products_by_query() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/catalog mug"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Поиск: mug" in sent["text"]
    assert "Найдено товаров: 0" in sent["text"]
    assert "Подходящих активных товаров не найдено." in sent["text"]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": None, "include_inactive": False}
    ]


def test_unknown_slash_command_returns_command_help_without_contact_lookup() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/unknown"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Команда `/unknown` не поддерживается." in sent["text"]
    assert "отправьте только номер без `/`" in sent["text"]
    assert backend.resolve_calls == []


def test_orders_command_reports_backend_orders() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/orders"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Заказы MAX" in sent["text"]
    assert "Открытые заказы: 1" in sent["text"]
    assert "№1001: Алиса, зарезервирован, 240 AC" in sent["text"]
    assert "Для выдачи, отмены или возврата откройте miniapp." in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_order_command_reports_order_details_and_actions() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/order 1001"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Заказ №1001" in sent["text"]
    assert "Статус: зарезервирован" in sent["text"]
    assert "Ученик: Алиса" in sent["text"]
    assert "Сумма: 240 AC" in sent["text"]
    assert "Преподаватель: Олейник Д" in sent["text"]
    assert "Ручка x2: 240 AC, Общий склад" in sent["text"]
    assert "/cancel 1001 - отменить" in sent["text"]
    assert "/issue 1001 - выдать заказ ученику" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]


def test_order_command_requires_order_number_without_backend_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/order"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Укажите номер заказа: /order <номер>" in sent["text"]
    assert backend.session_calls == []


def test_repeat_command_creates_new_order_from_existing_order_items() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/repeat 1001"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "1002" in sent["text"]
    assert "1001" in sent["text"]
    assert "240 AC" in sent["text"]
    assert "/order 1002" in sent["text"]
    assert backend.session_calls == [{"tenant_slug": "nn-partner-a", "max_user_id": 1}]
    assert backend.create_order_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "student_id": "11111111-1111-1111-1111-111111111111",
            "items": [{"product_id": "product-1", "quantity": 2}],
            "comment": "MAX bot /repeat 1001",
        }
    ]


def test_repeat_command_requires_order_number_without_backend_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/repeat"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "/repeat <" in sent["text"]
    assert backend.session_calls == []
    assert backend.create_order_calls == []


def test_order_details_formatter_reports_status_history() -> None:
    bot = LongPollingBot(FakeMaxClient(), default_tenant_slug="nn-partner-a")

    text = bot.format_order_details_text(
        {
            "id": "order-1",
            "order_number": 1001,
            "student_name": "Алиса",
            "status": "reserved",
            "total_astrocoins": 240,
            "created_at": "2026-06-29T00:00:00Z",
            "status_history": [
                {
                    "from_status": None,
                    "to_status": "reserved",
                    "comment": "MAX mini app",
                    "created_at": "2026-06-29T00:00:00Z",
                }
            ],
        },
        tenant_slug="nn-partner-a",
    )

    assert "История статусов:" in text
    assert "начало -> зарезервирован - MAX mini app" in text


def test_stock_command_reports_low_inventory() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/stock 3"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Остатки магазина" in sent["text"]
    assert "Порог: ≤ 3 шт." in sent["text"]
    assert "Ручка: 2 шт., Общий склад" in sent["text"]
    assert "Кружка: 0 шт., Общий склад" in sent["text"]
    assert "Скрытых/архивных: 1" in sent["text"]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "include_inactive": True}
    ]


def test_setstock_command_adjusts_single_warehouse_product() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/setstock PEN-LOGO 18"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "18" in sent["text"]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "include_inactive": True}
    ]
    assert backend.inventory_adjust_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "product_id": "product-1",
            "warehouse_id": "warehouse-1",
            "available_quantity": 18,
            "comment": "MAX bot /setstock",
        }
    ]


def test_setstock_command_rejects_invalid_quantity_without_backend_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/setstock PEN-LOGO many"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "/setstock PEN-LOGO 18" in sent["text"]
    assert backend.catalog_calls == []
    assert backend.inventory_adjust_calls == []


def test_setstock_command_requires_warehouse_for_multi_warehouse_product() -> None:
    backend = FakeBackendClient()
    backend.extra_products.append(
        {
            "id": "product-3",
            "sku": "STICKER-PACK",
            "name": "Sticker pack",
            "category_name": "Merch",
            "price_astrocoins": 30,
            "status": "active",
            "available_quantity": 10,
            "warehouses": [
                {
                    "warehouse_id": "warehouse-1",
                    "warehouse_name": "Main warehouse",
                    "warehouse_type": "common",
                    "stock_quantity": 5,
                    "reserved_quantity": 0,
                    "available_quantity": 5,
                },
                {
                    "warehouse_id": "warehouse-2",
                    "warehouse_name": "Venue warehouse",
                    "warehouse_type": "venue",
                    "stock_quantity": 5,
                    "reserved_quantity": 0,
                    "available_quantity": 5,
                },
            ],
        }
    )
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/setstock STICKER-PACK 7"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Main warehouse" in sent["text"]
    assert "Venue warehouse" in sent["text"]
    assert backend.inventory_adjust_calls == []


def test_ops_command_reports_operational_summary() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/ops 3"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Операционная сводка" in sent["text"]
    assert "Открытых заказов: 2" in sent["text"]
    assert "Ожидают выдачи: 1" in sent["text"]
    assert "#1001: Алиса, зарезервирован, 240 AC" in sent["text"]
    assert "Ручка: 1 шт., резерв 1, Общий склад" in sent["text"]
    assert backend.ops_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "low_stock_threshold": 3}
    ]


def test_todo_command_reports_pending_order_tasks() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/todo 3"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Задачи магазина" in sent["text"]
    assert "Открытых заказов: 2" in sent["text"]
    assert "Ожидают выдачи: 1" in sent["text"]
    assert "№1001" in sent["text"]
    assert "/issue 1001" in sent["text"]
    assert "/order 1001" in sent["text"]
    assert "Низкие остатки <= 3" in sent["text"]
    assert backend.ops_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "low_stock_threshold": 3}
    ]


def test_todo_command_rejects_invalid_threshold_without_backend_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/pending soon"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "/todo 3" in sent["text"]
    assert backend.ops_calls == []


def test_stock_command_rejects_invalid_threshold_without_backend_call() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "admin_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/stock low"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Порог остатка должен быть числом" in sent["text"]
    assert backend.catalog_calls == []


def test_cancel_command_updates_known_order() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/cancel 1001"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Заказ обновлен." in sent["text"]
    assert "№1001: Алиса, отменен, 240 AC" in sent["text"]
    assert "Баланс после операции: 1000 AC" in sent["text"]
    assert backend.order_calls == [
        {
            "order_id": "order-1",
            "action": "cancel",
            "tenant_slug": "nn-partner-a",
            "max_user_id": 1,
            "comment": "MAX bot command: cancel",
        }
    ]


def test_order_action_does_not_call_backend_for_unknown_order() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/issue 9999"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Не нашел заказ `9999`" in sent["text"]
    assert backend.order_calls == []


def test_miniapp_command_returns_profile_link(monkeypatch) -> None:
    monkeypatch.setattr(max_bot, "MAX_MINIAPP_URL", "https://example.test/miniapp")
    max_client = FakeMaxClient()
    bot = LongPollingBot(max_client, default_tenant_slug="nn-partner-a")

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 1, "username": "parent_user"},
                "recipient": {"chat_id": 10},
                "body": {"text": "/miniapp"},
            }
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Miniapp для текущего профиля" in sent["text"]
    assert "https://example.test/miniapp?max_user_id=1&tenant_slug=nn-partner-a" in sent["text"]


def test_role_callback_creates_backend_access_links() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )
    bot.handle_contact_payload(payload="cid_681", user_id=1)

    bot.handle_message_callback(
        {
            "payload": CALLBACK_ROLE_PARENT,
            "user": {
                "user_id": 1,
                "username": "parent_user",
                "first_name": "Родитель",
            },
            "chat_id": 10,
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Связи доступа созданы." in sent["text"]
    assert backend.link_calls[-1]["role"] == "parent"


def test_first_entry_requires_role_and_contact_id() -> None:
    class EmptySessionBackend(FakeBackendClient):
        def get_session(
            self,
            *,
            tenant_slug: str,
            max_user_id: int,
        ) -> dict[str, Any]:
            return {
                "tenant_slug": tenant_slug,
                "staff_roles": [],
                "student_roles": [],
                "students": [],
            }

    backend = EmptySessionBackend()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_bot_started(
        {
            "user": {"user_id": 77, "username": "new_user"},
            "chat_id": 77,
        }
    )
    first_message = max_client.sent_messages[-1]
    assert "Первый вход" in first_message["text"]
    first_buttons = first_message["attachments"][0]["payload"]["buttons"]
    assert first_buttons[0][0]["payload"] == CALLBACK_ROLE_PARENT
    assert first_buttons[0][1]["payload"] == CALLBACK_ROLE_STUDENT

    bot.handle_message_callback(
        {
            "payload": CALLBACK_ROLE_STUDENT,
            "user": {"user_id": 77, "username": "new_user"},
            "chat_id": 77,
        }
    )
    role_message = max_client.sent_messages[-1]
    assert "отправьте Contact ID" in role_message["text"]
    role_buttons = role_message["attachments"][0]["payload"]["buttons"]
    assert role_buttons[1][0]["payload"] == CALLBACK_ONBOARDING_CANCEL

    bot.handle_message_created(
        {
            "message": {
                "sender": {"user_id": 77, "username": "new_user"},
                "recipient": {"chat_id": 77, "user_id": 999},
                "body": {"text": "681"},
            }
        }
    )
    assert "Связи доступа созданы." in max_client.sent_messages[-1]["text"]
    assert backend.link_calls[-1]["role"] == "student"


def test_onboarding_can_be_cancelled() -> None:
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=FakeBackendClient(),
        default_tenant_slug="nn-partner-a",
    )
    bot.handle_role_selection_response(user_id=77, role="parent")

    bot.handle_message_callback(
        {
            "payload": CALLBACK_ONBOARDING_CANCEL,
            "user": {"user_id": 77},
            "chat_id": 77,
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Вход отменен" in sent["text"]
    assert 77 not in bot.pending_contact_ids
    assert 77 not in bot.pending_onboarding_roles
    buttons = sent["attachments"][0]["payload"]["buttons"]
    assert buttons[0][0]["payload"] == CALLBACK_ONBOARDING_RESTART


def test_catalog_callback_opens_catalog_from_menu() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_callback(
        {
            "payload": CALLBACK_CATALOG,
            "user": {"user_id": 1, "username": "parent_user"},
            "chat_id": 10,
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Каталог магазина" in sent["text"]
    assert "Ручка (PEN-LOGO): 120 AC" in sent["text"]
    assert backend.catalog_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": None, "include_inactive": False}
    ]


def test_ops_callback_opens_operational_summary_from_menu() -> None:
    backend = FakeBackendClient()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )

    bot.handle_message_callback(
        {
            "payload": CALLBACK_OPS,
            "user": {"user_id": 1, "username": "admin_user"},
            "chat_id": 10,
        }
    )

    sent = max_client.sent_messages[-1]
    assert "Операционная сводка" in sent["text"]
    assert backend.ops_calls == [
        {"tenant_slug": "nn-partner-a", "max_user_id": 1, "low_stock_threshold": 5}
    ]


def test_hidden_staff_invite_flow_assigns_role_after_approval() -> None:
    class StaffBackend(FakeBackendClient):
        def __init__(self) -> None:
            super().__init__()
            self.staff_assignment_calls: list[dict[str, Any]] = []

        def get_staff_onboarding_options(
            self,
            *,
            tenant_slug: str,
            max_user_id: int,
        ) -> dict[str, Any]:
            return {
                "tenants": [
                    {
                        "tenant_slug": "nn-partner-a",
                        "tenant_name": "Алгоритмика Нижний Новгород",
                        "city_name": "Нижний Новгород",
                    }
                ],
                "roles": ["partner_director", "admin", "curator", "teacher"],
            }

        def update_staff_assignment(self, **kwargs: Any) -> dict[str, Any]:
            self.staff_assignment_calls.append(kwargs)
            return {"status": "active", **kwargs}

    backend = StaffBackend()
    max_client = FakeMaxClient()
    bot = LongPollingBot(
        max_client,
        backend_client=backend,
        default_tenant_slug="nn-partner-a",
    )
    bot.staff_invite_command = "/staff"
    bot.staff_approver_user_id = 42

    bot.handle_message_created(
        {
            "message": {
                "sender": {
                    "user_id": 77,
                    "username": "teacher_user",
                    "first_name": "Анна",
                    "last_name": "Иванова",
                },
                "recipient": {"chat_id": 77},
                "body": {"text": "/staff"},
            }
        }
    )
    city_payload = max_client.sent_messages[-1]["attachments"][0]["payload"]["buttons"][0][
        0
    ]["payload"]

    bot.handle_message_callback(
        {"payload": city_payload, "user": {"user_id": 77}, "chat_id": 77}
    )
    role_payload = max_client.sent_messages[-1]["attachments"][0]["payload"]["buttons"][3][
        0
    ]["payload"]

    bot.handle_message_callback(
        {"payload": role_payload, "user": {"user_id": 77}, "chat_id": 77}
    )
    approval_message = max_client.sent_messages[-2]
    assert approval_message["user_id"] == 42
    assert "MAX ID: 77" in approval_message["text"]
    approval_payload = approval_message["attachments"][0]["payload"]["buttons"][0][0][
        "payload"
    ]

    bot.handle_message_callback(
        {"payload": approval_payload, "user": {"user_id": 42}, "chat_id": 42}
    )

    assert backend.staff_assignment_calls == [
        {
            "tenant_slug": "nn-partner-a",
            "max_user_id": 42,
            "target_max_user_id": 77,
            "role": "teacher",
            "status": "active",
            "username": "teacher_user",
            "display_name": "Анна Иванова",
        }
    ]
    assert any(
        message.get("user_id") == 77 and "Доступ сотрудника подтвержден" in message["text"]
        for message in max_client.sent_messages
    )
