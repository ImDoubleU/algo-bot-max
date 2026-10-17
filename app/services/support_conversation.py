"""Persist bot conversation routing separately from new-ticket drafts."""

from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.models.support import SupportConversation, SupportPhoto, SupportReply, SupportTicket


def conversation_response(ticket_id, text=None):
    return {"active": True, "stage": "conversation", "ticket_id": ticket_id,
            "text": text or (
                f"Обращение №{ticket_id}. Чтобы дополнить обращение, отправьте сообщение сюда. "
                "Можно приложить до 5 фотографий."
            )}


def incoming_key(user_id, event_id):
    return uuid5(NAMESPACE_URL, f"algo-max:support:{user_id}:{event_id}") if event_id else uuid4()


async def save_message_photos(db, user_id, urls, *, ticket_id=None):
    from app.services.support import (
        MAX_PHOTO_BYTES,
        _fetch_remote_bytes,
        add_photo,
        create_remote_product_image_client,
    )

    photo_ids = []
    if urls:
        async with create_remote_product_image_client() as client:
            for url in urls:
                if urlsplit(url).scheme != "https":
                    raise HTTPException(400, "Некорректная ссылка на фото MAX")
                content, _ = await _fetch_remote_bytes(client, url, max_bytes=MAX_PHOTO_BYTES)
                photo = await add_photo(db, user_id, content)
                photo.ticket_id = ticket_id
                photo_ids.append(str(photo.id))
    return photo_ids


async def append_message(db, ticket, payload):
    key = incoming_key(ticket.max_user_id, payload.get("event_id"))
    existing = await db.scalar(select(SupportReply).where(SupportReply.request_id == key))
    if existing:
        return
    text = payload.get("text", "").strip()
    urls = payload.get("photo_urls", [])
    saved_ids = payload.get("photo_ids", [])
    if not text and not urls and not saved_ids:
        raise HTTPException(400, "Отправьте текст или фотографию")
    count = await db.scalar(select(func.count()).select_from(SupportReply).join(
        SupportTicket, SupportTicket.id == SupportReply.ticket_id,
    ).where(SupportTicket.max_user_id == ticket.max_user_id, SupportReply.author == "user",
            SupportReply.created_at >= datetime.now(UTC) - timedelta(hours=1)))
    if count >= 60:
        raise HTTPException(429, "Можно отправить до 60 сообщений в час. Попробуйте позже")
    photo_ids = await save_message_photos(db, ticket.max_user_id, urls, ticket_id=ticket.id)
    if saved_ids:
        photos = list(await db.scalars(select(SupportPhoto).where(
            SupportPhoto.id.in_([UUID(pid) for pid in saved_ids]),
            SupportPhoto.owner_max_user_id == ticket.max_user_id,
            SupportPhoto.ticket_id.is_(None),
        )))
        if len(photos) != len(saved_ids):
            raise HTTPException(400, "Фото дополнения устарело. Отправьте /menu, "
                                "затем откройте обращение и прикрепите сообщение и фото заново")
        for photo in photos:
            photo.ticket_id = ticket.id
        photo_ids.extend(saved_ids)
    received_at = (datetime.fromisoformat(payload["received_at"])
                   if payload.get("received_at") else datetime.now(UTC))
    db.add(SupportReply(request_id=key, ticket_id=ticket.id, message=text,
                        author="user", status="received", photo_ids=photo_ids,
                        created_at=received_at))
    ticket.status = "new"
    ticket.updated_at = datetime.now(UTC)
    await db.flush()


