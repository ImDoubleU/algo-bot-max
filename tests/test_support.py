import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.bot.max_client import SimulationMaxClient
from app.bot.max_long_polling import LongPollingBot
from app.core.config import get_settings
from app.core.miniapp_auth import issue_miniapp_token
from app.db.session import get_db_session
from app.main import create_app
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.support import SupportDraft, SupportPhoto, SupportReply, SupportTicket
from app.services.support import deliver_next_reply, notification_loop


@pytest.fixture
def support_client(monkeypatch):
    monkeypatch.setattr(get_settings(), "initial_superadmin_max_user_id", "4242")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async def init():
        async with engine.begin() as conn:
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(init())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app()

    async def sessions():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db_session] = sessions
    client = TestClient(app)
    yield client, factory
    client.close()
    asyncio.run(engine.dispose())


def auth(user=77):
    return {"X-Miniapp-Token": issue_miniapp_token(max_user_id=user, tenant_slug="test-city")}


def ticket(**overrides):
    return {"request_id": str(uuid4()), "role": "parent", "first_name": "Анна",
            "last_name": "Иванова", "message": "Не работает привязка", **overrides}


def image():
    out = BytesIO()
    Image.new("RGB", (40, 40), "red").save(out, "PNG")
    return out.getvalue()


def test_ticket_unlinked_identity_and_owner_only_inbox(support_client):
    c, _ = support_client
    assert c.get("/api/v1/support/context", headers=auth()).json() == {"inbox_enabled": False}
    assert c.get("/api/v1/support/context", headers=auth(4242)).json() == {"inbox_enabled": True}
    submitted = c.post("/api/v1/support/tickets", headers=auth(), json=ticket())
    assert submitted.status_code == 201
    assert c.get("/api/v1/support/tickets", headers=auth()).status_code == 403
    assert c.get("/api/v1/support/tickets").status_code == 401
    inbox = c.get("/api/v1/support/tickets", headers=auth(4242)).json()
    assert inbox["total"] == 1
    assert inbox["items"][0]["max_user_id"] == "77"
    assert inbox["items"][0]["source"] == "miniapp"


def test_idempotent_submission_and_identity_cannot_be_spoofed(support_client):
    c, _ = support_client
    body = ticket()
    a = c.post("/api/v1/support/tickets", headers=auth(), json=body)
    b = c.post("/api/v1/support/tickets", headers=auth(), json=body)
    assert a.json()["id"] == b.json()["id"]
    assert c.post("/api/v1/support/tickets", headers=auth(88), json=body).status_code == 409
    assert c.post("/api/v1/support/tickets", headers=auth(),
                  json=ticket(max_user_id=999)).status_code == 422


@pytest.mark.parametrize("fields", [
    {"first_name": " "}, {"last_name": ""}, {"last_name": "123"},
    {"message": " "}, {"message": "a" * 4001}, {"role": "superadmin"},
])
def test_required_fields(support_client, fields):
    c, _ = support_client
    result = c.post("/api/v1/support/tickets", headers=auth(), json=ticket(**fields))
    assert result.status_code == 422


def test_private_photos_and_cross_identity_attachment_rejected(support_client):
    c, _ = support_client
    uploaded = c.post("/api/v1/support/photos", headers=auth(),
                      files={"photo": ("image.png", image(), "image/png")})
    assert uploaded.status_code == 201
    pid = uploaded.json()["id"]
    assert c.get(f"/api/v1/support/photos/{pid}").status_code == 401
    assert c.get(f"/api/v1/support/photos/{pid}", headers=auth(88)).status_code == 404
    owner_photo = c.get(f"/api/v1/support/photos/{pid}", headers=auth(4242))
    assert owner_photo.status_code == 200
    assert owner_photo.headers["content-type"] == "image/webp"
    assert "no-store" in owner_photo.headers["cache-control"]
    assert c.post("/api/v1/support/tickets", headers=auth(88),
                  json=ticket(photo_ids=[pid])).status_code == 400
    assert c.post("/api/v1/support/tickets", headers=auth(),
                  json=ticket(photo_ids=[pid])).status_code == 201
    assert c.delete(f"/api/v1/support/photos/{pid}", headers=auth()).status_code == 409


