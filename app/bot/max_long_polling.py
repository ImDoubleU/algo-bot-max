from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from app.core.config import get_settings, is_placeholder
from app.services.deep_links import (
    DeepLinkError,
    build_max_bot_deeplink,
    parse_contact_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
MARKER_FILE = PROJECT_ROOT / "main_bot.marker"


def load_local_env(env_path: Path = ENV_FILE) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip("'\"")


load_local_env()

API_BASE = os.getenv("MAX_API_BASE", "https://platform-api2.max.ru")
BACKEND_API_BASE = os.getenv("MAX_BACKEND_API_BASE", "").rstrip("/")
DEFAULT_TENANT_SLUG = os.getenv("DEFAULT_TENANT_SLUG", "nizhniy-novgorod-partner-a").strip().lower()
MAX_MINIAPP_URL = os.getenv("MAX_MINIAPP_URL", "").strip()
UPDATE_TYPES = "message_created,bot_started,message_callback"
CALLBACK_HELP = "help"
CALLBACK_MENU = "menu"
CALLBACK_MINIAPP = "miniapp:open"
CALLBACK_STATUS = "status"
CALLBACK_BALANCE = "balance"
CALLBACK_LEDGER = "ledger"
CALLBACK_STUDENTS = "students"
CALLBACK_CATALOG = "catalog"
CALLBACK_ORDERS = "orders"
CALLBACK_OPS = "ops"
CALLBACK_ROLE_PARENT = "role:parent"
CALLBACK_ROLE_STUDENT = "role:student"
logger = logging.getLogger("algo_bot_max.bot")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


class MaxApiError(RuntimeError):
    pass


class BackendApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PendingContact:
    contact_id: str
    tenant_slug: str
    students: list[dict[str, Any]]


@dataclass(frozen=True)
class BotResponse:
    text: str
    attachments: list[dict[str, Any]] | None = None

    def as_message_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"text": self.text}
        if self.attachments:
            body["attachments"] = self.attachments
        return body


@dataclass(frozen=True)
class AccrueCommand:
    amount: int
    student_query: str
    reason: str


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
    if not MAX_MINIAPP_URL:
        return ""

    parts = parse.urlsplit(MAX_MINIAPP_URL)
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
            callback_button("Ученики", CALLBACK_STUDENTS),
        ],
    ]
    rows.append([callback_button("Операции", CALLBACK_OPS)])
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
        [
            callback_button("Каталог", CALLBACK_CATALOG),
            callback_button("История AC", CALLBACK_LEDGER),
        ],
        [callback_button("В меню", CALLBACK_MENU)],
    ]
    rows.insert(-1, [callback_button("Операции", CALLBACK_OPS)])
    miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
    if miniapp_url:
        rows.insert(0, [link_button("Открыть mini app", miniapp_url)])
    else:
        rows.insert(0, [callback_button("Открыть mini app", CALLBACK_MINIAPP)])
    return inline_keyboard(rows)


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
    if exc.status_code == 404:
        return "Contact ID не найден для выбранного tenant."
    if exc.status_code == 429:
        return "Слишком много попыток. Попробуйте немного позже."
    return str(exc)


class AccessBackendClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        timeout: int = 15,
    ) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        if clean_params:
            url = f"{url}?{parse.urlencode(clean_params)}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(
            url,
            data=data,
            method=method.upper(),
            headers=headers,
        )

        try:
            with request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("detail"):
                detail = str(parsed["detail"])
            raise BackendApiError(
                f"HTTP {exc.code} {exc.reason}: {detail}",
                status_code=exc.code,
            ) from exc
        except error.URLError as exc:
            raise BackendApiError(f"Backend API недоступен: {exc}") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise BackendApiError(f"Backend API вернул некорректный JSON: {raw!r}") from exc

    def resolve_contact(
        self,
        *,
        tenant_slug: str,
        contact_id: str,
        max_user_id: int | None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/access/resolve-contact",
            body={
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
            },
        )

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
        return self._request(
            "POST",
            "/access/links",
            body={
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
                "role": role,
                "username": username,
                "display_name": display_name,
            },
        )

    def get_session(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/session",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
            },
        )

    def get_readiness(self) -> dict[str, Any]:
        return self._request("GET", "/ready")

    def get_catalog(
        self,
        *,
        tenant_slug: str,
        max_user_id: int | None = None,
        include_inactive: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/catalog",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "include_inactive": "true" if include_inactive else None,
            },
        )

    def get_ops_summary(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
        low_stock_threshold: int = 5,
    ) -> dict[str, Any]:
        return self._request(
            "GET",
            "/miniapp/ops/summary",
            params={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "low_stock_threshold": low_stock_threshold,
            },
        )

    def update_order(
        self,
        *,
        order_id: str,
        action: str,
        tenant_slug: str,
        max_user_id: int,
        comment: str | None = None,
    ) -> dict[str, Any]:
        if action not in {"cancel", "issue", "return"}:
            raise ValueError(f"Unsupported order action: {action}")
        return self._request(
            "POST",
            f"/miniapp/orders/{parse.quote(str(order_id))}/{action}",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "comment": comment,
            },
        )

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
        return self._request(
            "POST",
            "/miniapp/coins/accrue",
            body={
                "tenant_slug": tenant_slug,
                "max_user_id": max_user_id,
                "student_ids": student_ids,
                "amount": amount,
                "reason": reason,
                "comment": comment,
            },
        )


