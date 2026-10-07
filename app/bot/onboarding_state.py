from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


class OnboardingState:
    """Short-lived contact context. Never stores invitation tokens or message bodies."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS onboarding ("
                "user_id INTEGER PRIMARY KEY, contact_id TEXT, tenant_slug TEXT, "
                "role TEXT, correlation_id TEXT NOT NULL, expires_at REAL NOT NULL)"
            )
        if os.name != "nt":
            path.chmod(0o600)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, user_id: int) -> dict | None:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM onboarding WHERE user_id=?", (user_id,)
            ).fetchone()
            if row is None:
                return None
            result = dict(row)
            if result["expires_at"] <= time.time():
                connection.execute(
                    "DELETE FROM onboarding WHERE user_id=? AND expires_at <= ?",
                    (user_id, time.time()),
                )
                result["expired"] = True
            return result

    def save(
        self,
        user_id: int,
        *,
        contact_id: str | None,
        tenant_slug: str | None,
        role: str | None,
        correlation_id: str,
        ttl: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM onboarding WHERE expires_at <= ?", (time.time(),))
            connection.execute(
                "INSERT INTO onboarding VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET contact_id=excluded.contact_id, "
                "tenant_slug=excluded.tenant_slug, role=excluded.role, "
                "correlation_id=excluded.correlation_id, expires_at=excluded.expires_at",
                (user_id, contact_id, tenant_slug, role, correlation_id, time.time() + ttl),
            )

    def delete(self, user_id: int) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM onboarding WHERE user_id=?", (user_id,))
