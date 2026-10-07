from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.api.dependencies import get_miniapp_identity, require_matching_miniapp_identity
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.support import SupportPhoto, SupportReply, SupportTicket
from app.schemas.support import (
    SupportBotEvent,
    SupportCreate,
    SupportReplyCreate,
    SupportStatus,
    SupportUpdate,
)
from app.services.product_media import ProductMediaError
from app.services.staff import configured_superadmin_max_user_id
from app.services.support import (
    MAX_PHOTO_BYTES,
    add_photo,
    bot_event,
    create_ticket,
    lock_user,
    require_owner,
)

router = APIRouter()
Db = Annotated[AsyncSession, Depends(get_db_session)]


async def verified_identity(
    identity: Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)],
) -> MiniAppIdentity:
    if identity is None:
        raise HTTPException(401, "Откройте приложение из MAX")
    return identity


Identity = Annotated[MiniAppIdentity, Depends(verified_identity)]


def public_reply(reply: SupportReply) -> dict:
    return {"id": str(reply.id), "message": reply.message, "status": reply.status,
            "created_at": reply.created_at, "sent_at": reply.sent_at}


def public_ticket(ticket: SupportTicket, photo_ids: list, replies: list) -> dict:
    return {
        "id": ticket.id, "max_user_id": str(ticket.max_user_id),
        "tenant_slug": ticket.tenant_slug, "role": ticket.role,
        "first_name": ticket.first_name, "last_name": ticket.last_name,
        "message": ticket.message, "source": ticket.source, "status": ticket.status,
        "private_note": ticket.private_note, "created_at": ticket.created_at,
        "updated_at": ticket.updated_at, "photo_ids": [str(p) for p in photo_ids],
        "notification_sent": ticket.notified_at is not None,
        "replies": [public_reply(reply) for reply in replies],
    }


@router.get("/context")
async def context(identity: Identity, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return {"inbox_enabled": identity.max_user_id == configured_superadmin_max_user_id()}


@router.post("/photos", status_code=201)
async def upload_photo(db: Db, identity: Identity, photo: Annotated[UploadFile, File()]):
    try:
        content = await photo.read(MAX_PHOTO_BYTES + 1)
        await lock_user(db, identity.max_user_id)
        saved = await add_photo(db, identity.max_user_id, content)
        await db.commit()
        return {"id": str(saved.id)}
    except ProductMediaError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await photo.close()


@router.delete("/photos/{photo_id}", status_code=204)
async def remove_photo(photo_id: UUID, db: Db, identity: Identity):
    await lock_user(db, identity.max_user_id)
    photo = await db.get(SupportPhoto, photo_id)
    if photo is None or photo.owner_max_user_id != identity.max_user_id:
        raise HTTPException(404, "Фото не найдено")
    if photo.ticket_id is not None:
        raise HTTPException(409, "Фото уже отправлено в заявке")
    await db.delete(photo)
    await db.commit()


@router.get("/photos/{photo_id}")
async def read_photo(photo_id: UUID, db: Db, identity: Identity):
    photo = await db.scalar(select(SupportPhoto).where(SupportPhoto.id == photo_id))
    if photo is None or (
        photo.owner_max_user_id != identity.max_user_id and
        identity.max_user_id != configured_superadmin_max_user_id()
    ):
        raise HTTPException(404, "Фото не найдено")
    photo = await db.scalar(select(SupportPhoto).where(SupportPhoto.id == photo_id)
                            .options(undefer(SupportPhoto.content)))
    return Response(photo.content, media_type="image/webp", headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    })


@router.post("/tickets", status_code=201)
async def submit_ticket(payload: SupportCreate, db: Db, identity: Identity):
    ticket = await create_ticket(db, identity.max_user_id, payload,
                                 tenant_slug=identity.tenant_slug, source="miniapp")
    await db.commit()
    return {"id": ticket.id, "status": ticket.status}


@router.get("/tickets")
async def inbox(
    db: Db, identity: Identity, response: Response,
    status: SupportStatus | None = None, search: str = Query(default="", max_length=100),
    offset: int = Query(default=0, ge=0), limit: int = Query(default=30, ge=1, le=100),
):
    require_owner(identity.max_user_id)
    response.headers["Cache-Control"] = "private, no-store"
    filters = []
    if status:
        filters.append(SupportTicket.status == status)
    if search.strip():
        value = search.strip()
        filters.append(or_(SupportTicket.first_name.icontains(value, autoescape=True),
                           SupportTicket.last_name.icontains(value, autoescape=True),
                           SupportTicket.message.icontains(value, autoescape=True)))
    total = await db.scalar(select(func.count()).select_from(SupportTicket).where(*filters))
    tickets = list((await db.scalars(select(SupportTicket).where(*filters)
                                    .order_by(SupportTicket.id.desc())
                                    .offset(offset).limit(limit))).all())
    photos = (await db.execute(select(SupportPhoto.ticket_id, SupportPhoto.id)
                              .where(SupportPhoto.ticket_id.in_([t.id for t in tickets])))).all()
    counters = dict((await db.execute(select(SupportTicket.status, func.count())
                                     .group_by(SupportTicket.status))).all())
    replies = list((await db.scalars(select(SupportReply).where(
        SupportReply.ticket_id.in_([t.id for t in tickets])
    ).order_by(SupportReply.created_at, SupportReply.id))).all())
    return {"items": [public_ticket(t, [p for tid, p in photos if tid == t.id],
                                    [r for r in replies if r.ticket_id == t.id]) for t in tickets],
            "total": total, "counts": counters}


@router.post("/tickets/{ticket_id}/replies", status_code=202)
async def reply_to_ticket(ticket_id: int, payload: SupportReplyCreate, db: Db, identity: Identity):
    require_owner(identity.max_user_id)
    ticket = await db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id)
                             .with_for_update())
    if ticket is None:
        raise HTTPException(404, "Заявка не найдена")
    existing = await db.scalar(select(SupportReply).where(
        SupportReply.request_id == payload.request_id
    ))
    if existing:
        if existing.ticket_id != ticket_id:
            raise HTTPException(409, "Этот ответ относится к другой заявке")
        if existing.message != payload.message:
            raise HTTPException(409, "Ответ уже создан с другим текстом. Обновите заявку")
        return public_reply(existing)
    pending = await db.scalar(select(SupportReply.id).where(
        SupportReply.ticket_id == ticket_id, SupportReply.status.in_(["queued", "retry"])
    ).limit(1))
    if pending:
        raise HTTPException(409, "Предыдущий ответ ещё отправляется")
    reply = SupportReply(request_id=payload.request_id, ticket_id=ticket.id,
                         message=payload.message)
    db.add(reply)
    ticket.status = "in_progress"
    await db.commit()
    return public_reply(reply)


@router.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id: int, payload: SupportUpdate, db: Db, identity: Identity):
    require_owner(identity.max_user_id)
    ticket = await db.scalar(select(SupportTicket).where(SupportTicket.id == ticket_id)
                             .with_for_update())
    if ticket is None:
        raise HTTPException(404, "Заявка не найдена")
    ticket.status = payload.status
    ticket.private_note = payload.private_note
    await db.commit()
    return {"id": ticket.id, "status": ticket.status}


@router.post("/bot-event")
async def handle_bot_event(payload: SupportBotEvent, db: Db, identity: Identity):
    require_matching_miniapp_identity(identity, max_user_id=payload.max_user_id,
                                     tenant_slug=payload.tenant_slug)
    try:
        result = await bot_event(db, identity, payload)
        await db.commit()
        return result
    except ProductMediaError as exc:
        raise HTTPException(400, str(exc)) from exc
