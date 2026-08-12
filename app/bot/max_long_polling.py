from __future__ import annotations

import argparse
import hmac
import json
import logging
import secrets
import sys
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from app.bot.backend_client import AccessBackendClient, BackendApiError
from app.bot.keyboards import (
    CALLBACK_FEEDBACK,
    CALLBACK_HELP,
    CALLBACK_KNOWLEDGE,
    CALLBACK_MENU,
    CALLBACK_MINIAPP,
    CALLBACK_ONBOARDING_CANCEL,
    CALLBACK_ONBOARDING_RESTART,
    CALLBACK_ROLE_PARENT,
    CALLBACK_ROLE_STUDENT,
    build_miniapp_url,
    cabinet_keyboard,
    feedback_courses_keyboard,
    feedback_drafts_keyboard,
    feedback_groups_keyboard,
    feedback_lessons_keyboard,
    feedback_menu_keyboard,
    feedback_preview_keyboard,
    feedback_setup_keyboard,
    inline_keyboard_with_main_menu,
    knowledge_menu_keyboard,
    knowledge_section_keyboard,
    main_menu_keyboard,
    miniapp_button,
    onboarding_cancelled_keyboard,
    onboarding_contact_keyboard,
    parse_feedback_payload,
    parse_knowledge_payload,
    parse_staff_join_payload,
    role_selection_keyboard,
    staff_approval_keyboard,
    staff_role_keyboard,
    staff_role_label,
    staff_tenant_keyboard,
    without_open_app_buttons,
)
from app.bot.max_client import MaxApiClient, MaxApiError, SimulationMaxClient
from app.bot.models import (
    BotResponse,
    PendingContact,
    PendingStaffInvite,
    PendingStaffRequest,
)
from app.bot.runtime import MARKER_FILE, configure_logging
from app.core.config import get_settings, is_placeholder
from app.services.deep_links import (
    parse_contact_payload,
    parse_shop_payload,
)
from app.services.knowledge_base import (
    KnowledgeBaseError,
    KnowledgeBaseService,
    clean_knowledge_label,
)

logger = logging.getLogger("algo_bot_max.bot")
POLL_RETRY_INITIAL_SECONDS = 1.0
POLL_RETRY_MAX_SECONDS = 30.0
FEEDBACK_PAGE_SIZE = 8
STAFF_INVITE_TTL_SECONDS = 30 * 60
STAFF_REQUEST_TTL_SECONDS = 24 * 60 * 60
ONBOARDING_TTL_SECONDS = 30 * 60
FEEDBACK_LESSON_MODES = (
    ("group", "offline", "группа офлайн"),
    ("group", "online", "группа онлайн"),
    ("individual", "offline", "индивидуально"),
)
STAFF_MENU_ROLES = {
    "teacher",
    "curator",
    "admin",
    "partner_director",
    "superadmin",
}


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
            return "ID из письма не найден для выбранного города."
        if detail and detail != text:
            return f"Не найдено: {detail}"
        return "Не удалось найти нужные данные."
    return str(exc)


