from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.bot.backend_client import AccessBackendClient
from app.bot.max_client import MaxApiClient
from app.bot.max_long_polling import LongPollingBot
from app.bot.runtime import MARKER_FILE
from app.bot.webhook_inbox import WebhookInbox, WebhookInboxFull
from app.core.config import get_settings, is_placeholder

logger = logging.getLogger("algo_bot_max.webhook")


class WebhookQueueFull(RuntimeError):
    pass


class MaxWebhookRuntime:
    """Acknowledge only committed receipts, then process private updates in order."""

    def __init__(self, inbox_path: Path | None = None) -> None:
        self._inbox = WebhookInbox(inbox_path or Path(os.getenv(
            "MAX_WEBHOOK_INBOX_PATH",
            str(MARKER_FILE.parent / "storage" / "bot" / "webhook.sqlite3"),
        )), capacity=get_settings().max_webhook_queue_size)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._bot: LongPollingBot | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="max-webhook-worker",
            daemon=True,
        )
        self._thread.start()

    def submit(self, update: dict[str, Any]) -> None:
        try:
            event_id, inserted = self._inbox.put(update)
        except (sqlite3.Error, OSError, WebhookInboxFull) as exc:
            logger.error("MAX webhook receipt failed error_type=%s", type(exc).__name__)
            raise WebhookQueueFull("MAX webhook receipt could not be saved") from exc
        # Log receipt before returning success; never log payloads or message bodies.
        payload = update.get("payload")
        payload_kind = next((prefix.rstrip("_") for prefix in
                             ("student_", "shop_", "cid_", "staff_")
                             if isinstance(payload, str) and payload.startswith(prefix)),
                            "other" if payload else "missing")
        user = (update.get("callback") or {}).get("user") or update.get("user") or (
            update.get("message") or {}
        ).get("sender") or {}
        raw_user_id = user.get("user_id") or update.get("user_id")
        raw_chat_id = update.get("chat_id") or (
            (update.get("message") or {}).get("recipient") or {}
        ).get("chat_id")
        try:
            user_id = int(raw_user_id)
        except (ValueError, TypeError):
            user_id = None
        try:
            chat_id = int(raw_chat_id)
        except (ValueError, TypeError):
            chat_id = None
        logger.info(
            "MAX webhook receipt event_id=%s update_type=%s inserted=%s "
            "payload_present=%s payload_kind=%s max_user_id=%s chat_id=%s",
            event_id, update.get("update_type"), inserted, bool(payload), payload_kind,
            user_id, chat_id,
        )
        self._wake.set()

    def close(self) -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=10)

    @staticmethod
    def _build_bot() -> LongPollingBot:
        settings = get_settings()
        token = settings.max_bot_token
        if is_placeholder(token):
            raise RuntimeError("MAX_BOT_TOKEN is not configured")
        client = MaxApiClient(
            str(token).strip(),
            api_base=settings.max_api_base,
            timeout_seconds=settings.max_api_timeout_seconds,
            poll_timeout_seconds=settings.max_poll_timeout_seconds,
        )
        backend_client = (
            AccessBackendClient(
                str(settings.max_backend_api_base),
                timeout_seconds=settings.max_backend_timeout_seconds,
            )
            if not is_placeholder(settings.max_backend_api_base)
            else None
        )
        return LongPollingBot(
            client,
            backend_client=backend_client,
            default_tenant_slug=settings.default_tenant_slug,
        )

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                event = self._inbox.claim()
            except (sqlite3.Error, OSError) as exc:
                logger.error("MAX webhook inbox unavailable error_type=%s", type(exc).__name__)
                self._stop.wait(1)
                continue
            if event is None:
                self._wake.wait(1)
                self._wake.clear()
                continue
            error_type = None
            try:
                if self._bot is None:
                    self._bot = self._build_bot()
                    logger.info("MAX webhook worker initialized")
                logger.info(
                    "MAX webhook processing event_id=%s update_type=%s max_user_id=%s attempt=%s",
                    event["event_id"], event["update_type"],
                    event["max_user_id"], event["attempts"],
                )
                self._bot.webhook_event_id = event["event_id"]
                self._bot.handle_update(event["update"])
            except Exception as exc:
                error_type = type(exc).__name__
                self._bot = None
            try:
                status = self._inbox.finish(event, error_type=error_type)
            except (sqlite3.Error, OSError) as exc:
                logger.error("MAX webhook completion not saved event_id=%s error_type=%s",
                             event["event_id"], type(exc).__name__)
                continue
            logger.info(
                "MAX webhook processed event_id=%s status=%s error_type=%s attempt=%s",
                event["event_id"], status, error_type, event["attempts"],
            )


_runtime: MaxWebhookRuntime | None = None
_runtime_lock = threading.Lock()


def get_webhook_runtime() -> MaxWebhookRuntime:
    global _runtime
    if _runtime is None:
        with _runtime_lock:
            if _runtime is None:
                _runtime = MaxWebhookRuntime()
    return _runtime


def close_webhook_runtime() -> None:
    global _runtime
    with _runtime_lock:
        runtime = _runtime
        _runtime = None
    if runtime is not None:
        runtime.close()