def test_photo_validation_and_rate_limit(support_client):
    c, _ = support_client
    assert c.post("/api/v1/support/photos", headers=auth(),
                  files={"photo": ("fake.png", b"not an image", "image/png")}).status_code == 400
    for _ in range(5):
        assert c.post("/api/v1/support/tickets", headers=auth(), json=ticket()).status_code == 201
    assert c.post("/api/v1/support/tickets", headers=auth(), json=ticket()).status_code == 429


def test_status_note_search_and_filter(support_client):
    c, _ = support_client
    created = c.post("/api/v1/support/tickets", headers=auth(), json=ticket()).json()
    url = f'/api/v1/support/tickets/{created["id"]}'
    update = {"status": "in_progress", "private_note": "Проверить историю"}
    assert c.patch(url, headers=auth(), json=update).status_code == 403
    assert c.patch(url, headers=auth(4242), json=update).status_code == 200
    assert c.get("/api/v1/support/tickets?status=new", headers=auth(4242)).json()["total"] == 0
    found = c.get("/api/v1/support/tickets?search=Иванова", headers=auth(4242)).json()
    assert found["items"][0]["private_note"] == "Проверить историю"
    assert found["counts"] == {"in_progress": 1}


def event(c, action, **fields):
    return c.post("/api/v1/support/bot-event", headers=auth(), json={
        "max_user_id": 77, "tenant_slug": "test-city", "action": action, **fields,
    })


def test_bot_form_persists_deduplicates_and_submits(support_client, monkeypatch):
    c, factory = support_client
    assert event(c, "start").json()["stage"] == "role"
    name_prompt = event(c, "role", role="student").json()
    assert name_prompt["stage"] == "full_name"
    assert "имя и фамилию одним сообщением" in name_prompt["text"]
    assert event(c, "message", text="Дмитрий", event_id="m0").status_code == 400
    assert event(c, "start").json()["stage"] == "full_name"
    assert event(c, "message", text="Дмитрий Иванов", event_id="m1").json()["stage"] == "message"
    assert event(c, "message", text="Дмитрий Иванов", event_id="m1").json()["stage"] == "message"

    async def download(*args, **kwargs):
        return image(), "https://example.com/photo.png"

    monkeypatch.setattr("app.services.support._fetch_remote_bytes", download)
    ready = event(c, "message", text="Не работает магазин", event_id="m3",
                  photo_urls=["https://example.com/photo.png"])
    assert ready.json()["stage"] == "photos"
    assert "1 из 5" in ready.json()["text"]
    sent = event(c, "submit").json()
    assert sent["ticket_id"] > 0
    assert event(c, "submit").json()["active"] is False
    inbox = c.get("/api/v1/support/tickets", headers=auth(4242)).json()
    assert inbox["items"][0]["source"] == "bot"
    assert len(inbox["items"][0]["photo_ids"]) == 1

    async def count():
        async with factory() as db:
            assert await db.scalar(select(func.count()).select_from(SupportTicket)) == 1
            assert await db.get(SupportDraft, 77) is None

    asyncio.run(count())


def test_bot_cancel_deletes_unsubmitted_photos_and_spoof_denied(support_client):
    c, _ = support_client
    assert c.post("/api/v1/support/bot-event", headers=auth(), json={
        "max_user_id": 999, "tenant_slug": "test-city", "action": "start",
    }).status_code == 403
    event(c, "start")
    assert event(c, "cancel").json()["active"] is False
    assert event(c, "message", text="Привет").json()["active"] is False


def test_bot_wiring_handles_photo_only_message_and_callback():
    calls = []

    class Backend:
        def support_event(self, **fields):
            calls.append(fields)
            return {"active": True, "stage": "photos", "text": "Готово"}

    client = SimulationMaxClient()
    bot = LongPollingBot(client, backend_client=Backend())
    bot.handle_message_created({"message": {"sender": {"user_id": 77},
        "recipient": {"chat_id": 22}, "body": {"mid": "x", "attachments": [
            {"type": "image", "payload": {"url": "https://example.com/photo.png"}},
        ]}}})
    assert calls[-1]["photo_urls"] == ["https://example.com/photo.png"]
    assert calls[-1]["event_id"] == "x"
    bot.handle_message_callback({"callback": {"user": {"user_id": 77},
        "payload": "support:role:parent", "callback_id": "cb"}})
    assert calls[-1]["role"] == "parent"