class LongPollingBot:
    def __init__(
        self,
        client: MaxApiClient,
        *,
        backend_client: AccessBackendClient | None = None,
        default_tenant_slug: str | None = None,
    ) -> None:
        settings = get_settings()
        self.client = client
        self.backend_client = backend_client
        self.default_tenant_slug = default_tenant_slug or settings.default_tenant_slug
        self.bot_info = self.client.get_me()
        self.bot_user_id = self.bot_info.get("user_id")
        self.pending_contact_ids: dict[int, PendingContact] = {}
        self.pending_onboarding_roles: dict[int, tuple[str, float]] = {}
        self.pending_staff_invites: dict[int, PendingStaffInvite] = {}
        self.pending_staff_requests: dict[str, PendingStaffRequest] = {}
        self.user_tenant_slugs: dict[int, str] = {}
        self.user_menu_roles: dict[tuple[int, str], str] = {}
        self.feedback_drafts: dict[int, dict[str, Any]] = {}
        invite_command = (settings.max_staff_invite_command or "").strip().casefold()
        self.staff_invite_command = (
            invite_command
            if invite_command.startswith("/")
            and " " not in invite_command
            and len(invite_command) >= 3
            else None
        )
        try:
            approver_user_id = int(str(settings.initial_superadmin_max_user_id or "").strip())
        except ValueError:
            self.staff_approver_user_id = None
        else:
            self.staff_approver_user_id = approver_user_id if approver_user_id > 0 else None
        self.knowledge_base = KnowledgeBaseService()
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
        user_id = sender.get("user_id") or recipient.get("user_id")
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
        try:
            self.send_reply(
                text=response.text,
                attachments=response.attachments,
                chat_id=chat_id,
                user_id=user_id,
            )
        except MaxApiError:
            fallback_attachments = without_open_app_buttons(response.attachments)
            if fallback_attachments == response.attachments:
                raise
            logger.warning("MAX rejected open_app button; retrying response without it")
            self.send_reply(
                text=response.text,
                attachments=fallback_attachments,
                chat_id=chat_id,
                user_id=user_id,
            )

    def answer_callback_response(
        self,
        *,
        callback_id: str,
        response: BotResponse,
        notification: str | None,
    ) -> None:
        try:
            self.client.answer_callback(
                callback_id=callback_id,
                response=response,
                notification=notification,
            )
        except MaxApiError:
            fallback_attachments = without_open_app_buttons(response.attachments)
            if fallback_attachments == response.attachments:
                raise
            logger.warning("MAX rejected open_app button; retrying callback without it")
            self.client.answer_callback(
                callback_id=callback_id,
                response=BotResponse(response.text, fallback_attachments),
                notification=notification,
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

    def help_response(self, user_id: int | None = None, topic: str = "") -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        role = self.menu_role(user_id, tenant_slug)
        return BotResponse(
            self.role_help_text(role),
            self.main_menu_attachments(user_id),
        )

    def main_menu_response(self, user_id: int | None = None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        role = self.menu_role(user_id, tenant_slug) if user_id is not None else None
        if user_id is not None and role is None:
            return self.first_entry_response(user_id)
        title = {
            "student": "Кабинет ученика",
            "parent": "Семейный кабинет",
            "teacher": "Кабинет преподавателя",
            "curator": "Кабинет куратора",
            "admin": "Кабинет администратора",
            "partner_director": "Кабинет директора",
            "superadmin": "Управление партнерами",
        }.get(role, "Главное меню")
        hint = (
            "Откройте кабинет кнопкой ниже."
            if role in {"student", "parent"}
            else "Откройте рабочий кабинет или выберите раздел бота."
        )
        return BotResponse(
            f"{title}\n\n{hint}",
            self.main_menu_attachments(user_id),
        )

    @staticmethod
    def role_help_text(role: str | None) -> str:
        if role == "student":
            return (
                "Личный кабинет ученика\n\n"
                "Баланс, магазин, заказы и история начисления астрокоинов "
                "находятся в личном кабинете.\n\n"
                "Откройте его кнопкой ниже."
            )
        if role == "parent":
            return (
                "Семейный кабинет\n\n"
                "Дети, балансы, магазин и заказы находятся в семейном кабинете.\n\n"
                "Обратная связь от преподавателя приходит отдельным сообщением."
            )
        if role in {"teacher", "curator"}:
            role_title = "Кабинет куратора" if role == "curator" else "Рабочий кабинет"
            return (
                f"{role_title}\n\n"
                "Расписание, ученики, начисления и заказы находятся в приложении.\n\n"
                "Для подготовки и отправки сообщения родителям откройте отдельный "
                "раздел «Обратная связь». Инструкции и рабочие ссылки находятся "
                "в разделе «База знаний»."
            )
        if role in {"admin", "partner_director", "superadmin"}:
            role_title = {
                "admin": "Рабочий кабинет",
                "partner_director": "Кабинет директора",
                "superadmin": "Кабинет суперадминистратора",
            }[role]
            return (
                f"{role_title}\n\n"
                "Управление, импорт, склады, заказы и пользователи находятся в приложении.\n\n"
                "Подготовка сообщений родителям вынесена в раздел «Обратная связь», "
                "инструкции и ссылки — в раздел «База знаний»."
            )
        return "Откройте личный кабинет или выберите доступный раздел кнопкой ниже."

    def first_entry_response(self, user_id: int | None) -> BotResponse:
        if user_id is not None and self.backend_client is not None:
            tenant_slug = self.current_tenant_slug(user_id)
            try:
                discover_session = getattr(self.backend_client, "discover_session", None)
                session = (
                    discover_session(
                        default_tenant_slug=self.default_tenant_slug,
                        max_user_id=user_id,
                    )
                    if callable(discover_session)
                    else self.backend_client.get_session(
                        tenant_slug=tenant_slug,
                        max_user_id=user_id,
                    )
                )
            except BackendApiError:
                session = None
            if session and (
                session.get("staff_roles")
                or session.get("student_roles")
                or session.get("students")
            ):
                discovered_tenant = str(session.get("tenant_slug") or tenant_slug)
                self.user_tenant_slugs[user_id] = discovered_tenant
                self.remember_session_role(user_id, discovered_tenant, session)
                return self.help_response(user_id=user_id)
        return BotResponse(
            (
                "Вход · шаг 1 из 2\n\n"
                "Выберите, чей профиль вы привязываете. "
                "Родителю понадобится ID из письма школы, ребенку — QR-код из кабинета родителя."
            ),
            role_selection_keyboard(),
        )

    def restart_onboarding_response(self, user_id: int | None) -> BotResponse:
        if user_id is not None:
            self.pending_contact_ids.pop(user_id, None)
            self.pending_onboarding_roles.pop(user_id, None)
        return BotResponse(
            "Вход · шаг 1 из 2\n\nВыберите роль для входа.",
            role_selection_keyboard(),
        )

    def cancel_onboarding_response(self, user_id: int | None) -> BotResponse:
        if user_id is not None:
            self.pending_contact_ids.pop(user_id, None)
            self.pending_onboarding_roles.pop(user_id, None)
        return BotResponse(
            "Вход отменен. Данные не сохранены.",
            onboarding_cancelled_keyboard(),
        )

    def cleanup_staff_onboarding(self) -> None:
        now = time.monotonic()
        self.pending_staff_invites = {
            user_id: invite
            for user_id, invite in self.pending_staff_invites.items()
            if now - invite.created_at <= STAFF_INVITE_TTL_SECONDS
        }
        self.pending_staff_requests = {
            request_id: request
            for request_id, request in self.pending_staff_requests.items()
            if now - request.created_at <= STAFF_REQUEST_TTL_SECONDS
        }

    def cleanup_customer_onboarding(self) -> None:
        now = time.monotonic()
        self.pending_contact_ids = {
            user_id: pending
            for user_id, pending in self.pending_contact_ids.items()
            if now - pending.created_at <= ONBOARDING_TTL_SECONDS
        }
        self.pending_onboarding_roles = {
            user_id: pending
            for user_id, pending in self.pending_onboarding_roles.items()
            if now - pending[1] <= ONBOARDING_TTL_SECONDS
        }

    def is_staff_invite_command(self, command: str) -> bool:
        return bool(
            self.staff_invite_command and hmac.compare_digest(command, self.staff_invite_command)
        )

    def staff_invite_start_response(
        self,
        *,
        user_id: int | None,
        username: str | None,
        display_name: str | None,
    ) -> BotResponse:
        if user_id is None or self.backend_client is None or self.staff_approver_user_id is None:
            return BotResponse(
                "Регистрация сотрудников сейчас недоступна.",
                self.main_menu_attachments(user_id),
            )

        try:
            options = self.backend_client.get_staff_onboarding_options(
                tenant_slug=self.default_tenant_slug,
                max_user_id=self.staff_approver_user_id,
            )
        except BackendApiError as exc:
            logger.warning("Could not load staff onboarding options: %s", exc)
            return BotResponse(
                "Не удалось загрузить список городов. Попробуйте немного позже.",
                self.main_menu_attachments(user_id),
            )

        tenants = [
            tenant
            for tenant in options.get("tenants") or []
            if isinstance(tenant, dict) and tenant.get("tenant_slug")
        ]
        allowed_roles = ("partner_director", "admin", "curator", "teacher")
        roles = [str(role) for role in options.get("roles") or [] if str(role) in allowed_roles]
        if not tenants or not roles:
            return BotResponse(
                "Для регистрации пока нет доступных городов или ролей.",
                self.main_menu_attachments(user_id),
            )

        self.cleanup_staff_onboarding()
        self.pending_staff_invites[user_id] = PendingStaffInvite(
            created_at=time.monotonic(),
            username=username,
            display_name=display_name,
            tenants=tenants,
            roles=roles,
        )
        self.pending_staff_requests = {
            request_id: request
            for request_id, request in self.pending_staff_requests.items()
            if request.max_user_id != user_id
        }
        return BotResponse(
            (
                "Регистрация сотрудника\n\n"
                f"Ваш MAX ID: {user_id}\n\n"
                "Выберите город, в котором вы работаете."
            ),
            staff_tenant_keyboard(tenants),
        )

    @staticmethod
    def staff_request_text(
        request: PendingStaffRequest,
        *,
        heading: str,
    ) -> str:
        employee_name = request.display_name or (
            f"@{request.username}" if request.username else "Не указано"
        )
        lines = [
            heading,
            "",
            f"Сотрудник: {employee_name}",
            f"MAX ID: {request.max_user_id}",
        ]
        if request.username:
            lines.append(f"Логин: @{request.username.lstrip('@')}")
        lines.extend(
            [
                f"Город: {request.city_name}",
                f"Организация: {request.tenant_name}",
                f"Роль: {staff_role_label(request.role)}",
            ]
        )
        return "\n".join(lines)

    def staff_invite_state(self, user_id: int | None) -> PendingStaffInvite | None:
        if user_id is None:
            return None
        self.cleanup_staff_onboarding()
        return self.pending_staff_invites.get(user_id)

    def submit_staff_request(
        self,
        *,
        user_id: int,
        invite: PendingStaffInvite,
        role: str,
    ) -> BotResponse:
        tenant = next(
            (item for item in invite.tenants if item.get("tenant_slug") == invite.tenant_slug),
            None,
        )
        if tenant is None or self.staff_approver_user_id is None:
            return BotResponse(
                "Сначала выберите город.",
                staff_tenant_keyboard(invite.tenants),
            )

        request_id = secrets.token_urlsafe(6)
        while request_id in self.pending_staff_requests:
            request_id = secrets.token_urlsafe(6)
        request = PendingStaffRequest(
            request_id=request_id,
            created_at=time.monotonic(),
            max_user_id=user_id,
            username=invite.username,
            display_name=invite.display_name,
            tenant_slug=str(tenant["tenant_slug"]),
            tenant_name=str(tenant.get("tenant_name") or tenant["tenant_slug"]),
            city_name=str(
                tenant.get("city_name") or tenant.get("tenant_name") or tenant["tenant_slug"]
            ),
            role=role,
        )
        self.pending_staff_requests[request_id] = request
        try:
            self.send_response(
                BotResponse(
                    self.staff_request_text(
                        request,
                        heading="Новая заявка сотрудника",
                    ),
                    staff_approval_keyboard(request_id),
                ),
                user_id=self.staff_approver_user_id,
            )
        except MaxApiError as exc:
            self.pending_staff_requests.pop(request_id, None)
            logger.warning("Could not notify staff approver: %s", exc)
            return BotResponse(
                "Не удалось отправить заявку на подтверждение. Попробуйте позже.",
                staff_role_keyboard(invite.roles),
            )

        self.pending_staff_invites.pop(user_id, None)
        return BotResponse(
            (
                "Заявка отправлена на подтверждение.\n\n"
                f"MAX ID: {request.max_user_id}\n"
                f"Город: {request.city_name}\n"
                f"Роль: {staff_role_label(request.role)}\n\n"
                "После решения бот пришлет отдельное сообщение."
            ),
            self.main_menu_attachments(user_id),
        )

    def decide_staff_request(
        self,
        *,
        approver_user_id: int | None,
        request_id: str | None,
        approved: bool,
    ) -> BotResponse:
        if approver_user_id is None or approver_user_id != self.staff_approver_user_id:
            return BotResponse(
                "Подтверждение доступно только суперадминистратору.",
                self.main_menu_attachments(approver_user_id),
            )

        self.cleanup_staff_onboarding()
        request = self.pending_staff_requests.get(request_id or "")
        if request is None:
            return BotResponse(
                "Заявка уже обработана или устарела.",
                self.main_menu_attachments(approver_user_id),
            )

        if not approved:
            self.pending_staff_requests.pop(request.request_id, None)
            notification_sent = True
            try:
                self.send_response(
                    BotResponse(
                        (
                            "Заявка на доступ отклонена.\n\n"
                            f"Город: {request.city_name}\n"
                            f"Роль: {staff_role_label(request.role)}"
                        ),
                        self.main_menu_attachments(request.max_user_id),
                    ),
                    user_id=request.max_user_id,
                )
            except MaxApiError as exc:
                notification_sent = False
                logger.warning("Could not notify rejected staff applicant: %s", exc)
            suffix = "" if notification_sent else "\n\nУведомить сотрудника не удалось."
            return BotResponse(
                self.staff_request_text(
                    request,
                    heading="Заявка отклонена",
                )
                + suffix,
                self.main_menu_attachments(approver_user_id),
            )

        if self.backend_client is None:
            return BotResponse(
                "Backend API недоступен. Заявка не обработана.",
                self.main_menu_attachments(approver_user_id),
            )
        try:
            self.backend_client.update_staff_assignment(
                tenant_slug=request.tenant_slug,
                max_user_id=approver_user_id,
                target_max_user_id=request.max_user_id,
                role=request.role,
                status="active",
                username=request.username,
                display_name=request.display_name,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    self.staff_request_text(
                        request,
                        heading="Не удалось подтвердить заявку",
                    )
                    + f"\n\nПричина: {format_backend_error(exc)}"
                ),
                staff_approval_keyboard(request.request_id),
            )

        self.pending_staff_requests.pop(request.request_id, None)
        self.user_tenant_slugs[request.max_user_id] = request.tenant_slug
        self.user_menu_roles = {
            key: value
            for key, value in self.user_menu_roles.items()
            if key[0] != request.max_user_id
        }
        self.user_menu_roles[(request.max_user_id, request.tenant_slug)] = request.role

        notification_sent = True
        try:
            self.send_response(
                BotResponse(
                    (
                        "Доступ сотрудника подтвержден.\n\n"
                        f"Город: {request.city_name}\n"
                        f"Роль: {staff_role_label(request.role)}\n\n"
                        "Рабочий кабинет доступен в главном меню."
                    ),
                    cabinet_keyboard(
                        user_id=request.max_user_id,
                        tenant_slug=request.tenant_slug,
                        role=request.role,
                    ),
                ),
                user_id=request.max_user_id,
            )
        except MaxApiError as exc:
            notification_sent = False
            logger.warning("Could not notify approved staff applicant: %s", exc)

        suffix = (
            "" if notification_sent else "\n\nРоль назначена, но уведомить сотрудника не удалось."
        )
        return BotResponse(
            self.staff_request_text(
                request,
                heading="Заявка подтверждена",
            )
            + suffix,
            self.main_menu_attachments(approver_user_id),
        )

    def staff_join_callback_response(
        self,
        *,
        user_id: int | None,
        action: str,
        value: str | None,
    ) -> BotResponse:
        if action in {"approve", "reject"}:
            return self.decide_staff_request(
                approver_user_id=user_id,
                request_id=value,
                approved=action == "approve",
            )

        if action == "cancel":
            if user_id is not None:
                self.pending_staff_invites.pop(user_id, None)
            return BotResponse(
                "Регистрация сотрудника отменена.",
                self.main_menu_attachments(user_id),
            )

        invite = self.staff_invite_state(user_id)
        if invite is None:
            return BotResponse(
                "Время регистрации истекло. Запросите команду повторно.",
                self.main_menu_attachments(user_id),
            )

        if action == "cities":
            invite.tenant_slug = None
            return BotResponse(
                f"Ваш MAX ID: {user_id}\n\nВыберите город.",
                staff_tenant_keyboard(invite.tenants),
            )

        if action == "tenant":
            tenant = next(
                (item for item in invite.tenants if item.get("tenant_slug") == value),
                None,
            )
            if tenant is None:
                return BotResponse(
                    "Этот город недоступен. Выберите вариант из списка.",
                    staff_tenant_keyboard(invite.tenants),
                )
            invite.tenant_slug = str(tenant["tenant_slug"])
            return BotResponse(
                (
                    f"Город: {tenant.get('city_name') or tenant.get('tenant_name')}\n"
                    f"MAX ID: {user_id}\n\n"
                    "Выберите вашу роль."
                ),
                staff_role_keyboard(invite.roles),
            )

        if action == "role" and value in invite.roles and user_id is not None:
            return self.submit_staff_request(
                user_id=user_id,
                invite=invite,
                role=str(value),
            )

        return BotResponse(
            "Выберите роль кнопкой ниже.",
            staff_role_keyboard(invite.roles),
        )

    def knowledge_menu_response(self, user_id: int | None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        role = self.menu_role(user_id, tenant_slug)
        if role not in STAFF_MENU_ROLES:
            return BotResponse(
                "База знаний доступна сотрудникам.",
                self.main_menu_attachments(user_id),
            )
        try:
            sections = self.knowledge_base.main_sections()
        except KnowledgeBaseError as exc:
            return BotResponse(
                str(exc),
                self.main_menu_attachments(user_id),
            )
        return BotResponse(
            "База знаний\n\nВыберите раздел.",
            knowledge_menu_keyboard(sections),
        )

    def knowledge_section_response(
        self,
        *,
        user_id: int | None,
        section_id: str,
    ) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        role = self.menu_role(user_id, tenant_slug)
        if role not in STAFF_MENU_ROLES:
            return BotResponse(
                "База знаний доступна сотрудникам.",
                self.main_menu_attachments(user_id),
            )
        try:
            section = self.knowledge_base.section(section_id)
            section_ids = self.knowledge_base.section_ids()
        except KnowledgeBaseError as exc:
            return BotResponse(
                str(exc),
                self.main_menu_attachments(user_id),
            )
        if section is None:
            return self.knowledge_menu_response(user_id)
        title = clean_knowledge_label(str(section.get("title") or "База знаний"))
        text = str(section.get("text") or "").strip()
        return BotResponse(
            f"{title}\n\n{text}" if text else title,
            knowledge_section_keyboard(section, section_ids=section_ids),
        )

    def miniapp_response(self, user_id: int | None = None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        miniapp_url = build_miniapp_url(user_id=user_id, tenant_slug=tenant_slug)
        if not miniapp_url:
            return BotResponse(
                ("Приложение пока недоступно. Попробуйте позже."),
                self.main_menu_attachments(user_id),
            )

        return BotResponse(
            (f"Личный кабинет:\n{miniapp_url}\n\nОткройте ссылку кнопкой ниже."),
            self.cabinet_attachments(user_id, tenant_slug),
        )

    def feedback_menu_response(self, user_id: int | None = None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        if user_id is None or self.backend_client is None:
            return BotResponse(
                "Раздел обратной связи временно недоступен.",
                self.main_menu_attachments(user_id),
            )
        try:
            outputs = self.backend_client.get_manual_feedback_outputs(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                f"Не получилось открыть обратную связь.\n\n{format_backend_error(exc)}",
                self.main_menu_attachments(user_id),
            )

        lines = [
            "Обратная связь",
            "",
            "Здесь ОС создается вручную: выберите группу, курс и конкретный урок.",
            "Расписание и автоматическое формирование находятся в приложении.",
        ]
        unsent_count = sum(
            1 for output in outputs if str(output.get("status") or "") != "sent_to_parents"
        )
        if unsent_count:
            lines.extend(["", f"Готовых черновиков: {unsent_count}."])
        return BotResponse(
            "\n".join(lines),
            feedback_menu_keyboard(outputs),
        )

    def feedback_drafts_response(self, user_id: int | None = None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        if user_id is None or self.backend_client is None:
            return self.feedback_menu_response(user_id)
        try:
            outputs = self.backend_client.get_manual_feedback_outputs(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                f"Не получилось загрузить черновики.\n\n{format_backend_error(exc)}",
                self.main_menu_attachments(user_id),
            )
        outputs = [
            output for output in outputs if str(output.get("status") or "") != "sent_to_parents"
        ]
        text = (
            "Готовые черновики ОС\n\nВыберите черновик для просмотра и отправки."
            if outputs
            else "Готовых черновиков пока нет."
        )
        return BotResponse(text, feedback_drafts_keyboard(outputs))

    def feedback_manual_start_response(self, user_id: int | None) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        if user_id is None or self.backend_client is None:
            return self.feedback_menu_response(user_id)
        try:
            workspace = self.backend_client.get_teaching_workspace(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
            session = self.backend_client.get_session(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                f"Не получилось начать ручную ОС.\n\n{format_backend_error(exc)}",
                self.main_menu_attachments(user_id),
            )

        group_options: dict[str, dict[str, Any]] = {}
        for group in workspace.get("groups") or []:
            group_name = str(group.get("name") or "").strip()
            if not group_name:
                continue
            key = group_name.casefold()
            if key not in group_options:
                group_options[key] = dict(group)
                continue
            group_options[key]["student_count"] = max(
                int(group_options[key].get("student_count") or 0),
                int(group.get("student_count") or 0),
            )
            if not group_options[key].get("course_name") and group.get("course_name"):
                group_options[key]["course_name"] = group["course_name"]
        groups = sorted(
            group_options.values(),
            key=lambda group: str(group.get("name") or "").casefold(),
        )
        courses = sorted(
            [
                course
                for course in workspace.get("courses") or []
                if str(course.get("id") or "").strip()
            ],
            key=lambda course: str(course.get("name") or "").casefold(),
        )
        if not groups:
            return BotResponse(
                "Для ручной ОС нет доступных групп с активными учениками.",
                self.main_menu_attachments(user_id),
            )
        if not courses:
            return BotResponse(
                "Справочник курсов пуст. Сначала импортируйте курсы.",
                self.main_menu_attachments(user_id),
            )
        self.feedback_drafts[user_id] = {
            "tenant_slug": tenant_slug,
            "groups": groups,
            "courses": courses,
            "session_students": list(session.get("students") or []),
            "students": [],
            "absent_student_ids": set(),
            "is_repetition": False,
            "lesson_mode_index": 0,
        }
        return self.feedback_groups_response(user_id=user_id, page=0)

    def feedback_groups_response(
        self,
        *,
        user_id: int | None,
        page: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_manual_start_response(user_id)
        draft = self.feedback_drafts[user_id]
        groups = list(draft.get("groups") or [])
        start = max(page, 0) * FEEDBACK_PAGE_SIZE
        text = (
            "Ручная ОС · шаг 1 из 3\n\n"
            f"Выберите группу. Показано {min(start + 1, len(groups))}–"
            f"{min(start + FEEDBACK_PAGE_SIZE, len(groups))} из {len(groups)}."
        )
        return BotResponse(
            text,
            feedback_groups_keyboard(groups, page=max(page, 0)),
        )

    def feedback_group_response(
        self,
        *,
        user_id: int | None,
        group_index: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_manual_start_response(user_id)
        draft = self.feedback_drafts[user_id]
        groups = list(draft.get("groups") or [])
        if group_index < 0 or group_index >= len(groups):
            return self.feedback_groups_response(user_id=user_id, page=0)
        group = groups[group_index]
        group_name = str(group.get("name") or "").strip()
        students = sorted(
            [
                student
                for student in draft.get("session_students") or []
                if str(student.get("group_name") or "").strip().casefold() == group_name.casefold()
            ],
            key=lambda student: str(student.get("display_name") or "").casefold(),
        )
        preferred_course = str(group.get("course_name") or "").strip().casefold()
        courses = sorted(
            list(draft.get("courses") or []),
            key=lambda course: (
                str(course.get("name") or "").strip().casefold() != preferred_course,
                str(course.get("name") or "").casefold(),
            ),
        )
        draft.update(
            {
                "group": group,
                "students": students,
                "course_options": courses,
                "absent_student_ids": set(),
                "attendance_page": 0,
                "course": None,
                "lessons": [],
                "lesson": None,
            }
        )
        return self.feedback_courses_response(user_id=user_id, page=0)

    def feedback_courses_response(
        self,
        *,
        user_id: int | None,
        page: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_manual_start_response(user_id)
        draft = self.feedback_drafts[user_id]
        if not draft.get("group"):
            return self.feedback_groups_response(user_id=user_id, page=0)
        courses = list(draft.get("course_options") or draft.get("courses") or [])
        group_name = draft["group"].get("name") or "Группа"
        return BotResponse(
            f"Ручная ОС · шаг 2 из 3\n\nГруппа: {group_name}\nВыберите курс.",
            feedback_courses_keyboard(courses, page=max(page, 0)),
        )

    def feedback_course_response(
        self,
        *,
        user_id: int | None,
        course_index: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_manual_start_response(user_id)
        draft = self.feedback_drafts[user_id]
        courses = list(draft.get("course_options") or draft.get("courses") or [])
        if course_index < 0 or course_index >= len(courses):
            return self.feedback_courses_response(user_id=user_id, page=0)
        course = courses[course_index]
        try:
            lessons = self.backend_client.get_course_lessons(
                course_id=str(course.get("id") or ""),
                tenant_slug=str(draft["tenant_slug"]),
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                f"Не получилось загрузить уроки.\n\n{format_backend_error(exc)}",
                feedback_courses_keyboard(courses, page=0),
            )
        draft.update({"course": course, "lessons": lessons, "lesson": None})
        return self.feedback_lessons_response(user_id=user_id, page=0)

    def feedback_lessons_response(
        self,
        *,
        user_id: int | None,
        page: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_manual_start_response(user_id)
        draft = self.feedback_drafts[user_id]
        if not draft.get("course"):
            return self.feedback_courses_response(user_id=user_id, page=0)
        lessons = list(draft.get("lessons") or [])
        course_name = draft["course"].get("name") or "Курс"
        return BotResponse(
            f"Ручная ОС · шаг 3 из 3\n\nКурс: {course_name}\nВыберите урок.",
            feedback_lessons_keyboard(lessons, page=max(page, 0)),
        )

    def feedback_lesson_response(
        self,
        *,
        user_id: int | None,
        lesson_index: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_manual_start_response(user_id)
        draft = self.feedback_drafts[user_id]
        lessons = list(draft.get("lessons") or [])
        if lesson_index < 0 or lesson_index >= len(lessons):
            return self.feedback_lessons_response(user_id=user_id, page=0)
        draft["lesson"] = lessons[lesson_index]
        draft["lesson_date"] = datetime.now().date().isoformat()
        return self.feedback_draft_response(user_id)

    def feedback_draft_response(self, user_id: int | None) -> BotResponse:
        if user_id is None:
            return self.feedback_menu_response(user_id)
        draft = self.feedback_drafts.get(user_id)
        if not draft:
            return BotResponse(
                "Черновик завершен. Выберите группу заново.",
                self.main_menu_attachments(user_id),
            )
        if not draft.get("group") or not draft.get("course") or not draft.get("lesson"):
            return self.feedback_groups_response(user_id=user_id, page=0)
        group = draft["group"]
        course = draft["course"]
        lesson = draft["lesson"]
        students = list(draft["students"])
        absent_ids = set(draft["absent_student_ids"])
        attendance_page = max(int(draft.get("attendance_page") or 0), 0)
        lesson_date = datetime.fromisoformat(str(draft["lesson_date"])).date()
        mode_index = int(draft.get("lesson_mode_index") or 0) % len(FEEDBACK_LESSON_MODES)
        _, _, lesson_mode_label = FEEDBACK_LESSON_MODES[mode_index]
        absent_names = [
            str(student.get("display_name") or "Ученик")
            for student in students
            if str(student.get("student_id") or "") in absent_ids
        ]
        lines = [
            f"Ручная ОС · {group.get('name') or 'Группа'}",
            "",
            f"{course.get('name') or 'Курс'}",
            f"Урок {lesson.get('lesson_number') or 1}: {lesson.get('title') or 'Тема урока'}",
            f"Дата: {lesson_date:%d.%m.%Y}",
            f"Формат: {lesson_mode_label}.",
            "",
            "Нажмите на ученика, если он отсутствовал.",
            (f"Отсутствуют: {', '.join(absent_names)}" if absent_names else "Все были на уроке."),
            (
                "Тема: повторение прошлого урока."
                if draft["is_repetition"]
                else "Тема: выбранный урок."
            ),
        ]
        if len(students) > 10:
            start = attendance_page * 10
            lines.extend(
                [
                    "",
                    f"Ученики {min(start + 1, len(students))}–"
                    f"{min(start + 10, len(students))} из {len(students)}.",
                ]
            )
        return BotResponse(
            "\n".join(lines),
            feedback_setup_keyboard(
                students,
                absent_student_ids=absent_ids,
                is_repetition=bool(draft["is_repetition"]),
                lesson_mode_label=lesson_mode_label,
                attendance_page=attendance_page,
            ),
        )

    def feedback_toggle_absent_response(
        self,
        *,
        user_id: int | None,
        student_id: str,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_draft_response(user_id)
        draft = self.feedback_drafts[user_id]
        available_ids = {str(student.get("student_id") or "") for student in draft["students"]}
        if student_id not in available_ids:
            return self.feedback_draft_response(user_id)
        absent_ids = set(draft["absent_student_ids"])
        if student_id in absent_ids:
            absent_ids.remove(student_id)
        else:
            absent_ids.add(student_id)
        draft["absent_student_ids"] = absent_ids
        return self.feedback_draft_response(user_id)

    def feedback_toggle_repetition_response(self, user_id: int | None) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_draft_response(user_id)
        draft = self.feedback_drafts[user_id]
        draft["is_repetition"] = not bool(draft["is_repetition"])
        return self.feedback_draft_response(user_id)

    def feedback_attendance_page_response(
        self,
        *,
        user_id: int | None,
        page: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_draft_response(user_id)
        draft = self.feedback_drafts[user_id]
        students = list(draft.get("students") or [])
        last_page = max((len(students) - 1) // 10, 0)
        draft["attendance_page"] = max(0, min(page, last_page))
        return self.feedback_draft_response(user_id)

    def feedback_shift_date_response(
        self,
        *,
        user_id: int | None,
        days: int,
    ) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_draft_response(user_id)
        draft = self.feedback_drafts[user_id]
        current = datetime.fromisoformat(str(draft["lesson_date"])).date()
        draft["lesson_date"] = (current + timedelta(days=max(-1, min(days, 1)))).isoformat()
        return self.feedback_draft_response(user_id)

    def feedback_cycle_mode_response(self, user_id: int | None) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_draft_response(user_id)
        draft = self.feedback_drafts[user_id]
        current = int(draft.get("lesson_mode_index") or 0)
        draft["lesson_mode_index"] = (current + 1) % len(FEEDBACK_LESSON_MODES)
        return self.feedback_draft_response(user_id)

    def feedback_generate_response(self, user_id: int | None) -> BotResponse:
        if user_id is None or user_id not in self.feedback_drafts:
            return self.feedback_draft_response(user_id)
        if self.backend_client is None:
            return self.feedback_menu_response(user_id)
        draft = self.feedback_drafts[user_id]
        absent_ids = set(draft["absent_student_ids"])
        absent_names = [
            str(student.get("display_name") or "Ученик")
            for student in draft["students"]
            if str(student.get("student_id") or "") in absent_ids
        ]
        group = draft["group"]
        course = draft["course"]
        lesson = draft["lesson"]
        mode_index = int(draft.get("lesson_mode_index") or 0) % len(FEEDBACK_LESSON_MODES)
        lesson_mode, lesson_place, _ = FEEDBACK_LESSON_MODES[mode_index]
        try:
            output = self.backend_client.generate_manual_feedback(
                tenant_slug=str(draft["tenant_slug"]),
                max_user_id=user_id,
                group_name=str(group.get("name") or ""),
                course_id=str(course.get("id") or ""),
                lesson_number=int(lesson.get("lesson_number") or 1),
                lesson_date=str(draft["lesson_date"]),
                lesson_mode=lesson_mode,
                lesson_place=lesson_place,
                absent_students=absent_names,
                is_repetition=bool(draft["is_repetition"]),
            )
        except BackendApiError as exc:
            setup = self.feedback_draft_response(user_id)
            return BotResponse(
                f"Не получилось сформировать ОС.\n\n{format_backend_error(exc)}",
                setup.attachments,
            )
        draft["output_id"] = str(output.get("id") or "")
        return self.feedback_output_preview_response(output)

    def feedback_output_response(
        self,
        *,
        user_id: int | None,
        output_id: str,
    ) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        if user_id is None or self.backend_client is None:
            return self.feedback_menu_response(user_id)
        try:
            outputs = self.backend_client.get_manual_feedback_outputs(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                f"Не получилось открыть черновик.\n\n{format_backend_error(exc)}",
                self.main_menu_attachments(user_id),
            )
        output = next(
            (item for item in outputs if str(item.get("id") or "") == str(output_id)),
            None,
        )
        if output is None:
            return BotResponse(
                "Черновик не найден.",
                feedback_drafts_keyboard(outputs),
            )
        return self.feedback_output_preview_response(output)

    @staticmethod
    def feedback_output_preview_response(output: dict[str, Any]) -> BotResponse:
        text = (
            f"Черновик ОС · {output.get('group_name') or 'Группа'}\n\n"
            f"{output.get('feedback_text') or 'Текст обратной связи пуст.'}"
        )
        return BotResponse(
            text,
            feedback_preview_keyboard(str(output.get("id") or "") or None),
        )

    def feedback_send_response(
        self,
        *,
        user_id: int | None,
        output_id: str,
    ) -> BotResponse:
        tenant_slug = self.current_tenant_slug(user_id)
        if user_id is None or self.backend_client is None:
            return self.feedback_menu_response(user_id)
        try:
            result = self.backend_client.send_manual_feedback(
                output_id=output_id,
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                f"Не получилось отправить обратную связь.\n\n{format_backend_error(exc)}",
                self.main_menu_attachments(user_id),
            )
        recipients = int(result.get("parent_recipients") or 0)
        sent = int(result.get("sent_recipients") or 0)
        if recipients and sent == recipients:
            text = f"Обратная связь отправлена всем родителям: {sent}."
        elif sent:
            text = f"Отправлено {sent} из {recipients}. Проверьте связи родителей."
        else:
            text = "Сообщения не отправлены. Проверьте связи родителей и доступ к боту."
        return BotResponse(text, self.main_menu_attachments(user_id))

    def feedback_callback_response(
        self,
        *,
        user_id: int | None,
        action: str,
        value: str | None,
    ) -> BotResponse:
        if action in {"manual", "schedule"}:
            return self.feedback_manual_start_response(user_id)
        try:
            numeric_value = int(value or "0")
        except ValueError:
            numeric_value = 0
        if action == "groups":
            return self.feedback_groups_response(user_id=user_id, page=numeric_value)
        if action == "group" and value is not None:
            return self.feedback_group_response(
                user_id=user_id,
                group_index=numeric_value,
            )
        if action == "courses":
            return self.feedback_courses_response(user_id=user_id, page=numeric_value)
        if action == "course" and value is not None:
            return self.feedback_course_response(
                user_id=user_id,
                course_index=numeric_value,
            )
        if action == "lessons":
            return self.feedback_lessons_response(user_id=user_id, page=numeric_value)
        if action == "lesson" and value is not None:
            return self.feedback_lesson_response(
                user_id=user_id,
                lesson_index=numeric_value,
            )
        if action == "absent" and value:
            return self.feedback_toggle_absent_response(
                user_id=user_id,
                student_id=value,
            )
        if action == "attendance":
            return self.feedback_attendance_page_response(
                user_id=user_id,
                page=numeric_value,
            )
        if action == "date" and value:
            return self.feedback_shift_date_response(
                user_id=user_id,
                days=numeric_value,
            )
        if action == "mode":
            return self.feedback_cycle_mode_response(user_id)
        if action == "noop":
            return self.feedback_draft_response(user_id)
        if action == "repeat":
            return self.feedback_toggle_repetition_response(user_id)
        if action == "generate":
            return self.feedback_generate_response(user_id)
        if action == "drafts":
            return self.feedback_drafts_response(user_id)
        if action == "manual_output" and value:
            return self.feedback_output_response(user_id=user_id, output_id=value)
        if action == "manual_send" and value:
            return self.feedback_send_response(user_id=user_id, output_id=value)
        return self.feedback_menu_response(user_id)

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
                    "Откройте приложение, чтобы посмотреть весь каталог.",
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

    def current_tenant_slug(self, user_id: int | None) -> str:
        if user_id is not None:
            return self.user_tenant_slugs.get(user_id, self.default_tenant_slug)
        return self.default_tenant_slug

    def remember_session_role(
        self,
        user_id: int,
        tenant_slug: str,
        session: dict[str, Any],
    ) -> str | None:
        staff_roles = {str(role) for role in session.get("staff_roles") or []}
        student_roles = {str(role) for role in session.get("student_roles") or []}
        role = next(
            (
                candidate
                for candidate in (
                    "superadmin",
                    "partner_director",
                    "admin",
                    "curator",
                    "teacher",
                )
                if candidate in staff_roles
            ),
            (
                "parent"
                if "parent" in student_roles
                else "student"
                if "student" in student_roles
                else None
            ),
        )
        if role is not None:
            self.user_menu_roles[(user_id, tenant_slug)] = role
        return role

    def menu_role(self, user_id: int | None, tenant_slug: str) -> str | None:
        if user_id is None:
            return None
        key = (user_id, tenant_slug)
        if self.backend_client is None:
            return self.user_menu_roles.get(key)
        try:
            session = self.backend_client.get_session(
                tenant_slug=tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError:
            return self.user_menu_roles.get(key)
        role = self.remember_session_role(user_id, tenant_slug, session)
        if role is None:
            self.user_menu_roles.pop(key, None)
        return role

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
            "Вход · шаг 2 из 2",
            "",
            "ID из письма распознан.",
            f"Школа: {tenant_slug}",
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
                lines.append("По этому ID ученики не найдены.")
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
        raw_payload = (payload or "").strip()
        if raw_payload.casefold().startswith("student_"):
            return self.handle_student_invitation_response(
                token=raw_payload[len("student_") :],
                user_id=user_id,
            )
        is_shop_payload = raw_payload.casefold().startswith("shop_")
        linked_tenant_slug, shop_contact_id = parse_shop_payload(raw_payload)
        if is_shop_payload and not shop_contact_id:
            return BotResponse(
                "Ссылка из письма повреждена. Попросите школу отправить новую ссылку.",
                self.main_menu_attachments(user_id),
            )
        open_store_after_link = is_shop_payload
        contact_id = shop_contact_id if is_shop_payload else parse_contact_payload(raw_payload)
        if not contact_id:
            return None

        tenant_slug = linked_tenant_slug or self.current_tenant_slug(user_id)
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
                        "Не получилось проверить ID из письма.\n\n"
                        f"Город / партнер: {tenant_slug}\n"
                        f"ID из письма: {contact_id}\n"
                        f"Причина: {format_backend_error(exc)}"
                    ),
                    self.main_menu_attachments(user_id),
                )

            resolved_contact_id = str(resolved.get("contact_id") or contact_id)
            students = list(resolved.get("students") or [])
            if user_id is not None and linked_tenant_slug:
                self.user_tenant_slugs[user_id] = tenant_slug
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
                    created_at=time.monotonic(),
                    contact_id=resolved_contact_id,
                    tenant_slug=tenant_slug,
                    students=students,
                )
            if open_store_after_link:
                linked = self.handle_role_selection_response(
                    user_id=user_id,
                    role="parent",
                )
                if user_id is None or user_id in self.pending_contact_ids:
                    return linked
                store_url = build_miniapp_url(
                    user_id=user_id,
                    tenant_slug=tenant_slug,
                    view="store",
                )
                rows = [[miniapp_button("Перейти в магазин", store_url)]] if store_url else []
                return BotResponse(
                    (
                        "Здравствуйте! Данные из письма школы распознаны.\n\n"
                        f"Найдено учеников: {len(students)}. "
                        "Личный кабинет готов, можно перейти в магазин."
                    ),
                    inline_keyboard_with_main_menu(rows),
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
                created_at=time.monotonic(),
                contact_id=contact_id,
                tenant_slug=tenant_slug,
                students=[],
            )

        return BotResponse(
            self.contact_entry_text(contact_id, tenant_slug=tenant_slug, students=None),
            role_selection_keyboard(),
        )

    def handle_student_invitation_response(
        self,
        *,
        token: str,
        user_id: int | None,
    ) -> BotResponse:
        if user_id is None:
            return BotResponse(
                "Не получилось определить ваш MAX-профиль.",
                self.main_menu_attachments(user_id),
            )
        if not token or self.backend_client is None:
            return BotResponse(
                "Ссылка ученика недоступна. Попросите родителя открыть новый QR-код.",
                self.main_menu_attachments(user_id),
            )

        try:
            result = self.backend_client.create_student_invite_link(
                tenant_slug=self.current_tenant_slug(user_id),
                token=token,
                max_user_id=user_id,
            )
        except BackendApiError as exc:
            return BotResponse(
                (
                    "Не получилось привязать профиль ученика.\n\n"
                    "Попросите родителя обновить QR-код и попробуйте еще раз.\n"
                    f"Причина: {format_backend_error(exc)}"
                ),
                self.main_menu_attachments(user_id),
            )

        tenant_slug = str(result.get("tenant_slug") or self.default_tenant_slug)
        student_name = str(result.get("student_name") or "ученика")
        group_name = str(result.get("group_name") or "").strip()
        self.user_tenant_slugs[user_id] = tenant_slug
        self.user_menu_roles[(user_id, tenant_slug)] = "student"

        store_url = build_miniapp_url(
            user_id=user_id,
            tenant_slug=tenant_slug,
            view="store",
        )
        rows = [[miniapp_button("Перейти в магазин", store_url)]] if store_url else []
        profile_line = f"Профиль {student_name} привязан."
        if group_name:
            profile_line += f"\nГруппа: {group_name}."
        return BotResponse(
            (f"{profile_line}\n\nТеперь можно открыть магазин и пользоваться личным кабинетом."),
            inline_keyboard_with_main_menu(rows),
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
            (f"Contact ID по этому тексту не найден. Показываю поиск по каталогу.\n\n{text}"),
            self.cabinet_attachments(user_id, tenant_slug),
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

        if role not in {"parent", "student"}:
            return BotResponse(
                "Роль должна быть `parent` или `student`.",
                role_selection_keyboard(),
            )

        if role == "student":
            self.pending_contact_ids.pop(user_id, None)
            self.pending_onboarding_roles.pop(user_id, None)
            return BotResponse(
                (
                    "Для входа ученика нужен QR-код.\n\n"
                    "Сначала родитель связывает свой профиль по ID из письма школы, "
                    "затем открывает кабинет и показывает QR-код ребёнка."
                ),
                onboarding_cancelled_keyboard(),
            )

        role_text = "родитель"
        pending = self.pending_contact_ids.get(user_id)
        if not pending:
            self.pending_onboarding_roles[user_id] = (role, time.monotonic())
            return BotResponse(
                (
                    f"Выбрана роль: {role_text}.\n\n"
                    "Теперь отправьте ID из письма одним сообщением. "
                    "После проверки бот покажет найденных учеников и создаст связь."
                ),
                onboarding_contact_keyboard(),
            )

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
                        "Не получилось привязать профиль.\n\n"
                        f"Город / партнер: {pending.tenant_slug}\n"
                        f"ID из письма: {pending.contact_id}\n"
                        f"Роль: {role_text}\n"
                        f"Причина: {format_backend_error(exc)}"
                    ),
                    role_selection_keyboard(),
                )

            links = result.get("links") or []
            self.user_menu_roles[(user_id, pending.tenant_slug)] = role
            self.pending_contact_ids.pop(user_id, None)
            self.pending_onboarding_roles.pop(user_id, None)
            return BotResponse(
                (
                    "Профиль привязан.\n\n"
                    f"ID из письма: {pending.contact_id}\n"
                    f"Роль: {role_text}\n"
                    f"Связанных учеников: {len(links)}\n\n"
                    "Теперь можно открыть личный кабинет."
                ),
                self.cabinet_attachments(user_id, pending.tenant_slug),
            )

        return BotResponse(
            (f"Данные приняты.\n\nID из письма: {pending.contact_id}\nРоль: {role_text}"),
            self.cabinet_attachments(user_id, pending.tenant_slug),
        )

    def handle_bot_started(self, update: dict[str, Any]) -> None:
        self.cleanup_customer_onboarding()
        user = update.get("user") or {}
        user_id = user.get("user_id")
        chat_id = update.get("chat_id")
        payload = update.get("payload")

        response = self.handle_contact_payload_response(
            payload=payload,
            user_id=user_id,
        ) or self.first_entry_response(user_id)

        self.send_response(response, chat_id=chat_id, user_id=user_id)

    def handle_bot_stopped(self, update: dict[str, Any]) -> None:
        user = update.get("user") or {}
        raw_user_id = user.get("user_id") or update.get("user_id")
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            logger.warning("bot_stopped received without MAX user_id")
            return

        self.pending_contact_ids.pop(user_id, None)
        self.pending_onboarding_roles.pop(user_id, None)
        self.pending_staff_invites.pop(user_id, None)
        self.feedback_drafts.pop(user_id, None)
        self.user_tenant_slugs.pop(user_id, None)
        self.user_menu_roles = {
            key: role for key, role in self.user_menu_roles.items() if key[0] != user_id
        }

        if self.backend_client is None:
            logger.error(
                "Cannot revoke access after bot_stopped: backend client is disabled "
                "for max_user_id=%s",
                user_id,
            )
            return
        try:
            result = self.backend_client.revoke_stopped_bot_access(
                tenant_slug=self.default_tenant_slug,
                max_user_id=user_id,
            )
        except BackendApiError:
            logger.exception(
                "Failed to revoke access after bot_stopped for max_user_id=%s",
                user_id,
            )
            return

        logger.info(
            "Access revoked after bot_stopped: max_user_id=%s "
            "account_links=%s child_links=%s tenants=%s",
            user_id,
            result.get("revoked_account_links", 0),
            result.get("revoked_child_links", 0),
            result.get("affected_tenants", 0),
        )

    def handle_message_created(self, update: dict[str, Any]) -> None:
        self.cleanup_customer_onboarding()
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
                    "Выберите нужный раздел кнопкой ниже.",
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
        is_staff_invite = self.is_staff_invite_command(command)

        if is_staff_invite:
            response = self.staff_invite_start_response(
                user_id=user_id,
                username=sender.get("username"),
                display_name=display_name_from_user(sender),
            )
        elif command in {"/start", "start"}:
            response = self.handle_contact_payload_response(
                payload=argument, user_id=user_id
            ) or self.first_entry_response(user_id)
        elif command.startswith("/"):
            response = BotResponse(
                "Текстовые команды больше не используются. Выберите нужный раздел кнопкой.",
                self.main_menu_attachments(user_id),
            )
        else:
            response = self.handle_contact_payload_response(payload=text, user_id=user_id)
            if (
                response is not None
                and user_id is not None
                and user_id in self.pending_contact_ids
                and user_id in self.pending_onboarding_roles
            ):
                response = self.handle_role_selection_response(
                    user_id=user_id,
                    role=self.pending_onboarding_roles[user_id][0],
                    username=sender.get("username"),
                    display_name=display_name_from_user(sender),
                )
            if response is None:
                response = BotResponse(
                    "Выберите нужный раздел кнопкой ниже.",
                    self.main_menu_attachments(user_id),
                )

        self.log_interaction_result(
            event_type="message",
            action=(
                "staff_invite"
                if is_staff_invite
                else command
                if command.startswith("/")
                else "contact_or_search"
            ),
            user_id=user_id,
            chat_id=chat_id,
            tenant_slug=tenant_slug,
            started_at=started_at,
            response=response,
        )
        self.send_response(response, chat_id=chat_id, user_id=user_id)

    def handle_message_callback(self, update: dict[str, Any]) -> None:
        self.cleanup_customer_onboarding()
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
        staff_join_action = parse_staff_join_payload(payload)

        if staff_join_action:
            action, value = staff_join_action
            response = self.staff_join_callback_response(
                user_id=user_id,
                action=action,
                value=value,
            )
            notification = {
                "tenant": "Город выбран",
                "cities": "Выбор города",
                "role": "Заявка отправлена",
                "approve": "Заявка подтверждена",
                "reject": "Заявка отклонена",
                "cancel": "Регистрация отменена",
            }.get(action, "Регистрация сотрудника")
            self.log_interaction_result(
                event_type="callback",
                action=f"staff_join:{action}",
                user_id=user_id,
                chat_id=chat_id,
                tenant_slug=tenant_slug,
                started_at=started_at,
                response=response,
            )
            if callback_id and hasattr(self.client, "answer_callback"):
                self.answer_callback_response(
                    callback_id=callback_id,
                    response=response,
                    notification=notification,
                )
                return
            self.send_response(response, chat_id=chat_id, user_id=user_id)
            return

        if payload not in {CALLBACK_ROLE_PARENT, CALLBACK_ROLE_STUDENT}:
            feedback_action = parse_feedback_payload(payload)
            knowledge_section_id = parse_knowledge_payload(payload)
            if payload == CALLBACK_ONBOARDING_CANCEL:
                response = self.cancel_onboarding_response(user_id)
                notification = "Вход отменен"
            elif payload == CALLBACK_ONBOARDING_RESTART:
                response = self.restart_onboarding_response(user_id)
                notification = "Выбор роли"
            elif payload == CALLBACK_KNOWLEDGE:
                response = self.knowledge_menu_response(user_id)
                notification = "База знаний"
            elif knowledge_section_id:
                response = self.knowledge_section_response(
                    user_id=user_id,
                    section_id=knowledge_section_id,
                )
                notification = "Раздел базы знаний"
            elif payload == CALLBACK_FEEDBACK:
                response = self.feedback_menu_response(user_id)
                notification = "Обратная связь"
            elif feedback_action:
                action, value = feedback_action
                response = self.feedback_callback_response(
                    user_id=user_id,
                    action=action,
                    value=value,
                )
                notification = {
                    "manual": "Новая ОС",
                    "groups": "Группы",
                    "group": "Группа",
                    "courses": "Курсы",
                    "course": "Курс",
                    "lessons": "Уроки",
                    "lesson": "Урок",
                    "absent": "Посещаемость",
                    "attendance": "Ученики",
                    "date": "Дата",
                    "mode": "Формат занятия",
                    "repeat": "Формат урока",
                    "generate": "ОС готова",
                    "drafts": "Черновики",
                    "manual_output": "Черновик",
                    "manual_send": "ОС отправлена",
                }.get(action, "Обратная связь")
            elif payload == CALLBACK_MENU:
                response = self.main_menu_response(user_id=user_id)
                notification = "Главное меню"
            elif payload == CALLBACK_HELP:
                response = self.help_response(user_id=user_id)
                notification = "Помощь"
            elif payload == CALLBACK_MINIAPP:
                response = self.miniapp_response(user_id=user_id)
                notification = "Кабинет"
            else:
                response = BotResponse(
                    "Этот раздел перенесен в личный кабинет. Используйте актуальные кнопки.",
                    self.main_menu_attachments(user_id),
                )
                notification = "Откройте кабинет"

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
                self.answer_callback_response(
                    callback_id=callback_id,
                    response=response,
                    notification=notification,
                )
                return
            self.send_response(response, chat_id=chat_id, user_id=user_id)
            return

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
            self.answer_callback_response(
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

        if update_type == "bot_stopped":
            self.handle_bot_stopped(update)
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
            "Локально обработать callback payload кнопки и вывести JSON ответа без запуска polling"
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
            "BOT_MODE=webhook: события принимает FastAPI endpoint. Запустите uvicorn app.main:app.",
            file=sys.stderr,
        )
        return 1

    drop_webhooks = args.drop_webhooks or settings.max_drop_webhooks_on_start
    bot.ensure_polling_available(drop_webhooks=drop_webhooks)

    bot.run()
    return 0
