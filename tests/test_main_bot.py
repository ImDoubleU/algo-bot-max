from __future__ import annotations

from typing import Any

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
        self.revoke_calls.append(
            {"tenant_slug": tenant_slug, "max_user_id": max_user_id}
        )
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
    payloads = {button.get("payload") for button in _buttons(response)}
    assert CALLBACK_ROLE_PARENT in payloads
    assert CALLBACK_ROLE_STUDENT in payloads
    assert CALLBACK_MENU in payloads


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
    assert backend.revoke_calls == [
        {"tenant_slug": "n-novgorod", "max_user_id": 1}
    ]


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


def test_bot_ignores_its_own_messages() -> None:
    client = FakeMaxClient()
    bot = LongPollingBot(
        client,
        backend_client=FakeBackendClient(linked=False),
        default_tenant_slug="n-novgorod",
    )

    bot.handle_message_created(_message("/start", user_id=999))

    assert client.sent_messages == []
