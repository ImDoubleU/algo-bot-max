import asyncio
import importlib.util
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from test_support import auth, event, image
from test_support import support_client as _support_client

from app.models.support import SupportDraft

support_client = _support_client


@pytest.mark.parametrize("role", ["parent", "student", "staff"])
def test_new_bot_ticket_requires_city_for_all_and_child_name_only_for_parent(support_client, role):
    c, _ = support_client
    event(c, "start")
    event(c, "role", role=role)
    assert event(c, "message", text="Анна Иванова", event_id="name").json()["stage"] == "city"
    assert event(c, "submit").json()["stage"] == "city"
    assert event(c, "message", text=" ").status_code == 400
    assert event(c, "message", text="https://example.org").status_code == 400
    assert event(c, "start").json()["stage"] == "city"
    next_stage = "child_name" if role == "parent" else "message"
    for city in ["  Нижний   Новгород  ", "Нижний Новгород"]:
        assert event(c, "message", text=city, event_id="city").json()["stage"] == next_stage
    if role == "parent":
        assert event(c, "submit").json()["stage"] == "child_name"
        assert event(c, "message", text="Иван").status_code == 400
        assert event(c, "message", text="123 Иванов").status_code == 400
        for child in ["  Иван   Иванов  ", "Иван Иванов"]:
            assert event(c, "message", text=child, event_id="child").json()["stage"] == "message"
    ready = event(c, "message", text="Не открывается приложение").json()
    assert ready["stage"] == "photos"
    assert "Город: Нижний Новгород" in ready["text"]
    assert ("Ребёнок: Иван Иванов" in ready["text"]) == (role == "parent")
    assert event(c, "submit").json()["ticket_id"] > 0
    record = c.get("/api/v1/support/tickets", headers=auth(4242)).json()["items"][0]
    assert record["city_name"] == "Нижний Новгород"
    assert record["child_full_name"] == ("Иван Иванов" if role == "parent" else None)
    assert record["max_user_id"] == "77"
    assert record["message"] == "Не открывается приложение"


@pytest.mark.parametrize("action", ["start", "submit", "message"])
def test_unsubmitted_legacy_form_keeps_description_and_photos(support_client, action):
    c, factory = support_client
    photo_id = c.post("/api/v1/support/photos", headers=auth(),
                      files={"photo": ("photo.png", image(), "image/png")}).json()["id"]

    async def prepare():
        async with factory() as db:
            db.add(SupportDraft(max_user_id=77, request_id=uuid4(), stage="photos",
                                role="parent", first_name="Анна", last_name="Иванова",
                                message="Сохранённое описание", photo_ids=[photo_id]))
            await db.commit()

    asyncio.run(prepare())
    assert event(c, action, text="Не считать это городом").json()["stage"] == "city"
    assert event(c, "message", text="Бор").json()["stage"] == "child_name"
    assert event(c, "message", text="Иван Иванов").json()["stage"] == "photos"
    sent = event(c, "submit").json()
    record = c.get("/api/v1/support/tickets", headers=auth(4242)).json()["items"][0]
    assert record["id"] == sent["ticket_id"]
    assert record["message"] == "Сохранённое описание"
    assert record["photo_ids"] == [str(UUID(photo_id))]


def test_additive_migration_keeps_existing_tickets_and_drafts_untouched():
    path = Path(__file__).parents[1] / "alembic/versions/20261017_0038_support_city_child.py"
    spec = importlib.util.spec_from_file_location("support_city_child_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("support_tickets", "support_drafts"):
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, message TEXT)"))
            connection.execute(text(f"INSERT INTO {table} VALUES (7, 'Existing text')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            for table in ("support_tickets", "support_drafts"):
                assert connection.execute(text(
                    f"SELECT id, message, city_name, child_full_name FROM {table}"
                )).one() == (7, "Existing text", None, None)
            migration.downgrade()
            for table in ("support_tickets", "support_drafts"):
                row = connection.execute(text(f"SELECT * FROM {table}")).one()
                assert row == (7, "Existing text")
                assert len(inspect(connection).get_columns(table)) == 2
    engine.dispose()
