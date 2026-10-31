import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from app.bot.keyboards import build_miniapp_url, inline_keyboard, miniapp_button
from app.bot.max_client import MaxApiClient
from app.core.config import get_settings, is_placeholder
from app.models.account import MaxAccount
from app.models.enums import StaffRole
from app.models.pizza import PizzaCampaign, PizzaContribution, PizzaNotice
from app.models.tenant import Tenant
from app.services import pizza
from app.services.access import get_effective_customer_access_link

logger = logging.getLogger(__name__)


async def recipient_allowed(db, notice, campaign, account, now):
    if notice.event == "opened":
        return (
            campaign.status == "open"
            and pizza.utc(campaign.deadline) > now
            and account.id in await pizza.connected_recipients(db, campaign)
        )
    if notice.event in ("funded", "paid"):
        if campaign.status != notice.event:
            return False
        actor = await pizza.actor_for(
            db, account.max_user_id, (await db.get(Tenant, campaign.tenant_id)).slug
        )
        return (campaign.teacher_id == account.id and StaffRole.TEACHER in actor.roles) or (
            notice.event == "funded" and await pizza.director_can_manage(db, actor, campaign)
        )
    if notice.event == "refund":
        rows = list(
            await db.scalars(
                select(PizzaContribution).where(
                    PizzaContribution.campaign_id == campaign.id,
                    PizzaContribution.account_id == account.id,
                    PizzaContribution.refunded_at.is_not(None),
                )
            )
        )
        return any(
            [
                await get_effective_customer_access_link(
                    db,
                    tenant_id=campaign.tenant_id,
                    account_id=account.id,
                    student_id=row.student_id,
                )
                for row in rows
            ]
        )
    return False


async def deliver_next(db, client, *, now=None):
    now = now or datetime.now(UTC)
    item = await db.scalar(
        select(PizzaNotice)
        .where(
            PizzaNotice.sent_at.is_(None),
            PizzaNotice.cancelled_at.is_(None),
            or_(PizzaNotice.next_attempt_at.is_(None), PizzaNotice.next_attempt_at <= now),
        )
        .order_by(PizzaNotice.created_at, PizzaNotice.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if item is None:
        return False
    campaign = await db.get(PizzaCampaign, item.campaign_id)
    account = await db.get(MaxAccount, item.account_id)
    if not campaign or not account or not await recipient_allowed(db, item, campaign, account, now):
        item.cancelled_at = now
        await db.commit()
        return True
    item.attempts += 1
    item.attempted_at = now
    if item.event == "opened":
        names = (await pizza.connected_recipients(db, campaign))[account.id]
        item.message = pizza.opened_notice_text(campaign, names)
    try:
        await asyncio.to_thread(
            client.send_message,
            user_id=account.max_user_id,
            text=item.message,
            attachments=inline_keyboard(
                [[miniapp_button("Открыть Algo MAX", build_miniapp_url())]]
            ),
        )
        item.sent_at = now
        item.last_error = None
        logger.info(
            "Collection notice delivered notice=%s recipient=%s event=%s",
            item.id,
            account.max_user_id,
            item.event,
        )
    except Exception as exc:
        item.last_error = type(exc).__name__[:120]
        item.next_attempt_at = now + timedelta(seconds=min(1800, 10 * 2 ** min(item.attempts, 8)))
        logger.warning(
            "Collection notice retry notice=%s recipient=%s error=%s",
            item.id,
            account.max_user_id,
            item.last_error,
        )
    await db.commit()
    return True


async def collection_loop():
    from app.db.session import AsyncSessionLocal

    settings = get_settings()
    client = (
        MaxApiClient(
            settings.max_bot_token,
            settings.max_api_base,
            timeout_seconds=settings.max_api_timeout_seconds,
        )
        if (
            settings.group_collection_notifications_enabled
            and not is_placeholder(settings.max_bot_token)
        )
        else None
    )
    logger.info("Group collection worker started; delivery=%s", bool(client))
    while True:
        handled = False
        try:
            async with AsyncSessionLocal() as db:
                await pizza.expire_campaigns(db)
                await db.commit()
            if client:
                async with AsyncSessionLocal() as db:
                    handled = await deliver_next(db, client)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Group collection worker failed")
        await asyncio.sleep(0.2 if handled else 5)
