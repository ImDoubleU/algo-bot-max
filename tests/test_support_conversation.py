import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from test_support import auth, event, image, ticket
from test_support import support_client as _support_client

from app.bot.max_client import SimulationMaxClient
from app.bot.max_long_polling import LongPollingBot
from app.bot.support import handle_support_message, is_navigation_message
from app.models.support import SupportConversation, SupportReply, SupportTicket
from app.services.support import deliver_next_reply, notify_next_message

support_client = _support_client


def create_answered(c, factory):
    tid = c.post("/api/v1/support/tickets", headers=auth(), json=ticket()).json()["id"]
    c.post(f"/api/v1/support/tickets/{tid}/replies", headers=auth(4242),
           json={"request_id": str(uuid4()), "message": "Попробуйте ещё раз"})

    class Client:
        calls = []

        def send_message(self, **kwargs):
            self.calls.append(kwargs)

    client = Client()

    async def deliver():
        async with factory() as db:
            assert await deliver_next_reply(db, client)

    asyncio.run(deliver())
    assert f"support:reply:{tid}" in str(client.calls[-1]["attachments"])
    return tid


def inbox(c):
    return c.get("/api/v1/support/tickets", headers=auth(4242)).json()


def test_plain_reply_history_read_receipts_and_deduplication(support_client):
    c, factory = support_client
    tid = create_answered(c, factory)
    assert inbox(c)["items"][0]["status"] == "waiting"
    assert event(c, "message", text="Всё ещё ошибка", event_id="m1").json()["ticket_id"] == tid
    event(c, "message", text="Всё ещё ошибка", event_id="m1")
    record = inbox(c)["items"][0]
    assert record["status"] == "new"
    assert len(record["replies"]) == 2
    assert record["unread_count"] == 1
    reply = record["replies"][-1]
    assert reply["author"] == "user" and reply["status"] == "received"
    event(c, "message", text="И ещё", event_id="m2")
    path = f"/api/v1/support/tickets/{tid}/read"
    assert c.post(path, headers=auth(), json={"reply_ids": [reply["id"]]}).status_code == 403
    assert c.post(path, headers=auth(4242), json={"reply_ids": [reply["id"]]}).status_code == 204
    assert inbox(c)["items"][0]["unread_count"] == 1
    assert inbox(c)["unread_total"] == 1
    # Received messages do not block the next staff reply.
    assert c.post(f"/api/v1/support/tickets/{tid}/replies", headers=auth(4242), json={
        "request_id": str(uuid4()), "message": "Проверяем",
    }).status_code == 202


def test_multiple_tickets_hold_messages_until_choice(support_client):
    c, factory = support_client
    one = create_answered(c, factory)
    two = create_answered(c, factory)
    result = event(c, "message", text="Спасибо", event_id="multi1").json()
    assert result["stage"] == "choose"
    assert {t["id"] for t in result["tickets"]} == {one, two}
    event(c, "message", text="Спасибо", event_id="multi1")
    event(c, "message", text="Теперь работает", event_id="multi2")
    assert inbox(c)["unread_total"] == 0
    selected = event(c, "choose", ticket_id=one)
    assert selected.status_code == 200
    assert inbox(c)["unread_total"] == 2
    event(c, "choose", ticket_id=one)
    assert inbox(c)["unread_total"] == 2
    event(c, "reply", ticket_id=two)
    event(c, "message", text="Спасибо", event_id="multi1")
    assert inbox(c)["unread_total"] == 2


def test_pending_photos_survive_old_exit_and_are_deleted_on_cancel(
    support_client, monkeypatch,
):
    c, factory = support_client
    one = create_answered(c, factory)
    create_answered(c, factory)
    downloads = []

    async def download(*args, **kwargs):
        downloads.append(1)
        return image(), "https://example.com/photo.png"

    monkeypatch.setattr("app.services.support._fetch_remote_bytes", download)
    assert event(c, "message", event_id="buffer-photo", photo_urls=[
        "https://example.com/photo.png",
    ]).json()["stage"] == "choose"
    assert len(downloads) == 1
    event(c, "message", event_id="buffer-photo", photo_urls=["https://example.com/photo.png"])
    assert len(downloads) == 1
    assert event(c, "choose", ticket_id=one).status_code == 200
    record = next(t for t in inbox(c)["items"] if t["id"] == one)
    assert len(record["replies"][-1]["photo_ids"]) == 1
    assert len(downloads) == 1

    async def unselect():
        async with factory() as db:
            conversation = await db.get(SupportConversation, 77)
            conversation.ticket_id = None
            await db.commit()

    asyncio.run(unselect())
    event(c, "message", event_id="cancel-photo", photo_urls=["https://example.com/photo.png"])

    async def buffered_photo():
        async with factory() as db:
            conversation = await db.get(SupportConversation, 77)
            return conversation.pending_messages[0]["photo_ids"][0]

    photo_id = asyncio.run(buffered_photo())
    assert c.get(f"/api/v1/support/photos/{photo_id}", headers=auth()).status_code == 200
    event(c, "exit")
    assert c.get(f"/api/v1/support/photos/{photo_id}", headers=auth()).status_code == 200
    event(c, "cancel")
    assert c.get(f"/api/v1/support/photos/{photo_id}", headers=auth()).status_code == 404


