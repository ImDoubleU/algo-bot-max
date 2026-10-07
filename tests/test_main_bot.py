from __future__ import annotations

from typing import Any

import pytest

import app.bot.max_long_polling as max_bot
from app.bot.keyboards import (
    CALLBACK_KNOWLEDGE,
    CALLBACK_MENU,
    CALLBACK_ONBOARDING_CANCEL,
    CALLBACK_ONBOARDING_RESTART,
    CALLBACK_ROLE_PARENT,
    CALLBACK_ROLE_STUDENT,
)
from main_bot import LongPollingBot, simulate_command


@pytest.fixture(autouse=True)
def isolated_onboarding_state(monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_ONBOARDING_STATE_PATH", str(tmp_path / "onboarding.sqlite3"))


class FakeMaxClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []

    def get_me(self) -> dict[str, Any]:
        return {
            "user_id": 999,
            "username": "AlgoBot",
            "first_name": "Algo MAX",
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
    def __init__(self, *, linked: bool = True) -> None:
        self.linked = linked
        self.resolve_calls: list[dict[str, Any]] = []
        self.link_calls: list[dict[str, Any]] = []
        self.revoke_calls: list[dict[str, Any]] = []
        self.staff_invitation_calls: list[dict[str, Any]] = []

    def get_session(self, *, tenant_slug: str, max_user_id: int) -> dict[str, Any]:
        if not self.linked:
            return {
                "tenant_slug": tenant_slug,
                "has_access": False,
                "account": None,
                "staff_roles": [],
                "student_roles": [],
                "students": [],
                "access_links": [],
                "staff_assignments": [],
                "orders": [],
                "ledger": [],
            }
        return {
            "tenant_slug": tenant_slug,
            "has_access": True,
            "account": {
                "max_user_id": max_user_id,
                "username": "admin_user",
                "display_name": "Администратор",
            },
            "staff_roles": ["admin"],
            "student_roles": [],
            "students": [],
            "access_links": [],
            "staff_assignments": [],
            "orders": [],
            "ledger": [],
        }

    def resolve_contact(
        self,
        *,
        tenant_slug: str,
        contact_id: str,
        max_user_id: int | None,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        self.resolve_calls.append(
            {
                "tenant_slug": tenant_slug,
                "contact_id": contact_id,
                "max_user_id": max_user_id,
            }
        )
        return {
            "contact_id": contact_id,
            "contact_display_name": "Елена Воронова",
            "students": [
                {
                    "student_id": "11111111-1111-1111-1111-111111111111",
                    "display_name": "Воронова Александра",
                    "group_name": "Python Start",
                    "venue_name": "Союзный 45",
                    "teacher_name": "Анна Петрова",
                },
                {
                    "student_id": "22222222-2222-2222-2222-222222222222",
                    "display_name": "Воронова Мария",
                    "group_name": "Python Start",
                    "venue_name": "Союзный 45",
                    "teacher_name": "Анна Петрова",
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
        self.linked = True
        return {"links": [{"id": "link-1"}, {"id": "link-2"}]}

    def revoke_stopped_bot_access(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        self.revoke_calls.append({"tenant_slug": tenant_slug, "max_user_id": max_user_id})
        return {
            "revoked_account_links": 1,
            "revoked_child_links": 1,
            "affected_tenants": 1,
        }

    def get_staff_onboarding_options(
        self,
        *,
        tenant_slug: str,
        max_user_id: int,
    ) -> dict[str, Any]:
        return {
            "tenants": [
                {
                    "tenant_slug": "n-novgorod",
                    "tenant_name": "Нижний Новгород",
                    "city_name": "Нижний Новгород",
                }
            ],
            "roles": ["partner_director", "admin", "curator", "teacher"],
        }

    def redeem_staff_invitation(
        self,
        *,
        token: str,
        max_user_id: int,
        auth_tenant_slug: str,
        username: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        self.staff_invitation_calls.append(
            {
                "token": token,
                "max_user_id": max_user_id,
                "auth_tenant_slug": auth_tenant_slug,
                "username": username,
                "display_name": display_name,
            }
        )
        return {
            "tenant_slug": "n-novgorod",
            "tenant_name": "Нижний Новгород",
            "city_name": "Нижний Новгород",
            "role": "teacher",
            "assignment": {"role": "teacher"},
        }


def _message(text: str, *, user_id: int = 1, chat_id: int = 10) -> dict[str, Any]:
    return {
        "message": {
            "sender": {
                "user_id": user_id,
                "username": "user_one",
                "first_name": "Иван",
                "last_name": "Петров",
            },
            "recipient": {"chat_id": chat_id},
            "body": {"text": text},
        }
    }


def _callback(payload: str, *, user_id: int = 1, chat_id: int = 10) -> dict[str, Any]:
    return {
        "callback": {
            "payload": payload,
            "user": {
                "user_id": user_id,
                "username": "user_one",
                "first_name": "Иван",
                "last_name": "Петров",
            },
            "message": {"recipient": {"chat_id": chat_id}},
        }
    }


def _buttons(message: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = message.get("attachments") or []
    rows = attachments[0]["payload"]["buttons"] if attachments else []
    return [button for row in rows for button in row]


def test_build_miniapp_url_keeps_registered_url_exact(monkeypatch) -> None:
    monkeypatch.setenv("MAX_MINIAPP_URL", "https://example.test/miniapp?source=max")
    monkeypatch.setenv("MAX_BOT_USERNAME", "example_bot")

    url = max_bot.build_miniapp_url(
        user_id=53364725,
        tenant_slug="n-novgorod",
        view="orders",
    )

    assert url == "https://example.test/miniapp?source=max"
    button = max_bot.main_menu_keyboard(
        user_id=53364725,
        tenant_slug="n-novgorod",
    )[0]["payload"]["buttons"][0][0]
    assert button["type"] == "open_app"
    assert button["web_app"] == "example_bot"


def test_start_for_unlinked_user_opens_role_selection() -> None:
    response = simulate_command(
        command_text="/start",
        user_id=1,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )

    assert "Вход · шаг 1 из 2" in response["text"]
    assert "QR-код из кабинета преподавателя или родителя" in response["text"]
    payloads = {button.get("payload") for button in _buttons(response)}
    assert CALLBACK_ROLE_PARENT in payloads
    assert CALLBACK_ROLE_STUDENT in payloads
    assert CALLBACK_MENU in payloads


def test_unlinked_parent_is_told_to_use_the_school_email() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_callback(_callback(CALLBACK_ROLE_PARENT))

    response = client.sent_messages[-1]
    assert "Данные персональной ссылки пока не получены" in response["text"]
    assert "Перейдите по персональной ссылке" in response["text"]
    assert "отправьте указанный в нем ID" in response["text"]


def test_unlinked_student_is_told_to_request_teacher_qr() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_callback(_callback(CALLBACK_ROLE_STUDENT))

    response = client.sent_messages[-1]
    assert "Попросите преподавателя открыть QR-код ученика" in response["text"]
    assert "Если родитель уже подключен" in response["text"]


def test_start_for_linked_staff_opens_role_menu() -> None:
    response = simulate_command(
        command_text="start",
        user_id=1,
        backend_client=FakeBackendClient(linked=True),
        default_tenant_slug="n-novgorod",
    )

    assert "Рабочий кабинет" in response["text"]
    button_texts = {button.get("text") for button in _buttons(response)}
    assert "Открыть рабочий кабинет" in button_texts
    assert "Обратная связь" not in button_texts
    assert "База знаний" in button_texts


def test_removed_text_command_redirects_to_inline_menu() -> None:
    backend = FakeBackendClient(linked=True)
    response = simulate_command(
        command_text="/buy PEN-LOGO 2",
        user_id=1,
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )

    assert response["text"] == (
        "Текстовые команды больше не используются. Выберите нужный раздел кнопкой."
    )
    assert backend.resolve_calls == []
    assert response["attachments"]


def test_plain_contact_id_resolves_students_and_shows_roles() -> None:
    client = FakeMaxClient()
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(
        client,
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_created(_message("30420713"))

    response = client.sent_messages[-1]
    assert "Найдены ученики:" in response["text"]
    assert "Воронова Александра" in response["text"]
    assert "Воронова Мария" in response["text"]
    assert bot.pending_contact_ids[1].contact_id == "30420713"
    payloads = {button.get("payload") for button in _buttons(response)}
    assert {CALLBACK_ROLE_PARENT, CALLBACK_ROLE_STUDENT}.issubset(payloads)


def test_role_callback_creates_parent_links() -> None:
    client = FakeMaxClient()
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(
        client,
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )
    bot.handle_message_created(_message("30420713"))

    bot.handle_message_callback(_callback(CALLBACK_ROLE_PARENT))

    response = client.sent_messages[-1]
    assert "Профиль привязан" in response["text"]
    assert "Связанных учеников: 2" in response["text"]
    assert backend.link_calls[0]["role"] == "parent"
    assert 1 not in bot.pending_contact_ids


def test_onboarding_can_be_cancelled_and_restarted() -> None:
    client = FakeMaxClient()
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(
        client,
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )
    bot.handle_message_created(_message("30420713"))

    bot.handle_message_callback(_callback(CALLBACK_ONBOARDING_CANCEL))
    assert "Вход отменен" in client.sent_messages[-1]["text"]
    assert 1 not in bot.pending_contact_ids

    bot.handle_message_callback(_callback(CALLBACK_ONBOARDING_RESTART))
    assert "Вход · шаг 1 из 2" in client.sent_messages[-1]["text"]


def test_removed_staff_sections_return_current_menu() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=True),
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_callback(_callback(CALLBACK_KNOWLEDGE))
    assert client.sent_messages[-1]["text"].startswith("База знаний")

    bot.handle_message_callback(_callback("feedback"))
    assert "раздел перенесен в личный кабинет" in client.sent_messages[-1]["text"]

    bot.handle_message_callback(_callback("catalog"))
    assert "раздел перенесен в личный кабинет" in client.sent_messages[-1]["text"]


def test_main_menu_callback_returns_role_specific_menu() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=True),
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_callback(_callback(CALLBACK_MENU))

    assert client.sent_messages[-1]["text"].startswith("Кабинет администратора")


def test_bot_stopped_revokes_access_and_clears_pending_state() -> None:
    client = FakeMaxClient()
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(
        client,
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )
    bot.handle_message_created(_message("30420713"))
    assert 1 in bot.pending_contact_ids

    bot.handle_bot_stopped({"user": {"user_id": 1}})

    assert 1 not in bot.pending_contact_ids
    assert backend.revoke_calls == [{"tenant_slug": "n-novgorod", "max_user_id": 1}]


def test_staff_deeplink_submits_preselected_role_request() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )
    bot.staff_approver_user_id = 53364725

    response = bot.handle_contact_payload_response(
        payload="staff_n-novgorod~curator",
        user_id=901,
        username="curator_demo",
        display_name="Куратор Демо",
    )

    assert response is not None
    assert "Заявка отправлена на подтверждение" in response.text
    assert "Роль: Куратор" in response.text
    request = next(iter(bot.pending_staff_requests.values()))
    assert request.tenant_slug == "n-novgorod"
    assert request.role == "curator"
    assert client.sent_messages[-1]["user_id"] == 53364725


def test_staff_deeplink_does_not_notify_superadmin_when_approvals_are_disabled() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )
    bot.staff_approver_user_id = None

    response = bot.handle_contact_payload_response(
        payload="staff_n-novgorod~teacher",
        user_id=903,
        username="teacher_without_invite",
        display_name="Преподаватель Без Приглашения",
    )

    assert response is not None
    assert "Регистрация по общей ссылке отключена" in response.text
    assert "персональную ссылку" in response.text
    assert client.sent_messages == []
    assert bot.pending_staff_requests == {}


def test_unique_staff_invitation_is_activated_immediately() -> None:
    client = FakeMaxClient()
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(
        client,
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )
    token = "AbCdEfGhIjKlMnOpQrStUvWxYz_12345"

    response = bot.handle_contact_payload_response(
        payload=f"staffi_{token}",
        user_id=902,
        username="teacher_demo",
        display_name="Преподаватель Демо",
    )

    assert response is not None
    assert "Доступ сотрудника подключен" in response.text
    assert "Роль: Преподаватель" in response.text
    assert bot.user_menu_roles[(902, "n-novgorod")] == "teacher"
    assert backend.staff_invitation_calls[0]["token"] == token


def test_student_invitation_confirms_binding_without_promising_access(monkeypatch) -> None:
    backend = FakeBackendClient(linked=False)
    monkeypatch.setattr(
        backend,
        "create_student_invite_link",
        lambda **kwargs: {
            "tenant_slug": "n-novgorod",
            "student_name": "Романов Даниил",
            "group_name": "ВП1 сб 12:30 С БОР",
        },
        raising=False,
    )
    bot = LongPollingBot(
        FakeMaxClient(),
        backend_client=backend,
        default_tenant_slug="n-novgorod",
    )

    response = bot.handle_student_invitation_response(token="teacher-token", user_id=9901)

    assert "Профиль Романов Даниил привязан." in response.text
    assert "Группа: ВП1 сб 12:30 С БОР." in response.text
    assert "Откройте приложение" in response.text
    assert "Теперь можно открыть магазин" not in response.text
    assert bot.user_menu_roles[(9901, "n-novgorod")] == "student"


def test_bot_ignores_its_own_messages() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_created(_message("/start", user_id=999))

    assert client.sent_messages == []


def test_parent_link_context_survives_bot_restart():
    backend = FakeBackendClient(linked=False)
    first = LongPollingBot(FakeMaxClient(), backend_client=backend)
    first.handle_contact_payload_response(payload="cid_30420713", user_id=77)
    second = LongPollingBot(FakeMaxClient(), backend_client=backend)
    result = second.handle_role_selection_response(user_id=77, role="parent")
    assert "Профиль привязан" in result.text
    assert backend.link_calls[-1]["contact_id"] == "30420713"
    third = LongPollingBot(FakeMaxClient(), backend_client=backend)
    third.restore_onboarding(77)
    assert 77 not in third.pending_contact_ids


def test_expired_parent_link_context_is_not_used(monkeypatch):
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(FakeMaxClient(), backend_client=backend)
    bot.handle_contact_payload_response(payload="cid_30420713", user_id=77)
    now = max_bot.time.time()
    monkeypatch.setattr(max_bot.time, "time", lambda: now + 1801)
    restarted = LongPollingBot(FakeMaxClient(), backend_client=backend)
    result = restarted.handle_role_selection_response(user_id=77, role="parent")
    assert "Время подтверждения ссылки истекло" in result.text
    assert backend.link_calls == []


def test_pasted_max_letter_url_resolves_payload_without_logging_contact(caplog):
    import logging

    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(FakeMaxClient(), backend_client=backend)
    with caplog.at_level(logging.INFO, logger="algo_bot_max.bot"):
        result = bot.handle_contact_payload_response(
            payload="https://max.ru/AlgoBot?start=cid_30420713",
            user_id=77,
        )
    assert "Найдены ученики" in result.text
    assert backend.resolve_calls[-1]["contact_id"] == "30420713"
    assert "30420713" not in caplog.text
    assert "https://max.ru" not in caplog.text
    assert '"stage": "contact_resolved"' in caplog.text


def test_pasted_student_url_uses_student_invitation_endpoint(monkeypatch):
    backend = FakeBackendClient(linked=False)
    calls = []
    monkeypatch.setattr(
        backend,
        "create_student_invite_link",
        lambda **kwargs: (
            calls.append(kwargs)
            or {
                "student_name": "Саша",
                "tenant_slug": "n-novgorod",
            }
        ),
        raising=False,
    )
    bot = LongPollingBot(FakeMaxClient(), backend_client=backend)
    response = bot.handle_contact_payload_response(
        payload="https://max.ru/AlgoBot?start=student_secret-token",
        user_id=77,
    )
    assert "Профиль Саша привязан" in response.text
    assert calls[0]["token"] == "secret-token"
    assert backend.resolve_calls == []


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 429, 500, None])
def test_binding_errors_never_expose_server_text(status):
    from app.bot.backend_client import BackendApiError

    text = max_bot.format_backend_error(
        BackendApiError(
            "HTTP 500 Error: secret-token database internal error",
            status_code=status,
        )
    )
    assert "HTTP" not in text
    assert "secret-token" not in text
    assert "500" not in text


def test_restarted_parent_role_can_finish_with_contact_message():
    backend = FakeBackendClient(linked=False)
    first = LongPollingBot(FakeMaxClient(), backend_client=backend)
    first.handle_role_selection_response(user_id=1, role="parent")
    client = FakeMaxClient()
    restarted = LongPollingBot(client, backend_client=backend)
    restarted.handle_message_created(_message("30420713"))
    assert "Профиль привязан" in client.sent_messages[-1]["text"]
    assert backend.link_calls[-1]["role"] == "parent"


def test_other_bot_worker_cancellation_removes_cached_contact():
    backend = FakeBackendClient(linked=False)
    first = LongPollingBot(FakeMaxClient(), backend_client=backend)
    first.handle_contact_payload_response(payload="cid_30420713", user_id=77)
    second = LongPollingBot(FakeMaxClient(), backend_client=backend)
    second.cancel_onboarding_response(77)
    response = first.handle_role_selection_response(user_id=77, role="parent")
    assert "Данные персональной ссылки пока не получены" in response.text
    assert backend.link_calls == []


def test_failed_new_contact_cannot_bind_previous_contact(monkeypatch):
    from app.bot.backend_client import BackendApiError

    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(FakeMaxClient(), backend_client=backend)
    bot.handle_contact_payload_response(payload="cid_30420713", user_id=77)

    def fail(**kwargs):
        raise BackendApiError("HTTP 404 Error: private details", status_code=404)

    monkeypatch.setattr(backend, "resolve_contact", fail)
    bot.handle_contact_payload_response(payload="cid_99999999", user_id=77)
    response = bot.handle_role_selection_response(user_id=77, role="parent")
    assert "Данные персональной ссылки пока не получены" in response.text
    assert backend.link_calls == []


def test_malformed_url_has_actionable_message():
    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(FakeMaxClient(), backend_client=backend)
    response = bot.handle_contact_payload_response(payload="https://[", user_id=77)
    assert "Ссылка повреждена" in response.text
    assert backend.resolve_calls == []


def test_other_worker_role_only_context_discards_cached_contact():
    backend = FakeBackendClient(linked=False)
    first = LongPollingBot(FakeMaxClient(), backend_client=backend)
    first.handle_contact_payload_response(payload="cid_30420713", user_id=77)
    second = LongPollingBot(FakeMaxClient(), backend_client=backend)
    second.onboarding_state.save(
        77,
        contact_id=None,
        tenant_slug=None,
        role="parent",
        correlation_id="replacement-context",
        ttl=1800,
    )
    result = first.handle_role_selection_response(user_id=77, role="parent")
    assert "Данные персональной ссылки пока не получены" in result.text
    assert backend.link_calls == []


def test_unreadable_saved_context_cannot_use_cached_contact(monkeypatch):
    import sqlite3

    backend = FakeBackendClient(linked=False)
    bot = LongPollingBot(FakeMaxClient(), backend_client=backend)
    bot.handle_contact_payload_response(payload="cid_30420713", user_id=77)

    def fail(user_id):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(bot.onboarding_state, "get", fail)
    response = bot.handle_role_selection_response(user_id=77, role="parent")
    assert "Сейчас не удалось проверить данные ссылки" in response.text
    assert backend.link_calls == []
    assert 77 not in bot.pending_contact_ids


def test_failed_context_write_does_not_send_link_received_confirmation(monkeypatch):
    import sqlite3

    backend = FakeBackendClient(linked=False)
    client = FakeMaxClient()
    bot = LongPollingBot(client, backend_client=backend)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(bot.onboarding_state, "save", fail)
    with pytest.raises(sqlite3.OperationalError):
        bot.handle_message_created(_message("30420713"))
    assert client.sent_messages == []
    assert backend.link_calls == []


def test_failed_context_delete_does_not_acknowledge_cancellation(monkeypatch):
    import sqlite3

    backend = FakeBackendClient(linked=False)
    client = FakeMaxClient()
    bot = LongPollingBot(client, backend_client=backend)
    bot.handle_contact_payload_response(payload="cid_30420713", user_id=1)

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError("database unavailable")

    monkeypatch.setattr(bot.onboarding_state, "delete", fail)
    with pytest.raises(sqlite3.OperationalError):
        bot.handle_message_callback(_callback(CALLBACK_ONBOARDING_CANCEL))
    assert client.sent_messages == []
    assert backend.link_calls == []
