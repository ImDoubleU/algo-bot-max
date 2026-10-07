"""Safe activity metadata; business changes retain their existing domain audits."""

import asyncio
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings, is_local_environment
from app.models.account import MaxAccount
from app.models.audit import AuditLog
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)
OPERATIONS = {
    "session": "Проверка входа в личный кабинет",
    "catalog": "Просмотр магазина",
    "students": "Просмотр или изменение ученика",
    "orders": "Действие с заказом",
    "cart": "Действие с корзиной",
    "bank": "Действие в банке",
    "feedback": "Действие в обратной связи",
    "staff": "Действие с сотрудником",
    "warehouses": "Действие со складом",
    "products": "Действие с товаром",
    "broadcasts": "Действие с рассылкой",
    "support": "Действие в поддержке",
    "access": "Проверка или создание привязки",
    "admin": "Работа с управлением",
}


async def persist_event(
    *, action, event_id=None, user_id=None, tenant_slug=None, payload=None, at=None, ip_address=None
):
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        if event_id and await db.get(AuditLog, event_id):
            return
        account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == user_id))
        tenant = (
            await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
            if tenant_slug
            else None
        )
        db.add(
            AuditLog(
                id=event_id or uuid4(),
                action=action,
                tenant_id=tenant.id if tenant else None,
                actor_account_id=account.id if account else None,
                entity_type="activity",
                payload={"max_user_id": user_id, **(payload or {})},
                ip_address=ip_address,
                created_at=at or datetime.now(UTC),
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if not event_id or not await db.get(AuditLog, event_id):
                raise


async def persist_request(request, *, request_id, status, elapsed_ms, error_type=None):
    if is_local_environment(get_settings().app_env):
        return
    path = request.url.path
    if path.endswith(("/admin/history", "/activity")) or path.endswith("/actions"):
        return
    reason = getattr(request.state, "audit_reason", None)
    outcome = "error" if status >= 500 else "denied" if status >= 400 or reason else "success"
    if reason == "granted":
        reason, outcome = None, "success"
    parts = path.split("/")
    operation = next(
        (OPERATIONS[part] for part in parts if part in OPERATIONS), "Действие в приложении"
    )
    actor_id = getattr(request.state, "audit_verified_max_user_id", None)
    requested = request.query_params.get("max_user_id", "")
    requested_id = int(requested) if requested.isdigit() and len(requested) < 19 else None
    tenant = getattr(request.state, "audit_tenant_slug", None) or request.query_params.get(
        "tenant_slug"
    )
    try:
        await persist_event(
            action="activity.request",
            user_id=actor_id,
            tenant_slug=tenant,
            ip_address=request.client.host if request.client else None,
            payload={
                "request_id": request_id,
                "operation": operation,
                "method": request.method,
                "path": path,
                "http_status": status,
                "elapsed_ms": elapsed_ms,
                "outcome": outcome,
                "reason": reason,
                "detail": getattr(request.state, "audit_detail", None),
                "requested_max_user_id": requested_id,
                "error_type": error_type,
            },
        )
    except Exception as exc:
        logger.error(
            "activity_audit_save_failed request_id=%s error_type=%s", request_id, type(exc).__name__
        )


def inbox_metadata(path):
    if not path.exists():
        return []
    with sqlite3.connect("file:" + str(path) + "?mode=ro", uri=True) as db:
        return db.execute(
            "SELECT event_id,update_type,max_user_id,status,attempts,created_at,error_type "
            "FROM webhook_inbox WHERE status IN ('done','failed') AND audit_exported=0 "
            "ORDER BY rowid LIMIT 200"
        ).fetchall()


def mark_exported(path, key):
    with sqlite3.connect(path, timeout=5) as db:
        db.execute("UPDATE webhook_inbox SET audit_exported=1 WHERE event_id=?", (key,))


async def bot_audit_loop():
    import os

    path = Path(os.getenv("MAX_WEBHOOK_INBOX_PATH", "/opt/algo-max/storage/bot/webhook.sqlite3"))
    seen = set()
    while True:
        try:
            rows = await asyncio.to_thread(inbox_metadata, path)
            for key, kind, user_id, status, attempts, created_at, error_type in rows:
                if key in seen:
                    continue
                await persist_event(
                    action="bot.interaction",
                    event_id=uuid5(NAMESPACE_URL, "max-update:" + key),
                    user_id=user_id,
                    at=datetime.fromtimestamp(created_at, UTC),
                    payload={
                        "webhook_event_id": key,
                        "update_type": kind,
                        "operation": {
                            "bot_started": "Открытие бота по ссылке",
                            "bot_stopped": "Остановка бота",
                            "message_callback": "Нажатие кнопки в боте",
                            "message_created": "Сообщение боту",
                        }.get(kind, "Событие MAX"),
                        "outcome": "success" if status == "done" else "error",
                        "attempts": attempts,
                        "error_type": error_type,
                    },
                )
                await asyncio.to_thread(mark_exported, path, key)
                seen.add(key)
            if len(seen) > 5000:
                seen = {row[0] for row in rows}
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("bot_audit_bridge_failed error_type=%s", type(exc).__name__)
        await asyncio.sleep(3)