async def conversation_event(db, identity, payload):
    if payload.action == "exit":
        # Old MAX messages retain their buttons. Do not let them pause routing,
        # discard pending messages/photos, or cancel a new-ticket draft.
        return {"active": False, "text": "Закрыть обращение может только администратор. "
                "Для дополнения нажмите «Ответить по обращению» под ответом поддержки."}
    user_id = identity.max_user_id
    conversation = await db.get(SupportConversation, user_id)
    if payload.action in {"cancel", "start"}:
        if conversation is None:
            conversation = SupportConversation(max_user_id=user_id)
            db.add(conversation)
        pending_photo_ids = [UUID(pid) for message in conversation.pending_messages or []
                             for pid in message.get("photo_ids", [])]
        if pending_photo_ids:
            await db.execute(delete(SupportPhoto).where(
                SupportPhoto.id.in_(pending_photo_ids),
                SupportPhoto.owner_max_user_id == user_id, SupportPhoto.ticket_id.is_(None),
            ))
        conversation.ticket_id = None
        conversation.paused = True
        conversation.pending_messages = []
        return {"active": False, "text": "Вы вернулись в меню. Обращение сохранено. "
                "Продолжить можно кнопкой «Ответить по обращению» под ответом поддержки."}

    if payload.action not in {"reply", "choose", "message"}:
        return {"active": False}
    # MAX retries may arrive after another ticket has been selected or the dialog was exited.
    if payload.action == "message" and payload.event_id:
        existing = await db.scalar(select(SupportReply).where(
            SupportReply.request_id == incoming_key(user_id, payload.event_id)))
        if existing:
            return conversation_response(existing.ticket_id, "Это сообщение уже получено.")
    if conversation is None:
        conversation = SupportConversation(max_user_id=user_id, pending_messages=[], paused=False)
        db.add(conversation)
    if payload.action in {"reply", "choose"}:
        if payload.ticket_id is None:
            raise HTTPException(400, "Выберите обращение")
        ticket = await db.scalar(select(SupportTicket).where(
            SupportTicket.id == payload.ticket_id, SupportTicket.max_user_id == user_id,
        ).with_for_update())
        if ticket is None:
            raise HTTPException(404, "Обращение не найдено")
        conversation.ticket_id = ticket.id
        conversation.paused = False
        # This explicit button also permits continuing a previously closed ticket.
        if ticket.status == "resolved":
            ticket.status = "in_progress"
        pending = conversation.pending_messages
        for message in pending:
            await append_message(db, ticket, message)
        conversation.pending_messages = []
        return conversation_response(ticket.id, (
            f"Сообщения добавлены в обращение №{ticket.id}. Можно написать дополнение."
        ) if pending else None)
    if conversation.paused:
        return {"active": False}
    ticket = None
    if conversation.ticket_id:
        ticket = await db.scalar(select(SupportTicket).where(
            SupportTicket.id == conversation.ticket_id,
            SupportTicket.max_user_id == user_id,
        ).with_for_update())
        if ticket and ticket.status == "resolved":
            return {"active": True, "stage": "closed", "ticket_id": ticket.id,
                    "text": f"Обращение №{ticket.id} закрыто. Нажмите «Ответить по обращению» "
                    "и отправьте сообщение ещё раз, чтобы продолжить."}
    if ticket is None:
        tickets = list(await db.scalars(select(SupportTicket).where(
            SupportTicket.max_user_id == user_id,
            True if conversation.pending_messages else SupportTicket.status != "resolved",
            select(SupportReply.id).where(
                SupportReply.ticket_id == SupportTicket.id,
                SupportReply.author == "staff", SupportReply.status == "sent",
            ).exists(),
        ).order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())))
        if not tickets:
            return {"active": False}
        if len(tickets) > 1 or conversation.pending_messages:
            pending = conversation.pending_messages
            duplicate = payload.event_id and any(
                p.get("event_id") == payload.event_id for p in pending)
            if not duplicate:
                if len(pending) >= 5:
                    raise HTTPException(400, "Сначала выберите обращение. Новое сообщение "
                                        "не сохранено, отправьте его после выбора.")
                if not payload.text and not payload.photo_urls:
                    raise HTTPException(400, "Отправьте текст или фотографию")
                photo_ids = await save_message_photos(db, user_id, payload.photo_urls)
                conversation.pending_messages = [*pending, {
                    "text": payload.text, "event_id": payload.event_id,
                    "photo_ids": photo_ids, "received_at": datetime.now(UTC).isoformat(),
                }]
            return {"active": True, "stage": "choose", "tickets": [
                {"id": t.id, "label": f"№{t.id}: {t.message[:45]}"} for t in tickets],
                "text": "К какому обращению относится сообщение? "
                        "После выбора оно будет добавлено в переписку."}
        ticket = await db.scalar(select(SupportTicket).where(
            SupportTicket.id == tickets[0].id).with_for_update())
        conversation.ticket_id = ticket.id
    await append_message(db, ticket, payload.model_dump())
    return conversation_response(ticket.id, f"Сообщение добавлено в обращение №{ticket.id}. "
                                 "Можно написать дополнение.")
