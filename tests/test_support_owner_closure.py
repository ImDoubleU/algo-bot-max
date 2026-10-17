# ruff: noqa: F811
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.bot.support import support_keyboard
from app.models.support import (
    SupportConversation,
    SupportDraft,
    SupportPhoto,
    SupportReply,
    SupportTicket,
)
from tests.test_support import auth, event, image, support_client, ticket  # noqa: F401


@pytest.mark.parametrize("status", ["new", "in_progress", "waiting", "resolved"])
def test_only_owner_can_close_ticket_and_legacy_exit_preserves_status(support_client, status):
    client, _ = support_client
    ticket_id = client.post("/api/v1/support/tickets", headers=auth(), json=ticket()).json()["id"]
    url = f"/api/v1/support/tickets/{ticket_id}"
    assert client.patch(url, headers=auth(4242), json={"status": status}).status_code == 200
    for user in [77, 88]:
        assert client.patch(url, headers=auth(user), json={"status": "resolved"}).status_code == 403
    response = event(client, "exit")
    assert response.status_code == 200 and "только администратор" in response.json()["text"]
    current = client.get("/api/v1/support/tickets", headers=auth(4242)).json()["items"][0]
    assert current["status"] == status
    assert client.patch(url, headers=auth(4242), json={"status": "resolved"}).status_code == 200
    resolved = client.get("/api/v1/support/tickets?status=resolved", headers=auth(4242)).json()
    assert resolved["total"] == 1


@pytest.mark.parametrize("has_draft", [False, True])
def test_old_exit_button_keeps_pending_text_photos_and_new_draft(support_client, has_draft):
    client, factory = support_client
    tid = client.post("/api/v1/support/tickets", headers=auth(), json=ticket()).json()["id"]
    photo_id = client.post("/api/v1/support/photos", headers=auth(),
        files={"photo": ("image.png", image(), "image/png")}).json()["id"]
    pending = [{"text": "Дополнение", "photo_ids": [photo_id], "event_id": "pending-1"}]

    async def prepare():
        async with factory() as db:
            record = await db.get(SupportTicket, tid)
            record.status = "waiting"
            db.add(SupportConversation(max_user_id=77, ticket_id=None, paused=False,
                pending_messages=pending))
            if has_draft:
                db.add(SupportDraft(max_user_id=77, request_id=uuid4(), stage="message",
                    role="parent", first_name="Анна", last_name="Иванова"))
            await db.commit()

    asyncio.run(prepare())
    assert event(client, "exit").status_code == 200

    async def preserved():
        async with factory() as db:
            conversation = await db.get(SupportConversation, 77)
            assert conversation.ticket_id is None and conversation.paused is False
            assert conversation.pending_messages == pending
            assert (await db.scalar(select(SupportPhoto))).ticket_id is None
            assert (await db.get(SupportDraft, 77) is not None) == has_draft
            assert (await db.get(SupportTicket, tid)).status == "waiting"

    asyncio.run(preserved())
    if not has_draft:
        response = event(client, "choose", ticket_id=tid)
        assert response.status_code == 200 and response.json()["stage"] == "conversation"

        async def continued():
            async with factory() as db:
                reply = await db.scalar(select(SupportReply))
                assert reply.message == "Дополнение" and reply.photo_ids == [photo_id]
                assert (await db.scalar(select(SupportPhoto))).ticket_id == tid
                assert (await db.get(SupportTicket, tid)).status == "new"

        asyncio.run(continued())


@pytest.mark.parametrize("stage, result", [
    ("conversation", {"ticket_id": 1}),
    ("choose", {"tickets": [{"id": 1, "label": "№1"}, {"id": 2, "label": "№2"}]}),
    ("closed", {"ticket_id": 1}),
])
def test_user_keyboards_omit_finish_button_and_keep_reply_and_ticket_selection(stage, result):
    attachments = support_keyboard(stage, result)
    buttons = [button for attachment in attachments or []
        for row in attachment["payload"]["buttons"] for button in row]
    assert all(button["payload"] != "support:exit" for button in buttons)
    if stage == "conversation":
        assert attachments is None
    elif stage == "choose":
        assert [button["payload"] for button in buttons] == ["support:choose:1", "support:choose:2"]
    else:
        assert [button["payload"] for button in buttons] == ["support:reply:1"]
