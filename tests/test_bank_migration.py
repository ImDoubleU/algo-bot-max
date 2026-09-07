import sqlite3

import pytest
from alembic.config import Config

from alembic import command
from app.core.config import get_settings

PREVIOUS_REVISION = "20260904_0027"


def _table_columns(connection: sqlite3.Connection, table: str) -> dict[str, tuple]:
    return {row[1]: row for row in connection.execute(f"PRAGMA table_info({table})")}


def _seed_pre_bank_ledger(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys=ON;
        INSERT INTO cities (id, slug, name)
        VALUES ('11111111111111111111111111111111', 'test-city', 'Test City');
        INSERT INTO partners (id, slug, name)
        VALUES ('22222222222222222222222222222222', 'test-partner', 'Test Partner');
        INSERT INTO tenants (id, city_id, partner_id, slug, name, status)
        VALUES (
            '33333333333333333333333333333333',
            '11111111111111111111111111111111',
            '22222222222222222222222222222222',
            'test-tenant',
            'Test Tenant',
            'active'
        );
        INSERT INTO students (
            id, tenant_id, student_access_code, first_name, status
        ) VALUES (
            '44444444444444444444444444444444',
            '33333333333333333333333333333333',
            'TEST-1',
            'Student',
            'active'
        );
        INSERT INTO wallets (id, tenant_id, student_id, balance)
        VALUES (
            '55555555555555555555555555555555',
            '33333333333333333333333333333333',
            '44444444444444444444444444444444',
            1000
        );
        INSERT INTO astrocoin_ledger_entries (
            id, tenant_id, wallet_id, student_id, idempotency_key,
            direction, amount, reason
        ) VALUES
            (
                '66666666666666666666666666666661',
                '33333333333333333333333333333333',
                '55555555555555555555555555555555',
                '44444444444444444444444444444444',
                'accrual:test', 'credit', 100, 'Accrual'
            ),
            (
                '66666666666666666666666666666662',
                '33333333333333333333333333333333',
                '55555555555555555555555555555555',
                '44444444444444444444444444444444',
                'order:abc:debit', 'debit', 50, 'Purchase'
            ),
            (
                '66666666666666666666666666666663',
                '33333333333333333333333333333333',
                '55555555555555555555555555555555',
                '44444444444444444444444444444444',
                'demo:run:order:001', 'debit', 25, 'Demo purchase'
            );
        """
    )
    connection.commit()


def test_bank_migration_upgrade_backfill_and_downgrade(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "bank-migration.db"
    sync_url = f"sqlite:///{database_path.as_posix()}"
    async_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_SYNC_URL", sync_url)
    monkeypatch.setenv("DATABASE_URL", async_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")

    try:
        command.upgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database_path) as connection:
            _seed_pre_bank_ledger(connection)
            assert "category" not in _table_columns(
                connection,
                "astrocoin_ledger_entries",
            )

        command.upgrade(config, "head")
        with sqlite3.connect(database_path) as connection:
            categories = connection.execute(
                """
                SELECT idempotency_key, category
                FROM astrocoin_ledger_entries
                ORDER BY idempotency_key
                """
            ).fetchall()
            assert categories == [
                ("accrual:test", "accrual"),
                ("demo:run:order:001", "purchase"),
                ("order:abc:debit", "purchase"),
            ]
            category_column = _table_columns(
                connection,
                "astrocoin_ledger_entries",
            )["category"]
            assert category_column[4] is None
            assert connection.execute("SELECT bank_annual_rate_bps FROM tenants").fetchone() == (0,)
            table_names = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            assert {
                "bank_rate_history",
                "bank_deposits",
                "bank_daily_accruals",
                "bank_operations",
            }.issubset(table_names)
            assert connection.execute("SELECT count(*) FROM bank_deposits").fetchone() == (0,)
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO astrocoin_ledger_entries (
                        id, tenant_id, wallet_id, student_id, idempotency_key,
                        direction, category, amount, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "66666666666666666666666666666664",
                        "33333333333333333333333333333333",
                        "55555555555555555555555555555555",
                        "44444444444444444444444444444444",
                        "invalid-category",
                        "credit",
                        "other",
                        1,
                        "Invalid",
                    ),
                )

        command.downgrade(config, PREVIOUS_REVISION)
        with sqlite3.connect(database_path) as connection:
            assert "category" not in _table_columns(
                connection,
                "astrocoin_ledger_entries",
            )
            assert "bank_annual_rate_bps" not in _table_columns(connection, "tenants")
            table_names = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            assert not any(name.startswith("bank_") for name in table_names)
            assert connection.execute(
                "SELECT count(*) FROM astrocoin_ledger_entries"
            ).fetchone() == (3,)
    finally:
        get_settings.cache_clear()
