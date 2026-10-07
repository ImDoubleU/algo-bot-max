from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import HTTPException
from PIL import Image
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import build_miniapp_url, inline_keyboard, miniapp_button
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder
from app.models.support import SupportDraft, SupportPhoto, SupportReply, SupportTicket
from app.schemas.support import SupportCreate, clean_name
from app.services.product_media import (
    ProductMediaError,
    _decoded_product_image,
    _fetch_remote_bytes,
    create_remote_product_image_client,
)
from app.services.staff import configured_superadmin_max_user_id

logger = logging.getLogger(__name__)
ROLE_LABELS = {"parent": "Родитель", "student": "Ученик", "staff": "Сотрудник"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024


def require_owner(max_user_id: int) -> None:
    if max_user_id != configured_superadmin_max_user_id():
        raise HTTPException(403, "Тикеты доступны только владельцу системы")


async def lock_user(db: AsyncSession, max_user_id: int) -> None:
    if db.bind.dialect.name == "postgresql":
        # Serialize uploads and submissions for one identity across API workers.
        await db.execute(select(func.pg_advisory_xact_lock(-max_user_id)))


def encode_photo(content: bytes) -> bytes:
    if len(content) > MAX_PHOTO_BYTES:
        raise ProductMediaError("Фото должно быть не больше 10 МБ")
    image = _decoded_product_image(content, subject="Фото")
    image.thumbnail((2200, 2200), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, "WEBP", quality=88, method=4)
    return output.getvalue()


async def add_photo(db: AsyncSession, max_user_id: int, content: bytes) -> SupportPhoto:
    count = await db.scalar(select(func.count()).select_from(SupportPhoto).where(
        SupportPhoto.owner_max_user_id == max_user_id, SupportPhoto.ticket_id.is_(None)
    ))
    if count >= 10:
        raise HTTPException(429, "Слишком много незавершённых загрузок фото")
    encoded = await asyncio.to_thread(encode_photo, content)
    photo = SupportPhoto(owner_max_user_id=max_user_id, content=encoded)
    db.add(photo)
    await db.flush()
    return photo


async def create_ticket(
    db: AsyncSession, max_user_id: int, payload: SupportCreate,
    *, tenant_slug: str | None, source: str,
) -> SupportTicket:
    await lock_user(db, max_user_id)
    existing = await db.scalar(select(SupportTicket).where(
        SupportTicket.request_id == payload.request_id
    ))
    if existing:
        if existing.max_user_id != max_user_id:
            raise HTTPException(409, "Не удалось отправить заявку. Откройте новую форму")
        return existing
    count = await db.scalar(select(func.count()).select_from(SupportTicket).where(
        SupportTicket.max_user_id == max_user_id,
        SupportTicket.created_at >= datetime.now(UTC) - timedelta(hours=1),
    ))
    if count >= 5:
        raise HTTPException(429, "Можно отправить до 5 заявок в час. Попробуйте позже")
    photos = list((await db.scalars(select(SupportPhoto).where(
        SupportPhoto.id.in_(payload.photo_ids),
        SupportPhoto.owner_max_user_id == max_user_id,
        SupportPhoto.ticket_id.is_(None),
    ))).all()) if payload.photo_ids else []
    if len(photos) != len(payload.photo_ids):
        raise HTTPException(400, "Одно из фото недоступно. Прикрепите его заново")
    ticket = SupportTicket(
        request_id=payload.request_id, max_user_id=max_user_id, tenant_slug=tenant_slug,
        role=payload.role, first_name=payload.first_name, last_name=payload.last_name,
        message=payload.message, source=source,
    )
    db.add(ticket)
    await db.flush()
    for photo in photos:
        photo.ticket_id = ticket.id
    return ticket


def draft_response(draft: SupportDraft | None) -> dict:
    if draft is None:
        return {"active": False}
    texts = {
        "role": "Кто сообщает о проблеме?",
        "full_name": "Напишите имя и фамилию одним сообщением. Например: Иван Петров.",
        "first_name": "Напишите имя и фамилию одним сообщением. Например: Иван Петров.",
        "last_name": "Напишите имя и фамилию одним сообщением. Например: Иван Петров.",
        "message": "Опишите проблему. К сообщению можно прикрепить фотографии.",
        "photos": (
            f"{draft.first_name} {draft.last_name}\n"
            f"{ROLE_LABELS.get(draft.role, '')}\n\n{draft.message}\n\n"
            f"Фотографий: {len(draft.photo_ids)} из 5.\n"
            "Можно добавить фото или отправить заявку."
        ),
    }
    return {"active": True, "stage": draft.stage, "text": texts[draft.stage]}


async def bot_event(db: AsyncSession, identity, payload) -> dict:
    await lock_user(db, identity.max_user_id)
    draft = await db.get(SupportDraft, identity.max_user_id)
    if draft and draft.stage in {"first_name", "last_name"}:
        draft.stage = "full_name"
    if payload.action == "start":
        if draft is None:
            draft = SupportDraft(max_user_id=identity.max_user_id, request_id=uuid4(), stage="role")
            db.add(draft)
            await db.flush()
        return draft_response(draft)
    if payload.action == "cancel":
        if draft:
            if draft.photo_ids:
                await db.execute(delete(SupportPhoto).where(
                    SupportPhoto.id.in_([UUID(p) for p in draft.photo_ids]),
                    SupportPhoto.ticket_id.is_(None),
                ))
            await db.delete(draft)
        return {"active": False, "text": "Заявка отменена."}
    if draft is None:
        return {"active": False, "text": "Нажмите «Сообщить о проблеме», чтобы создать заявку."}
    if payload.event_id and payload.event_id in draft.event_ids:
        return draft_response(draft)
    if payload.action == "role":
        if draft.stage != "role":
            return draft_response(draft)
        if payload.role is None:
            raise HTTPException(400, "Выберите роль")
        draft.role = payload.role
        draft.stage = "full_name"
    elif payload.action == "submit":
        if draft.stage != "photos":
            return draft_response(draft)
        ticket = await create_ticket(db, identity.max_user_id, SupportCreate(
            request_id=draft.request_id, role=draft.role, first_name=draft.first_name,
            last_name=draft.last_name, message=draft.message, photo_ids=draft.photo_ids,
        ), tenant_slug=identity.tenant_slug, source="bot")
        await db.delete(draft)
        return {"active": False, "ticket_id": ticket.id,
                "text": f"Заявка №{ticket.id} отправлена."}
    elif payload.action == "message":
        if draft.stage == "full_name":
            try:
                parts = payload.text.split()
                if len(parts) < 2:
                    raise ValueError("Напишите имя и фамилию одним сообщением")
                draft.first_name = clean_name(parts[0])
                draft.last_name = clean_name(" ".join(parts[1:]))
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            draft.stage = "message"
        elif draft.stage == "role":
            return draft_response(draft)
        else:
            if draft.stage == "message" and not payload.text:
                raise HTTPException(400, "Сначала напишите описание проблемы")
            if len(draft.photo_ids) + len(payload.photo_urls) > 5:
                raise HTTPException(400, "К заявке можно прикрепить до 5 фотографий")
            saved_ids = []
            if payload.photo_urls:
                async with create_remote_product_image_client() as client:
                    for url in payload.photo_urls:
                        parsed = urlsplit(url)
                        if parsed.scheme != "https":
                            raise HTTPException(400, "Некорректная ссылка на фото MAX")
                        content, _ = await _fetch_remote_bytes(
                            client, url, max_bytes=MAX_PHOTO_BYTES
                        )
                        photo = await add_photo(db, identity.max_user_id, content)
                        saved_ids.append(str(photo.id))
            if draft.stage == "message":
                draft.message = payload.text
            elif payload.text:
                updated = f"{draft.message}\n\n{payload.text}"
                if len(updated) > 4000:
                    raise HTTPException(400, "Описание должно быть не длиннее 4000 символов")
                draft.message = updated
            draft.photo_ids = [*draft.photo_ids, *saved_ids]
            draft.stage = "photos"
    if payload.event_id:
        draft.event_ids = [*draft.event_ids[-49:], payload.event_id]
    return draft_response(draft)


async def deliver_next_reply(db: AsyncSession, client: MaxApiClient) -> bool:
    now = datetime.now(UTC)
    eligible = (
        SupportReply.status.in_(["queued", "retry"]),
        (SupportReply.attempted_at.is_(None)) |
        (SupportReply.attempted_at < now - timedelta(minutes=2)),
    )
    # Lock the ticket first, as deletion and reply creation do, to avoid deadlocks.
    ticket = await db.scalar(select(SupportTicket).join(
        SupportReply, SupportReply.ticket_id == SupportTicket.id
    ).where(*eligible).order_by(SupportReply.created_at, SupportReply.id).limit(1)
        .with_for_update(of=SupportTicket, key_share=True, skip_locked=True))
    if ticket is None:
        return False
    reply = await db.scalar(select(SupportReply).where(
        SupportReply.ticket_id == ticket.id, *eligible,
    ).order_by(SupportReply.created_at, SupportReply.id).limit(1).with_for_update())
    if reply is None:
        return False
    reply.attempts += 1
    reply.attempted_at = now
    try:
        await asyncio.to_thread(client.send_message, user_id=ticket.max_user_id,
                                text=f"Ответ по заявке №{ticket.id}\n\n{reply.message}")
    except Exception:
        reply.status = "retry"
        logger.warning("Support reply delivery failed for reply %s", reply.id)
    else:
        reply.status = "sent"
        reply.sent_at = now
        ticket.status = "resolved"
    await db.commit()
    return True


async def notification_loop() -> None:
    from app.db.session import AsyncSessionLocal

    settings = get_settings()
    owner_id = configured_superadmin_max_user_id()
    client = MaxApiClient(settings.max_bot_token, settings.max_api_base,
                          timeout_seconds=settings.max_api_timeout_seconds)
    while True:
        ticket = None
        try:
            async with AsyncSessionLocal() as reply_db:
                replied = await deliver_next_reply(reply_db, client)
            if replied:
                await asyncio.sleep(1)
                continue
            async with AsyncSessionLocal() as db:
                now = datetime.now(UTC)
                ticket = await db.scalar(select(SupportTicket).where(
                    SupportTicket.notified_at.is_(None),
                    (SupportTicket.notification_attempted_at.is_(None)) |
                    (SupportTicket.notification_attempted_at < now - timedelta(minutes=2)),
                ).order_by(SupportTicket.id).limit(1).with_for_update(skip_locked=True))
                if ticket:
                    ticket.notification_attempts += 1
                    ticket.notification_attempted_at = now
                    text = (
                        f"Новая заявка №{ticket.id}\n"
                        f"{ROLE_LABELS[ticket.role]}: {ticket.first_name} {ticket.last_name}\n"
                        f"MAX ID: {ticket.max_user_id}\n\n{ticket.message[:1500]}\n\n"
                        "Тикеты: миниприложение → Помощь."
                    )
                    button = miniapp_button("Открыть тикеты", build_miniapp_url(view="help"))
                    try:
                        await asyncio.to_thread(client.send_message, user_id=owner_id,
                                                text=text, attachments=inline_keyboard([[button]]))
                        ticket.notified_at = now
                    except Exception:
                        logger.warning("Support notification failed for ticket %s", ticket.id)
                    await db.commit()
                else:
                    # Unsubmitted uploads expire; ticket images are never cleaned up here.
                    await db.execute(delete(SupportPhoto).where(
                        SupportPhoto.ticket_id.is_(None),
                        SupportPhoto.updated_at < now - timedelta(days=7),
                    ))
                    await db.execute(delete(SupportDraft).where(
                        SupportDraft.updated_at < now - timedelta(days=7),
                    ))
                    await db.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Support notification worker failed")
        await asyncio.sleep(1 if ticket else 15)


def notifications_enabled() -> bool:
    return bool(configured_superadmin_max_user_id()) and not is_placeholder(
        get_settings().max_bot_token
    )
