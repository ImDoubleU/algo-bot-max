# ruff: noqa: F811
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.enums import StudentAccessRole, StudentAccessStatus
from app.models.pizza import PizzaNotice
from app.models.student import StudentAccessLink
from app.services import pizza
from app.services.collection_notifications import deliver_next
from tests.test_pizza import context  # noqa: F401


class FakeClient:
    def __init__(self, failures=0):
        self.messages = []
        self.failures = failures

    def send_message(self, **kwargs):
        if self.failures:
            self.failures -= 1
            raise RuntimeError("simulated failure")
        self.messages.append(kwargs)
        return {"ok": True}


async def drain(c, client, now=None):
    for _ in range(30):
        if not await deliver_next(c["db"], client, now=now):
            return
    raise AssertionError("Unbounded notification queue")


async def test_opened_notifies_each_connected_student_and_parent_once(context):
    c = context
    client = FakeClient()
    await drain(c, client)
    ids = [m["user_id"] for m in client.messages]
    assert set(ids) == {
        c["parent"].account.max_user_id,
        *(a.max_user_id for a in c["accounts"][:3]),
    }
    assert len(ids) == 4  # One parent with three children receives one message.
    assert all("200 AC" in m["text"] and "Магазин" in m["text"] for m in client.messages)
    await drain(c, client)
    assert len(client.messages) == 4


async def test_retry_is_durable_and_success_is_not_sent_twice(context):
    c = context
    client = FakeClient(failures=1)
    now = datetime.now(UTC)
    await drain(c, client, now)
    assert len(client.messages) == 3
    pending = list(await c["db"].scalars(select(PizzaNotice).where(PizzaNotice.sent_at.is_(None))))
    assert len(pending) == 1 and pending[0].attempts == 1
    assert pending[0].last_error == "RuntimeError" and pending[0].next_attempt_at
    await drain(c, client, now + timedelta(minutes=2))
    assert len(client.messages) == 4
    await drain(c, client, now + timedelta(minutes=3))
    assert len(client.messages) == 4


async def test_closed_collection_never_sends_late_opening_notice(context):
    c = context
    await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "cancel")
    await c["db"].commit()
    client = FakeClient()
    await drain(c, client)
    assert client.messages == []
    assert all(n.cancelled_at for n in await c["db"].scalars(select(PizzaNotice)))


async def test_revoked_links_do_not_receive_student_or_parent_notice(context):
    c = context
    parent_link = await c["db"].scalar(
        select(StudentAccessLink).where(
            StudentAccessLink.student_id == c["pupils"][0].id,
            StudentAccessLink.role == StudentAccessRole.PARENT,
        )
    )
    parent_link.status = StudentAccessStatus.REVOKED
    await c["db"].commit()
    client = FakeClient()
    await drain(c, client)
    assert c["accounts"][0].max_user_id not in {m["user_id"] for m in client.messages}
    parent_message = next(
        m["text"] for m in client.messages if m["user_id"] == c["parent"].account.max_user_id
    )
    assert c["pupils"][0].display_name not in parent_message


async def test_parent_sees_open_collection_but_cannot_spend_child_coins(context):
    c = context
    data = await pizza.board(c["db"], c["parent"], student_id=c["pupils"][0].id)
    assert len(data["campaigns"]) == 1
    assert not data["campaigns"][0]["can_contribute"]
    assert not data["campaigns"][0]["can_manage"]
