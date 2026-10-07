"""Private, crash-safe MAX update inbox. Credentials never enter log messages."""

import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

LEASE_SECONDS = 300
RETENTION_SECONDS = 7 * 24 * 60 * 60
MAX_ATTEMPTS = 5


class WebhookInboxFull(RuntimeError):
    pass


class WebhookInbox:
    def __init__(self, path: Path, *, capacity: int = 500):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        self.capacity = max(1, capacity)
        if os.name != "nt":
            path.parent.chmod(0o700)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS webhook_inbox ("
                "event_id TEXT PRIMARY KEY, body TEXT, update_type TEXT NOT NULL, "
                "max_user_id INTEGER, status TEXT NOT NULL, attempts INTEGER NOT NULL, "
                "created_at REAL NOT NULL, available_at REAL NOT NULL, "
                "lease_until REAL, claim_id TEXT, error_type TEXT)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS webhook_pending "
                "ON webhook_inbox (status, max_user_id, created_at)"
            )
            columns = {row[1] for row in db.execute("PRAGMA table_info(webhook_inbox)")}
            if "audit_exported" not in columns:
                db.execute(
                    "ALTER TABLE webhook_inbox ADD COLUMN audit_exported INTEGER NOT NULL DEFAULT 0"
                )
        if os.name != "nt":
            path.chmod(0o600)

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            # A committed receipt must survive an interrupted worker process.
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def put(self, update: dict) -> tuple[str, bool]:
        body = json.dumps(update, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        event_id = hashlib.sha256(body.encode()).hexdigest()
        user = update.get("user") or (update.get("message") or {}).get("sender") or {}
        callback = update.get("callback") or {}
        user = callback.get("user") or user
        raw_id = user.get("user_id") or update.get("user_id")
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            user_id = None
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM webhook_inbox WHERE status IN ('done', 'failed') "
                "AND audit_exported = 1 AND created_at < ?",
                (now - RETENTION_SECONDS,),
            )
            if db.execute("SELECT 1 FROM webhook_inbox WHERE event_id=?", (event_id,)).fetchone():
                return event_id, False
            pending = db.execute(
                "SELECT count(*) FROM webhook_inbox WHERE status IN ('queued', 'processing')"
            ).fetchone()[0]
            if pending >= self.capacity:
                raise WebhookInboxFull("MAX webhook inbox is full")
            result = db.execute(
                "INSERT OR IGNORE INTO webhook_inbox "
                "(event_id, body, update_type, max_user_id, status, attempts, "
                "created_at, available_at) "
                "VALUES (?, ?, ?, ?, 'queued', 0, ?, ?)",
                (event_id, body, update.get("update_type", "unknown"), user_id, now, now),
            )
            return event_id, result.rowcount == 1

    def claim(self) -> dict | None:
        now = time.time()
        claim_id = str(uuid4())
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "DELETE FROM webhook_inbox WHERE status IN ('done', 'failed') "
                "AND audit_exported = 1 AND created_at < ?",
                (now - RETENTION_SECONDS,),
            )
            # A worker that crashed on its final attempt still needs safe finalization.
            result = db.execute(
                "UPDATE webhook_inbox SET status='failed', body=NULL, claim_id=NULL, "
                "lease_until=NULL, error_type='WorkerInterrupted' "
                "WHERE status='processing' AND lease_until <= ? AND attempts >= ?",
                (now, MAX_ATTEMPTS),
            )
            row = db.execute(
                "SELECT q.* FROM webhook_inbox q WHERE q.body IS NOT NULL AND q.attempts < ? "
                "AND ((q.status='queued' AND q.available_at <= ?) "
                "OR (q.status='processing' AND q.lease_until <= ?)) "
                "AND NOT EXISTS (SELECT 1 FROM webhook_inbox p "
                "WHERE p.status IN ('queued', 'processing') "
                "AND p.max_user_id IS q.max_user_id "
                "AND p.rowid < q.rowid) "
                "ORDER BY q.rowid LIMIT 1", (MAX_ATTEMPTS, now, now),
            ).fetchone()
            if row is None:
                return None
            db.execute(
                "UPDATE webhook_inbox SET status='processing', attempts=attempts+1, "
                "lease_until=?, claim_id=? WHERE event_id=?",
                (now + LEASE_SECONDS, claim_id, row["event_id"]),
            )
            result = dict(row)
            result["claim_id"] = claim_id
            result["attempts"] += 1
            result["update"] = json.loads(result.pop("body"))
            return result

    def finish(self, event: dict, *, error_type: str | None = None):
        failed = error_type is not None
        final = not failed or event["attempts"] >= MAX_ATTEMPTS
        delay = (1, 5, 30, 120, 300)[min(event["attempts"] - 1, 4)]
        status = "done" if not failed else "failed" if final else "queued"
        with self._connect() as db:
            result = db.execute(
                "UPDATE webhook_inbox SET status=?, body=CASE WHEN ? THEN NULL ELSE body END, "
                "available_at=?, lease_until=NULL, claim_id=NULL, error_type=? "
                "WHERE event_id=? AND claim_id=?",
                (status, final, time.time() + delay, error_type,
                 event["event_id"], event["claim_id"]),
            )
        return status if result.rowcount else "lease_lost"
