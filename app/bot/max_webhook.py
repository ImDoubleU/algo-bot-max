from __future__ import annotations

import logging
import queue
import threading
from typing import Any

from app.bot.backend_client import AccessBackendClient
from app.bot.max_client import MaxApiClient
from app.bot.max_long_polling import LongPollingBot
from app.core.config import get_settings, is_placeholder

logger = logging.getLogger("algo_bot_max.webhook")
STOP = object()


class WebhookQueueFull(RuntimeError):
    pass


class MaxWebhookRuntime:
    """Processes MAX updates sequentially while the HTTP endpoint responds immediately."""

    def __init__(self) -> None:
        settings = get_settings()
        self._updates: queue.Queue[dict[str, Any] | object] = queue.Queue(
            maxsize=settings.max_webhook_queue_size
        )
        self._bot: LongPollingBot | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="max-webhook-worker",
            daemon=True,
        )
        self._thread.start()

    def submit(self, update: dict[str, Any]) -> None:
        try:
            self._updates.put_nowait(update)
        except queue.Full as exc:
            raise WebhookQueueFull("MAX webhook queue is full") from exc

    def close(self) -> None:
        try:
            self._updates.put_nowait(STOP)
        except queue.Full:
            logger.warning("Webhook worker queue is full during shutdown")
            return
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
        while True:
            update = self._updates.get()
            try:
                if update is STOP:
                    return
                if self._bot is None:
                    self._bot = self._build_bot()
                    logger.info("MAX webhook worker initialized")
                self._bot.handle_update(update)
            except Exception:
                logger.exception("MAX webhook update processing failed")
                self._bot = None
            finally:
                self._updates.task_done()


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
