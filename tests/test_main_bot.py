from __future__ import annotations

from typing import Any

import app.bot.max_long_polling as max_bot
from app.bot.max_long_polling import CALLBACK_ROLE_PARENT, CALLBACK_ROLE_STUDENT
from main_bot import LongPollingBot


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


def test_build_miniapp_url_adds_user_and_tenant(monkeypatch) -> None:
    monkeypatch.setattr(
        max_bot,
        "MAX_MINIAPP_URL",
        "https://example.test/miniapp?source=max",
    )

    url = max_bot.build_miniapp_url(
        user_id=53364725,
        tenant_slug="nizhniy-novgorod-partner-a",
    )

    assert (
        url
        == "https://example.test/miniapp?source=max&max_user_id=53364725&tenant_slug=nizhniy-novgorod-partner-a"
    )


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