def test_notification_only_to_owner_and_failure_is_retried(support_client, monkeypatch):
    c, factory = support_client
    c.post("/api/v1/support/tickets", headers=auth(), json=ticket())
    calls = []

    class FakeMax:
        fail = True

        def send_message(self, **kwargs):
            calls.append(kwargs)
            if self.fail:
                raise RuntimeError("MAX unavailable")

    max_client = FakeMax()
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", factory)
    monkeypatch.setattr("app.services.support.MaxApiClient", lambda *a, **k: max_client)

    async def stop(_):
        raise asyncio.CancelledError

    def run_once():
        with monkeypatch.context() as patch:
            patch.setattr("app.services.support.asyncio.sleep", stop)
            with pytest.raises(asyncio.CancelledError):
                asyncio.run(notification_loop())

    run_once()

    async def retry_ready():
        async with factory() as db:
            record = await db.scalar(select(SupportTicket))
            assert record.notified_at is None
            assert record.notification_attempts == 1
            record.notification_attempted_at = datetime.now(UTC) - timedelta(minutes=3)
            await db.commit()

    asyncio.run(retry_ready())
    max_client.fail = False
    run_once()

    async def delivered():
        async with factory() as db:
            record = await db.scalar(select(SupportTicket))
            assert record.notified_at is not None
            assert record.notification_attempts == 2

    asyncio.run(delivered())
    assert len(calls) == 2
    assert all(call["user_id"] == 4242 for call in calls)


def test_personal_reply_access_idempotency_retry_and_resolution(support_client):
    c, factory = support_client
    tid = c.post("/api/v1/support/tickets", headers=auth(), json=ticket()).json()["id"]
    url = f"/api/v1/support/tickets/{tid}/replies"
    body = {"request_id": str(uuid4()), "message": "Связь восстановлена, попробуйте снова"}
    assert c.post(url, headers=auth(), json=body).status_code == 403
    assert c.post(url, json=body).status_code == 401
    assert c.post(url, headers=auth(4242), json={**body, "max_user_id": 999}).status_code == 422
    a = c.post(url, headers=auth(4242), json=body)
    assert a.status_code == 202
    b = c.post(url, headers=auth(4242), json=body)
    assert a.json()["id"] == b.json()["id"]
    assert c.post(url, headers=auth(4242), json={
        **body, "request_id": str(uuid4()),
    }).status_code == 409
    changed = c.post(url, headers=auth(4242), json={**body, "message": "Другой текст"})
    assert changed.status_code == 409
    sent = []

    class FakeMax:
        fail = True

        def send_message(self, **kwargs):
            sent.append(kwargs)
            if self.fail:
                raise RuntimeError("Bot blocked")

    max_client = FakeMax()

    async def delivery():
        async with factory() as db:
            assert await deliver_next_reply(db, max_client)
        async with factory() as db:
            reply = await db.scalar(select(SupportReply))
            record = await db.get(SupportTicket, tid)
            assert reply.status == "retry"
            assert record.status == "in_progress"
            reply.attempted_at = datetime.now(UTC) - timedelta(minutes=3)
            await db.commit()
        max_client.fail = False
        async with factory() as db:
            assert await deliver_next_reply(db, max_client)
            assert not await deliver_next_reply(db, max_client)
        async with factory() as db:
            reply = await db.scalar(select(SupportReply))
            record = await db.get(SupportTicket, tid)
            assert reply.status == "sent" and reply.sent_at
            assert record.status == "resolved"
            assert reply.attempts == 2

    asyncio.run(delivery())
    assert len(sent) == 2
    assert all(item["user_id"] == 77 for item in sent)
    assert all(body["message"] in item["text"] for item in sent)
    inbox = c.get("/api/v1/support/tickets", headers=auth(4242)).json()
    assert inbox["items"][0]["replies"][0]["status"] == "sent"


