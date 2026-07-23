from __future__ import annotations

import argparse
import json
import logging
import sys
import threading
import time
from datetime import datetime
from typing import Any

from app.bot.backend_client import AccessBackendClient, BackendApiError
from app.bot.command_parsers import (
    parse_accrue_command,
    parse_buy_command,
    parse_productset_command,
    parse_productstatus_command,
    parse_setphoto_command,
    parse_setprice_command,
    parse_setstock_command,
    parse_staffrole_command,
    parse_transfer_command,
    parse_warehouse_command,
)
from app.bot.keyboards import (
    CALLBACK_BALANCE,
    CALLBACK_CATALOG,
    CALLBACK_CATEGORIES,
    CALLBACK_GROUPS,
    CALLBACK_HELP,
    CALLBACK_LEADERBOARD,
    CALLBACK_LEDGER,
    CALLBACK_MENU,
    CALLBACK_MINIAPP,
    CALLBACK_OPEN_ORDERS,
    CALLBACK_OPS,
    CALLBACK_ORDERS,
    CALLBACK_ROLE_PARENT,
    CALLBACK_ROLE_STUDENT,
    CALLBACK_STATUS,
    CALLBACK_STOCK,
    CALLBACK_STUDENTS,
    CALLBACK_TODO,
    build_miniapp_url,
    cabinet_keyboard,
    main_menu_keyboard,
    order_actions_keyboard,
    order_confirmation_keyboard,
    parse_order_action_payload,
    parse_order_confirm_payload,
    role_selection_keyboard,
)
from app.bot.max_client import MaxApiClient, MaxApiError, SimulationMaxClient
from app.bot.models import BotResponse, PendingContact
from app.bot.runtime import APP_REVISION, APP_VERSION, MARKER_FILE, configure_logging
from app.core.config import get_settings, is_placeholder
from app.services.deep_links import (
    DeepLinkError,
    build_max_bot_deeplink,
    parse_contact_payload,
)

logger = logging.getLogger("algo_bot_max.bot")
POLL_RETRY_INITIAL_SECONDS = 1.0
POLL_RETRY_MAX_SECONDS = 30.0


def display_name_from_user(user: dict[str, Any]) -> str | None:
    first_name = user.get("first_name")
    last_name = user.get("last_name")
    parts = [str(value).strip() for value in (first_name, last_name) if value]
    if parts:
        return " ".join(parts)

    for key in ("display_name", "name"):
        value = user.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def format_backend_error(exc: BackendApiError) -> str:
    if exc.status_code == 429:
        return "Слишком много попыток. Попробуйте немного позже."
    if exc.status_code == 404:
        text = str(exc).strip()
        if text.startswith("HTTP 404") and ": " in text:
            detail = text.split(": ", 1)[1].strip()
        else:
            detail = text
        if "contact id" in detail.casefold():
            return "Contact ID не найден для выбранного tenant."
        if detail and detail != text:
            return f"Не найдено: {detail}"
        return "Запрошенный объект не найден в backend API."
    return str(exc)