class MaxApiClient:
    def __init__(self, token: str, api_base: str = API_BASE) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        url = f"{self.api_base}{path}"
        if not params:
            return url

        clean_params = {key: value for key, value in params.items() if value is not None}
        query = parse.urlencode(clean_params)
        return f"{url}?{query}" if query else url

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        url = self._build_url(path, params)
        headers = {
            "Authorization": self.token,
            "Accept": "application/json",
        }
        data = None

        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = request.Request(url, data=data, headers=headers, method=method.upper())

        try:
            with request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MaxApiError(
                f"HTTP {exc.code} {exc.reason} для {method.upper()} {path}: {detail}"
            ) from exc
        except error.URLError as exc:
            raise MaxApiError(f"Сетевая ошибка для {method.upper()} {path}: {exc}") from exc

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise MaxApiError(f"MAX API вернул некорректный JSON: {raw!r}") from exc

    def get_me(self) -> dict[str, Any]:
        return self._request("GET", "/me", timeout=15)

    def get_subscriptions(self) -> dict[str, Any]:
        return self._request("GET", "/subscriptions", timeout=15)

    def delete_subscription(self, url: str) -> dict[str, Any]:
        return self._request(
            "DELETE",
            "/subscriptions",
            params={"url": url},
            timeout=15,
        )

    def get_updates(self, marker: int | None) -> dict[str, Any]:
        return self._request(
            "GET",
            "/updates",
            params={
                "marker": marker,
                "limit": 100,
                "timeout": 30,
                "types": UPDATE_TYPES,
            },
            timeout=40,
        )

    def send_message(
        self,
        *,
        text: str,
        attachments: list[dict[str, Any]] | None = None,
        user_id: int | None = None,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        if chat_id is None and user_id is None:
            raise ValueError("Нужен chat_id или user_id")

        body: dict[str, Any] = {"text": text}
        if attachments:
            body["attachments"] = attachments

        return self._request(
            "POST",
            "/messages",
            params={"chat_id": chat_id, "user_id": user_id},
            body=body,
            timeout=15,
        )

    def answer_callback(
        self,
        *,
        callback_id: str,
        response: BotResponse,
        notification: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"message": response.as_message_body()}
        if notification:
            body["notification"] = notification
        return self._request(
            "POST",
            "/answers",
            params={"callback_id": callback_id},
            body=body,
            timeout=15,
        )


class SimulationMaxClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    def get_me(self) -> dict[str, Any]:
        return {
            "user_id": 0,
            "username": "LocalSimulationBot",
            "first_name": "Local Simulation",
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


class LongPollingBot:
    def __init__(
        self,
        client: MaxApiClient,
        *,
        backend_client: AccessBackendClient | None = None,
        default_tenant_slug: str = DEFAULT_TENANT_SLUG,
    ) -> None:
        self.client = client
        self.backend_client = backend_client
        self.default_tenant_slug = default_tenant_slug
        self.bot_info = self.client.get_me()
        self.bot_user_id = self.bot_info.get("user_id")
        self.pending_contact_ids: dict[int, PendingContact] = {}
        self.user_tenant_slugs: dict[int, str] = {}
        self.running = True

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
            "Запустите `python main_bot.py --drop-webhooks` или удалите webhook в MAX."
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

    def help_text(self) -> str:
        backend_state = "подключен" if self.backend_client else "выключен"
        return (
            "Добро пожаловать в MAX-бот Алгоритмики.\n\n"
            f"Tenant: {self.default_tenant_slug}\n"
            f"Доменный API: {backend_state}\n\n"
            "Пришлите Contact ID сообщением. Я найду связанных учеников и покажу кнопки "
            "для выбора роли.\n\n"
            "Команды:\n"
            "/catalog [поиск] - активные товары, цены и остатки.\n"
            "/balance - балансы астрокоинов по связанным ученикам.\n"
            "/ledger - последние операции с астрокоинами.\n"
            "/students [поиск] - ученики, роли, группы и балансы.\n"
            "/access - связи доступа и staff-роли.\n"
            "/accrue <AC> <ученик> | <причина> - начислить астрокоины staff/admin.\n"
            "/orders - открытые и последние заказы.\n"
            "/order <номер> - детали конкретного заказа.\n"
            "/me - профиль, роли и связанные ученики.\n"
            "/miniapp - персональная ссылка на магазин.\n"
            "/stock [порог] - проблемные остатки для staff/admin.\n"
            "/ops [порог] - операционная сводка заказов и остатков.\n"
            "/status - состояние бота и backend API.\n"
            "/ready - readiness backend, БД и seed-данных.\n"
            "/id - диагностический MAX user_id."
        )

    def help_response(self, user_id: int | None = None) -> BotResponse:
        return BotResponse(self.help_text(), self.main_menu_attachments(user_id))

    def unknown_command_response(self, command: str, user_id: int | None = None) -> BotResponse:
        return BotResponse(
            (
                f"Команда `{command}` не поддерживается.\n\n"
                "Откройте меню кнопками или отправьте /help.\n"
                "Частые команды: /catalog, /balance, /orders, /students, /miniapp.\n\n"
                "Если вы хотели войти по Contact ID, отправьте только номер без `/`."
            ),
            self.main_menu_attachments(user_id),
        )

    def status_text(self, user_id: int | None = None) -> str:
        tenant_slug = self.current_tenant_slug(user_id)
        marker = self.load_marker()
        miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
        return (
            "Статус MAX-бота\n\n"
            f"Tenant: {tenant_slug}\n"
            f"Backend API: {'подключен' if self.backend_client else 'выключен'}\n"
            f"Miniapp: {'настроен' if miniapp_url else 'не настроен'}\n"
            f"Marker: {marker if marker is not None else 'нет'}\n"
            "Polling: long polling"
        )

    def status_response(self, user_id: int | None = None) -> BotResponse:
        return BotResponse(self.status_text(user_id), self.main_menu_attachments(user_id))

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

    def profile_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="профиль")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_profile_text(session, tenant_slug=tenant_slug, user_id=user_id),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def orders_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="список заказов")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_orders_text(session, tenant_slug=tenant_slug),
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
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def balance_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="баланс")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_balance_text(session, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def ledger_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(
            user_id=user_id,
            noun="историю астрокоинов",
        )
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_ledger_text(session, tenant_slug=tenant_slug),
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

    def access_response(self, user_id: int | None = None) -> BotResponse:
        session_result = self.load_session_response(user_id=user_id, noun="связи доступа")
        if isinstance(session_result, BotResponse):
            return session_result
        tenant_slug, session = session_result

        return BotResponse(
            self.format_access_text(session, tenant_slug=tenant_slug),
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

        parsed = self.parse_accrue_command(argument)
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

    @staticmethod
    def parse_accrue_command(argument: str) -> AccrueCommand | str:
        text = argument.strip()
        usage = "Формат: /accrue <AC> <ученик> | <причина>. Например: /accrue 50 алиса | За проект"
        if not text:
            return usage
        if "|" not in text:
            return "Добавьте причину после `|`: /accrue 50 алиса | За проект"

        left, reason = (part.strip() for part in text.split("|", 1))
        amount_text, _, student_query = left.partition(" ")
        if not amount_text or not student_query.strip():
            return usage
        try:
            amount = int(amount_text)
        except ValueError:
            return (
                "Сумма начисления должна быть целым числом. "
                "Например: /accrue 50 алиса | За проект"
            )
        if amount <= 0 or amount > 10000:
            return "Сумма начисления должна быть от 1 до 10000 AC."
        if len(reason) < 2:
            return "Причина начисления должна быть не короче 2 символов."
        return AccrueCommand(
            amount=amount,
            student_query=student_query.strip(),
            reason=reason,
        )

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
                    f"Backend API не подключен, поэтому {noun} недоступен.\n\n"
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

    def ops_response(self, user_id: int | None = None, threshold_text: str = "") -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить MAX user_id. Отправьте /id для диагностики.",
                self.main_menu_attachments(user_id),
            )
        if self.backend_client is None:
            return BotResponse(
                (
                    "Backend API не подключен, поэтому операционная сводка недоступна.\n\n"
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
                    "Порог остатка должен быть числом. Например: /ops 3",
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
                    "Не получилось загрузить операционную сводку через backend API.\n\n"
                    f"Tenant: {tenant_slug}\n"
                    f"MAX user_id: {user_id}\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            self.format_ops_summary_text(summary, tenant_slug=tenant_slug),
            self.cabinet_attachments(user_id, tenant_slug),
        )

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
            self.cabinet_attachments(user_id, tenant_slug),
        )

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
        open_statuses = {"created", "reserved", "transferred_to_teacher"}
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

    def format_orders_text(self, session: dict[str, Any], *, tenant_slug: str) -> str:
        orders = list(session.get("orders") or [])
        open_statuses = {"created", "reserved", "transferred_to_teacher"}
        open_orders = [
            order for order in orders if str(order.get("status") or "") in open_statuses
        ]
        recent_orders = orders[:8]

        lines = [
            "Заказы MAX",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
            f"Открытые заказы: {len(open_orders)}",
            f"Всего заказов в профиле: {len(orders)}",
        ]

        if open_orders:
            lines.extend(["", "Открытые:"])
            for order in open_orders[:5]:
                lines.append(self.format_order_line(order))
            if len(open_orders) > 5:
                lines.append(f"...и еще {len(open_orders) - 5} открытых")

        lines.extend(["", "Последние:"])
        if recent_orders:
            for order in recent_orders:
                lines.append(self.format_order_line(order))
        else:
            lines.append("Заказов пока нет.")

        lines.extend(
            [
                "",
                "Для выдачи, отмены или возврата откройте miniapp.",
            ]
        )
        return "\n".join(lines)

    def format_order_line(self, order: dict[str, Any]) -> str:
        order_number = order.get("order_number") or order.get("id") or "-"
        student = order.get("student_name") or "ученик"
        status = self.order_status_label(order.get("status"))
        total = order.get("total_astrocoins")
        total_text = f", {total} AC" if total is not None else ""
        return f"№{order_number}: {student}, {status}{total_text}"

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
        if status in {"created", "reserved", "transferred_to_teacher"}:
            action_lines.extend(
                [
                    f"/cancel {order_number} - отменить и вернуть астрокоины",
                    f"/issue {order_number} - выдать заказ ученику",
                ]
            )
        elif status == "issued_to_student":
            action_lines.append(f"/return {order_number} - принять возврат")
        if action_lines:
            lines.extend(["", "Действия:"])
            lines.extend(action_lines)
        else:
            lines.extend(["", "Для этого статуса быстрых действий нет."])
        return "\n".join(lines)

    def format_balance_text(self, session: dict[str, Any], *, tenant_slug: str) -> str:
        students = list(session.get("students") or [])
        total = sum(int(student.get("balance") or 0) for student in students)
        lines = [
            "Баланс астрокоинов",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]
        if not students:
            lines.extend(
                [
                    "Связанных учеников пока нет.",
                    "",
                    "Чтобы привязать доступ, отправьте Contact ID или откройте deep link.",
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

    def format_ledger_text(self, session: dict[str, Any], *, tenant_slug: str) -> str:
        students_by_id = {
            str(student.get("student_id")): student.get("display_name") or "ученик"
            for student in session.get("students") or []
        }
        ledger = list(session.get("ledger") or [])
        lines = [
            "История астрокоинов",
            "",
            f"Tenant: {session.get('tenant_slug') or tenant_slug}",
        ]

        if not ledger:
            lines.extend(
                [
                    "Операций пока нет.",
                    "",
                    "Когда будут начисления, покупки, отмены или возвраты, они появятся здесь.",
                ]
            )
            return "\n".join(lines)

        lines.extend(["", "Последние операции:"])
        for entry in ledger[:10]:
            lines.append(self.format_ledger_line(entry, students_by_id=students_by_id))
        if len(ledger) > 10:
            lines.append(f"...и еще {len(ledger) - 10}")
        return "\n".join(lines)

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
                student = link.get("student_name") or link.get("student_id") or "ученик"
                group = link.get("group_name")
                max_user_id = link.get("max_user_id")
                role = link.get("role") or "role"
                status = link.get("status") or "status"
                display_name = link.get("display_name") or link.get("username") or max_user_id
                group_text = f" / {group}" if group else ""
                lines.append(
                    f"- {student}{group_text}: {role}, {status}, MAX {display_name}"
                )
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

        if errors:
            lines.extend(["", "Errors:"])
            lines.extend(f"- {error_text}" for error_text in errors[:6])
        if warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"- {warning_text}" for warning_text in warnings[:6])
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
        lines.extend(["", "Для заказа откройте miniapp кнопкой ниже."])
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

    def main_menu_attachments(self, user_id: int | None) -> list[dict[str, Any]]:
        return main_menu_keyboard(
            user_id=user_id,
            tenant_slug=self.current_tenant_slug(user_id),
        )

    def cabinet_attachments(
        self,
        user_id: int | None,
        tenant_slug: str | None = None,
    ) -> list[dict[str, Any]]:
        return cabinet_keyboard(
            user_id=user_id,
            tenant_slug=tenant_slug or self.current_tenant_slug(user_id),
        )

    def handle_tenant_selection(self, *, user_id: int | None, tenant_slug: str) -> str:
        if user_id is None:
            return "Не получилось определить MAX user_id."

        normalized = tenant_slug.strip().lower()
        if not normalized:
            return f"Текущий tenant: {self.current_tenant_slug(user_id)}"
        if len(normalized) < 2:
            return "Tenant slug слишком короткий."

        self.user_tenant_slugs[user_id] = normalized
        return (
            f"Tenant выбран: {normalized}\n\n"
            "Теперь отправьте Contact ID сообщением или откройте deep link с Contact ID."
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
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command == "/start":
            response = (
                self.handle_contact_payload_response(payload=argument, user_id=user_id)
                or self.help_response(user_id=user_id)
            )
        elif command in {"/help", "/menu", "/commands"}:
            response = self.help_response(user_id=user_id)
        elif command == "/status":
            response = self.status_response(user_id=user_id)
        elif command == "/ready":
            response = self.ready_response(user_id=user_id)
        elif command == "/me":
            response = self.profile_response(user_id=user_id)
        elif command == "/balance":
            response = self.balance_response(user_id=user_id)
        elif command in {"/ledger", "/history"}:
            response = self.ledger_response(user_id=user_id)
        elif command == "/students":
            response = self.students_response(user_id=user_id, query=argument)
        elif command == "/access":
            response = self.access_response(user_id=user_id)
        elif command == "/accrue":
            response = self.accrue_response(user_id=user_id, argument=argument)
        elif command in {"/catalog", "/shop"}:
            response = self.catalog_response(user_id=user_id, query=argument)
        elif command == "/order":
            response = self.order_response(user_id=user_id, order_ref=argument)
        elif command == "/orders":
            response = self.orders_response(user_id=user_id)
        elif command == "/stock":
            response = self.stock_response(user_id=user_id, threshold_text=argument)
        elif command == "/ops":
            response = self.ops_response(user_id=user_id, threshold_text=argument)
        elif command in {"/cancel", "/issue", "/return"}:
            response = self.order_action_response(
                user_id=user_id,
                action=command.lstrip("/"),
                order_ref=argument,
            )
        elif command == "/miniapp":
            response = self.miniapp_response(user_id=user_id)
        elif command == "/ping":
            response = BotResponse(
                "Все хорошо, бот на связи.",
                self.main_menu_attachments(user_id),
            )
        elif command == "/id":
            sender_id = sender.get("user_id")
            response = BotResponse(
                f"user_id: {sender_id}\nchat_id: {chat_id}\nusername: {sender.get('username')}",
                self.main_menu_attachments(user_id),
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
        elif payload == CALLBACK_CATALOG:
            response = self.catalog_response(user_id=user_id)
            notification = "Каталог"
        elif payload == CALLBACK_ORDERS:
            response = self.orders_response(user_id=user_id)
            notification = "Заказы"
        elif payload == CALLBACK_OPS:
            response = self.ops_response(user_id=user_id)
            notification = "Операции"
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

            except KeyboardInterrupt:
                logger.info("Остановлено пользователем.")
                break
            except MaxApiError as exc:
                logger.error("%s", exc)
                time.sleep(3)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Неожиданная ошибка: %s", exc)
                time.sleep(3)


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
    parser.add_argument(
        "--simulate-command",
        metavar="TEXT",
        help="Локально обработать текст команды и вывести JSON ответа без запуска polling",
    )
    parser.add_argument(
        "--simulate-user-id",
        type=int,
        default=1,
        help="MAX user_id для --simulate-command",
    )
    parser.add_argument(
        "--simulate-offline",
        action="store_true",
        help="Не подключать backend API во время --simulate-command",
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
            else AccessBackendClient(settings.max_backend_api_base)
        )
        response = simulate_command(
            command_text=args.simulate_command,
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

    client = MaxApiClient(token_value, api_base=settings.max_api_base)
    backend_client = (
        AccessBackendClient(settings.max_backend_api_base)
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

    bot.ensure_polling_available(drop_webhooks=args.drop_webhooks)

    if args.check:
        subscriptions = client.get_subscriptions().get("subscriptions") or []
        print(json.dumps(bot.bot_info, ensure_ascii=False, indent=2))
        print(f"[info] Активные webhook-подписки: {len(subscriptions)}")
        print(f"[info] Tenant по умолчанию: {settings.default_tenant_slug}")
        print(f"[info] Backend API: {settings.max_backend_api_base or 'выключен'}")
        for warning in settings.config_warnings():
            print(f"[warn] {warning}")
        for item in subscriptions:
            url = item.get("url")
            if url:
                print(f" - {url}")
        return 0

    bot.run()
    return 0