def test_owner_is_checked_not_current_city_and_cancel_stops_capture(support_client):
    c, factory = support_client
    tid = create_answered(c, factory)
    path = "/api/v1/support/bot-event"
    assert c.post(path, headers=auth(88), json={"max_user_id": 88,
        "tenant_slug": "test-city", "action": "reply", "ticket_id": tid}).status_code == 404
    assert event(c, "reply", ticket_id=tid).status_code == 200
    assert event(c, "cancel").json()["active"] is False
    assert event(c, "message", text="Не в поддержку", event_id="out").json()["active"] is False
    assert inbox(c)["unread_total"] == 0
    event(c, "reply", ticket_id=tid)
    event(c, "message", text="В поддержку", event_id="in")
    assert inbox(c)["unread_total"] == 1


def test_closed_ticket_requires_explicit_button_and_can_be_reopened(support_client):
    c, factory = support_client
    tid = create_answered(c, factory)
    event(c, "reply", ticket_id=tid)
    c.patch(f"/api/v1/support/tickets/{tid}", headers=auth(4242), json={"status": "resolved"})
    assert event(c, "message", text="Проверка", event_id="closed").json()["stage"] == "closed"
    assert inbox(c)["unread_total"] == 0
    event(c, "reply", ticket_id=tid)
    event(c, "message", text="Опять ошибка", event_id="reopened")
    assert inbox(c)["items"][0]["status"] == "new"


def test_new_ticket_draft_is_not_mixed_with_conversation(support_client):
    c, factory = support_client
    tid = create_answered(c, factory)
    event(c, "reply", ticket_id=tid)
    event(c, "start")
    assert event(c, "reply", ticket_id=tid).status_code == 400
    event(c, "role", role="parent")
    event(c, "message", text="Анна Иванова")
    event(c, "message", text="Другая проблема")
    assert inbox(c)["unread_total"] == 0
    assert event(c, "submit").json()["ticket_id"] != tid


def test_incoming_photos_and_retry_notification_after_read(support_client, monkeypatch):
    c, factory = support_client
    tid = create_answered(c, factory)

    async def download(*args, **kwargs):
        return image(), "https://example.com/photo.png"

    monkeypatch.setattr("app.services.support._fetch_remote_bytes", download)
    result = event(c, "message", event_id="photo", photo_urls=["https://example.com/photo.png"])
    assert result.status_code == 200
    record = inbox(c)["items"][0]
    reply = record["replies"][-1]
    assert len(reply["photo_ids"]) == 1
    photo_url = "/api/v1/support/photos/" + reply["photo_ids"][0]
    assert c.get(photo_url, headers=auth(88)).status_code == 404
    assert c.get(photo_url, headers=auth(4242)).status_code == 200
    c.post(f"/api/v1/support/tickets/{tid}/read", headers=auth(4242),
           json={"reply_ids": [reply["id"]]})

    class Client:
        fail = True
        calls = []

        def send_message(self, **kwargs):
            self.calls.append(kwargs)
            if self.fail:
                raise RuntimeError("offline")

    client = Client()

    async def notify():
        async with factory() as db:
            assert await notify_next_message(db, client, 4242)
            assert not await notify_next_message(db, client, 4242)
            message = await db.get(SupportReply, UUID(reply["id"]))
            assert message.notified_at is None
            message.notification_attempted_at = datetime.now(UTC) - timedelta(minutes=3)
            await db.commit()
        client.fail = False
        async with factory() as db:
            assert await notify_next_message(db, client, 4242)
            assert not await notify_next_message(db, client, 4242)

    asyncio.run(notify())
    assert len(client.calls) == 2
    assert all(call["user_id"] == 4242 for call in client.calls)


def test_delete_ticket_cleans_conversation_and_does_not_reroute(support_client):
    c, factory = support_client
    tid = create_answered(c, factory)
    event(c, "reply", ticket_id=tid)
    event(c, "message", text="Проверка", event_id="delete")
    assert c.delete(f"/api/v1/support/tickets/{tid}", headers=auth(4242)).status_code == 204
    assert event(c, "message", text="После удаления").json()["active"] is False

    async def verify():
        async with factory() as db:
            conv = await db.get(SupportConversation, 77)
            assert conv.ticket_id is None and conv.paused
            assert not list(await db.scalars(select(SupportReply)))

    asyncio.run(verify())


def test_delivery_does_not_hide_message_received_after_staff_queued_reply(support_client):
    c, factory = support_client
    tid = create_answered(c, factory)
    c.post(f"/api/v1/support/tickets/{tid}/replies", headers=auth(4242), json={
        "request_id": str(uuid4()), "message": "Проверяем"})
    event(c, "message", text="Новое уточнение", event_id="race")

    async def send():
        async with factory() as db:
            await deliver_next_reply(db, SimulationMaxClient())
            assert (await db.get(SupportTicket, tid)).status == "new"

    asyncio.run(send())


@pytest.mark.parametrize("text", ["/start shop_bor~123", "start", "shop_bor~123",
    "cid_123", "staffi_abc", "https://max.ru/bot?start=shop_bor~123"])
def test_commands_and_invitation_links_bypass_support(text):
    assert is_navigation_message(text)
    calls = []

    class Backend:
        def support_event(self, **fields):
            calls.append(fields)
            return {"active": False}

    bot = LongPollingBot(SimulationMaxClient(), backend_client=Backend())
    assert handle_support_message(bot, 77, {"text": text}) is None
    assert calls[-1]["action"] == "cancel"


def test_reply_callback_wiring():
    calls = []

    class Backend:
        def support_event(self, **fields):
            calls.append(fields)
            return {"active": True, "stage": "conversation", "ticket_id": 12, "text": "Ответ"}

    client = SimulationMaxClient()
    bot = LongPollingBot(client, backend_client=Backend())
    bot.handle_message_callback({"callback": {"user": {"user_id": 77},
        "payload": "support:reply:12", "callback_id": "cb"}})
    assert calls[-1]["ticket_id"] == 12
    assert calls[-1]["action"] == "reply"