class LongPollingBot:
    def __init__(
        self,
        client: MaxApiClient,
        *,
        backend_client: AccessBackendClient | None = None,
        default_tenant_slug: str | None = None,
    ) -> None:
        self.client = client
        self.backend_client = backend_client
        self.default_tenant_slug = default_tenant_slug or get_settings().default_tenant_slug
        self.bot_info = self.client.get_me()
        self.bot_user_id = self.bot_info.get("user_id")
        self.pending_contact_ids: dict[int, PendingContact] = {}
        self.user_tenant_slugs: dict[int, str] = {}
        self.user_menu_roles: dict[tuple[int, str], str] = {}
        self.running = True
        self.stop_event = threading.Event()

    def stop(self) -> None:
        self.running = False
        self.stop_event.set()

    def load_marker(self) -> int | None:
        if not MARKER_FILE.exists():
            return None

        value = MARKER_FILE.read_text(encoding="utf-8").strip()
        if not value:
            return None

        try:
            return int(value)
        except ValueError:
            return None

    def save_marker(self, marker: int | None) -> None:
        if marker is not None:
            MARKER_FILE.write_text(str(marker), encoding="utf-8")

    def reset_marker(self) -> None:
        if MARKER_FILE.exists():
            MARKER_FILE.unlink()

    def ensure_polling_available(self, *, drop_webhooks: bool) -> None:
        data = self.client.get_subscriptions()
        subscriptions = data.get("subscriptions") or []

        if not subscriptions:
            return

        urls = [item.get("url") for item in subscriptions if item.get("url")]
        if drop_webhooks:
            for url in urls:
                self.client.delete_subscription(url)
                logger.info("Удалена webhook-подписка: %s", url)
            return

        joined = ", ".join(urls) if urls else "unknown"
        raise SystemExit(
            "Активна webhook-подписка, поэтому long polling не получит события.\n"
            f"Текущие подписки: {joined}\n"
            "Запустите `python main_bot.py --drop-webhooks`, задайте "
            "`MAX_DROP_WEBHOOKS_ON_START=true` или удалите webhook в MAX."
        )

    def target_from_message(self, message: dict[str, Any]) -> tuple[int | None, int | None]:
        recipient = message.get("recipient") or {}
        sender = message.get("sender") or {}

        chat_id = recipient.get("chat_id")
        user_id = recipient.get("user_id") or sender.get("user_id")
        return chat_id, user_id

    def send_reply(
        self,
        *,
        text: str,
        attachments: list[dict[str, Any]] | None = None,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        self.client.send_message(
            text=text,
            attachments=attachments,
            chat_id=chat_id,
            user_id=user_id,
        )

    def send_response(
        self,
        response: BotResponse,
        *,
        chat_id: int | None = None,
        user_id: int | None = None,
    ) -> None:
        self.send_reply(
            text=response.text,
            attachments=response.attachments,
            chat_id=chat_id,
            user_id=user_id,
        )

    def log_interaction_result(
        self,
        *,
        event_type: str,
        action: str,
        user_id: int | None,
        chat_id: int | None,
        tenant_slug: str,
        started_at: float,
        response: BotResponse,
    ) -> None:
        logger.info(
            "bot_interaction event=%s action=%s user_id=%s chat_id=%s "
            "tenant=%s elapsed_ms=%s text_len=%s attachments=%s",
            event_type,
            action,
            user_id,
            chat_id,
            tenant_slug,
            int((time.monotonic() - started_at) * 1000),
            len(response.text),
            len(response.attachments or []),
        )

    def help_text(self, topic: str = "") -> str:
        backend_state = "подключен" if self.backend_client else "выключен"
        normalized_topic = topic.strip().casefold()
        topic_aliases = {
            "shop": "shop",
            "catalog": "shop",
            "store": "shop",
            "магазин": "shop",
            "каталог": "shop",
            "orders": "orders",
            "order": "orders",
            "заказы": "orders",
            "staff": "staff",
            "admin": "staff",
            "ops": "staff",
            "сотрудник": "staff",
            "операции": "staff",
            "students": "students",
            "student": "students",
            "pupils": "students",
            "groups": "students",
            "classes": "students",
            "leaderboard": "students",
            "top": "students",
            "ученики": "students",
            "группы": "students",
            "рейтинг": "students",
            "teaching": "teaching",
            "teacher": "teaching",
            "schedule": "teaching",
            "feedback": "teaching",
            "расписание": "teaching",
            "ос": "teaching",
            "setup": "setup",
            "config": "setup",
            "run": "setup",
            "запуск": "setup",
            "настройка": "setup",
        }
        resolved_topic = topic_aliases.get(normalized_topic)
        if resolved_topic == "shop":
            return (
                "Помощь: магазин\n\n"
                "/catalog [поиск] - товары, цены и остатки.\n"
                "/categories - разделы каталога.\n"
                "/product <SKU или товар> - карточка товара и остатки по складам.\n"
                "/quote <SKU> [шт.][, SKU шт.] [| <ученик>] - расчет без создания заказа.\n"
                "/canbuy <SKU> [шт.][, SKU шт.] [| фильтр] - кто может купить без списания AC.\n"
                "/buy <SKU> [шт.][, SKU шт.] [| <ученик>] - заказ из чата.\n"
                "/balance [ученик] - балансы учеников.\n"
                "/miniapp - ссылка на магазин.\n\n"
                "Без команды можно написать название товара или SKU: если это не Contact ID, "
                "бот покажет поиск по каталогу."
            )
        if resolved_topic == "orders":
            return (
                "Помощь: заказы\n\n"
                "/orders [open|issued|cancelled|поиск] - список и быстрые фильтры.\n"
                "/myorders - все заказы, /open - открытые заказы.\n"
                "/order <номер> - карточка заказа.\n"
                "/last [open|issued|cancelled] - последний заказ по статусу.\n"
                "/repeat <номер> - повторить заказ.\n"
                "/cancel <номер> или /void <номер> - отменить заказ.\n"
                "/issue <номер> или /done <номер> - выдать заказ.\n"
                "/return <номер> или /refund <номер> - принять возврат.\n\n"
                "Для действий нужен точный номер заказа. "
                "Если номер неизвестен: /last open или /orders open.\n\n"
                "Backend проверяет права, статусы, складские резервы и баланс."
            )
        if resolved_topic == "students":
            return (
                "Помощь: ученики и группы\n\n"
                "/students [поиск] - список учеников, роли, группы, площадки и балансы.\n"
                "/student <поиск> - карточка ученика: профиль, баланс, заказы и история AC.\n"
                "/groups [поиск] - сводка по группам: ученики, баланс, низкие балансы и заказы.\n"
                "/leaderboard [поиск] - топ учеников по балансу AC; aliases: /top, /leaders.\n"
                "/lowbalance [AC] - ученики с балансом ниже порога; alias: /lowwallets.\n"
                "/balance [ученик] - баланс одного ученика или всех связанных учеников.\n"
                "/ledger [поиск] - операции AC по ученику, причине, направлению или дате.\n"
                "/canbuy <SKU> [шт.][, SKU шт.] [| фильтр] - кто может купить корзину "
                "без списания AC.\n\n"
                "Фильтр можно задавать по имени, группе, площадке, преподавателю или LMS ID."
            )
        if resolved_topic == "staff":
            return (
                "Помощь: staff/admin\n\n"
                "/todo [порог] - ближайшие заказы к выдаче и низкие остатки.\n"
                "/ops [порог] - операционная сводка; aliases: /dashboard, /overview.\n"
                "/sales [open|issued|cancelled|all] - суммы и топ товаров; alias: /revenue.\n"
                "/groups [поиск] - группы, балансы и открытые заказы; alias: /classes.\n"
                "/leaderboard [поиск] - топ учеников по AC; aliases: /top, /leaders.\n"
                "/lowbalance [AC] - ученики с балансом ниже порога; alias: /lowwallets.\n"
                "/stock [порог] - проблемные остатки; alias: /lowstock.\n"
                "/inventory [порог] - расширенный список остатков.\n"
                "/productset <SKU> | <название> | <цена> [| категория] - "
                "создать или обновить товар.\n"
                "/setprice <SKU> <цена> - быстро изменить цену товара; alias: /pricechange.\n"
                "/productstatus <SKU> <active|hidden|archived> - изменить видимость товара.\n"
                "/setphoto <SKU> | <url> - обновить фото товара; "
                "/clearphoto <SKU> - удалить фото.\n"
                "/warehouses - склады, slug и суммарные остатки; alias: /wh.\n"
                "/warehouse <slug> | <название> [| type] [| адрес] - создать или обновить склад.\n"
                "/setstock <SKU> <остаток> [| склад] - поправить фактический остаток.\n"
                "/transfer <SKU> <шт> | <откуда> -> <куда> - переместить свободный остаток.\n"
                "/accrue <AC> <ученик> | <причина> - начислить астрокоины.\n"
                "/access - связи доступа и staff-роли.\n"
                "/accessoff <id> и /accesson <id> - отозвать или восстановить связь доступа.\n"
                "/staffrole <MAX_ID> <role> [active|revoked] [| имя] - "
                "выдать или отозвать staff-роль.\n"
                "/staffoff <MAX_ID> <role> - отозвать staff-роль; "
                "/staffon <MAX_ID> <role> - вернуть.\n"
                "/id - MAX user_id для выдачи ролей."
            )
        if resolved_topic == "teaching":
            return (
                "Помощь: преподавателю\n\n"
                "/schedule - ближайшие занятия и ссылка на расписание.\n"
                "/feedback - открыть подготовку обратных связей.\n"
                "/groups - группы и состав учеников.\n"
                "/students - поиск ученика.\n"
                "/accrue <AC> <ученик> | <причина> - начислить астрокоины.\n\n"
                "В mini-app можно добавить группу, выбрать курс, дату и время, "
                "настроить автоматическую ОС и доставку связанным родителям."
            )
        if resolved_topic == "setup":
            return (
                "Помощь: запуск и настройка\n\n"
                "/status - текущий tenant, backend API, miniapp и marker polling.\n"
                "/setup - открыть этот раздел короткой командой.\n"
                "/version или /about - версия, revision, окружение и runtime-ссылки.\n"
                "/config или /doctor - безопасный локальный config report без секретов.\n"
                "/ready - readiness backend, БД и seed-данных.\n"
                "/health - alias для /ready.\n"
                "/id - MAX user_id, tenant и miniapp URL.\n"
                "/tenant <slug|reset> - сменить tenant в текущем чате или вернуть default.\n"
                "/link <Contact ID> - создать deep link для входа.\n"
                "/miniapp - проверить персональную ссылку.\n\n"
                "Перед polling проверьте .env: MAX_BOT_TOKEN, MAX_BACKEND_API_BASE, "
                "DEFAULT_TENANT_SLUG и MAX_MINIAPP_URL."
            )
        if normalized_topic:
            return (
                f"Раздел помощи `{topic.strip()}` не найден.\n\n"
                "Доступные разделы: /help shop, /help orders, /help students, "
                "/help teaching, /help staff, /help setup."
            )
        return (
            "Добро пожаловать в MAX-бот Алгоритмики.\n\n"
            f"Tenant: {self.default_tenant_slug}\n"
            f"Доменный API: {backend_state}\n\n"
            "Пришлите Contact ID сообщением. Я найду связанных учеников и покажу кнопки "
            "для выбора роли. Если пишете название товара или SKU, я покажу поиск по каталогу.\n\n"
            "Разделы помощи: /help shop, /help orders, /help students, "
            "/help staff, /help setup.\n\n"
            "Команды:\n"
            "/search <текст> - общий поиск по товарам, ученикам и заказам.\n"
            "/catalog [поиск] - активные товары, цены и остатки.\n"
            "/categories - разделы каталога и быстрые поисковые запросы.\n"
            "/product <SKU или товар> - карточка товара, остатки по складам и быстрая покупка.\n"
            "/balance [ученик] - балансы астрокоинов по связанным ученикам.\n"
            "/ledger [поиск] - операции с астрокоинами по ученику, причине или дате.\n"
            "/students [поиск] - ученики, роли, группы и балансы.\n"
            "/groups [поиск] - группы, балансы и открытые заказы; alias: /classes.\n"
            "/leaderboard [поиск] - топ учеников по AC; aliases: /top, /leaders.\n"
            "/student <поиск> - карточка ученика, баланс, заказы и история.\n"
            "/access - связи доступа и staff-роли.\n"
            "/accessoff <id> и /accesson <id> - отозвать или восстановить связь доступа.\n"
            "/staffrole <MAX_ID> <role> [active|revoked] [| имя] - "
            "выдать или отозвать staff-роль.\n"
            "/accrue <AC> <ученик> | <причина> - начислить астрокоины staff/admin.\n"
            "/quote <SKU> [шт.][, SKU шт.] [| <ученик>] - рассчитать корзину без списания AC.\n"
            "/canbuy <SKU> [шт.][, SKU шт.] [| фильтр] - кто может купить без списания AC.\n"
            "/buy <SKU> [шт.][, SKU шт.] [| <ученик>] - оформить заказ из чата.\n"
            "/orders [open|issued|cancelled|поиск] - заказы с быстрым фильтром.\n"
            "/myorders - все заказы, /open - открытые заказы.\n"
            "/order <номер> - детали конкретного заказа.\n"
            "/last [open|issued|cancelled] - последняя карточка заказа по статусу.\n"
            "/repeat <номер> - повторить заказ теми же товарами.\n"
            "/sales [open|issued|cancelled|all] - суммы и топ товаров; alias: /revenue.\n"
            "/me - профиль, роли и связанные ученики.\n"
            "/miniapp - персональная ссылка на магазин.\n"
            "/stock [порог] - проблемные остатки для staff/admin; alias: /lowstock.\n"
            "/inventory [порог] - расширенный список остатков.\n"
            "/lowbalance [AC] - ученики с балансом ниже порога; alias: /lowwallets.\n"
            "/productset <SKU> | <название> | <цена> [| категория] - "
            "создать или обновить товар.\n"
            "/setprice <SKU> <цена> - быстро изменить цену товара; alias: /pricechange.\n"
            "/productstatus <SKU> <active|hidden|archived> - изменить видимость товара.\n"
            "/setphoto <SKU> | <url> - обновить фото товара; "
            "/clearphoto <SKU> - удалить фото.\n"
            "/warehouses - склады, slug и суммарные остатки; alias: /wh.\n"
            "/warehouse <slug> | <название> [| type] [| адрес] - создать или обновить склад.\n"
            "/ops [порог] - операционная сводка заказов и остатков; "
            "aliases: /dashboard, /overview.\n"
            "/todo [порог] - ближайшие заказы к выдаче для staff/admin.\n"
            "/setstock <SKU> <остаток> [| склад] - поправить фактический остаток.\n"
            "/transfer <SKU> <шт> | <откуда> -> <куда> - переместить свободный остаток.\n"
            "/done, /void, /refund <номер> - быстрые aliases выдачи, отмены и возврата.\n"
            "/status - состояние бота и backend API.\n"
            "/setup - запуск, env и диагностические команды.\n"
            "/version или /about - версия, revision и окружение.\n"
            "/config или /doctor - безопасный config report без секретов.\n"
            "/ready - readiness backend, БД и seed-данных.\n"
            "/id - диагностический MAX user_id, tenant и miniapp URL."
        )

    def help_response(self, user_id: int | None = None, topic: str = "") -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        role = self.menu_role(user_id, tenant_slug)
        text = self.role_help_text(role) if role and not topic.strip() else self.help_text(topic)
        return BotResponse(text, self.main_menu_attachments(user_id))

    @staticmethod
    def role_help_text(role: str) -> str:
        if role == "student":
            return (
                "Личный кабинет ученика\n\n"
                "• /balance — мой баланс астрокоинов.\n"
                "• /catalog — магазин подарков.\n"
                "• /orders — мои заказы.\n"
                "• /ledger — история астрокоинов.\n"
                "• /miniapp — открыть полный кабинет.\n\n"
                "Основные действия доступны кнопками ниже."
            )
        if role == "parent":
            return (
                "Семейный кабинет\n\n"
                "• /students — связанные дети.\n"
                "• /balance — балансы детей.\n"
                "• /catalog — магазин подарков.\n"
                "• /orders — семейные заказы.\n"
                "• /miniapp — открыть полный кабинет.\n\n"
                "Обратные связи от преподавателя придут отдельными сообщениями."
            )
        if role == "teacher":
            return (
                "Кабинет преподавателя\n\n"
                "• /schedule — расписание, курсы и обратные связи.\n"
                "• /groups — мои рабочие группы.\n"
                "• /students — ученики.\n"
                "• /accrue <AC> <ученик> | <причина> — начисление AC.\n"
                "• /todo — ближайшие заказы к выдаче.\n\n"
                "Добавление групп и настройка автоматических ОС находятся в расписании."
            )
        return (
            "Кабинет администратора\n\n"
            "• /ops — операционная сводка.\n"
            "• /todo — заказы к выдаче.\n"
            "• /stock — проблемные остатки.\n"
            "• /groups — группы и ученики.\n"
            "• /access — связи и роли.\n"
            "• /miniapp — полный рабочий кабинет.\n\n"
            "Расширенная справка: /help staff."
        )

    def unknown_command_response(self, command: str, user_id: int | None = None) -> BotResponse:
        return BotResponse(
            (
                f"Команда `{command}` не поддерживается.\n\n"
                "Откройте меню кнопками или отправьте /help.\n"
                "Разделы помощи: /help shop, /help orders, /help staff, /help setup.\n"
                "Частые команды: /catalog, /balance, /open, /dashboard, "
                "/setup, /doctor, /version, /miniapp.\n\n"
                "Если вы хотели войти по Contact ID, отправьте только номер без `/`."
            ),
            self.main_menu_attachments(user_id),
        )

    def status_text(self, user_id: int | None = None) -> str:
        settings = get_settings()
        tenant_slug = self.current_tenant_slug(user_id)
        marker = self.load_marker()
        miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
        lines = [
            "Статус MAX-бота",
            "",
            f"Version: {APP_VERSION}",
            f"Revision: {APP_REVISION}",
            f"Tenant: {tenant_slug}",
            f"Default tenant: {self.default_tenant_slug}",
            f"MAX API: {settings.max_api_base}",
            f"MAX API timeout: {settings.max_api_timeout_seconds}s",
            f"MAX poll timeout: {settings.max_poll_timeout_seconds}s",
            f"Backend API: {'подключен' if self.backend_client else 'выключен'}",
            f"Backend URL: {settings.max_backend_api_base or 'не задан'}",
            f"Backend timeout: {settings.max_backend_timeout_seconds}s",
            f"Miniapp: {'настроен' if miniapp_url else 'не настроен'}",
            f"Miniapp URL: {miniapp_url or 'не задан'}",
            f"Marker: {marker if marker is not None else 'нет'}",
            "Polling: long polling",
            (
                "Drop webhooks on start: "
                f"{'да' if settings.max_drop_webhooks_on_start else 'нет'}"
            ),
        ]
        lines.extend(
            [
                "",
                "Проверки:",
                "/version - версия, revision и окружение",
                "/ready - backend, БД и seed-данные",
                "/id - MAX user_id, tenant и miniapp URL",
                "/help setup - запуск и переменные .env",
            ]
        )
        return "\n".join(lines)

    def status_response(self, user_id: int | None = None) -> BotResponse:
        return BotResponse(self.status_text(user_id), self.main_menu_attachments(user_id))

    def version_response(self, user_id: int | None = None) -> BotResponse:
        settings = get_settings()
        tenant_slug = self.current_tenant_slug(user_id)
        miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
        bot_username = self.bot_username()
        lines = [
            "Версия MAX-бота",
            "",
            f"Version: {APP_VERSION}",
            f"Revision: {APP_REVISION}",
            f"Environment: {settings.app_env}",
            f"Tenant: {tenant_slug}",
            f"Default tenant: {self.default_tenant_slug}",
            f"Backend client: {'connected' if self.backend_client else 'offline'}",
            f"Backend URL: {settings.max_backend_api_base or 'not set'}",
            f"Backend timeout: {settings.max_backend_timeout_seconds}s",
            f"MAX API timeout: {settings.max_api_timeout_seconds}s",
            f"MAX poll timeout: {settings.max_poll_timeout_seconds}s",
            f"Miniapp URL: {miniapp_url or 'not set'}",
            f"Bot username: @{bot_username}" if bot_username else "Bot username: not set",
            "",
            "Для глубокой проверки: /doctor или /ready",
        ]
        return BotResponse("\n".join(lines), self.main_menu_attachments(user_id))

    def ready_response(self, user_id: int | None = None) -> BotResponse:
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, readiness недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        try:
            report = self.backend_client.get_readiness()
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось проверить readiness backend API.\n\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            self.format_readiness_text(report),
            self.main_menu_attachments(user_id),
        )

    def config_response(self, user_id: int | None = None) -> BotResponse:
        settings = get_settings()
        return BotResponse(
            self.format_safe_config_text(
                settings.safe_config_report(),
                runtime_backend_connected=self.backend_client is not None,
            ),
            self.main_menu_attachments(user_id),
        )

    def miniapp_response(self, user_id: int | None = None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
        if not miniapp_url:
            return BotResponse(
                (
                    "Miniapp URL не настроен.\n\n"
                    "Задайте MAX_MINIAPP_URL в .env или окружении, затем перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            (
                "Miniapp для текущего профиля:\n"
                f"{miniapp_url}\n\n"
                f"Tenant: {tenant_slug}"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def diagnostic_response(
        self,
        *,
        sender: dict[str, Any],
        chat_id: int | None,
        user_id: int | None,
    ) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
        lines = [
            "Диагностика MAX",
            "",
            f"user_id: {sender.get('user_id')}",
            f"chat_id: {chat_id}",
            f"username: {sender.get('username') or '-'}",
            f"display_name: {display_name_from_user(sender) or '-'}",
            f"tenant: {tenant_slug}",
            f"backend_api: {'подключен' if self.backend_client else 'выключен'}",
            f"miniapp_url: {miniapp_url or 'не настроен'}",
        ]
        lines.extend(
            [
                "",
                "Для выдачи staff-ролей используйте этот user_id.",
                "Текущий tenant можно сменить командой /tenant <slug>.",
            ]
        )
        return BotResponse("\n".join(lines), self.main_menu_attachments(user_id))

    def profile_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="профиль")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_profile_text(session, tenant_slug=tenant_slug, user_id=user_id),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def orders_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="список заказов")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_orders_text(session, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def order_response(self, user_id: int | None = None, order_ref: str = "") -> BotResponse:
        if not order_ref.strip():
            return BotResponse(
                "Укажите номер заказа: /order <номер>",
                self.main_menu_attachments(user_id),
            )

        session_result = self.load_session_response(user_id=user_id, noun="заказ")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        order = self.find_order(session, order_ref)
        if order is None:
            return BotResponse(
                (
                    f"Не нашел заказ `{order_ref}` в доступном профиле.\n\n"
                    "Отправьте /orders, чтобы увидеть доступные номера."
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        return BotResponse(
            self.format_order_details_text(order, tenant_slug=tenant_slug),
            self.order_attachments(order, user_id=user_id, tenant_slug=tenant_slug),
        )

    def latest_order_response(
        self,
        user_id: int | None = None,
        filter_text: str = "",
    ) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="последний заказ")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        orders = list(session.get("orders") or [])
        normalized_filter = filter_text.strip().casefold()
        status_filter = self.order_status_filter(normalized_filter)
        if status_filter is not None:
            orders = [
                order
                for order in orders
                if str(order.get("status") or "") in status_filter
            ]
            empty_text = "Заказов с таким статусом нет."
        elif normalized_filter:
            orders = [
                order
                for order in orders
                if normalized_filter in self.order_search_text(order)
            ]
            empty_text = "Заказов по этому фильтру нет."
        else:
            empty_text = "Заказов пока нет."

        if not orders:
            return BotResponse(
                (
                    f"{empty_text}\n\n"
                    "Команды: /orders, /open, /last issued, /search <текст>."
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        return BotResponse(
            self.format_order_details_text(orders[0], tenant_slug=tenant_slug),
            self.order_attachments(orders[0], user_id=user_id, tenant_slug=tenant_slug),
        )

    def sales_response(self, user_id: int | None = None, filter_text: str = "") -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="сводку продаж")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_sales_text(session, tenant_slug=tenant_slug, filter_text=filter_text),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def teaching_response(self, user_id: int | None = None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        schedule_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="teaching",
        )
        if user_id is None or self.backend_client is None:
            text = "Расписание доступно в mini-app."
            if schedule_url:
                text = f"{text}\n\n{schedule_url}"
            return BotResponse(text, self.cabinet_attachments(user_id, tenant_slug))

        try:
            workspace = self.backend_client.get_teaching_workspace(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось открыть расписание преподавателя.\n\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        schedules = list(workspace.get("schedules") or [])
        lines = ["Расписание преподавателя", ""]
        if not schedules:
            lines.append("Группы пока не добавлены.")
        for schedule in schedules[:8]:
            lesson_time = str(schedule.get("lesson_time") or "")[:5]
            lines.append(
                f"• {lesson_time} · {schedule.get('group_name') or 'Группа'}\n"
                f"  {schedule.get('course_name') or 'Курс'} · урок "
                f"{schedule.get('current_lesson_number') or 1}"
            )
        if len(schedules) > 8:
            lines.append(f"\nЕще групп: {len(schedules) - 8}")
        if schedule_url:
            lines.extend(["", "Добавление групп и подготовка ОС:", schedule_url])
        return BotResponse(
            "\n".join(lines),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def balance_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="баланс")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_balance_text(session, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def lowbalance_response(
        self,
        user_id: int | None = None,
        threshold_text: str = "",
    ) -> BotResponse:
        threshold = 200
        if threshold_text.strip():
            try:
                threshold = int(threshold_text.strip())
            except ValueError:
                return BotResponse(
                    "Порог баланса должен быть числом AC. Например: /lowbalance 200",
                    self.main_menu_attachments(user_id),
                )
        if threshold < 0 or threshold > 1_000_000:
            return BotResponse(
                "Порог баланса должен быть от 0 до 1000000 AC.",
                self.main_menu_attachments(user_id),
            )

        session_result = self.load_session_response(user_id=user_id, noun="низкие балансы")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_lowbalance_text(
                session,
                tenant_slug=tenant_slug,
                threshold=threshold,
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def ledger_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        session_result = self.load_session_response(
            user_id=user_id,
            noun="просмотр истории астрокоинов",
        )
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_ledger_text(session, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def students_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="список учеников")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_students_text(session, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def groups_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="сводку групп")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_groups_text(session, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def leaderboard_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="рейтинг учеников")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_leaderboard_text(session, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def student_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        student_query = query.strip()
        if not student_query:
            return BotResponse(
                "Укажите имя, группу, площадку или LMS ID. Например: /student Алиса",
                self.main_menu_attachments(user_id),
            )

        session_result = self.load_session_response(user_id=user_id, noun="профиль")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        student_result = self.find_unique_student(
            session,
            student_query,
            empty_hint=(
                "Не нашел ученика.\n\n"
                "Проверьте запрос через /students или отправьте Contact ID для привязки."
            ),
            many_hint="Нашлось несколько учеников. Уточните имя, группу, площадку или LMS ID.",
        )
        if isinstance(student_result, BotResponse):
            return BotResponse(student_result.text, self.cabinet_attachments(user_id, tenant_slug))

        return BotResponse(
            self.format_student_details_text(
                session,
                student_result,
                tenant_slug=tenant_slug,
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def search_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        search_query = query.strip()
        if not search_query:
            return BotResponse(
                (
                    "Укажите текст для поиска. Например: /search ручка\n\n"
                    "Ищу по товарам, ученикам и заказам."
                ),
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому общий поиск недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        session_result = self.load_session_response(user_id=user_id, noun="поиск")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        catalog: dict[str, Any] = {}
        catalog_warning: str | None = None
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=False,
            )
        except BackendApiError as exc:
            catalog_warning = format_backend_error(exc)

        return BotResponse(
            self.format_search_text(
                session,
                catalog,
                tenant_slug=tenant_slug,
                query=search_query,
                catalog_warning=catalog_warning,
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def access_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="связи доступа")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_access_text(session, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def access_status_response(
        self,
        user_id: int | None = None,
        *,
        link_id: str = "",
        status: str,
    ) -> BotResponse:
        action_hint = "/accessoff <id>" if status == "revoked" else "/accesson <id>"
        normalized_link_id = link_id.strip()
        if not normalized_link_id:
            return BotResponse(
                (
                    f"Укажите ID связи доступа. Формат: {action_hint}\n\n"
                    "ID можно посмотреть в /access."
                ),
                self.main_menu_attachments(user_id),
            )
        if len(normalized_link_id) < 8:
            return BotResponse(
                "ID связи доступа слишком короткий. Скопируйте ID из /access.",
                self.main_menu_attachments(user_id),
            )
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому управление связями доступа недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            result = self.backend_client.update_access_link_status(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                link_id=normalized_link_id,
                status=status,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось изменить связь доступа через backend API.\n\n"
                    f"ID: {normalized_link_id}\n"
                    f"Статус: {status}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        status_text = result.get("status") or status
        role = result.get("role") or "-"
        student_id = result.get("student_id") or "-"
        return BotResponse(
            (
                "Связь доступа обновлена.\n\n"
                f"ID: {normalized_link_id}\n"
                f"Статус: {status_text}\n"
                f"Роль: {role}\n"
                f"Student ID: {student_id}\n\n"
                "Проверить список: /access"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def staffrole_response(
        self,
        user_id: int | None = None,
        argument: str = "",
        *,
        forced_status: str | None = None,
    ) -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому управление staff-ролями недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_staffrole_command(argument, forced_status=forced_status)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            result = self.backend_client.update_staff_assignment(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                target_max_user_id=parsed.target_max_user_id,
                role=parsed.role,
                status=parsed.status,
                display_name=parsed.display_name,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось изменить staff-роль через backend API.\n\n"
                    f"MAX user_id: {parsed.target_max_user_id}\n"
                    f"Роль: {parsed.role}\n"
                    f"Статус: {parsed.status}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        display_name = (
            result.get("display_name")
            or result.get("username")
            or result.get("max_user_id")
        )
        return BotResponse(
            (
                "Staff-роль обновлена.\n\n"
                f"MAX user_id: {result.get('max_user_id') or parsed.target_max_user_id}\n"
                f"Имя: {display_name or '-'}\n"
                f"Роль: {result.get('role') or parsed.role}\n"
                f"Статус: {result.get('status') or parsed.status}\n\n"
                "Проверить список: /access"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def accrue_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому начисление астрокоинов недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_accrue_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        session_result = self.load_session_response(user_id=user_id, noun="список учеников")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        matches = [
            student
            for student in session.get("students") or []
            if parsed.student_query.casefold() in self.student_search_text(student)
        ]
        if not matches:
            return BotResponse(
                (
                    "Не нашел ученика для начисления.\n\n"
                    "Уточните имя, группу, площадку или LMS ID: "
                    "/accrue 50 алиса | За проект"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )
        if len(matches) > 1:
            lines = [
                "Нашлось несколько учеников. Уточните запрос, начисление не выполнено.",
                "",
            ]
            for student in matches[:8]:
                name = student.get("display_name") or student.get("student_id") or "ученик"
                group = student.get("group_name")
                venue = student.get("venue_name")
                details = " / ".join(str(value) for value in (group, venue) if value)
                suffix = f" - {details}" if details else ""
                lines.append(f"- {name}{suffix}")
            if len(matches) > 8:
                lines.append(f"...и еще {len(matches) - 8}")
            return BotResponse("\n".join(lines), self.cabinet_attachments(user_id, tenant_slug))

        student = matches[0]
        student_id = str(student.get("student_id") or "")
        if not student_id:
            return BotResponse(
                "У найденного ученика нет student_id, начисление не выполнено.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        try:
            result = self.backend_client.accrue_astrocoins(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                student_ids=[student_id],
                amount=parsed.amount,
                reason=parsed.reason,
                comment="MAX bot /accrue",
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось начислить астрокоины через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        student_name = student.get("display_name") or student_id
        total = result.get("total_astrocoins", parsed.amount)
        return BotResponse(
            (
                "Астрокоины начислены.\n\n"
                f"Ученик: {student_name}\n"
                f"Сумма: +{parsed.amount} AC\n"
                f"Причина: {parsed.reason}\n"
                f"Всего начислено: {total} AC"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def quote_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому расчет корзины недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_buy_command(argument)
        if isinstance(parsed, str):
            return BotResponse(
                parsed.replace("/buy", "/quote"),
                self.main_menu_attachments(user_id),
            )

        session_result = self.load_session_response(user_id=user_id, noun="список учеников")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        student: dict[str, Any] | None = None
        balance_hint = "Баланс не проверен: уточните ученика после `|`."
        students = list(session.get("students") or [])
        if parsed.student_query:
            student_result = self.find_unique_student(
                session,
                parsed.student_query,
                empty_hint=(
                    "Не нашел ученика для расчета.\n\n"
                    "Уточните имя, группу, площадку или LMS ID: /quote PEN-LOGO 1 | алиса"
                ),
                many_hint="Нашлось несколько учеников. Уточните запрос, расчет не выполнен.",
            )
            if isinstance(student_result, BotResponse):
                return BotResponse(
                    student_result.text,
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            student = student_result
        elif len(students) == 1:
            student = students[0]
            balance_hint = ""
        elif not students:
            balance_hint = "Баланс не проверен: связанных учеников пока нет."

        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=False,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        products_by_id: dict[str, dict[str, Any]] = {}
        quantities_by_product_id: dict[str, int] = {}
        for item in parsed.items:
            product_result = self.find_unique_product(
                catalog,
                item.product_query,
                empty_hint=(
                    "Не нашел активный товар для расчета.\n\n"
                    "Проверьте SKU или название: /catalog, затем /quote PEN-LOGO 1"
                ),
                many_hint=(
                    "Нашлось несколько товаров. Уточните SKU или название, "
                    "расчет не выполнен."
                ),
            )
            if isinstance(product_result, BotResponse):
                return BotResponse(
                    product_result.text,
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            product_id = str(product_result.get("id") or "")
            if not product_id:
                return BotResponse(
                    "У найденного товара нет product_id, расчет не выполнен.",
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            products_by_id[product_id] = product_result
            quantities_by_product_id[product_id] = (
                quantities_by_product_id.get(product_id, 0) + item.quantity
            )

        total = 0
        item_lines = []
        warnings = []
        for product_id, quantity in quantities_by_product_id.items():
            product = products_by_id[product_id]
            product_name = product.get("name") or product.get("sku") or product_id
            sku = product.get("sku")
            price = int(product.get("price_astrocoins") or 0)
            subtotal = price * quantity
            available = int(product.get("available_quantity") or 0)
            total += subtotal
            sku_text = f" ({sku})" if sku else ""
            item_lines.append(
                f"- {product_name}{sku_text} x{quantity}: {subtotal} AC, остаток {available} шт."
            )
            if available < quantity:
                warnings.append(
                    f"- {product_name}: нужно {quantity} шт., доступно {available} шт."
                )

        lines = [
            "Расчет заказа",
            "",
            "Заказ не создан, астрокоины не списаны.",
            f"Tenant: {tenant_slug}",
            "",
            "Товары:",
            *item_lines,
            f"Итого: {total} AC",
        ]
        if student is not None:
            student_name = student.get("display_name") or student.get("student_id") or "ученик"
            balance = student.get("balance")
            lines.extend(["", f"Ученик: {student_name}"])
            if balance is not None:
                balance_value = int(balance)
                lines.append(f"Баланс: {balance_value} AC")
                lines.append(f"После заказа: {balance_value - total} AC")
                if balance_value < total:
                    warnings.append(
                        f"- Недостаточно AC: баланс {balance_value}, стоимость {total}."
                    )
        elif balance_hint:
            lines.extend(["", balance_hint])

        if warnings:
            lines.extend(["", "Предупреждения:", *warnings])

        lines.extend(["", f"Создать заказ: /buy {argument.strip()}"])
        return BotResponse("\n".join(lines), self.cabinet_attachments(user_id, tenant_slug))

    def canbuy_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому проверка покупки недоступна.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_buy_command(argument)
        if isinstance(parsed, str):
            return BotResponse(
                parsed.replace("/buy", "/canbuy"),
                self.main_menu_attachments(user_id),
            )

        session_result = self.load_session_response(user_id=user_id, noun="балансы учеников")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=False,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        products_by_id: dict[str, dict[str, Any]] = {}
        quantities_by_product_id: dict[str, int] = {}
        for item in parsed.items:
            product_result = self.find_unique_product(
                catalog,
                item.product_query,
                empty_hint=(
                    "Не нашел активный товар для проверки.\n\n"
                    "Проверьте SKU или название: /catalog, затем /canbuy PEN-LOGO 1"
                ),
                many_hint="Нашлось несколько товаров. Уточните SKU или название.",
            )
            if isinstance(product_result, BotResponse):
                return BotResponse(
                    product_result.text,
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            product_id = str(product_result.get("id") or "")
            if not product_id:
                return BotResponse(
                    "У найденного товара нет product_id, проверка не выполнена.",
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            products_by_id[product_id] = product_result
            quantities_by_product_id[product_id] = (
                quantities_by_product_id.get(product_id, 0) + item.quantity
            )

        total = 0
        item_lines: list[str] = []
        stock_warnings: list[str] = []
        for product_id, quantity in quantities_by_product_id.items():
            product = products_by_id[product_id]
            name = product.get("name") or product.get("sku") or product_id
            sku = product.get("sku")
            price = int(product.get("price_astrocoins") or 0)
            available = int(product.get("available_quantity") or 0)
            subtotal = price * quantity
            total += subtotal
            sku_text = f" ({sku})" if sku else ""
            item_lines.append(f"- {name}{sku_text} x{quantity}: {subtotal} AC")
            if available < quantity:
                stock_warnings.append(f"- {name}: нужно {quantity} шт., доступно {available} шт.")

        students = list(session.get("students") or [])
        filter_text = parsed.student_query.strip() if parsed.student_query else ""
        if filter_text:
            normalized_filter = filter_text.casefold()
            students = [
                student
                for student in students
                if normalized_filter in self.student_search_text(student)
            ]
        students.sort(key=lambda student: int(student.get("balance") or 0), reverse=True)
        can_buy = [student for student in students if int(student.get("balance") or 0) >= total]
        cannot_buy = [student for student in students if int(student.get("balance") or 0) < total]

        lines = [
            "Кто может купить",
            "",
            "Заказ не создан, астрокоины не списаны.",
            f"Tenant: {tenant_slug}",
        ]
        if filter_text:
            lines.append(f"Фильтр учеников: {filter_text}")
        lines.extend(["", "Товары:", *item_lines, f"Итого: {total} AC"])

        if stock_warnings:
            lines.extend(["", "Остатки:", *stock_warnings])

        if not students:
            lines.extend(
                [
                    "",
                    "Подходящих учеников не найдено.",
                    "Проверьте /students или уточните фильтр после `|`.",
                ]
            )
            return BotResponse("\n".join(lines), self.cabinet_attachments(user_id, tenant_slug))

        lines.extend(["", f"Хватает баланса: {len(can_buy)}"])
        for student in can_buy[:10]:
            name = student.get("display_name") or student.get("student_id") or "ученик"
            balance = int(student.get("balance") or 0)
            lines.append(f"- {name}: {balance} AC, останется {balance - total} AC")
        if len(can_buy) > 10:
            lines.append(f"...и еще {len(can_buy) - 10}")

        if cannot_buy:
            lines.extend(["", f"Не хватает баланса: {len(cannot_buy)}"])
            for student in cannot_buy[:8]:
                name = student.get("display_name") or student.get("student_id") or "ученик"
                balance = int(student.get("balance") or 0)
                lines.append(f"- {name}: {balance} AC, не хватает {total - balance} AC")
            if len(cannot_buy) > 8:
                lines.append(f"...и еще {len(cannot_buy) - 8}")

        lines.extend(["", f"Создать заказ: /buy {argument.strip()}"])
        return BotResponse("\n".join(lines), self.cabinet_attachments(user_id, tenant_slug))

    def buy_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому заказ из чата недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_buy_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        session_result = self.load_session_response(user_id=user_id, noun="список учеников")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        if parsed.student_query:
            student_result = self.find_unique_student(
                session,
                parsed.student_query,
                empty_hint=(
                    "Не нашел ученика для заказа.\n\n"
                    "Уточните имя, группу, площадку или LMS ID: /buy PEN-LOGO 1 | алиса"
                ),
                many_hint="Нашлось несколько учеников. Уточните запрос, заказ не создан.",
            )
        else:
            student_result = self.default_buy_student(session)
        if isinstance(student_result, BotResponse):
            return BotResponse(student_result.text, self.cabinet_attachments(user_id, tenant_slug))
        student = student_result
        student_id = str(student.get("student_id") or "")
        if not student_id:
            return BotResponse(
                "У найденного ученика нет student_id, заказ не создан.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=False,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        products_by_id: dict[str, dict[str, Any]] = {}
        quantities_by_product_id: dict[str, int] = {}
        for item in parsed.items:
            product_result = self.find_unique_product(
                catalog,
                item.product_query,
                empty_hint=(
                    "Не нашел активный товар для заказа.\n\n"
                    "Проверьте SKU или название: /catalog, затем /buy PEN-LOGO 1 | алиса"
                ),
                many_hint="Нашлось несколько товаров. Уточните SKU или название, заказ не создан.",
            )
            if isinstance(product_result, BotResponse):
                return BotResponse(
                    product_result.text,
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            product = product_result
            product_id = str(product.get("id") or "")
            if not product_id:
                return BotResponse(
                    "У найденного товара нет product_id, заказ не создан.",
                    self.cabinet_attachments(user_id, tenant_slug),
                )
            products_by_id[product_id] = product
            quantities_by_product_id[product_id] = (
                quantities_by_product_id.get(product_id, 0) + item.quantity
            )

        order_items: list[dict[str, Any]] = []
        item_lines: list[str] = []
        total = 0
        for product_id, quantity in quantities_by_product_id.items():
            product = products_by_id[product_id]
            product_name = product.get("name") or product.get("sku") or product_id
            available = int(product.get("available_quantity") or 0)
            if available < quantity:
                return BotResponse(
                    (
                        "Недостаточно товара на складе, заказ не создан.\n\n"
                        f"Товар: {product_name}\n"
                        f"Запрошено: {quantity} шт.\n"
                        f"Доступно: {available} шт."
                    ),
                    self.cabinet_attachments(user_id, tenant_slug),
                )

            price = int(product.get("price_astrocoins") or 0)
            total += price * quantity
            order_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )
            item_lines.append(f"- {product_name} x{quantity}: {price * quantity} AC")

        balance = student.get("balance")
        if balance is not None and int(balance) < total:
            student_name = student.get("display_name") or student_id
            return BotResponse(
                (
                    "Недостаточно астрокоинов, заказ не создан.\n\n"
                    f"Ученик: {student_name}\n"
                    f"Баланс: {int(balance)} AC\n"
                    f"Стоимость: {total} AC"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        try:
            result = self.backend_client.create_order(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                student_id=student_id,
                items=order_items,
                comment="MAX bot /buy",
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось создать заказ через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        order = result.get("order") or {}
        order_number = order.get("order_number") or order.get("id") or "-"
        balance_after = result.get("balance_after")
        student_name = order.get("student_name") or student.get("display_name") or student_id
        lines = [
            "Заказ создан.",
            "",
            f"№{order_number}: {student_name}, {self.order_status_label(order.get('status'))}",
            "Товары:",
            *item_lines,
            f"Сумма: {order.get('total_astrocoins') or total} AC",
        ]
        if balance_after is not None:
            lines.append(f"Баланс после заказа: {balance_after} AC")
        lines.extend(["", f"Детали: /order {order_number}"])
        return BotResponse("\n".join(lines), self.cabinet_attachments(user_id, tenant_slug))

    def load_session_response(
        self,
        *,
        user_id: int | None,
        noun: str,
    ) -> tuple[str, dict[str, Any]] | BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        if self.backend_client is None:
            return BotResponse(
                (
                    f"Backend API не подключен, невозможно загрузить {noun}.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        try:
            session = self.backend_client.get_session(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    f"Не получилось загрузить {noun} через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )
        self.remember_session_role(user_id, tenant_slug, session)
        return tenant_slug, session

    def catalog_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому каталог недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                include_inactive=False,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            self.format_catalog_text(catalog, tenant_slug=tenant_slug, query=query),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def categories_response(self, user_id: int | None = None) -> BotResponse:
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому категории недоступны.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                include_inactive=False,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            self.format_categories_text(catalog, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def warehouses_response(self, user_id: int | None = None) -> BotResponse:
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому список складов недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить склады через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            self.format_warehouses_text(catalog, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def warehouse_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому управление складами недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_warehouse_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            warehouse = self.backend_client.upsert_warehouse(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                slug=parsed.slug,
                name=parsed.name,
                warehouse_type=parsed.warehouse_type,
                address=parsed.address,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось сохранить склад через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        address = warehouse.get("address") or "не задан"
        return BotResponse(
            (
                "Склад сохранен.\n\n"
                f"Tenant: {tenant_slug}\n"
                f"Название: {warehouse.get('name') or parsed.name}\n"
                f"Slug: {warehouse.get('slug') or parsed.slug}\n"
                f"Тип: {warehouse.get('warehouse_type') or parsed.warehouse_type}\n"
                f"Адрес: {address}\n\n"
                "Проверить список: /warehouses"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def product_response(self, user_id: int | None = None, query: str = "") -> BotResponse:
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому карточка товара недоступна.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        product_query = query.strip()
        if not product_query:
            return BotResponse(
                "Укажите SKU или название товара. Например: /product PEN-LOGO",
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                include_inactive=False,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        product_result = self.find_unique_product(
            catalog,
            product_query,
            empty_hint=(
                "Не нашел активный товар.\n\n"
                "Проверьте SKU или название: /catalog, затем /product PEN-LOGO"
            ),
            many_hint="Нашлось несколько товаров. Уточните SKU или название.",
        )
        if isinstance(product_result, BotResponse):
            return BotResponse(product_result.text, self.cabinet_attachments(user_id, tenant_slug))

        return BotResponse(
            self.format_product_text(product_result, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def productset_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому управление товарами недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_productset_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            product = self.backend_client.upsert_product(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                sku=parsed.sku,
                name=parsed.name,
                category_name=parsed.category_name,
                price_astrocoins=parsed.price_astrocoins,
                status=parsed.status,
                description=parsed.description,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось сохранить товар через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"SKU: {parsed.sku}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        name = product.get("name") or parsed.name
        sku = product.get("sku") or parsed.sku
        price_value = product.get("price_astrocoins")
        price = int(price_value if price_value is not None else parsed.price_astrocoins)
        category = product.get("category_name") or parsed.category_name
        status = product.get("status") or parsed.status
        return BotResponse(
            (
                "Товар сохранен.\n\n"
                f"Tenant: {tenant_slug}\n"
                f"SKU: {sku}\n"
                f"Название: {name}\n"
                f"Категория: {category}\n"
                f"Цена: {price} AC\n"
                f"Статус: {status}\n\n"
                f"Карточка: /product {sku}\n"
                f"Остаток: /setstock {sku} 10 | склад"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def setprice_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому изменение цены недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_setprice_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        product_result = self.find_unique_product(
            catalog,
            parsed.product_query,
            empty_hint=(
                "Не нашел товар для изменения цены.\n\n"
                "Проверьте SKU или название: /catalog, затем /setprice PEN-LOGO 120"
            ),
            many_hint="Нашлось несколько товаров. Уточните SKU или название, цена не изменена.",
            include_inactive=True,
        )
        if isinstance(product_result, BotResponse):
            return BotResponse(product_result.text, self.cabinet_attachments(user_id, tenant_slug))

        product = product_result
        sku = str(product.get("sku") or "").strip()
        if not sku:
            return BotResponse(
                "У найденного товара нет SKU, цена не изменена.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        old_price = int(product.get("price_astrocoins") or 0)
        try:
            updated = self.backend_client.upsert_product(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                sku=sku,
                name=str(product.get("name") or sku),
                category_name=str(product.get("category_name") or "Без категории"),
                category_slug=product.get("category_slug"),
                price_astrocoins=parsed.price_astrocoins,
                status=str(product.get("status") or "active"),
                description=product.get("description"),
                photo_url=product.get("photo_url"),
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось изменить цену товара через backend API.\n\n"
                    f"SKU: {sku}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        new_price_value = updated.get("price_astrocoins")
        new_price = int(new_price_value if new_price_value is not None else parsed.price_astrocoins)
        product_name = updated.get("name") or product.get("name") or sku
        return BotResponse(
            (
                "Цена товара обновлена.\n\n"
                f"Товар: {product_name}\n"
                f"SKU: {updated.get('sku') or sku}\n"
                f"Было: {old_price} AC\n"
                f"Стало: {new_price} AC\n\n"
                f"Карточка: /product {updated.get('sku') or sku}"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def productstatus_response(
        self,
        user_id: int | None = None,
        argument: str = "",
        *,
        forced_status: str | None = None,
    ) -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому изменение статуса товара недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_productstatus_command(argument, forced_status=forced_status)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        product_result = self.find_unique_product(
            catalog,
            parsed.product_query,
            empty_hint=(
                "Не нашел товар для изменения статуса.\n\n"
                "Проверьте SKU или название: /catalog, затем /productstatus PEN-LOGO hidden"
            ),
            many_hint="Нашлось несколько товаров. Уточните SKU или название, статус не изменен.",
            include_inactive=True,
        )
        if isinstance(product_result, BotResponse):
            return BotResponse(product_result.text, self.cabinet_attachments(user_id, tenant_slug))

        product = product_result
        sku = str(product.get("sku") or "").strip()
        if not sku:
            return BotResponse(
                "У найденного товара нет SKU, статус не изменен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        old_status = str(product.get("status") or "active")
        price_value = product.get("price_astrocoins")
        price = int(price_value if price_value is not None else 0)
        try:
            updated = self.backend_client.upsert_product(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                sku=sku,
                name=str(product.get("name") or sku),
                category_name=str(product.get("category_name") or "Без категории"),
                category_slug=product.get("category_slug"),
                price_astrocoins=price,
                status=parsed.status,
                description=product.get("description"),
                photo_url=product.get("photo_url"),
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось изменить статус товара через backend API.\n\n"
                    f"SKU: {sku}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        new_status = str(updated.get("status") or parsed.status)
        product_name = updated.get("name") or product.get("name") or sku
        return BotResponse(
            (
                "Статус товара обновлен.\n\n"
                f"Товар: {product_name}\n"
                f"SKU: {updated.get('sku') or sku}\n"
                f"Было: {old_status}\n"
                f"Стало: {new_status}\n\n"
                f"Карточка: /product {updated.get('sku') or sku}"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def setphoto_response(
        self,
        user_id: int | None = None,
        argument: str = "",
        *,
        clear_photo: bool = False,
    ) -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому изменение фото товара недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_setphoto_command(argument, clear_photo=clear_photo)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        product_result = self.find_unique_product(
            catalog,
            parsed.product_query,
            empty_hint=(
                "Не нашел товар для изменения фото.\n\n"
                "Проверьте SKU или название: /catalog, затем /setphoto PEN-LOGO | https://..."
            ),
            many_hint="Нашлось несколько товаров. Уточните SKU или название, фото не изменено.",
            include_inactive=True,
        )
        if isinstance(product_result, BotResponse):
            return BotResponse(product_result.text, self.cabinet_attachments(user_id, tenant_slug))

        product = product_result
        sku = str(product.get("sku") or "").strip()
        if not sku:
            return BotResponse(
                "У найденного товара нет SKU, фото не изменено.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        price_value = product.get("price_astrocoins")
        price = int(price_value if price_value is not None else 0)
        try:
            updated = self.backend_client.upsert_product(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                sku=sku,
                name=str(product.get("name") or sku),
                category_name=str(product.get("category_name") or "Без категории"),
                category_slug=product.get("category_slug"),
                price_astrocoins=price,
                status=str(product.get("status") or "active"),
                description=product.get("description"),
                photo_url=parsed.photo_url,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось изменить фото товара через backend API.\n\n"
                    f"SKU: {sku}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        product_name = updated.get("name") or product.get("name") or sku
        photo_text = updated.get("photo_url") or "не задано"
        return BotResponse(
            (
                "Фото товара обновлено.\n\n"
                f"Товар: {product_name}\n"
                f"SKU: {updated.get('sku') or sku}\n"
                f"Фото: {photo_text}\n\n"
                f"Карточка: /product {updated.get('sku') or sku}"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def stock_response(self, user_id: int | None = None, threshold_text: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому остатки недоступны.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        threshold = 5
        if threshold_text:
            try:
                threshold = max(0, min(int(threshold_text.strip()), 999))
            except ValueError:
                return BotResponse(
                    "Порог остатка должен быть числом. Например: /stock 3",
                    self.main_menu_attachments(user_id),
                )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить остатки через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            self.format_stock_text(catalog, tenant_slug=tenant_slug, threshold=threshold),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def setstock_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому корректировка остатка недоступна.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_setstock_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        product_result = self.find_unique_product(
            catalog,
            parsed.product_query,
            empty_hint=(
                "Не нашел товар для корректировки остатка.\n\n"
                "Проверьте SKU или название: /stock, затем /setstock PEN-LOGO 18"
            ),
            many_hint="Нашлось несколько товаров. Уточните SKU или название, остаток не изменен.",
            include_inactive=True,
        )
        if isinstance(product_result, BotResponse):
            return BotResponse(product_result.text, self.cabinet_attachments(user_id, tenant_slug))
        product = product_result
        product_id = str(product.get("id") or "")
        if not product_id:
            return BotResponse(
                "У найденного товара нет product_id, остаток не изменен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        warehouse_result = self.find_product_warehouse(product, parsed.warehouse_query)
        if isinstance(warehouse_result, BotResponse):
            return BotResponse(
                warehouse_result.text,
                self.cabinet_attachments(user_id, tenant_slug),
            )
        warehouse = warehouse_result
        warehouse_id = str(warehouse.get("warehouse_id") or "")
        if not warehouse_id:
            return BotResponse(
                "У выбранного склада нет warehouse_id, остаток не изменен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        try:
            result = self.backend_client.adjust_inventory(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                available_quantity=parsed.available_quantity,
                comment="MAX bot /setstock",
            )
        except BackendApiError as exc:
            product_name = product.get("name") or product.get("sku") or parsed.product_query
            return BotResponse(
                (
                    f"Не получилось изменить остаток товара {product_name}.\n\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        product_name = product.get("name") or product.get("sku") or parsed.product_query
        warehouse_name = result.get("warehouse_name") or warehouse.get("warehouse_name") or "склад"
        reserved = int(result.get("reserved_quantity") or 0)
        available = int(result.get("available_quantity") or parsed.available_quantity)
        return BotResponse(
            (
                "Остаток обновлен.\n\n"
                f"Товар: {product_name}\n"
                f"Склад: {warehouse_name}\n"
                f"Факт: {available} шт.\n"
                f"Резерв: {reserved} шт."
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def transfer_response(self, user_id: int | None = None, argument: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому перемещение остатков недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        parsed = parse_transfer_command(argument)
        if isinstance(parsed, str):
            return BotResponse(parsed, self.main_menu_attachments(user_id))

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=True,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить каталог через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        product_result = self.find_unique_product(
            catalog,
            parsed.product_query,
            empty_hint=(
                "Не нашел товар для перемещения остатка.\n\n"
                "Проверьте SKU или название: /transfer PEN-LOGO 3 | основной -> витрина"
            ),
            many_hint="Нашлось несколько товаров. Уточните SKU или название, перенос не выполнен.",
            include_inactive=True,
        )
        if isinstance(product_result, BotResponse):
            return BotResponse(product_result.text, self.cabinet_attachments(user_id, tenant_slug))
        product = product_result
        product_id = str(product.get("id") or "")
        if not product_id:
            return BotResponse(
                "У найденного товара нет product_id, перенос не выполнен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        product_name = product.get("name") or product.get("sku") or parsed.product_query
        example = (
            f"/transfer {product.get('sku') or product_name} {parsed.quantity} "
            "| склад 1 -> склад 2"
        )
        source_result = self.find_product_warehouse(
            product,
            parsed.from_warehouse_query,
            action_text="перемещение не выполнено",
            example_command=example,
            not_found_text="Не нашел склад отправки для выбранного товара.",
            many_text="Нашлось несколько складов отправки. Уточните запрос, перенос не выполнен.",
        )
        if isinstance(source_result, BotResponse):
            return BotResponse(source_result.text, self.cabinet_attachments(user_id, tenant_slug))
        source_warehouse = source_result
        source_warehouse_id = str(source_warehouse.get("warehouse_id") or "")
        if not source_warehouse_id:
            return BotResponse(
                "У склада отправки нет warehouse_id, перенос не выполнен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        target_result = self.find_catalog_warehouse(
            catalog,
            parsed.to_warehouse_query,
            not_found_text="Не нашел склад получения.",
            many_text="Нашлось несколько складов получения. Уточните запрос, перенос не выполнен.",
            example_command=example,
        )
        if isinstance(target_result, BotResponse):
            return BotResponse(target_result.text, self.cabinet_attachments(user_id, tenant_slug))
        target_warehouse = target_result
        target_warehouse_id = str(target_warehouse.get("id") or "")
        if not target_warehouse_id:
            return BotResponse(
                "У склада получения нет warehouse_id, перенос не выполнен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )
        if source_warehouse_id == target_warehouse_id:
            return BotResponse(
                "Склады отправки и получения должны отличаться, перенос не выполнен.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        free_quantity = int(source_warehouse.get("available_quantity") or 0)
        if parsed.quantity > free_quantity:
            source_name = source_warehouse.get("warehouse_name") or "склад отправки"
            return BotResponse(
                (
                    "На складе отправки недостаточно свободного остатка.\n\n"
                    f"Товар: {product_name}\n"
                    f"Склад: {source_name}\n"
                    f"Свободно: {free_quantity} шт.\n"
                    f"Запрошено: {parsed.quantity} шт."
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        try:
            result = self.backend_client.transfer_inventory(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                product_id=product_id,
                from_warehouse_id=source_warehouse_id,
                to_warehouse_id=target_warehouse_id,
                quantity=parsed.quantity,
                comment="MAX bot /transfer",
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    f"Не получилось переместить остаток товара {product_name}.\n\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        from_name = result.get("from_warehouse_name") or source_warehouse.get("warehouse_name")
        to_name = result.get("to_warehouse_name") or target_warehouse.get("name")
        return BotResponse(
            (
                "Остаток перемещен.\n\n"
                f"Товар: {product_name}\n"
                f"Количество: {int(result.get('quantity') or parsed.quantity)} шт.\n"
                f"Из: {from_name or 'склад отправки'}\n"
                f"Осталось свободно: {int(result.get('from_available_quantity') or 0)} шт.\n"
                f"В: {to_name or 'склад получения'}\n"
                f"Теперь свободно: {int(result.get('to_available_quantity') or 0)} шт."
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def ops_response(self, user_id: int | None = None, threshold_text: str = "") -> BotResponse:
        summary_result = self.load_ops_summary_response(
            user_id=user_id,
            threshold_text=threshold_text,
            noun="операционную сводку",
            example_command="/ops 3",
        )
        if isinstance(summary_result, BotResponse):
            return summary_result
        tenant_slug, summary = summary_result

        return BotResponse(
            self.format_ops_summary_text(summary, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def todo_response(self, user_id: int | None = None, threshold_text: str = "") -> BotResponse:
        summary_result = self.load_ops_summary_response(
            user_id=user_id,
            threshold_text=threshold_text,
            noun="список задач",
            example_command="/todo 3",
        )
        if isinstance(summary_result, BotResponse):
            return summary_result
        tenant_slug, summary = summary_result

        return BotResponse(
            self.format_todo_text(summary, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def load_ops_summary_response(
        self,
        *,
        user_id: int | None,
        threshold_text: str,
        noun: str,
        example_command: str,
    ) -> tuple[str, dict[str, Any]] | BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    f"Backend API не подключен, невозможно загрузить {noun}.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        threshold = 5
        if threshold_text:
            try:
                threshold = max(0, min(int(threshold_text.strip()), 999))
            except ValueError:
                return BotResponse(
                    f"Порог остатка должен быть числом. Например: {example_command}",
                    self.main_menu_attachments(user_id),
                )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            summary = self.backend_client.get_ops_summary(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                low_stock_threshold=threshold,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    f"Не получилось загрузить {noun} через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )
        return tenant_slug, summary

    def order_action_response(
        self,
        *,
        user_id: int | None,
        action: str,
        order_ref: str,
    ) -> BotResponse:
        labels = {
            "cancel": "отменить",
            "issue": "выдать",
            "return": "принять возврат",
        }
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if not order_ref:
            command = {"cancel": "/cancel", "issue": "/issue", "return": "/return"}[action]
            return BotResponse(
                f"Укажите номер заказа: {command} <номер>",
                self.main_menu_attachments(user_id),
            )
        if self.is_ambiguous_order_ref(order_ref):
            return BotResponse(
                (
                    "Для действия с заказом нужен точный номер, а не `last` или `open`.\n\n"
                    "Сначала откройте нужный заказ: /last open или /orders open.\n"
                    "Затем выполните действие по номеру: /order <номер>, "
                    "/done <номер>, /void <номер>."
                ),
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому действие с заказом недоступно.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            session = self.backend_client.get_session(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить список заказов через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        order = self.find_order(session, order_ref)
        if order is None:
            return BotResponse(
                (
                    f"Не нашел заказ `{order_ref}` в доступном профиле.\n\n"
                    "Отправьте /orders, чтобы увидеть доступные номера."
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        order_id = str(order.get("id") or "")
        if not order_id:
            return BotResponse(
                "У заказа нет backend id. Откройте miniapp и попробуйте действие там.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        try:
            result = self.backend_client.update_order(
                order_id=order_id,
                action=action,
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                comment=f"MAX bot command: {action}",
            )
        except BackendApiError as exc:
            order_number = order.get("order_number") or order_ref
            return BotResponse(
                (
                    f"Не получилось {labels[action]} заказ №{order_number}.\n\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        changed_order = result.get("order") or {}
        balance_after = result.get("balance_after")
        balance_text = (
            f"\nБаланс после операции: {balance_after} AC"
            if balance_after is not None
            else ""
        )
        return BotResponse(
            (
                "Заказ обновлен.\n\n"
                f"{self.format_order_line(changed_order)}"
                f"{balance_text}"
            ),
            self.order_attachments(
                changed_order or order,
                user_id=user_id,
                tenant_slug=tenant_slug,
                fallback_ref=order_ref,
            ),
        )

    def order_action_confirmation_response(
        self,
        *,
        user_id: int | None,
        action: str,
        order_ref: str,
    ) -> BotResponse:
        labels = {
            "repeat": "повторить",
            "cancel": "отменить",
            "issue": "выдать",
            "return": "принять возврат",
        }
        label = labels.get(action)
        if label is None:
            return BotResponse(
                "Действие с заказом пока не поддерживается.",
                self.main_menu_attachments(user_id),
            )
        return BotResponse(
            (
                f"Подтвердите действие: {label} заказ №{order_ref}.\n\n"
                "После подтверждения бот изменит заказ, баланс или остатки."
            ),
            order_confirmation_keyboard(action, order_ref),
        )

    def repeat_order_response(
        self,
        *,
        user_id: int | None,
        order_ref: str,
    ) -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if not order_ref.strip():
            return BotResponse(
                "Укажите номер заказа: /repeat <номер>",
                self.main_menu_attachments(user_id),
            )
        if self.is_ambiguous_order_ref(order_ref):
            return BotResponse(
                (
                    "Для повтора нужен точный номер заказа, а не `last` или `open`.\n\n"
                    "Сначала откройте нужный заказ: /last open или /orders open.\n"
                    "Затем повторите его по номеру: /repeat <номер>."
                ),
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому повтор заказа недоступен.\n\n"
                    "Задайте MAX_BACKEND_API_BASE и перезапустите бота."
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = self.current_tenant_slug(user_id)
        try:
            session = self.backend_client.get_session(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось загрузить список заказов через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        source_order = self.find_order(session, order_ref)
        if source_order is None:
            return BotResponse(
                (
                    f"Не нашел заказ `{order_ref}` в доступном профиле.\n\n"
                    "Отправьте /orders, чтобы увидеть доступные номера."
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        student_id = str(source_order.get("student_id") or "")
        if not student_id:
            return BotResponse(
                "У исходного заказа нет student_id, повтор не создан.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        repeat_items: list[dict[str, Any]] = []
        item_lines: list[str] = []
        for item in source_order.get("items") or []:
            product_id = str(item.get("product_id") or "")
            quantity = int(item.get("quantity") or 0)
            if not product_id or quantity <= 0:
                continue
            repeat_items.append(
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )
            product_name = item.get("product_name") or product_id
            total_price = item.get("total_price_astrocoins")
            total_text = f": {total_price} AC" if total_price is not None else ""
            item_lines.append(f"- {product_name} x{quantity}{total_text}")

        if not repeat_items:
            return BotResponse(
                "В исходном заказе нет позиций для повтора.",
                self.cabinet_attachments(user_id, tenant_slug),
            )

        source_number = source_order.get("order_number") or source_order.get("id") or order_ref
        try:
            result = self.backend_client.create_order(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                student_id=student_id,
                items=repeat_items,
                comment=f"MAX bot /repeat {source_number}",
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    f"Не получилось повторить заказ №{source_number}.\n\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.cabinet_attachments(user_id, tenant_slug),
            )

        order = result.get("order") or {}
        order_number = order.get("order_number") or order.get("id") or "-"
        balance_after = result.get("balance_after")
        student_name = (
            order.get("student_name")
            or source_order.get("student_name")
            or source_order.get("student_id")
            or "ученик"
        )
        lines = [
            "Заказ повторен.",
            "",
            f"Новый заказ: №{order_number}: {student_name}, "
            f"{self.order_status_label(order.get('status'))}",
            f"Исходный заказ: №{source_number}",
            "Товары:",
            *item_lines,
            (
                "Сумма: "
                f"{order.get('total_astrocoins') or source_order.get('total_astrocoins') or '-'} AC"
            ),
        ]
        if balance_after is not None:
            lines.append(f"Баланс после заказа: {balance_after} AC")
        lines.extend(["", f"Детали: /order {order_number}"])
        return BotResponse("\n".join(lines), self.cabinet_attachments(user_id, tenant_slug))

    def format_profile_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        user_id: int,
    ) -> str:
        account = session.get("account") or {}
        students = list(session.get("students") or [])
        staff_roles = [str(role) for role in session.get("staff_roles") or []]
        student_roles = [str(role) for role in session.get("student_roles") or []]
        orders = list(session.get("orders") or [])
        open_statuses = self.open_order_statuses()
        open_orders = [
            order for order in orders if str(order.get("status") or "") in open_statuses
        ]

        lines = [
            "Профиль MAX",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"MAX user_id: {account.get('max_user_id') or user_id}",
        ]
        if account.get("display_name"):
            lines.append(f"Имя: {account['display_name']}")
        if account.get("username"):
            lines.append(f"Username: @{account['username']}")
        if staff_roles:
            lines.append(f"Staff-роли: {', '.join(staff_roles)}")
        if student_roles:
            lines.append(f"Роли доступа: {', '.join(student_roles)}")

        lines.extend(["", "Ученики:"])
        if students:
            for index, student in enumerate(students[:8], start=1):
                details = [
                    student.get("display_name"),
                    student.get("group_name"),
                    student.get("venue_name"),
                ]
                label = " / ".join(str(value) for value in details if value)
                role = student.get("role")
                balance = student.get("balance")
                suffix = []
                if role:
                    suffix.append(str(role))
                if balance is not None:
                    suffix.append(f"{balance} AC")
                meta = f" ({', '.join(suffix)})" if suffix else ""
                lines.append(f"{index}. {label or student.get('student_id')}{meta}")
            if len(students) > 8:
                lines.append(f"...и еще {len(students) - 8}")
        else:
            lines.append("Связанных учеников пока нет.")

        lines.extend(
            [
                "",
                f"Открытые заказы: {len(open_orders)}",
                f"Всего заказов в профиле: {len(orders)}",
            ]
        )
        if not students and not staff_roles:
            lines.extend(
                [
                    "",
                    "Чтобы привязать доступ, отправьте Contact ID или откройте "
                    "deep link от администратора.",
                ]
            )
        return "\n".join(lines)

    def format_orders_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        orders = list(session.get("orders") or [])
        open_statuses = self.open_order_statuses()
        raw_query = query.strip()
        normalized_query = raw_query.casefold()
        filtered_orders = orders
        filter_label = ""
        if normalized_query:
            status_filter = self.order_status_filter(normalized_query)
            if status_filter is not None:
                filtered_orders = [
                    order
                    for order in orders
                    if str(order.get("status") or "") in status_filter
                ]
                filter_label = raw_query
            else:
                filtered_orders = [
                    order
                    for order in orders
                    if normalized_query in self.order_search_text(order)
                ]
                filter_label = raw_query

        open_orders = [
            order for order in orders if str(order.get("status") or "") in open_statuses
        ]
        recent_orders = filtered_orders[:8]

        lines = [
            "Заказы MAX",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"Открытые заказы: {len(open_orders)}",
            f"Всего заказов в профиле: {len(orders)}",
        ]
        if filter_label:
            lines.append(f"Фильтр: {filter_label}")
            lines.append(f"Найдено: {len(filtered_orders)}")

        if not filter_label and open_orders:
            lines.extend(["", "Открытые:"])
            for order in open_orders[:5]:
                lines.append(self.format_order_line(order))
            if len(open_orders) > 5:
                lines.append(f"...и еще {len(open_orders) - 5} открытых")

        lines.extend(["", "Заказы:" if filter_label else "Последние:"])
        if recent_orders:
            for order in recent_orders:
                lines.append(self.format_order_line(order))
        else:
            lines.append("Заказов по этому фильтру нет." if filter_label else "Заказов пока нет.")

        lines.extend(
            [
                "",
                "Фильтры: /orders open, /orders issued, /orders cancelled, /orders <ученик>.",
                "Команды: /order <номер>, /repeat <номер>, /cancel <номер>.",
            ]
        )
        return "\n".join(lines)

    def order_search_text(self, order: dict[str, Any]) -> str:
        values = (
            order.get("id"),
            order.get("order_number"),
            order.get("student_id"),
            order.get("student_name"),
            order.get("status"),
            self.order_status_label(order.get("status")),
            order.get("teacher_name"),
            order.get("venue_name"),
        )
        item_values: list[str] = []
        for item in order.get("items") or []:
            item_values.extend(
                str(value or "")
                for value in (
                    item.get("product_id"),
                    item.get("product_name"),
                    item.get("sku"),
                    item.get("warehouse_name"),
                )
            )
        return " ".join([*(str(value or "") for value in values), *item_values]).casefold()

    def format_order_line(self, order: dict[str, Any]) -> str:
        order_number = order.get("order_number") or order.get("id") or "-"
        student = order.get("student_name") or "ученик"
        status = self.order_status_label(order.get("status"))
        total = order.get("total_astrocoins")
        total_text = f", {total} AC" if total is not None else ""
        return f"№{order_number}: {student}, {status}{total_text}"

    @staticmethod
    def open_order_statuses() -> set[str]:
        return {"created", "reserved", "transferred_to_teacher"}

    @classmethod
    def order_status_filter(cls, query: str) -> set[str] | None:
        normalized = query.strip().casefold()
        if not normalized:
            return None
        open_statuses = cls.open_order_statuses()
        return {
            "open": open_statuses,
            "opened": open_statuses,
            "active": open_statuses,
            "pending": open_statuses,
            "created": {"created"},
            "reserved": {"reserved"},
            "teacher": {"transferred_to_teacher"},
            "issued": {"issued_to_student"},
            "done": {"issued_to_student"},
            "cancelled": {"cancelled"},
            "canceled": {"cancelled"},
            "returned": {"returned"},
            "problem": {"problem"},
            "открытые": open_statuses,
            "открытый": open_statuses,
            "открыт": open_statuses,
            "выданные": {"issued_to_student"},
            "выданный": {"issued_to_student"},
            "выдан": {"issued_to_student"},
            "отмененные": {"cancelled"},
            "отменённые": {"cancelled"},
            "отмененный": {"cancelled"},
            "отменённый": {"cancelled"},
            "отменен": {"cancelled"},
            "отменён": {"cancelled"},
            "возвраты": {"returned"},
            "возврат": {"returned"},
            "проблемные": {"problem"},
            "проблема": {"problem"},
        }.get(normalized)

    @staticmethod
    def is_ambiguous_order_ref(order_ref: str) -> bool:
        return order_ref.strip().casefold() in {
            "last",
            "latest",
            "recent",
            "open",
            "opened",
            "active",
            "pending",
            "последний",
            "последняя",
            "последние",
            "открытый",
            "открытые",
        }

    def order_status_label(self, status: Any) -> str:
        value = str(status or "unknown")
        return {
            "created": "создан",
            "reserved": "зарезервирован",
            "transferred_to_teacher": "передан преподавателю",
            "issued_to_student": "выдан ученику",
            "cancelled": "отменен",
            "returned": "возврат",
            "problem": "проблема",
            "start": "начало",
        }.get(value, value)

    def format_order_details_text(self, order: dict[str, Any], *, tenant_slug: str) -> str:
        order_number = order.get("order_number") or order.get("id") or "-"
        status = str(order.get("status") or "unknown")
        status_label = self.order_status_label(status)
        total = order.get("total_astrocoins")
        created_at = self.format_ledger_date(order.get("created_at"))
        lines = [
            f"Заказ №{order_number}",
            "",
            f"Tenant: {tenant_slug}",
            f"Статус: {status_label}",
            f"Ученик: {order.get('student_name') or order.get('student_id') or 'ученик'}",
        ]
        if total is not None:
            lines.append(f"Сумма: {total} AC")
        if created_at != "дата неизвестна":
            lines.append(f"Создан: {created_at}")
        if order.get("teacher_name"):
            lines.append(f"Преподаватель: {order['teacher_name']}")
        if order.get("venue_name"):
            lines.append(f"Площадка: {order['venue_name']}")

        items = list(order.get("items") or [])
        if items:
            lines.extend(["", "Состав:"])
            for item in items[:10]:
                product_name = item.get("product_name") or item.get("product_id") or "товар"
                quantity = int(item.get("quantity") or 0)
                total_price = int(item.get("total_price_astrocoins") or 0)
                warehouse_name = item.get("warehouse_name")
                warehouse_text = f", {warehouse_name}" if warehouse_name else ""
                lines.append(f"- {product_name} x{quantity}: {total_price} AC{warehouse_text}")
            if len(items) > 10:
                lines.append(f"...и еще {len(items) - 10}")

        history = list(order.get("status_history") or [])
        if history:
            lines.extend(["", "История статусов:"])
            for event in history[-5:]:
                date = self.format_ledger_date(event.get("created_at"))
                from_status = self.order_status_label(event.get("from_status") or "start")
                to_status = self.order_status_label(event.get("to_status"))
                comment = event.get("comment")
                comment_text = f" - {comment}" if comment else ""
                lines.append(f"- {date}: {from_status} -> {to_status}{comment_text}")

        action_lines: list[str] = []
        action_lines.append(f"/repeat {order_number} - повторить заказ")
        if status in self.open_order_statuses():
            action_lines.extend(
                [
                    f"/cancel {order_number} или /void {order_number} - отменить заказ",
                    f"/issue {order_number} или /done {order_number} - выдать заказ",
                ]
            )
        elif status == "issued_to_student":
            action_lines.append(f"/return {order_number} или /refund {order_number} - возврат")
        if action_lines:
            lines.extend(["", "Действия:"])
            lines.extend(action_lines)
        return "\n".join(lines)

    def format_sales_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        filter_text: str = "",
    ) -> str:
        orders = list(session.get("orders") or [])
        normalized_filter = filter_text.strip().casefold()
        filter_label = "все доступные"
        if normalized_filter and normalized_filter not in {"all", "все"}:
            status_filter = self.order_status_filter(normalized_filter)
            if status_filter is None:
                return (
                    "Фильтр сводки не распознан.\n\n"
                    "Формат: /sales [open|issued|cancelled|all]"
                )
            orders = [
                order
                for order in orders
                if str(order.get("status") or "") in status_filter
            ]
            filter_label = normalized_filter

        total_sum = sum(int(order.get("total_astrocoins") or 0) for order in orders)
        status_counts: dict[str, int] = {}
        status_totals: dict[str, int] = {}
        product_totals: dict[str, dict[str, int]] = {}

        for order in orders:
            raw_status = str(order.get("status") or "unknown")
            status_counts[raw_status] = status_counts.get(raw_status, 0) + 1
            status_totals[raw_status] = status_totals.get(raw_status, 0) + int(
                order.get("total_astrocoins") or 0
            )
            for item in order.get("items") or []:
                product_name = str(item.get("product_name") or item.get("product_id") or "товар")
                quantity = int(item.get("quantity") or 0)
                total = int(item.get("total_price_astrocoins") or 0)
                bucket = product_totals.setdefault(product_name, {"quantity": 0, "total": 0})
                bucket["quantity"] += quantity
                bucket["total"] += total

        lines = [
            "Сводка заказов",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"Фильтр: {filter_label}",
            f"Заказов: {len(orders)}",
            f"Сумма: {total_sum} AC",
        ]
        if not orders:
            lines.extend(
                [
                    "",
                    "Заказов по этому фильтру нет.",
                    "Попробуйте /sales all, /sales open или /orders.",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "По статусам:"])
        for status, count in sorted(status_counts.items()):
            lines.append(
                f"- {self.order_status_label(status)}: {count} шт., {status_totals[status]} AC"
            )

        if product_totals:
            lines.extend(["", "Топ товаров:"])
            top_products = sorted(
                product_totals.items(),
                key=lambda item: (item[1]["total"], item[1]["quantity"]),
                reverse=True,
            )
            for product_name, totals in top_products[:8]:
                lines.append(
                    f"- {product_name}: {totals['quantity']} шт., {totals['total']} AC"
                )
            if len(top_products) > 8:
                lines.append(f"...и еще {len(top_products) - 8}")

        lines.extend(["", "Последние заказы:"])
        for order in orders[:5]:
            lines.append(f"- {self.format_order_line(order)}")
        if len(orders) > 5:
            lines.append(f"...и еще {len(orders) - 5}")

        lines.extend(["", "Фильтры: /sales issued, /sales open, /sales cancelled, /sales all"])
        return "\n".join(lines)

    def format_search_text(
        self,
        session: dict[str, Any],
        catalog: dict[str, Any],
        *,
        tenant_slug: str,
        query: str,
        catalog_warning: str | None = None,
    ) -> str:
        normalized_query = query.casefold()
        products = [
            product
            for product in catalog.get("products") or []
            if str(product.get("status") or "active") == "active"
            and normalized_query in self.product_search_text(product)
        ]
        students = [
            student
            for student in session.get("students") or []
            if normalized_query in self.student_search_text(student)
        ]
        orders = [
            order
            for order in session.get("orders") or []
            if normalized_query in self.order_search_text(order)
        ]

        products.sort(
            key=lambda product: (
                int(product.get("available_quantity") or 0) <= 0,
                str(product.get("name") or product.get("sku") or ""),
            )
        )

        lines = [
            "Поиск MAX",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"Запрос: {query}",
        ]
        if catalog_warning:
            lines.append(f"Каталог: не загружен - {catalog_warning}")
        lines.extend(
            [
                f"Товаров: {len(products)}",
                f"Учеников: {len(students)}",
                f"Заказов: {len(orders)}",
            ]
        )

        if products:
            lines.extend(["", "Товары:"])
            for product in products[:5]:
                name = product.get("name") or product.get("sku") or "товар"
                sku = product.get("sku")
                price = int(product.get("price_astrocoins") or 0)
                available = int(product.get("available_quantity") or 0)
                sku_text = f" ({sku})" if sku else ""
                lines.append(f"- {name}{sku_text}: {price} AC, остаток {available} шт.")
                if sku:
                    lines.append(f"  /product {sku} | /buy {sku} 1")
            if len(products) > 5:
                lines.append(f"...и еще {len(products) - 5}")

        if students:
            lines.extend(["", "Ученики:"])
            for student in students[:5]:
                name = student.get("display_name") or student.get("student_id") or "ученик"
                group = student.get("group_name")
                balance = student.get("balance")
                meta = []
                if group:
                    meta.append(str(group))
                if balance is not None:
                    meta.append(f"{int(balance)} AC")
                suffix = f" - {', '.join(meta)}" if meta else ""
                lines.append(f"- {name}{suffix}")
                lines.append(f"  /student {name}")
            if len(students) > 5:
                lines.append(f"...и еще {len(students) - 5}")

        if orders:
            lines.extend(["", "Заказы:"])
            for order in orders[:5]:
                lines.append(f"- {self.format_order_line(order)}")
                number = order.get("order_number") or order.get("id")
                if number:
                    lines.append(f"  /order {number}")
            if len(orders) > 5:
                lines.append(f"...и еще {len(orders) - 5}")

        if not products and not students and not orders:
            lines.extend(
                [
                    "",
                    "Совпадений не найдено.",
                    "Попробуйте SKU, часть имени ученика, номер заказа или /catalog <поиск>.",
                ]
            )
        return "\n".join(lines)

    def format_balance_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        students = list(session.get("students") or [])
        normalized_query = query.strip().casefold()
        if normalized_query:
            students = [
                student
                for student in students
                if normalized_query in self.student_search_text(student)
            ]
        total = sum(int(student.get("balance") or 0) for student in students)
        lines = [
            "Баланс астрокоинов",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]
        if query.strip():
            lines.append(f"Фильтр: {query.strip()}")
            lines.append(f"Найдено учеников: {len(students)}")
        if not students:
            lines.extend(
                [
                    "Подходящих учеников не найдено."
                    if query.strip()
                    else "Связанных учеников пока нет.",
                    "",
                    (
                        "Попробуйте имя, группу, площадку или LMS ID: /balance Алиса"
                        if query.strip()
                        else "Чтобы привязать доступ, отправьте Contact ID или откройте deep link."
                    ),
                ]
            )
            return "\n".join(lines)

        lines.append(f"Всего по профилю: {total} AC")
        lines.extend(["", "Ученики:"])
        for index, student in enumerate(students[:10], start=1):
            name = student.get("display_name") or student.get("student_id") or "ученик"
            group = student.get("group_name")
            balance = int(student.get("balance") or 0)
            group_text = f" / {group}" if group else ""
            lines.append(f"{index}. {name}{group_text}: {balance} AC")
        if len(students) > 10:
            lines.append(f"...и еще {len(students) - 10}")
        return "\n".join(lines)

    def format_lowbalance_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        threshold: int,
    ) -> str:
        students = [
            student
            for student in session.get("students") or []
            if int(student.get("balance") or 0) <= threshold
        ]
        students.sort(key=lambda student: int(student.get("balance") or 0))
        lines = [
            "Низкие балансы AC",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"Порог: {threshold} AC",
            f"Найдено учеников: {len(students)}",
        ]
        if not students:
            lines.extend(
                [
                    "",
                    "У доступных учеников нет балансов ниже порога.",
                    "Изменить порог: /lowbalance 500",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Ученики:"])
        for student in students[:12]:
            name = student.get("display_name") or student.get("student_id") or "ученик"
            group = student.get("group_name")
            venue = student.get("venue_name")
            balance = int(student.get("balance") or 0)
            details = " / ".join(str(value) for value in (group, venue) if value)
            details_text = f" ({details})" if details else ""
            lines.append(f"- {name}{details_text}: {balance} AC")
            lines.append(f"  /accrue 100 {name} | Пополнение баланса")
        if len(students) > 12:
            lines.append(f"...и еще {len(students) - 12}")
        lines.extend(["", "Команды: /balance, /students, /accrue <AC> <ученик> | <причина>"])
        return "\n".join(lines)

    def format_groups_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        students = list(session.get("students") or [])
        normalized_query = query.strip().casefold()
        if normalized_query:
            students = [
                student
                for student in students
                if normalized_query
                in " ".join(
                    str(value or "")
                    for value in (
                        student.get("group_name"),
                        student.get("course_name"),
                        student.get("venue_name"),
                        student.get("teacher_name"),
                    )
                ).casefold()
            ]

        student_groups: dict[str, str] = {}
        buckets: dict[str, dict[str, int]] = {}
        for student in students:
            group = str(student.get("group_name") or "Без группы").strip() or "Без группы"
            student_id = str(student.get("student_id") or "")
            if student_id:
                student_groups[student_id] = group
            balance = int(student.get("balance") or 0)
            bucket = buckets.setdefault(
                group,
                {"students": 0, "balance": 0, "low_balance": 0, "open_orders": 0, "orders": 0},
            )
            bucket["students"] += 1
            bucket["balance"] += balance
            if balance <= 200:
                bucket["low_balance"] += 1

        open_statuses = self.open_order_statuses()
        for order in session.get("orders") or []:
            group = student_groups.get(str(order.get("student_id") or ""))
            if not group or group not in buckets:
                continue
            buckets[group]["orders"] += 1
            if str(order.get("status") or "") in open_statuses:
                buckets[group]["open_orders"] += 1

        lines = [
            "Группы учеников",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]
        if query.strip():
            lines.append(f"Фильтр: {query.strip()}")
        lines.append(f"Групп: {len(buckets)}")
        lines.append(f"Учеников: {sum(bucket['students'] for bucket in buckets.values())}")

        if not buckets:
            lines.extend(
                [
                    "",
                    "Подходящих групп не найдено.",
                    "Проверьте /students или уточните фильтр: /groups python",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Сводка:"])
        sorted_groups = sorted(
            buckets.items(),
            key=lambda item: (item[1]["open_orders"], item[1]["students"], item[0].casefold()),
            reverse=True,
        )
        for group, stats in sorted_groups[:12]:
            average = round(stats["balance"] / stats["students"]) if stats["students"] else 0
            lines.append(
                f"- {group}: {stats['students']} уч., баланс {stats['balance']} AC, "
                f"средний {average} AC"
            )
            lines.append(
                f"  низкий баланс: {stats['low_balance']}, "
                f"открытых заказов: {stats['open_orders']}, всего заказов: {stats['orders']}"
            )
            lines.append(f"  /students {group}")
        if len(sorted_groups) > 12:
            lines.append(f"...и еще {len(sorted_groups) - 12}")

        lines.extend(["", "Команды: /students <группа>, /lowbalance, /sales open"])
        return "\n".join(lines)

    def format_leaderboard_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        students = list(session.get("students") or [])
        normalized_query = query.strip().casefold()
        if normalized_query:
            students = [
                student
                for student in students
                if normalized_query
                in " ".join(
                    str(value or "")
                    for value in (
                        student.get("display_name"),
                        student.get("group_name"),
                        student.get("course_name"),
                        student.get("venue_name"),
                        student.get("teacher_name"),
                        student.get("lms_student_id"),
                    )
                ).casefold()
            ]

        open_statuses = self.open_order_statuses()
        open_orders_by_student: dict[str, int] = {}
        for order in session.get("orders") or []:
            student_id = str(order.get("student_id") or "")
            if not student_id or str(order.get("status") or "") not in open_statuses:
                continue
            open_orders_by_student[student_id] = open_orders_by_student.get(student_id, 0) + 1

        students.sort(
            key=lambda student: (
                int(student.get("balance") or 0),
                str(student.get("display_name") or student.get("student_id") or "").casefold(),
            ),
            reverse=True,
        )

        lines = [
            "Рейтинг учеников по AC",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]
        if query.strip():
            lines.append(f"Фильтр: {query.strip()}")
        lines.append(f"Учеников: {len(students)}")

        if not students:
            lines.extend(
                [
                    "",
                    "Подходящих учеников не найдено.",
                    "Попробуйте /students или уточните фильтр: /leaderboard python",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Топ:"])
        for index, student in enumerate(students[:15], start=1):
            name = student.get("display_name") or student.get("student_id") or "ученик"
            group = student.get("group_name")
            venue = student.get("venue_name")
            balance = int(student.get("balance") or 0)
            details = " / ".join(str(value) for value in (group, venue) if value)
            details_text = f" ({details})" if details else ""
            open_orders = open_orders_by_student.get(str(student.get("student_id") or ""), 0)
            order_text = f", открытых заказов: {open_orders}" if open_orders else ""
            lines.append(f"{index}. {name}{details_text}: {balance} AC{order_text}")
            lines.append(f"   /student {name}")
        if len(students) > 15:
            lines.append(f"...и еще {len(students) - 15}")

        lines.extend(["", "Команды: /groups, /lowbalance, /canbuy PEN-LOGO 1"])
        return "\n".join(lines)

    def format_ledger_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        students_by_id = {
            str(student.get("student_id")): student.get("display_name") or "ученик"
            for student in session.get("students") or []
        }
        ledger = list(session.get("ledger") or [])
        normalized_query = query.strip().casefold()
        if normalized_query:
            ledger = [
                entry
                for entry in ledger
                if normalized_query in self.ledger_search_text(
                    entry,
                    students_by_id=students_by_id,
                )
            ]

        lines = [
            "История астрокоинов",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]
        if query.strip():
            lines.append(f"Фильтр: {query.strip()}")
            lines.append(f"Найдено операций: {len(ledger)}")

        if not ledger:
            lines.extend(
                [
                    "Операций по этому фильтру нет." if query.strip() else "Операций пока нет.",
                    "",
                    (
                        "Попробуйте имя ученика, дату, причину, credit/debit/reversal "
                        "или /ledger без фильтра."
                        if query.strip()
                        else (
                            "Когда будут начисления, покупки, отмены или возвраты, "
                            "они появятся здесь."
                        )
                    ),
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Операции:" if query.strip() else "Последние операции:"])
        for entry in ledger[:10]:
            lines.append(self.format_ledger_line(entry, students_by_id=students_by_id))
        if len(ledger) > 10:
            lines.append(f"...и еще {len(ledger) - 10}")
        lines.extend(["", "Фильтры: /ledger <ученик>, /ledger credit, /ledger 2026-07."])
        return "\n".join(lines)

    def ledger_search_text(
        self,
        entry: dict[str, Any],
        *,
        students_by_id: dict[str, str],
    ) -> str:
        student_id = str(entry.get("student_id") or "")
        values = (
            student_id,
            students_by_id.get(student_id),
            entry.get("direction"),
            entry.get("reason"),
            entry.get("comment"),
            entry.get("created_at"),
            self.format_ledger_date(entry.get("created_at")),
        )
        return " ".join(str(value or "") for value in values).casefold()

    def format_ledger_line(
        self,
        entry: dict[str, Any],
        *,
        students_by_id: dict[str, str],
    ) -> str:
        direction = str(entry.get("direction") or "").lower()
        amount = int(entry.get("amount") or 0)
        sign = "-" if direction == "debit" else "+"
        direction_labels = {
            "credit": "начисление",
            "debit": "списание",
            "reversal": "возврат",
        }
        label = direction_labels.get(direction, direction or "операция")
        student = students_by_id.get(str(entry.get("student_id")), "ученик")
        reason = entry.get("reason") or label
        created_at = self.format_ledger_date(entry.get("created_at"))
        comment = entry.get("comment")
        comment_text = f" ({comment})" if comment else ""
        return f"- {created_at}: {student}, {label} {sign}{amount} AC - {reason}{comment_text}"

    @staticmethod
    def format_ledger_date(value: Any) -> str:
        if isinstance(value, datetime):
            return value.strftime("%d.%m.%Y")
        text = str(value or "").strip()
        if not text:
            return "дата неизвестна"
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text[:10]
        return parsed.strftime("%d.%m.%Y")

    def format_students_text(
        self,
        session: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        students = list(session.get("students") or [])
        normalized_query = query.strip().casefold()
        if normalized_query:
            students = [
                student
                for student in students
                if normalized_query in self.student_search_text(student)
            ]

        lines = [
            "Ученики MAX",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]
        if query.strip():
            lines.append(f"Поиск: {query.strip()}")
        lines.append(f"Найдено учеников: {len(students)}")

        if not students:
            lines.extend(
                [
                    "",
                    "Подходящих учеников не найдено.",
                    "Проверьте Contact ID или откройте miniapp для полного профиля.",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Список:"])
        for index, student in enumerate(students[:12], start=1):
            name = student.get("display_name") or student.get("student_id") or "ученик"
            details = [
                student.get("group_name"),
                student.get("venue_name"),
                student.get("teacher_name"),
            ]
            details_text = " / ".join(str(value) for value in details if value)
            role = student.get("role")
            balance = student.get("balance")
            meta = []
            if role:
                meta.append(str(role))
            if balance is not None:
                meta.append(f"{int(balance)} AC")
            meta_text = f" ({', '.join(meta)})" if meta else ""
            suffix = f" - {details_text}" if details_text else ""
            lines.append(f"{index}. {name}{meta_text}{suffix}")

        if len(students) > 12:
            lines.append(f"...и еще {len(students) - 12}")
        lines.extend(["", "Карточка ученика: /student <имя или LMS ID>"])
        return "\n".join(lines)

    def format_student_details_text(
        self,
        session: dict[str, Any],
        student: dict[str, Any],
        *,
        tenant_slug: str,
    ) -> str:
        student_id = str(student.get("student_id") or "")
        name = student.get("display_name") or student_id or "ученик"
        lines = [
            f"Ученик: {name}",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]

        details = [
            ("Группа", student.get("group_name")),
            ("Курс", student.get("course_name")),
            ("Площадка", student.get("venue_name")),
            ("Преподаватель", student.get("teacher_name")),
            ("Роль доступа", student.get("role")),
            ("LMS ID", student.get("lms_student_id")),
        ]
        for label, value in details:
            if value:
                lines.append(f"{label}: {value}")
        if student_id:
            lines.append(f"Student ID: {student_id}")
        if student.get("balance") is not None:
            lines.append(f"Баланс: {int(student.get('balance') or 0)} AC")

        orders = [
            order
            for order in session.get("orders") or []
            if str(order.get("student_id") or "") == student_id
            or str(order.get("student_name") or "").casefold() == str(name).casefold()
        ]
        open_statuses = self.open_order_statuses()
        open_orders = [
            order for order in orders if str(order.get("status") or "") in open_statuses
        ]
        lines.extend(
            [
                "",
                f"Открытые заказы: {len(open_orders)}",
                f"Всего заказов: {len(orders)}",
            ]
        )
        if orders:
            lines.extend(["", "Последние заказы:"])
            for order in orders[:5]:
                lines.append(f"- {self.format_order_line(order)}")
            if len(orders) > 5:
                lines.append(f"...и еще {len(orders) - 5}")

        ledger = [
            entry
            for entry in session.get("ledger") or []
            if str(entry.get("student_id") or "") == student_id
        ]
        if ledger:
            students_by_id = {student_id: name}
            lines.extend(["", "Последние операции:"])
            for entry in ledger[:5]:
                lines.append(self.format_ledger_line(entry, students_by_id=students_by_id))
            if len(ledger) > 5:
                lines.append(f"...и еще {len(ledger) - 5}")

        buy_hint = f" /buy <SKU> 1 | {name}" if name else " /buy <SKU> 1"
        lines.extend(
            [
                "",
                "Команды:",
                f"/accrue <AC> {name} | причина",
                buy_hint.strip(),
                "/orders",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def student_search_text(student: dict[str, Any]) -> str:
        values = (
            student.get("display_name"),
            student.get("group_name"),
            student.get("course_name"),
            student.get("venue_name"),
            student.get("teacher_name"),
            student.get("lms_student_id"),
            student.get("student_id"),
        )
        return " ".join(str(value or "") for value in values).casefold()

    def find_unique_student(
        self,
        session: dict[str, Any],
        query: str,
        *,
        empty_hint: str,
        many_hint: str,
    ) -> dict[str, Any] | BotResponse:
        normalized_query = query.strip().casefold()
        matches = [
            student
            for student in session.get("students") or []
            if normalized_query in self.student_search_text(student)
        ]
        if not matches:
            return BotResponse(empty_hint)
        if len(matches) > 1:
            lines = [many_hint, ""]
            for student in matches[:8]:
                name = student.get("display_name") or student.get("student_id") or "ученик"
                group = student.get("group_name")
                venue = student.get("venue_name")
                details = " / ".join(str(value) for value in (group, venue) if value)
                suffix = f" - {details}" if details else ""
                lines.append(f"- {name}{suffix}")
            if len(matches) > 8:
                lines.append(f"...и еще {len(matches) - 8}")
            return BotResponse("\n".join(lines))
        return matches[0]

    def default_buy_student(self, session: dict[str, Any]) -> dict[str, Any] | BotResponse:
        students = list(session.get("students") or [])
        if not students:
            return BotResponse(
                "Связанных учеников пока нет, заказ не создан.\n\n"
                "Сначала привяжите доступ по Contact ID или откройте miniapp."
            )
        if len(students) == 1:
            return students[0]

        lines = [
            "Уточните ученика после `|`, заказ не создан.",
            "",
            "Например: /buy PEN-LOGO 2 | Алиса",
            "",
            "Доступные ученики:",
        ]
        for student in students[:8]:
            name = student.get("display_name") or student.get("student_id") or "ученик"
            group = student.get("group_name")
            venue = student.get("venue_name")
            details = " / ".join(str(value) for value in (group, venue) if value)
            suffix = f" - {details}" if details else ""
            lines.append(f"- {name}{suffix}")
        if len(students) > 8:
            lines.append(f"...и еще {len(students) - 8}")
        return BotResponse("\n".join(lines))

    @staticmethod
    def product_search_text(product: dict[str, Any]) -> str:
        values = (
            product.get("name"),
            product.get("sku"),
            product.get("category_name"),
            product.get("category_slug"),
            product.get("description"),
        )
        warehouse_values: list[str] = []
        for warehouse in product.get("warehouses") or []:
            warehouse_values.extend(
                str(value or "")
                for value in (
                    warehouse.get("warehouse_id"),
                    warehouse.get("warehouse_name"),
                    warehouse.get("warehouse_type"),
                )
            )
        return " ".join([*(str(value or "") for value in values), *warehouse_values]).casefold()

    def find_unique_product(
        self,
        catalog: dict[str, Any],
        query: str,
        *,
        empty_hint: str,
        many_hint: str,
        include_inactive: bool = False,
    ) -> dict[str, Any] | BotResponse:
        normalized_query = query.strip().casefold()
        products = [
            product
            for product in catalog.get("products") or []
            if include_inactive or str(product.get("status") or "active") == "active"
        ]
        exact_sku_matches = [
            product
            for product in products
            if str(product.get("sku") or "").casefold() == normalized_query
        ]
        matches = exact_sku_matches or [
            product
            for product in products
            if normalized_query in self.product_search_text(product)
        ]
        if not matches:
            return BotResponse(empty_hint)
        if len(matches) > 1:
            lines = [many_hint, ""]
            for product in matches[:8]:
                name = product.get("name") or product.get("sku") or "товар"
                sku = product.get("sku")
                available = int(product.get("available_quantity") or 0)
                price = int(product.get("price_astrocoins") or 0)
                sku_text = f" ({sku})" if sku else ""
                lines.append(f"- {name}{sku_text}: {price} AC, остаток {available} шт.")
            if len(matches) > 8:
                lines.append(f"...и еще {len(matches) - 8}")
            return BotResponse("\n".join(lines))
        return matches[0]

    def find_product_warehouse(
        self,
        product: dict[str, Any],
        warehouse_query: str | None,
        *,
        action_text: str = "остаток не изменен",
        example_command: str | None = None,
        not_found_text: str = "Не нашел склад для корректировки остатка.",
        many_text: str = "Нашлось несколько складов. Уточните запрос, остаток не изменен.",
    ) -> dict[str, Any] | BotResponse:
        warehouses = list(product.get("warehouses") or [])
        product_name = product.get("name") or product.get("sku") or "товар"
        if not warehouses:
            return BotResponse(f"У товара {product_name} нет складов в каталоге, {action_text}.")
        example = example_command or f"/setstock {product.get('sku') or product_name} 18 | склад"
        if warehouse_query is None:
            if len(warehouses) == 1:
                return warehouses[0]
            lines = [
                f"У товара несколько складов. Уточните склад после `|`, {action_text}.",
                "",
                f"Например: {example}",
                "",
                "Доступные склады:",
            ]
            for warehouse in warehouses[:8]:
                name = warehouse.get("warehouse_name") or warehouse.get("warehouse_id") or "склад"
                available = int(warehouse.get("available_quantity") or 0)
                reserved = int(warehouse.get("reserved_quantity") or 0)
                lines.append(f"- {name}: {available} шт., резерв {reserved}")
            if len(warehouses) > 8:
                lines.append(f"...и еще {len(warehouses) - 8}")
            return BotResponse("\n".join(lines))

        normalized_query = warehouse_query.strip().casefold()
        matches = [
            warehouse
            for warehouse in warehouses
            if normalized_query
            in " ".join(
                str(value or "")
                for value in (
                    warehouse.get("warehouse_id"),
                    warehouse.get("warehouse_name"),
                    warehouse.get("warehouse_type"),
                )
            ).casefold()
        ]
        if not matches:
            return BotResponse(
                f"{not_found_text}\n\n"
                f"Проверьте название склада: {example}"
            )
        if len(matches) > 1:
            lines = [many_text, ""]
            for warehouse in matches[:8]:
                name = warehouse.get("warehouse_name") or warehouse.get("warehouse_id") or "склад"
                available = int(warehouse.get("available_quantity") or 0)
                reserved = int(warehouse.get("reserved_quantity") or 0)
                lines.append(f"- {name}: {available} шт., резерв {reserved}")
            if len(matches) > 8:
                lines.append(f"...и еще {len(matches) - 8}")
            return BotResponse("\n".join(lines))
        return matches[0]

    @staticmethod
    def find_catalog_warehouse(
        catalog: dict[str, Any],
        warehouse_query: str,
        *,
        not_found_text: str,
        many_text: str,
        example_command: str,
    ) -> dict[str, Any] | BotResponse:
        warehouses = list(catalog.get("warehouses") or [])
        normalized_query = warehouse_query.strip().casefold()
        matches = [
            warehouse
            for warehouse in warehouses
            if normalized_query
            in " ".join(
                str(value or "")
                for value in (
                    warehouse.get("id"),
                    warehouse.get("slug"),
                    warehouse.get("name"),
                    warehouse.get("warehouse_type"),
                    warehouse.get("address"),
                )
            ).casefold()
        ]
        if not matches:
            return BotResponse(f"{not_found_text}\n\nПроверьте склад: {example_command}")
        if len(matches) > 1:
            lines = [many_text, ""]
            for warehouse in matches[:8]:
                name = warehouse.get("name") or warehouse.get("slug") or warehouse.get("id")
                slug = warehouse.get("slug")
                slug_text = f" ({slug})" if slug else ""
                lines.append(f"- {name}{slug_text}")
            if len(matches) > 8:
                lines.append(f"...и еще {len(matches) - 8}")
            return BotResponse("\n".join(lines))
        return matches[0]

    def format_access_text(self, session: dict[str, Any], *, tenant_slug: str) -> str:
        access_links = list(session.get("access_links") or [])
        staff_assignments = list(session.get("staff_assignments") or [])
        staff_roles = [str(role) for role in session.get("staff_roles") or []]
        student_roles = [str(role) for role in session.get("student_roles") or []]

        lines = [
            "Доступы MAX",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"Ваши staff-роли: {', '.join(staff_roles) if staff_roles else 'нет'}",
            f"Ваши роли у учеников: {', '.join(student_roles) if student_roles else 'нет'}",
            f"Связей доступа: {len(access_links)}",
            f"Staff-назначений: {len(staff_assignments)}",
        ]

        if access_links:
            lines.extend(["", "Связи доступа:"])
            for link in access_links[:10]:
                link_id = str(link.get("id") or "")
                short_id = link_id[:8] if link_id else "-"
                student = link.get("student_name") or link.get("student_id") or "ученик"
                group = link.get("group_name")
                max_user_id = link.get("max_user_id")
                role = link.get("role") or "role"
                status = link.get("status") or "status"
                display_name = link.get("display_name") or link.get("username") or max_user_id
                group_text = f" / {group}" if group else ""
                lines.append(
                    f"- #{short_id} {student}{group_text}: {role}, {status}, MAX {display_name}"
                )
                if link_id:
                    action = "accessoff" if str(status) == "active" else "accesson"
                    lines.append(f"  ID: {link_id}")
                    lines.append(f"  /{action} {link_id}")
            if len(access_links) > 10:
                lines.append(f"...и еще {len(access_links) - 10}")
        else:
            lines.extend(["", "Связей доступа пока нет."])

        if staff_assignments:
            lines.extend(["", "Staff-роли:"])
            for assignment in staff_assignments[:10]:
                max_user_id = assignment.get("max_user_id")
                display_name = (
                    assignment.get("display_name")
                    or assignment.get("username")
                    or f"MAX {max_user_id}"
                )
                role = assignment.get("role") or "role"
                status = assignment.get("status") or "status"
                lines.append(f"- {display_name}: {role}, {status}")
            if len(staff_assignments) > 10:
                lines.append(f"...и еще {len(staff_assignments) - 10}")

        return "\n".join(lines)

    def format_readiness_text(self, report: dict[str, Any]) -> str:
        checks = report.get("checks") or {}
        database = checks.get("database") or {}
        app_data = checks.get("app_data") or {}
        errors = [str(value) for value in report.get("errors") or []]
        warnings = [str(value) for value in report.get("warnings") or []]

        lines = [
            "Readiness backend",
            "",
            f"Status: {report.get('status') or 'unknown'}",
            f"Environment: {report.get('environment') or '-'}",
            f"Service: {report.get('service') or '-'}",
            f"Tenant: {report.get('default_tenant_slug') or '-'}",
            "",
            f"Database: {database.get('status') or 'unknown'}",
        ]
        if database.get("message"):
            lines.append(f"- {database['message']}")
        if database.get("reason"):
            lines.append(f"- reason: {database['reason']}")

        lines.append(f"App data: {app_data.get('status') or 'unknown'}")
        if app_data.get("message"):
            lines.append(f"- {app_data['message']}")
        counts = [
            f"{key}={app_data[key]}"
            for key in ("products", "warehouses", "students", "contacts")
            if key in app_data
        ]
        if counts:
            lines.append(f"- {', '.join(counts)}")
        if app_data.get("missing"):
            lines.append(f"- missing: {', '.join(str(value) for value in app_data['missing'])}")
        if app_data.get("seed_command"):
            lines.append(f"- seed: {app_data['seed_command']}")
        if app_data.get("next_step"):
            lines.append(f"- next: {app_data['next_step']}")

        if errors:
            lines.extend(["", "Errors:"])
            lines.extend(f"- {error_text}" for error_text in errors[:6])
        if warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning_text}" for warning_text in warnings[:6])
        return "\n".join(lines)

    def format_safe_config_text(
        self,
        report: dict[str, Any],
        *,
        runtime_backend_connected: bool | None = None,
    ) -> str:
        errors = [str(value) for value in report.get("errors") or []]
        warnings = [str(value) for value in report.get("warnings") or []]
        lines = [
            "Конфигурация бота",
            "",
            f"Status: {report.get('status') or 'unknown'}",
            f"Environment: {report.get('environment') or '-'}",
            f"Service: {report.get('service') or '-'}",
            f"Bot mode: {report.get('bot_mode') or '-'}",
            f"Default tenant: {report.get('default_tenant_slug') or '-'}",
            f"MAX API: {report.get('max_api_base') or '-'}",
            f"MAX API timeout: {report.get('max_api_timeout_seconds') or '-'}s",
            f"MAX poll timeout: {report.get('max_poll_timeout_seconds') or '-'}s",
            f"MAX bot token: {report.get('max_bot_token') or 'missing'}",
            f"Backend API: {report.get('max_backend_api_base') or 'disabled'}",
            f"Backend timeout: {report.get('max_backend_timeout_seconds') or '-'}s",
            f"Miniapp URL: {report.get('max_miniapp_url') or 'disabled'}",
            (
                "Drop webhooks on start: "
                f"{'true' if report.get('max_drop_webhooks_on_start') else 'false'}"
            ),
            f"Database URL: {report.get('database_url') or 'missing'}",
            f"Redis URL: {report.get('redis_url') or 'missing'}",
            f"Rate limit: {report.get('rate_limit_backend') or '-'}",
            f"Google Sheets: {report.get('google_sheets') or 'disabled'}",
            f"Sentry: {report.get('sentry') or 'disabled'}",
        ]
        if runtime_backend_connected is not None:
            lines.append(
                "Runtime backend client: "
                f"{'connected' if runtime_backend_connected else 'offline'}"
            )
        if errors:
            lines.extend(["", "Errors:"])
            lines.extend(f"- {error_text}" for error_text in errors[:8])
        if warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning_text}" for warning_text in warnings[:8])
        lines.extend(
            [
                "",
                "Команды: /status, /ready, /id, /help setup",
            ]
        )
        return "\n".join(lines)

    def format_catalog_text(
        self,
        catalog: dict[str, Any],
        *,
        tenant_slug: str,
        query: str = "",
    ) -> str:
        products = [
            product
            for product in catalog.get("products") or []
            if str(product.get("status") or "active") == "active"
        ]
        normalized_query = query.strip().casefold()
        if normalized_query:
            products = [
                product
                for product in products
                if normalized_query
                in " ".join(
                    str(value or "")
                    for value in (
                        product.get("name"),
                        product.get("sku"),
                        product.get("category_name"),
                    )
                ).casefold()
            ]

        products.sort(
            key=lambda product: (
                int(product.get("available_quantity") or 0) <= 0,
                str(product.get("category_name") or ""),
                str(product.get("name") or product.get("sku") or ""),
            )
        )

        lines = [
            "Каталог магазина",
            "",
            f"Tenant: {catalog.get('tenant_slug') or tenant_slug}",
        ]
        if query.strip():
            lines.append(f"Поиск: {query.strip()}")
        lines.append(f"Найдено товаров: {len(products)}")

        if not products:
            lines.extend(
                [
                    "",
                    "Подходящих активных товаров не найдено.",
                    "Откройте miniapp, чтобы посмотреть полный каталог.",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Доступные товары:"])
        for product in products[:10]:
            name = product.get("name") or product.get("sku") or "товар"
            sku = product.get("sku")
            category = product.get("category_name")
            price = int(product.get("price_astrocoins") or 0)
            available = int(product.get("available_quantity") or 0)
            details = [f"{price} AC", f"остаток {available} шт."]
            if category:
                details.append(str(category))
            sku_text = f" ({sku})" if sku else ""
            lines.append(f"- {name}{sku_text}: {', '.join(details)}")

        if len(products) > 10:
            lines.append(f"...и еще {len(products) - 10}")
        lines.extend(
            [
                "",
                "Карточка товара: /product <SKU>",
                "Заказ из чата: /buy <SKU> [шт.][, SKU шт.] [| <ученик>]",
            ]
        )
        return "\n".join(lines)

    def format_categories_text(self, catalog: dict[str, Any], *, tenant_slug: str) -> str:
        buckets: dict[str, dict[str, int]] = {}
        for product in catalog.get("products") or []:
            if str(product.get("status") or "active") != "active":
                continue
            category = str(product.get("category_name") or "Без категории").strip()
            if not category:
                category = "Без категории"
            bucket = buckets.setdefault(category, {"products": 0, "available": 0})
            bucket["products"] += 1
            bucket["available"] += int(product.get("available_quantity") or 0)

        lines = [
            "Категории магазина",
            "",
            f"Tenant: {catalog.get('tenant_slug') or tenant_slug}",
            f"Категорий: {len(buckets)}",
        ]

        if not buckets:
            lines.extend(
                [
                    "",
                    "Активных категорий пока нет.",
                    "Добавьте товары в miniapp или проверьте seed-данные.",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Разделы:"])
        for category, stats in sorted(
            buckets.items(),
            key=lambda item: (item[0].casefold() == "без категории", item[0].casefold()),
        )[:12]:
            lines.append(
                f"- {category}: {stats['products']} тов., остаток {stats['available']} шт."
            )
            lines.append(f"  /catalog {category}")
        if len(buckets) > 12:
            lines.append(f"...и еще {len(buckets) - 12}")
        return "\n".join(lines)

    def format_warehouses_text(self, catalog: dict[str, Any], *, tenant_slug: str) -> str:
        warehouses = list(catalog.get("warehouses") or [])
        products = list(catalog.get("products") or [])
        product_counts: dict[str, int] = {}
        stock_totals: dict[str, int] = {}
        free_totals: dict[str, int] = {}

        for product in products:
            for warehouse in product.get("warehouses") or []:
                warehouse_id = str(warehouse.get("warehouse_id") or "")
                if not warehouse_id:
                    continue
                product_counts[warehouse_id] = product_counts.get(warehouse_id, 0) + 1
                stock_totals[warehouse_id] = stock_totals.get(warehouse_id, 0) + int(
                    warehouse.get("stock_quantity") or 0
                )
                free_totals[warehouse_id] = free_totals.get(warehouse_id, 0) + int(
                    warehouse.get("available_quantity") or 0
                )

        lines = [
            "Склады магазина",
            "",
            f"Tenant: {catalog.get('tenant_slug') or tenant_slug}",
            f"Складов: {len(warehouses)}",
        ]
        if not warehouses:
            lines.extend(
                [
                    "",
                    "Склады пока не заведены.",
                    "Добавьте склад в miniapp: Операции -> Склады.",
                ]
            )
            return "\n".join(lines)

        for warehouse in warehouses[:12]:
            warehouse_id = str(warehouse.get("id") or "")
            name = warehouse.get("name") or warehouse.get("slug") or warehouse_id or "склад"
            slug = warehouse.get("slug")
            warehouse_type = warehouse.get("warehouse_type") or "warehouse"
            address = warehouse.get("address")
            lines.extend(["", f"- {name}"])
            if slug:
                lines.append(f"  slug: {slug}")
            lines.append(f"  тип: {warehouse_type}")
            if address:
                lines.append(f"  адрес: {address}")
            if warehouse_id:
                lines.append(
                    "  остатки: "
                    f"{stock_totals.get(warehouse_id, 0)} шт., "
                    f"свободно {free_totals.get(warehouse_id, 0)} шт., "
                    f"товаров {product_counts.get(warehouse_id, 0)}"
                )

        if len(warehouses) > 12:
            lines.append(f"...и еще {len(warehouses) - 12}")

        lines.extend(
            [
                "",
                "Команды:",
                "/stock - проблемные остатки",
                "/setstock <SKU> <остаток> | <склад>",
                "/transfer <SKU> <шт> | <откуда> -> <куда>",
            ]
        )
        return "\n".join(lines)

    def format_product_text(self, product: dict[str, Any], *, tenant_slug: str) -> str:
        name = product.get("name") or product.get("sku") or "товар"
        sku = product.get("sku")
        status = str(product.get("status") or "active")
        category = product.get("category_name")
        price = int(product.get("price_astrocoins") or 0)
        available = int(product.get("available_quantity") or 0)
        reserved = int(product.get("reserved_quantity") or 0)
        description = str(product.get("description") or "").strip()

        lines = [
            f"Товар: {name}",
            "",
            f"Tenant: {tenant_slug}",
        ]
        if sku:
            lines.append(f"SKU: {sku}")
        if category:
            lines.append(f"Категория: {category}")
        lines.extend(
            [
                f"Цена: {price} AC",
                f"Остаток: {available} шт.",
            ]
        )
        if reserved:
            lines.append(f"В резерве: {reserved} шт.")
        if status != "active":
            lines.append(f"Статус: {status}")

        warehouses = list(product.get("warehouses") or [])
        if warehouses:
            lines.extend(["", "Склады:"])
            for warehouse in warehouses[:8]:
                warehouse_name = (
                    warehouse.get("warehouse_name")
                    or warehouse.get("warehouse_id")
                    or "склад"
                )
                warehouse_available = int(warehouse.get("available_quantity") or 0)
                warehouse_reserved = int(warehouse.get("reserved_quantity") or 0)
                suffix = f", резерв {warehouse_reserved}" if warehouse_reserved else ""
                lines.append(f"- {warehouse_name}: {warehouse_available} шт.{suffix}")
            if len(warehouses) > 8:
                lines.append(f"...и еще {len(warehouses) - 8}")

        if description:
            if len(description) <= 240:
                short_description = description
            else:
                short_description = f"{description[:237].rstrip()}..."
            lines.extend(["", short_description])

        if sku and available > 0:
            lines.extend(["", f"Купить: /buy {sku} 1"])
        elif sku:
            lines.extend(["", f"Нет в наличии. Проверить похожие товары: /catalog {sku}"])
        return "\n".join(lines)

    def format_stock_text(
        self,
        catalog: dict[str, Any],
        *,
        tenant_slug: str,
        threshold: int,
    ) -> str:
        products = list(catalog.get("products") or [])
        rows: list[tuple[int, str]] = []
        zero_count = 0
        low_count = 0
        inactive_count = 0

        for product in products:
            status = str(product.get("status") or "active")
            if status != "active":
                inactive_count += 1
            product_name = product.get("name") or product.get("sku") or "товар"
            warehouses = list(product.get("warehouses") or [])
            if not warehouses:
                available = int(product.get("available_quantity") or 0)
                if available == 0:
                    zero_count += 1
                elif available <= threshold:
                    low_count += 1
                if available <= threshold:
                    rows.append((available, f"{product_name}: {available} шт., склад не указан"))
                continue

            for warehouse in warehouses:
                available = int(warehouse.get("available_quantity") or 0)
                if available == 0:
                    zero_count += 1
                elif available <= threshold:
                    low_count += 1
                if available <= threshold:
                    warehouse_name = warehouse.get("warehouse_name") or "склад"
                    rows.append((available, f"{product_name}: {available} шт., {warehouse_name}"))

        rows.sort(key=lambda item: (item[0], item[1]))
        lines = [
            "Остатки магазина",
            "",
            f"Tenant: {catalog.get('tenant_slug') or tenant_slug}",
            f"Порог: ≤ {threshold} шт.",
            f"Товаров в каталоге: {len(products)}",
            f"Скрытых/архивных: {inactive_count}",
            f"Нулевых складских позиций: {zero_count}",
            f"Низких складских позиций: {low_count}",
        ]

        if rows:
            lines.extend(["", "Проблемные остатки:"])
            for _, row in rows[:12]:
                lines.append(f"- {row}")
            if len(rows) > 12:
                lines.append(f"...и еще {len(rows) - 12}")
        else:
            lines.extend(["", "Проблемных остатков по выбранному порогу нет."])
        return "\n".join(lines)

    def format_ops_summary_text(self, summary: dict[str, Any], *, tenant_slug: str) -> str:
        statuses = {
            str(item.get("status") or ""): int(item.get("count") or 0)
            for item in summary.get("order_statuses") or []
        }
        low_stock = list(summary.get("low_stock") or [])
        recent_open_orders = list(summary.get("recent_open_orders") or [])
        threshold = int(summary.get("low_stock_threshold") or 0)
        lines = [
            "Операционная сводка",
            "",
            f"Tenant: {summary.get('tenant_slug') or tenant_slug}",
            f"Роль: {summary.get('staff_role') or 'staff'}",
            f"Заказов всего: {int(summary.get('total_orders') or 0)}",
            f"Открытых заказов: {int(summary.get('open_orders') or 0)}",
            f"Ожидают выдачи: {int(summary.get('pending_issue_orders') or 0)}",
            f"Активных товаров: {int(summary.get('active_products') or 0)}",
            f"Складов: {int(summary.get('warehouses') or 0)}",
            (
                "Остаток/резерв: "
                f"{int(summary.get('total_stock_quantity') or 0)} / "
                f"{int(summary.get('total_reserved_quantity') or 0)} шт."
            ),
        ]

        if statuses:
            lines.extend(["", "Статусы заказов:"])
            for status, count in sorted(statuses.items()):
                lines.append(f"- {self.order_status_label(status)}: {count}")

        if recent_open_orders:
            lines.extend(["", "Ближайшие открытые:"])
            for order in recent_open_orders[:6]:
                number = order.get("order_number") or order.get("id") or "?"
                student = order.get("student_name") or "ученик"
                status = self.order_status_label(order.get("status"))
                total = int(order.get("total_astrocoins") or 0)
                lines.append(f"- #{number}: {student}, {status}, {total} AC")
            if len(recent_open_orders) > 6:
                lines.append(f"...и еще {len(recent_open_orders) - 6}")

        if low_stock:
            lines.extend(["", f"Остатки <= {threshold} шт.:"])
            for item in low_stock[:8]:
                product_name = item.get("product_name") or item.get("sku") or "товар"
                warehouse_name = item.get("warehouse_name") or "склад"
                available = int(item.get("available_quantity") or 0)
                reserved = int(item.get("reserved_quantity") or 0)
                lines.append(
                    f"- {product_name}: {available} шт., резерв {reserved}, {warehouse_name}"
                )
            if len(low_stock) > 8:
                lines.append(f"...и еще {len(low_stock) - 8}")
        else:
            lines.extend(["", f"Остатков <= {threshold} шт. нет."])

        lines.extend(["", "Команды: /orders, /order <номер>, /stock"])
        return "\n".join(lines)

    def format_todo_text(self, summary: dict[str, Any], *, tenant_slug: str) -> str:
        recent_open_orders = list(summary.get("recent_open_orders") or [])
        low_stock = list(summary.get("low_stock") or [])
        threshold = int(summary.get("low_stock_threshold") or 0)
        lines = [
            "Задачи магазина",
            "",
            f"Tenant: {summary.get('tenant_slug') or tenant_slug}",
            f"Роль: {summary.get('staff_role') or 'staff'}",
            f"Открытых заказов: {int(summary.get('open_orders') or 0)}",
            f"Ожидают выдачи: {int(summary.get('pending_issue_orders') or 0)}",
        ]

        if recent_open_orders:
            lines.extend(["", "Ближайшие заказы:"])
            for order in recent_open_orders[:8]:
                number = order.get("order_number") or order.get("id") or "?"
                student = order.get("student_name") or "ученик"
                status = self.order_status_label(order.get("status"))
                total = int(order.get("total_astrocoins") or 0)
                lines.append(f"- №{number}: {student}, {status}, {total} AC")
                lines.append(f"  /done {number} | /issue {number} | /order {number}")
            if len(recent_open_orders) > 8:
                lines.append(f"...и еще {len(recent_open_orders) - 8}")
        else:
            lines.extend(["", "Открытых заказов для обработки нет."])

        if low_stock:
            lines.extend(["", f"Низкие остатки <= {threshold} шт.:"])
            for item in low_stock[:5]:
                product_name = item.get("product_name") or item.get("sku") or "товар"
                warehouse_name = item.get("warehouse_name") or "склад"
                available = int(item.get("available_quantity") or 0)
                reserved = int(item.get("reserved_quantity") or 0)
                lines.append(
                    f"- {product_name}: {available} шт., резерв {reserved}, {warehouse_name}"
                )
            if len(low_stock) > 5:
                lines.append(f"...и еще {len(low_stock) - 5}")

        lines.extend(["", "Команды: /ops, /stock, /orders"])
        return "\n".join(lines)

    def find_order(self, session: dict[str, Any], order_ref: str) -> dict[str, Any] | None:
        normalized = order_ref.strip().lower().lstrip("#№")
        if not normalized:
            return None
        for order in session.get("orders") or []:
            candidates = {
                str(order.get("id") or "").lower(),
                str(order.get("order_number") or "").lower(),
            }
            if normalized in candidates:
                return order
        return None

    def current_tenant_slug(self, user_id: int | None) -> str:
        if user_id is not None:
            return self.user_tenant_slugs.get(user_id, self.default_tenant_slug)
        return self.default_tenant_slug

    def remember_session_role(
        self,
        user_id: int,
        tenant_slug: str,
        session: dict[str, Any],
    ) -> str:
        staff_roles = {str(role) for role in session.get("staff_roles") or []}
        student_roles = {str(role) for role in session.get("student_roles") or []}
        if staff_roles & {"superadmin", "partner_director", "admin"}:
            role = "admin"
        elif staff_roles & {"teacher", "curator"}:
            role = "teacher"
        elif "parent" in student_roles:
            role = "parent"
        else:
            role = "student"
        self.user_menu_roles[(user_id, tenant_slug)] = role
        return role

    def menu_role(self, user_id: int | None, tenant_slug: str) -> str | None:
        if user_id is None:
            return None
        key = (user_id, tenant_slug)
        if key in self.user_menu_roles:
            return self.user_menu_roles[key]
        if self.backend_client is None:
            return None
        try:
            session = self.backend_client.get_session(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError:
            return None
        return self.remember_session_role(user_id, tenant_slug, session)

    def main_menu_attachments(self, user_id: int | None) -> list[dict[str, Any]]:
        tenant_slug = self.current_tenant_slug(user_id)
        return main_menu_keyboard(
            user_id=user_id,
            tenant_slug=tenant_slug,
            role=self.menu_role(user_id, tenant_slug),
        )

    def cabinet_attachments(
        self,
        user_id: int | None,
        tenant_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        resolved_tenant = tenant_slug or self.current_tenant_slug(user_id)
        return cabinet_keyboard(
            user_id=user_id,
            tenant_slug=resolved_tenant,
            role=self.menu_role(user_id, resolved_tenant),
        )

    def order_attachments(
        self,
        order: dict[str, Any],
        *,
        user_id: int | None,
        tenant_slug: str,
        fallback_ref: str | int | None = None,
    ) -> list[dict[str, Any]]:
        order_ref = (
            order.get("order_number")
            or order.get("id")
            or fallback_ref
            or ""
        )
        if not order_ref:
            return self.cabinet_attachments(user_id, tenant_slug)
        return order_actions_keyboard(
            order_ref,
            status=str(order.get("status") or ""),
            user_id=user_id,
            tenant_slug=tenant_slug,
        )

    def handle_tenant_selection(self, *, user_id: int | None, tenant_slug: str) -> str:
        if user_id is None:
            return "Не получилось определить MAX user_id."

        normalized = tenant_slug.strip().lower()
        if not normalized:
            return (
                f"Текущий tenant: {self.current_tenant_slug(user_id)}\n"
                f"Default tenant: {self.default_tenant_slug}\n\n"
                "Сменить: /tenant <slug>\n"
                "Вернуть default: /tenant reset"
            )
        if normalized in {"reset", "default", "сброс"}:
            self.user_tenant_slugs.pop(user_id, None)
            self.user_menu_roles = {
                key: role for key, role in self.user_menu_roles.items() if key[0] != user_id
            }
            return (
                f"Tenant сброшен к default: {self.default_tenant_slug}\n\n"
                "Теперь команды снова используют tenant по умолчанию."
            )
        if len(normalized) < 2:
            return "Tenant slug слишком короткий. Например: /tenant nizhniy-novgorod-partner-a"
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-_")
        if any(char not in allowed for char in normalized):
            return (
                "Tenant slug должен содержать только латинские буквы, цифры, `-` и `_`.\n\n"
                "Например: /tenant nizhniy-novgorod-partner-a"
            )

        self.user_tenant_slugs[user_id] = normalized
        self.user_menu_roles = {
            key: role for key, role in self.user_menu_roles.items() if key[0] != user_id
        }
        return (
            f"Tenant выбран: {normalized}\n\n"
            "Теперь отправьте Contact ID сообщением или откройте deep link с Contact ID.\n"
            "Вернуть tenant по умолчанию: /tenant reset"
        )

    def handle_tenant_selection_response(
        self,
        *,
        user_id: int | None,
        tenant_slug: str,
    ) -> BotResponse:
        return BotResponse(
            self.handle_tenant_selection(user_id=user_id, tenant_slug=tenant_slug),
            self.main_menu_attachments(user_id),
        )

    def bot_username(self) -> str | None:
        username = self.bot_info.get("username")
        if isinstance(username, str) and username.strip():
            return username.strip().lstrip("@")
        return None

    def normalize_command_token(self, command_token: str) -> str | None:
        command = command_token.strip().casefold()
        if "@" not in command:
            return command

        command_name, mention = command.split("@", 1)
        bot_username = self.bot_username()
        if bot_username is None:
            return command_name
        if mention == bot_username.casefold():
            return command_name
        return None

    def contact_entry_text(
        self,
        contact_id: str,
        *,
        tenant_slug: str,
        students: list[dict[str, Any]] | None,
        contact_display_name: str | None = None,
    ) -> str:
        lines = [
            "Contact ID распознан.",
            "",
            f"Tenant: {tenant_slug}",
            f"Contact ID: {contact_id}",
        ]
        if contact_display_name:
            lines.append(f"Контакт: {contact_display_name}")

        if self.backend_client:
            lines.extend(["", "Найдены ученики:"])
            for index, student in enumerate(students or [], start=1):
                details = [
                    student.get("display_name"),
                    student.get("group_name"),
                    student.get("venue_name"),
                    student.get("teacher_name"),
                ]
                label = " / ".join(str(value) for value in details if value)
                lines.append(f"{index}. {label or student.get('student_id')}")
            if not students:
                lines.append("Backend не вернул связанных учеников.")
        else:
            lines.extend(
                [
                    "",
                    "Доменный API не подключен. Сейчас это только локальная проверка связи.",
                ]
            )

        lines.extend(
            [
                "",
                "Выберите роль кнопкой ниже:",
            ]
        )
        return "\n".join(lines)

    def handle_contact_payload_response(
        self,
        *,
        payload: str | None,
        user_id: int | None,
    ) -> BotResponse | None:
        contact_id = parse_contact_payload(payload)
        if not contact_id:
            return None

        tenant_slug = self.current_tenant_slug(user_id)
        if self.backend_client:
            try:
                resolved = self.backend_client.resolve_contact(
                    tenant_slug=tenant_slug,
                    contact_id=contact_id,
                    max_user_id=user_id,
                )
            except BackendApiError as exc:
                fallback = self.catalog_search_fallback_response(
                    payload=payload,
                    user_id=user_id,
                    tenant_slug=tenant_slug,
                    source_error=exc,
                )
                if fallback is not None:
                    return fallback
                return BotResponse(
                    (
                        "Не получилось проверить Contact ID через backend API.\n\n"
                        f"Tenant: {tenant_slug}\n"
                        f"Contact ID: {contact_id}\n"
                        f"Причина: {format_backend_error(exc)}"
                    ),
                    self.main_menu_attachments(user_id),
                )

            resolved_contact_id = str(resolved.get("contact_id") or contact_id)
            students = list(resolved.get("students") or [])
            fallback = self.catalog_search_fallback_response(
                payload=payload,
                user_id=user_id,
                tenant_slug=tenant_slug,
                source_error=None,
                students=students,
            )
            if fallback is not None:
                return fallback
            if user_id is not None:
                self.pending_contact_ids[user_id] = PendingContact(
                    contact_id=resolved_contact_id,
                    tenant_slug=tenant_slug,
                    students=students,
                )
            return BotResponse(
                self.contact_entry_text(
                    resolved_contact_id,
                    tenant_slug=tenant_slug,
                    students=students,
                    contact_display_name=resolved.get("contact_display_name"),
                ),
                role_selection_keyboard(),
            )

        if user_id is not None:
            self.pending_contact_ids[user_id] = PendingContact(
                contact_id=contact_id,
                tenant_slug=tenant_slug,
                students=[],
            )

        return BotResponse(
            self.contact_entry_text(contact_id, tenant_slug=tenant_slug, students=None),
            role_selection_keyboard(),
        )

    @staticmethod
    def is_catalog_search_fallback_candidate(payload: str | None) -> bool:
        text = (payload or "").strip()
        if len(text) < 2:
            return False
        lowered = text.casefold()
        explicit_prefixes = ("cid_", "sid_", "contact_", "contact:", "id_", "id:")
        if lowered.startswith(explicit_prefixes):
            return False
        normalized_contact_id = parse_contact_payload(text) or ""
        if normalized_contact_id.isdigit():
            return False
        return any(character.isalpha() for character in text)

    def catalog_search_fallback_response(
        self,
        *,
        payload: str | None,
        user_id: int | None,
        tenant_slug: str,
        source_error: BackendApiError | None,
        students: list[dict[str, Any]] | None = None,
    ) -> BotResponse | None:
        if not self.backend_client or not self.is_catalog_search_fallback_candidate(payload):
            return None
        if source_error is not None and source_error.status_code != 404:
            return None
        if source_error is None and students:
            return None

        query = (payload or "").strip()
        try:
            catalog = self.backend_client.get_catalog(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
                include_inactive=False,
            )
        except BackendApiError:
            return None

        text = self.format_catalog_text(catalog, tenant_slug=tenant_slug, query=query)
        return BotResponse(
            (
                "Contact ID по этому тексту не найден. "
                "Показываю поиск по каталогу.\n\n"
                f"{text}"
            ),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def handle_contact_payload(
        self,
        *,
        payload: str | None,
        user_id: int | None,
    ) -> str | None:
        response = self.handle_contact_payload_response(payload=payload, user_id=user_id)
        return response.text if response else None

    def build_contact_link_response(self, contact_id: str, *, tenant_slug: str) -> str:
        username = self.bot_username()
        if not username:
            return (
                "Не получилось создать ссылку: MAX API не вернул username бота.\n"
                "Запустите `python main_bot.py --check` и проверьте данные бота."
            )

        try:
            link = build_max_bot_deeplink(username, contact_id)
        except DeepLinkError as exc:
            return f"Не получилось создать ссылку: {exc}"

        return (
            "Deep link для Contact ID:\n"
            f"{link}\n\n"
            f"Текущий tenant в этом чате: {tenant_slug}\n\n"
            "Отправьте эту ссылку родителю или ученику. MAX передаст Contact ID боту "
            "через start payload."
        )

    def handle_role_selection_response(
        self,
        *,
        user_id: int | None,
        role: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id.",
                self.main_menu_attachments(user_id),
            )

        pending = self.pending_contact_ids.get(user_id)
        if not pending:
            return BotResponse(
                "Сначала отправьте Contact ID сообщением или откройте ссылку с Contact ID.",
                self.main_menu_attachments(user_id),
            )

        if role not in {"parent", "student"}:
            return BotResponse(
                "Роль должна быть `parent` или `student`.",
                role_selection_keyboard(),
            )

        role_text = "родитель" if role == "parent" else "ученик"
        if self.backend_client:
            try:
                result = self.backend_client.create_links(
                    tenant_slug=pending.tenant_slug,
                    contact_id=pending.contact_id,
                    max_user_id=user_id,
                    role=role,
                    username=username,
                    display_name=display_name,
                )
            except BackendApiError as exc:
                return BotResponse(
                    (
                        "Не получилось создать связи доступа через backend API.\n\n"
                        f"Tenant: {pending.tenant_slug}\n"
                        f"Contact ID: {pending.contact_id}\n"
                        f"Роль: {role_text}\n"
                        f"Причина: {format_backend_error(exc)}"
                    ),
                    role_selection_keyboard(),
                )

            links = result.get("links") or []
            self.user_menu_roles[(user_id, pending.tenant_slug)] = role
            return BotResponse(
                (
                    "Связи доступа созданы.\n\n"
                    f"Tenant: {pending.tenant_slug}\n"
                    f"Contact ID: {pending.contact_id}\n"
                    f"Роль: {role_text}\n"
                    f"Связанных учеников: {len(links)}\n\n"
                    "Готово. Теперь можно проверить личный кабинет в mini app."
                ),
                self.cabinet_attachments(user_id, pending.tenant_slug),
            )

        return BotResponse(
            (
                "Тестовая связь создана.\n\n"
                f"Tenant: {pending.tenant_slug}\n"
                f"Contact ID: {pending.contact_id}\n"
                f"Роль: {role_text}\n\n"
                "После подключения backend будут создаваться связи доступа для всех учеников, "
                "которые привязаны к этому контакту внутри выбранного tenant."
            ),
            self.cabinet_attachments(user_id, pending.tenant_slug),
        )

    def handle_role_selection(
        self,
        *,
        user_id: int | None,
        role: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> str:
        return self.handle_role_selection_response(
            user_id=user_id,
            role=role,
            username=username,
            display_name=display_name,
        ).text

    def handle_bot_started(self, update: dict[str, Any]) -> None:
        user = update.get("user") or {}
        user_id = user.get("user_id")
        chat_id = update.get("chat_id")
        payload = update.get("payload")

        response = self.handle_contact_payload_response(
            payload=payload,
            user_id=user_id,
        ) or self.help_response(user_id=user_id)
        if payload:
            response = BotResponse(
                f"{response.text}\n\nStart payload: {payload}",
                response.attachments,
            )

        self.send_response(response, chat_id=chat_id, user_id=user_id)

    def handle_message_created(self, update: dict[str, Any]) -> None:
        message = update.get("message") or {}
        sender = message.get("sender") or {}

        if sender.get("is_bot"):
            return
        if self.bot_user_id is not None and sender.get("user_id") == self.bot_user_id:
            return

        chat_id, user_id = self.target_from_message(message)
        body = message.get("body") or {}
        text = (body.get("text") or "").strip()

        if not text:
            self.send_response(
                BotResponse(
                    "Пока я понимаю только текстовые сообщения. Пришлите Contact ID текстом.",
                    self.main_menu_attachments(user_id),
                ),
                chat_id=chat_id,
                user_id=user_id,
            )
            return

        parts = text.split(maxsplit=1)
        command = self.normalize_command_token(parts[0])
        if command is None:
            return
        argument = parts[1].strip() if len(parts) > 1 else ""
        started_at = time.monotonic()
        tenant_slug = self.current_tenant_slug(user_id)

        if command == "/start":
            response = (
                self.handle_contact_payload_response(payload=argument, user_id=user_id)
                or self.help_response(user_id=user_id)
            )
        elif command in {"/help", "/menu", "/commands"}:
            response = self.help_response(user_id=user_id, topic=argument)
        elif command == "/setup":
            response = self.help_response(user_id=user_id, topic="setup")
        elif command == "/status":
            response = self.status_response(user_id=user_id)
        elif command in {"/version", "/about"}:
            response = self.version_response(user_id=user_id)
        elif command in {"/ready", "/health"}:
            response = self.ready_response(user_id=user_id)
        elif command in {"/config", "/doctor"}:
            response = self.config_response(user_id=user_id)
        elif command in {"/me", "/whoami", "/profile"}:
            response = self.profile_response(user_id=user_id)
        elif command in {"/search", "/find"}:
            response = self.search_response(user_id=user_id, query=argument)
        elif command in {"/balance", "/wallet"}:
            response = self.balance_response(user_id=user_id, query=argument)
        elif command in {"/lowbalance", "/lowwallets"}:
            response = self.lowbalance_response(user_id=user_id, threshold_text=argument)
        elif command in {"/ledger", "/history"}:
            response = self.ledger_response(user_id=user_id, query=argument)
        elif command == "/students":
            response = self.students_response(user_id=user_id, query=argument)
        elif command in {"/groups", "/classes"}:
            response = self.groups_response(user_id=user_id, query=argument)
        elif command in {"/leaderboard", "/top", "/leaders"}:
            response = self.leaderboard_response(user_id=user_id, query=argument)
        elif command == "/student":
            response = self.student_response(user_id=user_id, query=argument)
        elif command == "/access":
            response = self.access_response(user_id=user_id)
        elif command in {"/accessoff", "/revokeaccess"}:
            response = self.access_status_response(
                user_id=user_id,
                link_id=argument,
                status="revoked",
            )
        elif command in {"/accesson", "/restoreaccess"}:
            response = self.access_status_response(
                user_id=user_id,
                link_id=argument,
                status="active",
            )
        elif command in {"/staffrole", "/staffset"}:
            response = self.staffrole_response(user_id=user_id, argument=argument)
        elif command == "/staffoff":
            response = self.staffrole_response(
                user_id=user_id,
                argument=argument,
                forced_status="revoked",
            )
        elif command == "/staffon":
            response = self.staffrole_response(
                user_id=user_id,
                argument=argument,
                forced_status="active",
            )
        elif command == "/accrue":
            response = self.accrue_response(user_id=user_id, argument=argument)
        elif command in {"/quote", "/price"}:
            response = self.quote_response(user_id=user_id, argument=argument)
        elif command in {"/canbuy", "/afford"}:
            response = self.canbuy_response(user_id=user_id, argument=argument)
        elif command == "/buy":
            response = self.buy_response(user_id=user_id, argument=argument)
        elif command in {"/catalog", "/shop"}:
            response = self.catalog_response(user_id=user_id, query=argument)
        elif command in {"/categories", "/cats"}:
            response = self.categories_response(user_id=user_id)
        elif command in {"/product", "/item"}:
            response = self.product_response(user_id=user_id, query=argument)
        elif command in {"/productset", "/setproduct"}:
            response = self.productset_response(user_id=user_id, argument=argument)
        elif command in {"/setprice", "/pricechange"}:
            response = self.setprice_response(user_id=user_id, argument=argument)
        elif command in {"/productstatus", "/statusproduct"}:
            response = self.productstatus_response(user_id=user_id, argument=argument)
        elif command in {"/setphoto", "/productphoto"}:
            response = self.setphoto_response(user_id=user_id, argument=argument)
        elif command == "/clearphoto":
            response = self.setphoto_response(
                user_id=user_id,
                argument=argument,
                clear_photo=True,
            )
        elif command == "/hideproduct":
            response = self.productstatus_response(
                user_id=user_id,
                argument=argument,
                forced_status="hidden",
            )
        elif command == "/showproduct":
            response = self.productstatus_response(
                user_id=user_id,
                argument=argument,
                forced_status="active",
            )
        elif command == "/archiveproduct":
            response = self.productstatus_response(
                user_id=user_id,
                argument=argument,
                forced_status="archived",
            )
        elif command == "/order":
            response = self.order_response(user_id=user_id, order_ref=argument)
        elif command in {"/orders", "/myorders"}:
            response = self.orders_response(user_id=user_id, query=argument)
        elif command == "/open":
            response = self.orders_response(user_id=user_id, query=argument or "open")
        elif command in {"/last", "/latest", "/lastorder"}:
            response = self.latest_order_response(user_id=user_id, filter_text=argument)
        elif command in {"/sales", "/revenue"}:
            response = self.sales_response(user_id=user_id, filter_text=argument)
        elif command in {"/repeat", "/reorder"}:
            response = self.repeat_order_response(user_id=user_id, order_ref=argument)
        elif command in {"/stock", "/lowstock"}:
            response = self.stock_response(user_id=user_id, threshold_text=argument)
        elif command == "/inventory":
            response = self.stock_response(user_id=user_id, threshold_text=argument or "999")
        elif command in {"/warehouses", "/wh"}:
            response = self.warehouses_response(user_id=user_id)
        elif command in {"/warehouse", "/upsertwarehouse"}:
            response = self.warehouse_response(user_id=user_id, argument=argument)
        elif command in {"/setstock", "/stockset"}:
            response = self.setstock_response(user_id=user_id, argument=argument)
        elif command in {"/transfer", "/move"}:
            response = self.transfer_response(user_id=user_id, argument=argument)
        elif command in {"/ops", "/dashboard", "/overview"}:
            response = self.ops_response(user_id=user_id, threshold_text=argument)
        elif command in {"/todo", "/pending"}:
            response = self.todo_response(user_id=user_id, threshold_text=argument)
        elif command in {"/cancel", "/issue", "/return", "/done", "/void", "/refund"}:
            action = {
                "/cancel": "cancel",
                "/void": "cancel",
                "/issue": "issue",
                "/done": "issue",
                "/return": "return",
                "/refund": "return",
            }[command]
            response = self.order_action_response(
                user_id=user_id,
                action=action,
                order_ref=argument,
            )
        elif command == "/miniapp":
            response = self.miniapp_response(user_id=user_id)
        elif command in {"/schedule", "/teaching", "/feedback"}:
            response = self.teaching_response(user_id=user_id)
        elif command == "/ping":
            response = BotResponse(
                "Все хорошо, бот на связи.",
                self.main_menu_attachments(user_id),
            )
        elif command == "/id":
            response = self.diagnostic_response(
                sender=sender,
                chat_id=chat_id,
                user_id=user_id,
            )
        elif command == "/tenant":
            response = self.handle_tenant_selection_response(
                user_id=user_id,
                tenant_slug=argument,
            )
        elif command == "/link":
            response = BotResponse(
                (
                    self.build_contact_link_response(
                        argument,
                        tenant_slug=self.current_tenant_slug(user_id),
                    )
                    if argument
                    else "Отправьте Contact ID: /link <Contact ID>"
                ),
                self.main_menu_attachments(user_id),
            )
        elif command == "/code":
            response = (
                self.handle_contact_payload_response(payload=argument, user_id=user_id)
                if argument
                else BotResponse(
                    "Отправьте Contact ID текстом, без команды. Например: 681",
                    self.main_menu_attachments(user_id),
                )
            )
        elif command == "/role":
            response = (
                self.handle_role_selection_response(
                    user_id=user_id,
                    role=argument.lower(),
                    username=sender.get("username"),
                    display_name=display_name_from_user(sender),
                )
                if argument
                else BotResponse("Выберите роль кнопкой ниже.", role_selection_keyboard())
            )
        elif command.startswith("/"):
            response = self.unknown_command_response(command, user_id=user_id)
        else:
            response = self.handle_contact_payload_response(payload=text, user_id=user_id)
            if response is None:
                response = BotResponse(
                    "Пришлите Contact ID текстом, а дальше я покажу кнопки.",
                    self.main_menu_attachments(user_id),
                )

        self.log_interaction_result(
            event_type="message",
            action=command if command.startswith("/") else "contact_or_search",
            user_id=user_id,
            chat_id=chat_id,
            tenant_slug=tenant_slug,
            started_at=started_at,
            response=response,
        )
        self.send_response(response, chat_id=chat_id, user_id=user_id)

    def handle_message_callback(self, update: dict[str, Any]) -> None:
        callback = update.get("callback") or {}
        payload = callback.get("payload") or update.get("payload") or ""
        callback_id = callback.get("callback_id") or update.get("callback_id")
        user = callback.get("user") or update.get("user") or {}
        message = callback.get("message") or update.get("message") or {}

        user_id = user.get("user_id")
        chat_id = update.get("chat_id")
        if chat_id is None:
            recipient = message.get("recipient") or {}
            chat_id = recipient.get("chat_id")
        started_at = time.monotonic()
        tenant_slug = self.current_tenant_slug(user_id)

        if payload == CALLBACK_ROLE_PARENT:
            response = self.handle_role_selection_response(
                user_id=user_id,
                role="parent",
                username=user.get("username"),
                display_name=display_name_from_user(user),
            )
            notification = "Роль выбрана"
        elif payload == CALLBACK_ROLE_STUDENT:
            response = self.handle_role_selection_response(
                user_id=user_id,
                role="student",
                username=user.get("username"),
                display_name=display_name_from_user(user),
            )
            notification = "Роль выбрана"
        elif order_confirm := parse_order_confirm_payload(payload):
            action, order_ref = order_confirm
            if action == "repeat":
                response = self.repeat_order_response(user_id=user_id, order_ref=order_ref)
                notification = "Повтор"
            elif action in {"cancel", "issue", "return"}:
                response = self.order_action_response(
                    user_id=user_id,
                    action=action,
                    order_ref=order_ref,
                )
                notification = {
                    "cancel": "Отмена",
                    "issue": "Выдача",
                    "return": "Возврат",
                }[action]
            else:
                response = BotResponse(
                    "Действие с заказом пока не поддерживается. Вернемся к заказам.",
                    self.cabinet_attachments(user_id, tenant_slug),
                )
                notification = "Заказы"
        elif order_action := parse_order_action_payload(payload):
            action, order_ref = order_action
            if action in {"repeat", "cancel", "issue", "return"}:
                response = self.order_action_confirmation_response(
                    user_id=user_id,
                    action=action,
                    order_ref=order_ref,
                )
                notification = {
                    "repeat": "Подтвердите",
                    "cancel": "Отмена",
                    "issue": "Выдача",
                    "return": "Возврат",
                }[action]
            else:
                response = BotResponse(
                    "Действие с заказом пока не поддерживается. Вернемся к заказам.",
                    self.cabinet_attachments(user_id, tenant_slug),
                )
                notification = "Заказы"
        elif payload == CALLBACK_STATUS:
            response = self.status_response(user_id=user_id)
            notification = "Статус"
        elif payload == CALLBACK_BALANCE:
            response = self.balance_response(user_id=user_id)
            notification = "Баланс"
        elif payload == CALLBACK_LEDGER:
            response = self.ledger_response(user_id=user_id)
            notification = "История"
        elif payload == CALLBACK_STUDENTS:
            response = self.students_response(user_id=user_id)
            notification = "Ученики"
        elif payload == CALLBACK_GROUPS:
            response = self.groups_response(user_id=user_id)
            notification = "Группы"
        elif payload == CALLBACK_LEADERBOARD:
            response = self.leaderboard_response(user_id=user_id)
            notification = "Топ AC"
        elif payload == CALLBACK_CATALOG:
            response = self.catalog_response(user_id=user_id)
            notification = "Каталог"
        elif payload == CALLBACK_CATEGORIES:
            response = self.categories_response(user_id=user_id)
            notification = "Категории"
        elif payload == CALLBACK_ORDERS:
            response = self.orders_response(user_id=user_id)
            notification = "Заказы"
        elif payload == CALLBACK_OPEN_ORDERS:
            response = self.orders_response(user_id=user_id, query="open")
            notification = "Открытые"
        elif payload == CALLBACK_OPS:
            response = self.ops_response(user_id=user_id)
            notification = "Операции"
        elif payload == CALLBACK_STOCK:
            response = self.stock_response(user_id=user_id)
            notification = "Остатки"
        elif payload == CALLBACK_TODO:
            response = self.todo_response(user_id=user_id)
            notification = "К выдаче"
        elif payload in {CALLBACK_HELP, CALLBACK_MENU}:
            response = self.help_response(user_id=user_id)
            notification = "Готово"
        elif payload == CALLBACK_MINIAPP:
            response = BotResponse(
                "Mini app будет открываться кнопкой после настройки публичного HTTPS-адреса.",
                self.main_menu_attachments(user_id),
            )
            notification = "Mini app"
        else:
            response = BotResponse(
                "Кнопка пока не поддерживается. Вернемся в меню.",
                self.main_menu_attachments(user_id),
            )
            notification = "Меню"

        self.log_interaction_result(
            event_type="callback",
            action=payload or "unknown",
            user_id=user_id,
            chat_id=chat_id,
            tenant_slug=tenant_slug,
            started_at=started_at,
            response=response,
        )
        if callback_id and hasattr(self.client, "answer_callback"):
            self.client.answer_callback(
                callback_id=callback_id,
                response=response,
                notification=notification,
            )
            return

        self.send_response(response, chat_id=chat_id, user_id=user_id)

    def handle_update(self, update: dict[str, Any]) -> None:
        update_type = update.get("update_type")

        if update_type == "bot_started":
            self.handle_bot_started(update)
            return

        if update_type == "message_created":
            self.handle_message_created(update)
            return

        if update_type == "message_callback":
            self.handle_message_callback(update)
            return

        logger.warning("Неподдерживаемый update_type=%s", update_type)

    def run(self) -> None:
        marker = self.load_marker()
        retry_delay = POLL_RETRY_INITIAL_SECONDS
        bot_name = self.bot_info.get("first_name") or self.bot_info.get("name") or "MAX bot"
        bot_username = self.bot_info.get("username") or "-"

        logger.info("Бот запущен: %s (@%s)", bot_name, bot_username)
        logger.info("Файл marker: %s", MARKER_FILE)
        logger.info("Жду события. Для остановки нажмите Ctrl+C.")

        while self.running:
            try:
                page = self.client.get_updates(marker)
                updates = page.get("updates") or []
                next_marker = page.get("marker")

                for update in updates:
                    try:
                        self.handle_update(update)
                    except Exception as exc:  # noqa: BLE001
                        logger.exception("Не получилось обработать событие: %s", exc)

                if next_marker is not None:
                    marker = next_marker
                    self.save_marker(marker)
                retry_delay = POLL_RETRY_INITIAL_SECONDS

            except KeyboardInterrupt:
                logger.info("Остановлено пользователем.")
                break
            except MaxApiError as exc:
                logger.error("%s; повтор через %.0f сек.", exc, retry_delay)
                if self.stop_event.wait(retry_delay):
                    break
                retry_delay = min(retry_delay * 2, POLL_RETRY_MAX_SECONDS)
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Неожиданная ошибка: %s; повтор через %.0f сек.",
                    exc,
                    retry_delay,
                )
                if self.stop_event.wait(retry_delay):
                    break
                retry_delay = min(retry_delay * 2, POLL_RETRY_MAX_SECONDS)

        self.stop()
        logger.info("Long polling завершен.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MAX-бот Алгоритмики в режиме long polling")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Проверить токен, данные бота и подписки без запуска polling",
    )
    parser.add_argument(
        "--config-check",
        action="store_true",
        help="Проверить локальную конфигурацию без сетевых запросов к MAX API",
    )
    simulate_group = parser.add_mutually_exclusive_group()
    simulate_group.add_argument(
        "--simulate-command",
        metavar="TEXT",
        help="Локально обработать текст команды и вывести JSON ответа без запуска polling",
    )
    simulate_group.add_argument(
        "--simulate-callback",
        metavar="PAYLOAD",
        help=(
            "Локально обработать callback payload кнопки и вывести JSON ответа "
            "без запуска polling"
        ),
    )
    parser.add_argument(
        "--simulate-user-id",
        type=int,
        default=1,
        help="MAX user_id для --simulate-command или --simulate-callback",
    )
    parser.add_argument(
        "--simulate-offline",
        action="store_true",
        help="Не подключать backend API во время локальной симуляции команды или callback",
    )
    parser.add_argument(
        "--drop-webhooks",
        action="store_true",
        help="Удалить активные webhook-подписки перед запуском",
    )
    parser.add_argument(
        "--reset-marker",
        action="store_true",
        help="Удалить сохраненный marker перед запуском",
    )
    return parser.parse_args()


def simulate_command(
    *,
    command_text: str,
    user_id: int,
    backend_client: AccessBackendClient | None,
    default_tenant_slug: str,
) -> dict[str, Any]:
    client = SimulationMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=backend_client,
        default_tenant_slug=default_tenant_slug,
    )
    bot.handle_message_created(
        {
            "message": {
                "sender": {
                    "user_id": user_id,
                    "username": "local_simulation",
                    "first_name": "Local",
                    "last_name": "Simulation",
                },
                "recipient": {"chat_id": user_id},
                "body": {"text": command_text},
            }
        }
    )
    if not client.sent_messages:
        raise RuntimeError("Команда не сформировала ответ")
    return client.sent_messages[-1]


def simulate_callback(
    *,
    payload: str,
    user_id: int,
    backend_client: AccessBackendClient | None,
    default_tenant_slug: str,
) -> dict[str, Any]:
    client = SimulationMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=backend_client,
        default_tenant_slug=default_tenant_slug,
    )
    bot.handle_message_callback(
        {
            "callback": {
                "payload": payload,
                "callback_id": "local-simulation-callback",
                "user": {
                    "user_id": user_id,
                    "username": "local_simulation",
                    "first_name": "Local",
                    "last_name": "Simulation",
                },
                "message": {"recipient": {"chat_id": user_id}},
            }
        }
    )
    if not client.sent_messages:
        raise RuntimeError("Callback не сформировал ответ")
    return client.sent_messages[-1]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    if args.config_check:
        report = settings.safe_config_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if not report["errors"] else 1

    if args.simulate_command:
        backend_client = (
            None
            if args.simulate_offline or is_placeholder(settings.max_backend_api_base)
            else AccessBackendClient(
                settings.max_backend_api_base,
                timeout_seconds=settings.max_backend_timeout_seconds,
            )
        )
        response = simulate_command(
            command_text=args.simulate_command,
            user_id=args.simulate_user_id,
            backend_client=backend_client,
            default_tenant_slug=settings.default_tenant_slug,
        )
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0

    if args.simulate_callback:
        backend_client = (
            None
            if args.simulate_offline or is_placeholder(settings.max_backend_api_base)
            else AccessBackendClient(
                settings.max_backend_api_base,
                timeout_seconds=settings.max_backend_timeout_seconds,
            )
        )
        response = simulate_callback(
            payload=args.simulate_callback,
            user_id=args.simulate_user_id,
            backend_client=backend_client,
            default_tenant_slug=settings.default_tenant_slug,
        )
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return 0

    token = settings.max_bot_token
    if is_placeholder(token):
        print("Переменная MAX_BOT_TOKEN не задана.", file=sys.stderr)
        print('Пример PowerShell: $env:MAX_BOT_TOKEN = "your_token_here"', file=sys.stderr)
        print(
            "Для локальной проверки без токена: python main_bot.py --config-check",
            file=sys.stderr,
        )
        return 1
    token_value = token.strip()

    config_errors = settings.bot_config_errors()
    if config_errors:
        for message in config_errors:
            print(f"[config] {message}", file=sys.stderr)
        return 1

    client = MaxApiClient(
        token_value,
        api_base=settings.max_api_base,
        timeout_seconds=settings.max_api_timeout_seconds,
        poll_timeout_seconds=settings.max_poll_timeout_seconds,
    )
    backend_client = (
        AccessBackendClient(
            settings.max_backend_api_base,
            timeout_seconds=settings.max_backend_timeout_seconds,
        )
        if not is_placeholder(settings.max_backend_api_base)
        else None
    )
    bot = LongPollingBot(
        client,
        backend_client=backend_client,
        default_tenant_slug=settings.default_tenant_slug,
    )

    if args.reset_marker:
        bot.reset_marker()
        print(f"[info] Marker удален: {MARKER_FILE}")

    if args.check:
        subscriptions = client.get_subscriptions().get("subscriptions") or []
        print(json.dumps(bot.bot_info, ensure_ascii=False, indent=2))
        print(f"[info] Активные webhook-подписки: {len(subscriptions)}")
        print(f"[info] Tenant по умолчанию: {settings.default_tenant_slug}")
        print(f"[info] Backend API: {settings.max_backend_api_base or 'выключен'}")
        print(f"[info] Bot mode: {settings.bot_mode}")
        for warning in settings.config_warnings():
            print(f"[warn] {warning}")
        for item in subscriptions:
            url = item.get("url")
            if url:
                print(f" - {url}")
        return 0

    if settings.bot_mode.strip().lower() == "webhook":
        print(
            "BOT_MODE=webhook: события принимает FastAPI endpoint. "
            "Запустите uvicorn app.main:app.",
            file=sys.stderr,
        )
        return 1

    drop_webhooks = args.drop_webhooks or settings.max_drop_webhooks_on_start
    bot.ensure_polling_available(drop_webhooks=drop_webhooks)

    bot.run()
    return 0
