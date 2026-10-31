from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_miniapp_identity, require_matching_miniapp_identity
from app.core.config import get_settings
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.schemas.pizza import PizzaAction, PizzaCampaignCreate, PizzaContribute, PizzaOfferCreate
from app.services import pizza

router = APIRouter()


async def context(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    identity: Annotated[MiniAppIdentity | None, Depends(get_miniapp_identity)],
    tenant_slug: str = Query(min_length=1, max_length=120),
):
    if not get_settings().group_collections_enabled:
        raise HTTPException(404, "Раздел пока недоступен")
    if identity is None:
        raise HTTPException(401, "Откройте приложение из MAX")
    require_matching_miniapp_identity(
        identity, max_user_id=identity.max_user_id, tenant_slug=tenant_slug
    )
    try:
        actor = await pizza.actor_for(db, identity.max_user_id, tenant_slug)
        # Expiration is committed independently of a subsequent rejected operation.
        await pizza.expire_campaigns(db)
        await db.commit()
        yield db, actor
    except pizza.PizzaError as exc:
        await db.rollback()
        raise HTTPException(exc.code, str(exc)) from exc
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Сбор уже изменился. Обновите страницу") from exc


Context = Annotated[tuple, Depends(context)]


@router.get("")
async def read_board(ctx: Context, student_id: UUID | None = None):
    db, actor = ctx
    return await pizza.board(db, actor, student_id=student_id)


@router.post("/offers", status_code=201)
async def offer_create(payload: PizzaOfferCreate, ctx: Context):
    db, actor = ctx
    offer = await pizza.create_offer(db, actor, payload)
    await db.commit()
    return {"id": str(offer.id)}


@router.post("/campaigns", status_code=201)
async def campaign_create(payload: PizzaCampaignCreate, ctx: Context):
    db, actor = ctx
    campaign = await pizza.create_campaign(db, actor, payload)
    await db.commit()
    return {"id": str(campaign.id)}


@router.post("/campaigns/{campaign_id}/contribute")
async def campaign_contribute(campaign_id: UUID, payload: PizzaContribute, ctx: Context):
    db, actor = ctx
    campaign = await pizza.contribute(db, actor, campaign_id, payload.student_id)
    await db.commit()
    return {"id": str(campaign.id), "status": campaign.status}


@router.post("/campaigns/{campaign_id}/action")
async def campaign_update(campaign_id: UUID, payload: PizzaAction, ctx: Context):
    db, actor = ctx
    campaign = await pizza.campaign_action(db, actor, campaign_id, payload.action)
    await db.commit()
    return {"id": str(campaign.id), "status": campaign.status}
