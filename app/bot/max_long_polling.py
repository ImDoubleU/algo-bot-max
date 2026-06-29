from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

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
CALLBACK_ROLE_PARENT = "role:parent"
CALLBACK_ROLE_STUDENT = "role:student"


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
        [callback_button("Помощь", CALLBACK_HELP)],
    ]
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
    rows = [[callback_button("В меню", CALLBACK_MENU)]]
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
        body: dict[str, Any],
        timeout: int = 15,
    ) -> dict[str, Any]:
        url = f"{self.api_base}{path}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            method=method.upper(),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
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
                print(f"[info] Удалена webhook-подписка: {url}")
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
            "Если нужна диагностика, можно отправить /id или /ping."
        )

    def help_response(self, user_id: int | None = None) -> BotResponse:
        return BotResponse(self.help_text(), self.main_menu_attachments(user_id))

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
        elif command == "/help":
            response = self.help_response(user_id=user_id)
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

        print(f"[skip] Неподдерживаемый update_type={update_type}")

    def run(self) -> None:
        marker = self.load_marker()
        bot_name = self.bot_info.get("first_name") or self.bot_info.get("name") or "MAX bot"
        bot_username = self.bot_info.get("username") or "-"

        print(f"[info] Бот запущен: {bot_name} (@{bot_username})")
        print(f"[info] Файл marker: {MARKER_FILE}")
        print("[info] Жду события. Для остановки нажмите Ctrl+C.")

        while self.running:
            try:
                page = self.client.get_updates(marker)
                updates = page.get("updates") or []
                next_marker = page.get("marker")

                for update in updates:
                    try:
                        self.handle_update(update)
                    except Exception as exc:  # noqa: BLE001
                        print(f"[error] Не получилось обработать событие: {exc}")

                if next_marker is not None:
                    marker = next_marker
                    self.save_marker(marker)

            except KeyboardInterrupt:
                print("\n[info] Остановлено пользователем.")
                break
            except MaxApiError as exc:
                print(f"[error] {exc}")
                time.sleep(3)
            except Exception as exc:  # noqa: BLE001
                print(f"[error] Неожиданная ошибка: {exc}")
                time.sleep(3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MAX-бот Алгоритмики в режиме long polling")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Проверить токен, данные бота и подписки без запуска polling",
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


def main() -> int:
    args = parse_args()
    token = os.getenv("MAX_BOT_TOKEN")

    if not token:
        print("Переменная MAX_BOT_TOKEN не задана.", file=sys.stderr)
        print('Пример PowerShell: $env:MAX_BOT_TOKEN = "your_token_here"', file=sys.stderr)
        return 1

    client = MaxApiClient(token)
    backend_client = AccessBackendClient(BACKEND_API_BASE) if BACKEND_API_BASE else None
    bot = LongPollingBot(
        client,
        backend_client=backend_client,
        default_tenant_slug=DEFAULT_TENANT_SLUG,
    )

    if args.reset_marker:
        bot.reset_marker()
        print(f"[info] Marker удален: {MARKER_FILE}")

    bot.ensure_polling_available(drop_webhooks=args.drop_webhooks)

    if args.check:
        subscriptions = client.get_subscriptions().get("subscriptions") or []
        print(json.dumps(bot.bot_info, ensure_ascii=False, indent=2))
        print(f"[info] Активные webhook-подписки: {len(subscriptions)}")
        print(f"[info] Tenant по умолчанию: {DEFAULT_TENANT_SLUG}")
        print(f"[info] Backend API: {BACKEND_API_BASE or 'выключен'}")
        for item in subscriptions:
            url = item.get("url")
            if url:
                print(f" - {url}")
        return 0

    bot.run()
    return 0
