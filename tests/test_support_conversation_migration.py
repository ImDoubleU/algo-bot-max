import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def test_migration_keeps_old_replies_and_downgrades_waiting_status():
    path = (Path(__file__).parents[1] / "alembic" / "versions"
            / "20261012_0037_support_conversations.py")
    spec = importlib.util.spec_from_file_location("support_conversation_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE support_tickets (id INTEGER PRIMARY KEY, status TEXT)"))
        connection.execute(text(
            "CREATE TABLE support_replies (id INTEGER PRIMARY KEY, message TEXT)"))
        connection.execute(text("INSERT INTO support_tickets VALUES (1, 'waiting')"))
        connection.execute(text("INSERT INTO support_replies VALUES (1, 'Old reply')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            row = connection.execute(text(
                "SELECT message, author, photo_ids FROM support_replies")).one()
            assert row == ("Old reply", "staff", "[]")
            assert "support_conversations" in inspect(connection).get_table_names()
            migration.downgrade()
            assert connection.scalar(text("SELECT status FROM support_tickets")) == "in_progress"
            assert connection.scalar(text("SELECT message FROM support_replies")) == "Old reply"
            assert "support_conversations" not in inspect(connection).get_table_names()
    engine.dispose()
