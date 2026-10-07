import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.bot.max_webhook import MaxWebhookRuntime, WebhookQueueFull
from app.bot.webhook_inbox import (
    LEASE_SECONDS,
    MAX_ATTEMPTS,
    RETENTION_SECONDS,
    WebhookInbox,
    WebhookInboxFull,
)


def event(*, user_id=1, payload="shop_review~681", timestamp=1):
    return {
        "update_type": "bot_started", "user": {"user_id": user_id},
        "payload": payload, "timestamp": timestamp,
    }


def test_committed_receipt_survives_reopening_before_any_worker_runs(tmp_path):
    path = tmp_path / "private" / "webhook.sqlite3"
    original = WebhookInbox(path)
    key, inserted = original.put(event())
    assert inserted
    reopened = WebhookInbox(path)
    claimed = reopened.claim()
    assert claimed["event_id"] == key
    assert claimed["update"]["payload"] == "shop_review~681"


def test_duplicate_receipts_do_not_replay_finished_events(tmp_path):
    store = WebhookInbox(tmp_path / "inbox.sqlite3")
    key, _ = store.put(event())
    repeated, inserted = store.put(event())
    assert repeated == key
    assert not inserted
    claimed = store.claim()
    store.finish(claimed)
    assert store.put(event()) == (key, False)
    assert store.claim() is None
    with sqlite3.connect(store.path) as db:
        row = db.execute("SELECT status, body FROM webhook_inbox").fetchone()
    assert row == ("done", None)


def test_processing_receipt_is_reclaimed_after_crashed_worker_lease_expires(tmp_path, monkeypatch):
    now = 1000
    monkeypatch.setattr("app.bot.webhook_inbox.time.time", lambda: now)
    path = tmp_path / "inbox.sqlite3"
    original = WebhookInbox(path)
    original.put(event())
    old_claim = original.claim()
    reopened = WebhookInbox(path)
    assert reopened.claim() is None
    now += LEASE_SECONDS + 1
    fresh_claim = reopened.claim()
    assert fresh_claim["event_id"] == old_claim["event_id"]
    assert fresh_claim["claim_id"] != old_claim["claim_id"]
    assert fresh_claim["attempts"] == 2
    # A late completion from the old worker cannot overwrite the newer claim.
    original.finish(old_claim)
    assert reopened.claim() is None
    reopened.finish(fresh_claim)
    assert reopened.claim() is None


def test_same_user_callbacks_wait_for_link_processing_and_delayed_retries(tmp_path, monkeypatch):
    now = 1000
    monkeypatch.setattr("app.bot.webhook_inbox.time.time", lambda: now)
    store = WebhookInbox(tmp_path / "inbox.sqlite3")
    first_id, _ = store.put(event())
    now += 1
    store.put(event(timestamp=2))
    now += 1
    other_id, _ = store.put(event(user_id=2, timestamp=3))
    first = store.claim()
    assert first["event_id"] == first_id
    other = store.claim()
    assert other["event_id"] == other_id
    assert store.claim() is None
    store.finish(first, error_type="ConnectionError")
    assert store.claim() is None
    now += 2
    retry = store.claim()
    assert retry["event_id"] == first_id
    store.finish(retry)
    next_for_first_user = store.claim()
    assert next_for_first_user["update"]["timestamp"] == 2


def test_two_workers_do_not_claim_same_receipt(tmp_path):
    path = tmp_path / "inbox.sqlite3"
    left, right = WebhookInbox(path), WebhookInbox(path)
    left.put(event())
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda store: store.claim(), [left, right]))
    assert sum(claim is not None for claim in claims) == 1


def test_terminal_failure_discards_private_body_and_keeps_reason(tmp_path, monkeypatch):
    now = 1000
    monkeypatch.setattr("app.bot.webhook_inbox.time.time", lambda: now)
    store = WebhookInbox(tmp_path / "inbox.sqlite3")
    store.put(event())
    for _ in range(MAX_ATTEMPTS):
        claimed = store.claim()
        status = store.finish(claimed, error_type="ConnectionError")
        now += 301
    assert status == "failed"
    with sqlite3.connect(store.path) as db:
        row = db.execute("SELECT status, body, error_type FROM webhook_inbox").fetchone()
    assert row == ("failed", None, "ConnectionError")
    assert store.claim() is None


def test_private_store_permissions(tmp_path):
    store = WebhookInbox(tmp_path / "private" / "inbox.sqlite3")
    if os.name != "nt":
        assert store.path.stat().st_mode & 0o777 == 0o600
        assert store.path.parent.stat().st_mode & 0o777 == 0o700


def test_capacity_rejects_new_receipts_but_accepts_duplicates(tmp_path):
    store = WebhookInbox(tmp_path / "inbox.sqlite3", capacity=1)
    update = event()
    key, _ = store.put(update)
    with pytest.raises(WebhookInboxFull):
        store.put(event(timestamp=2))
    assert store.put(update) == (key, False)
    store.finish(store.claim())
    assert store.put(event(timestamp=2))[1]


def test_old_accepted_backlog_survives_retention_until_processed(tmp_path, monkeypatch):
    now = 1000
    monkeypatch.setattr("app.bot.webhook_inbox.time.time", lambda: now)
    store = WebhookInbox(tmp_path / "inbox.sqlite3")
    store.put(event())
    now += RETENTION_SECONDS + 1
    claimed = store.claim()
    assert claimed["update"] == event()
    store.finish(claimed)
    assert store.claim() is None
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT count(*) FROM webhook_inbox").fetchone()[0] == 0


def test_failed_receipt_raises_without_acknowledging_or_logging_private_payload(caplog):
    class UnavailableInbox:
        def put(self, update):
            raise sqlite3.OperationalError("private-token-that-must-not-be-logged")

    runtime = MaxWebhookRuntime.__new__(MaxWebhookRuntime)
    runtime._inbox = UnavailableInbox()
    runtime._wake = threading.Event()
    with pytest.raises(WebhookQueueFull):
        runtime.submit(event(payload="private-payload-that-must-not-be-logged"))
    assert not runtime._wake.is_set()
    assert "OperationalError" in caplog.text
    assert "private-token" not in caplog.text
    assert "private-payload" not in caplog.text