def test_legacy_name_step_resumes_with_combined_prompt(support_client):
    c, factory = support_client

    async def prepare():
        async with factory() as db:
            db.add(SupportDraft(max_user_id=77, request_id=uuid4(), stage="last_name",
                                role="parent", first_name="Анна"))
            await db.commit()

    asyncio.run(prepare())
    assert event(c, "start").json()["stage"] == "full_name"
    assert event(c, "message", text="Анна Иванова").json()["stage"] == "message"


@pytest.mark.parametrize("status", ["new", "in_progress", "resolved"])
def test_owner_can_permanently_delete_ticket_with_photos_replies_and_history(
    support_client, status, monkeypatch,
):
    c, factory = support_client
    photo_id = c.post("/api/v1/support/photos", headers=auth(),
                      files={"photo": ("screen.png", image(), "image/png")}).json()["id"]
    body = ticket(photo_ids=[photo_id])
    tid = c.post("/api/v1/support/tickets", headers=auth(), json=body).json()["id"]
    other = c.post("/api/v1/support/tickets", headers=auth(), json=ticket()).json()["id"]
    pending_photo = c.post("/api/v1/support/photos", headers=auth(),
                          files={"photo": ("new.png", image(), "image/png")}).json()["id"]
    url = f"/api/v1/support/tickets/{tid}"
    flags = []

    async def capture(request, **kwargs):
        if request.method == "DELETE":
            flags.append((kwargs["status"], getattr(request.state, "audit_skip", False)))

    monkeypatch.setattr("app.services.activity_audit.persist_request", capture)

    async def prepare():
        async with factory() as db:
            row = await db.get(SupportTicket, tid)
            row.status = status
            db.add_all([SupportReply(ticket_id=tid, request_id=uuid4(), message="Ответ",
                                     status=reply_status)
                        for reply_status in ["sent", "queued", "retry"]])
            db.add(SupportDraft(max_user_id=77, request_id=row.request_id, stage="photos"))
            db.add(SupportDraft(max_user_id=88, request_id=uuid4(), stage="message"))
            paths = [url, url + "/replies", f"/api/v1/support/photos/{photo_id}",
                     url + "0", f"/api/v1/support/tickets/{other}", "/api/v1/miniapp/session"]
            db.add_all([AuditLog(action="activity.request", entity_type="activity",
                                 payload={"path": path}) for path in paths])
            await db.commit()

    asyncio.run(prepare())
    assert c.delete(url).status_code == 401
    assert c.delete(url, headers=auth()).status_code == 403
    assert c.delete(url, headers=auth(88)).status_code == 403
    assert c.get("/api/v1/support/tickets", headers=auth(4242)).json()["total"] == 2
    assert c.delete(url, headers=auth(4242)).status_code == 204
    assert flags[-1] == (204, True)
    assert all(not skip for _, skip in flags[:-1])
    inbox = c.get("/api/v1/support/tickets", headers=auth(4242)).json()
    assert inbox["total"] == 1 and inbox["items"][0]["id"] == other
    assert sum(inbox["counts"].values()) == 1
    assert c.get(f"/api/v1/support/photos/{photo_id}", headers=auth(4242)).status_code == 404
    assert c.get(f"/api/v1/support/photos/{pending_photo}", headers=auth()).status_code == 200
    assert c.patch(url, headers=auth(4242), json={"status": "resolved"}).status_code == 404
    assert c.post(url + "/replies", headers=auth(4242), json={
        "request_id": str(uuid4()), "message": "Ответ после удаления",
    }).status_code == 404
    assert c.delete(url, headers=auth(4242)).status_code == 404

    async def gone():
        async with factory() as db:
            assert await db.get(SupportTicket, tid) is None
            assert await db.scalar(select(func.count()).select_from(SupportReply)) == 0
            assert await db.scalar(select(func.count()).select_from(SupportPhoto)) == 1
            assert await db.get(SupportDraft, 77) is None
            assert await db.get(SupportDraft, 88) is not None
            paths = [log.payload["path"] for log in await db.scalars(select(AuditLog))]
            assert set(paths) == {url + "0", f"/api/v1/support/tickets/{other}",
                                  "/api/v1/miniapp/session"}

            class NoSend:
                def send_message(self, **kwargs):
                    pytest.fail("Deleted ticket must not deliver a queued reply")

            assert not await deliver_next_reply(db, NoSend())

    asyncio.run(gone())
