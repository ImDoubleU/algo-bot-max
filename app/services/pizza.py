from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.audit import AuditLog
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    StaffRole,
    StudentAccessRole,
    StudentAccessStatus,
    StudentStatus,
)
from app.models.pizza import PizzaCampaign, PizzaContribution, PizzaNotice, PizzaOffer
from app.models.student import AstrocoinLedgerEntry, Student, StudentAccessLink, Wallet
from app.models.tenant import Tenant
from app.schemas.pizza import PizzaCampaignCreate, PizzaOfferCreate, PizzaOfferEdit
from app.services.access import get_effective_customer_access_link
from app.services.staff import (
    active_staff_roles_for_tenant,
    staff_names_match,
    staff_venue_scope_ids,
    teacher_staff_name,
)
from app.services.student_access_policy import student_access_window


class PizzaError(ValueError):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.code = code


@dataclass
class PizzaActor:
    tenant: Tenant
    account: MaxAccount
    roles: set

    @property
    def director(self):
        return bool(self.roles & {StaffRole.SUPERADMIN, StaffRole.PARTNER_DIRECTOR})


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def actor_for(db, max_user_id, tenant_slug):
    tenant = await db.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
    account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_user_id))
    if tenant is None or account is None:
        raise PizzaError("Откройте приложение из своего аккаунта MAX", 403)
    roles = await active_staff_roles_for_tenant(db, tenant_id=tenant.id, account_id=account.id)
    return PizzaActor(tenant, account, roles)


async def teacher_students(db, actor):
    if not (actor.director or StaffRole.TEACHER in actor.roles):
        return []
    students = list(
        await db.scalars(
            select(Student)
            .where(
                Student.tenant_id == actor.tenant.id,
                Student.status == StudentStatus.ACTIVE,
            )
            .order_by(Student.last_name, Student.first_name)
        )
    )
    if actor.director:
        if StaffRole.SUPERADMIN in actor.roles:
            return students
        scope = await staff_venue_scope_ids(
            db,
            tenant_id=actor.tenant.id,
            account_id=actor.account.id,
            role=StaffRole.PARTNER_DIRECTOR,
        )
        return [s for s in students if scope is None or s.venue_id in scope]
    return [
        s for s in students if staff_names_match(teacher_staff_name(actor.account), s.teacher_name)
    ]


async def own_student(db, actor, student_id, *, spending=False):
    student = await db.get(Student, student_id)
    if student is None or student.tenant_id != actor.tenant.id:
        raise PizzaError("Ученик не найден", 404)
    link = await get_effective_customer_access_link(
        db,
        tenant_id=actor.tenant.id,
        account_id=actor.account.id,
        student_id=student.id,
        required_role=StudentAccessRole.STUDENT if spending else None,
    )
    if link is None:
        raise PizzaError(
            "Взнос может внести только ученик из своего кабинета"
            if spending
            else "Нет доступа к этому ученику",
            403,
        )
    window = student_access_window(student, actor.tenant)
    if not window.allowed or window.paused or student.status != StudentStatus.ACTIVE:
        raise PizzaError("Участие доступно после подключения профиля и родителя", 403)
    return student


def audit(db, actor, campaign, event, **payload):
    db.add(
        AuditLog(
            tenant_id=campaign.tenant_id,
            actor_account_id=actor.account.id if actor else None,
            action="pizza." + event,
            entity_type="pizza_campaign",
            entity_id=str(campaign.id),
            payload={"group": campaign.group_name, **payload},
        )
    )


async def notice(db, campaign, account_id, event, message):
    exists = await db.scalar(
        select(PizzaNotice.id).where(
            PizzaNotice.campaign_id == campaign.id,
            PizzaNotice.account_id == account_id,
            PizzaNotice.event == event,
        )
    )
    if exists is None:
        db.add(
            PizzaNotice(
                campaign_id=campaign.id, account_id=account_id, event=event, message=message
            )
        )


async def director_can_manage(db, actor, campaign):
    if not actor.director or campaign.tenant_id != actor.tenant.id:
        return False
    if StaffRole.SUPERADMIN in actor.roles:
        return True
    scope = await staff_venue_scope_ids(
        db,
        tenant_id=actor.tenant.id,
        account_id=actor.account.id,
        role=StaffRole.PARTNER_DIRECTOR,
    )
    if scope is None:
        return True
    for row in campaign.roster:
        if "venue_id" in row:
            venue_id = UUID(row["venue_id"]) if row["venue_id"] else None
        else:
            student = await db.get(Student, UUID(row["id"]))
            venue_id = student.venue_id if student else None
        if venue_id not in scope:
            return False
    return True


async def notify_funded(db, campaign):
    directors = set(
        await db.scalars(
            select(StaffRoleAssignment.account_id).where(
                StaffRoleAssignment.tenant_id == campaign.tenant_id,
                StaffRoleAssignment.status == AssignmentStatus.ACTIVE,
                StaffRoleAssignment.role.in_([StaffRole.PARTNER_DIRECTOR, StaffRole.SUPERADMIN]),
            )
        )
    )
    for account_id in directors | {campaign.teacher_id}:
        if account_id != campaign.teacher_id:
            tenant = await db.get(Tenant, campaign.tenant_id)
            roles = await active_staff_roles_for_tenant(
                db, tenant_id=tenant.id, account_id=account_id
            )
            account = await db.get(MaxAccount, account_id)
            if not await director_can_manage(db, PizzaActor(tenant, account, roles), campaign):
                continue
        await notice(
            db,
            campaign,
            account_id,
            "funded",
            f"Сбор «{campaign.title}» закрыт: {campaign.collected} AC. "
            f"Группа: {campaign.group_name}. Можно организовать заказ.",
        )


async def connected_recipients(db, campaign):
    links = list(
        await db.scalars(
            select(StudentAccessLink)
            .join(Student, Student.id == StudentAccessLink.student_id)
            .where(
                StudentAccessLink.tenant_id == campaign.tenant_id,
                StudentAccessLink.student_id.in_([UUID(row["id"]) for row in campaign.roster]),
                StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                Student.status == StudentStatus.ACTIVE,
                Student.group_name == campaign.group_name,
            )
        )
    )
    recipients = {}
    names = {row["id"]: row["name"] for row in campaign.roster}
    for link in links:
        if link.role == StudentAccessRole.STUDENT and not await get_effective_customer_access_link(
            db,
            tenant_id=campaign.tenant_id,
            account_id=link.account_id,
            student_id=link.student_id,
            required_role=StudentAccessRole.STUDENT,
        ):
            continue
        recipients.setdefault(link.account_id, set()).add(names[str(link.student_id)])
    return recipients


def opened_notice_text(campaign, names):
    deadline = (
        utc(campaign.deadline).astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")
    )
    students = ", ".join(sorted(names))
    if len(students) > 180:
        students = students[:177] + "…"
    return (
        f"В группе начался сбор: {campaign.title}\n\n"
        f"Группа: {campaign.group_name}\nУченики: {students}\n"
        f"Взнос с ученика: {campaign.share} AC\nСобрать до: {deadline} МСК\n\n"
        "Сбор находится в миниприложении, в разделе «Магазин»."
    )[:700]


async def notify_opened(db, campaign):
    for account_id, names in (await connected_recipients(db, campaign)).items():
        await notice(db, campaign, account_id, "opened", opened_notice_text(campaign, names))


async def create_offer(db, actor, payload: PizzaOfferCreate):
    if not actor.director:
        raise PizzaError("Варианты сбора создаёт директор", 403)
    offer = PizzaOffer(
        tenant_id=actor.tenant.id, created_by=actor.account.id, **payload.model_dump()
    )
    db.add(offer)
    await db.flush()
    return offer


async def editable_offer(db, actor, offer_id, revision):
    if not actor.director:
        raise PizzaError("Варианты сбора изменяет директор", 403)
    offer = await db.scalar(
        select(PizzaOffer)
        .where(
            PizzaOffer.id == offer_id,
            PizzaOffer.tenant_id == actor.tenant.id,
            PizzaOffer.active.is_(True),
        )
        .with_for_update()
    )
    if offer is None:
        raise PizzaError("Вариант уже удалён или недоступен", 404)
    if offer.revision != revision:
        raise PizzaError("Вариант изменён в другом окне. Обновите список и повторите", 409)
    return offer


async def edit_offer(db, actor, offer_id, payload: PizzaOfferEdit):
    offer = await editable_offer(db, actor, offer_id, payload.revision)
    for key, value in payload.model_dump(exclude={"revision"}).items():
        setattr(offer, key, value)
    offer.revision += 1
    await db.flush()
    return offer


async def delete_offer(db, actor, offer_id, revision):
    offer = await editable_offer(db, actor, offer_id, revision)
    # The reference remains for financial history; it is not listed or reusable.
    offer.active = False
    offer.revision += 1
    await db.flush()


async def create_campaign(db, actor, payload: PizzaCampaignCreate, *, now=None):
    now = now or datetime.now(UTC)
    if StaffRole.TEACHER not in actor.roles:
        raise PizzaError("Сбор открывает преподаватель своей группы", 403)
    if not now < utc(payload.deadline) <= now + timedelta(days=90):
        raise PizzaError("Выберите срок в пределах следующих 90 дней")
    # Lock the offer to serialize simultaneous creation requests, including an empty group.
    offer = await db.scalar(
        select(PizzaOffer)
        .where(
            PizzaOffer.id == payload.offer_id,
            PizzaOffer.tenant_id == actor.tenant.id,
            PizzaOffer.active.is_(True),
        )
        .with_for_update()
    )
    if offer is None:
        raise PizzaError("Этот вариант уже недоступен", 404)
    pupils = [
        s
        for s in await teacher_students(db, actor)
        if (s.group_name or "") == payload.group_name
        and staff_names_match(teacher_staff_name(actor.account), s.teacher_name)
    ]
    if len(pupils) < 2:
        raise PizzaError("Выберите свою группу, в которой минимум два ученика", 403)
    existing = await db.scalar(
        select(PizzaCampaign.id).where(
            PizzaCampaign.tenant_id == actor.tenant.id,
            PizzaCampaign.group_name == payload.group_name,
            PizzaCampaign.status.in_(["open", "funded", "paid", "ordered"]),
        )
    )
    if existing:
        raise PizzaError("В этой группе уже есть незавершённый сбор", 409)
    campaign = PizzaCampaign(
        tenant_id=actor.tenant.id,
        offer_id=offer.id,
        teacher_id=actor.account.id,
        group_name=payload.group_name,
        title=offer.title,
        description=offer.description,
        kind=offer.kind,
        share=offer.share,
        target=offer.share * len(pupils),
        roster=[
            {
                "id": str(s.id),
                "name": s.display_name,
                "venue_id": str(s.venue_id) if s.venue_id else None,
            }
            for s in pupils
        ],
        deadline=payload.deadline,
    )
    db.add(campaign)
    await db.flush()
    audit(db, actor, campaign, "opened", share=offer.share, target=campaign.target)
    await notify_opened(db, campaign)
    return campaign


async def locked_campaign(db, actor, campaign_id):
    campaign = await db.scalar(
        select(PizzaCampaign)
        .where(PizzaCampaign.id == campaign_id, PizzaCampaign.tenant_id == actor.tenant.id)
        .with_for_update()
    )
    if campaign is None:
        raise PizzaError("Сбор не найден", 404)
    return campaign


async def refund_campaign(db, campaign, *, reason, actor=None):
    if campaign.status not in ("open", "funded"):
        return
    rows = list(
        await db.scalars(
            select(PizzaContribution)
            .where(
                PizzaContribution.campaign_id == campaign.id,
                PizzaContribution.refunded_at.is_(None),
            )
            .order_by(PizzaContribution.student_id)
        )
    )
    now = datetime.now(UTC)
    for contribution in rows:
        wallet = await db.scalar(
            select(Wallet)
            .where(
                Wallet.student_id == contribution.student_id, Wallet.tenant_id == campaign.tenant_id
            )
            .with_for_update()
        )
        if wallet is None:
            raise PizzaError("Не найден кошелёк для возврата. Обратитесь к директору", 409)
        await db.execute(
            update(Wallet)
            .where(Wallet.id == wallet.id)
            .values(balance=Wallet.balance + contribution.amount)
        )
        db.add(
            AstrocoinLedgerEntry(
                tenant_id=campaign.tenant_id,
                wallet_id=wallet.id,
                student_id=contribution.student_id,
                actor_account_id=actor.account.id if actor else None,
                idempotency_key=f"pizza:refund:{campaign.id}:{contribution.student_id}",
                direction=LedgerDirection.CREDIT,
                category="purchase",
                amount=contribution.amount,
                reason="Возврат за групповой сбор",
                comment=campaign.title,
            )
        )
        contribution.refunded_at = now
        await notice(
            db,
            campaign,
            contribution.account_id,
            "refund",
            f"Сбор «{campaign.title}» "
            f"{'отменён' if reason == 'cancelled' else 'завершился без полной суммы'}. "
            f"{contribution.amount} AC возвращены на баланс.",
        )
    campaign.status = reason
    campaign.closed_at = now
    audit(db, actor, campaign, reason, refunded=sum(c.amount for c in rows))


async def expire_campaigns(db, *, now=None):
    now = now or datetime.now(UTC)
    rows = list(
        await db.scalars(
            select(PizzaCampaign)
            .where(PizzaCampaign.status == "open", PizzaCampaign.deadline <= now)
            .order_by(PizzaCampaign.id)
            .with_for_update()
        )
    )
    for campaign in rows:
        await refund_campaign(db, campaign, reason="expired")
    return len(rows)


async def contribute(db: AsyncSession, actor, campaign_id, student_id, *, now=None):
    now = now or datetime.now(UTC)
    await own_student(db, actor, student_id, spending=True)
    campaign = await locked_campaign(db, actor, campaign_id)
    if str(student_id) not in {row["id"] for row in campaign.roster}:
        raise PizzaError("Этот сбор открыт для другой группы", 403)
    previous = await db.scalar(
        select(PizzaContribution).where(
            PizzaContribution.campaign_id == campaign.id, PizzaContribution.student_id == student_id
        )
    )
    if previous is not None:
        return campaign  # Network retry or a second device never debits a second share.
    if campaign.status != "open" or utc(campaign.deadline) <= now:
        raise PizzaError("Сбор уже закрыт. Взнос не списан", 409)
    wallet = await db.scalar(
        select(Wallet)
        .where(Wallet.student_id == student_id, Wallet.tenant_id == actor.tenant.id)
        .with_for_update()
    )
    if wallet is None:
        raise PizzaError("Кошелёк ученика пока не готов", 409)
    result = await db.execute(
        update(Wallet)
        .where(Wallet.id == wallet.id, Wallet.balance >= campaign.share)
        .values(balance=Wallet.balance - campaign.share)
    )
    if not result.rowcount:
        raise PizzaError("На балансе не хватает астрокоинов. Взнос не списан", 409)
    db.add(
        PizzaContribution(
            campaign_id=campaign.id,
            student_id=student_id,
            account_id=actor.account.id,
            amount=campaign.share,
        )
    )
    db.add(
        AstrocoinLedgerEntry(
            tenant_id=actor.tenant.id,
            wallet_id=wallet.id,
            student_id=student_id,
            actor_account_id=actor.account.id,
            idempotency_key=f"pizza:contribute:{campaign.id}:{student_id}",
            direction=LedgerDirection.DEBIT,
            category="purchase",
            amount=campaign.share,
            reason="Взнос на групповой сбор",
            comment=campaign.title,
        )
    )
    campaign.collected += campaign.share
    audit(db, actor, campaign, "contributed", student_id=str(student_id), amount=campaign.share)
    if campaign.collected == campaign.target:
        campaign.status = "funded"
        audit(db, actor, campaign, "funded", target=campaign.target)
        await db.flush()
        await notify_funded(db, campaign)
    await db.flush()
    return campaign


async def campaign_action(db, actor, campaign_id, action):
    campaign = await locked_campaign(db, actor, campaign_id)
    own = campaign.teacher_id == actor.account.id and StaffRole.TEACHER in actor.roles
    director = await director_can_manage(db, actor, campaign)
    if not (own or director):
        raise PizzaError("Нет доступа к этому сбору", 403)
    if action == "cancel":
        if campaign.status in ("cancelled", "expired"):
            return campaign
        if campaign.status not in ("open", "funded"):
            raise PizzaError("После передачи денег отмена через приложение недоступна", 409)
        await refund_campaign(db, campaign, reason="cancelled", actor=actor)
    else:
        previous = {"paid": "funded", "ordered": "paid", "delivered": "ordered"}[action]
        if action == "paid" and not director:
            raise PizzaError("Передачу денег подтверждает директор", 403)
        if action in ("ordered", "delivered") and not own:
            raise PizzaError("Заказ и получение подтверждает преподаватель группы", 403)
        if campaign.status == action:
            return campaign
        if campaign.status != previous:
            raise PizzaError("Сначала завершите предыдущий этап", 409)
        campaign.status = action
        if action == "delivered":
            campaign.closed_at = datetime.now(UTC)
        audit(db, actor, campaign, action)
        if action == "paid":
            await notice(
                db,
                campaign,
                campaign.teacher_id,
                "paid",
                "Директор подтвердил передачу денег. "
                f"Можно организовать «{campaign.title}» для {campaign.group_name}.",
            )
    await db.flush()
    return campaign


async def board(db, actor, *, student_id=None):
    customer_view = student_id is not None
    visible_students = [] if customer_view else await teacher_students(db, actor)
    own = None
    if student_id is not None:
        own = await own_student(db, actor, student_id)
    campaigns = list(
        await db.scalars(
            select(PizzaCampaign)
            .where(PizzaCampaign.tenant_id == actor.tenant.id)
            .order_by(PizzaCampaign.created_at.desc())
        )
    )
    output = []
    history = []
    for c in campaigns:
        member = own is not None and str(own.id) in {r["id"] for r in c.roster}
        staff = (c.teacher_id == actor.account.id and StaffRole.TEACHER in actor.roles) or (
            await director_can_manage(db, actor, c)
        )
        staff = staff and not customer_view
        if not (member or staff):
            continue
        contributions = list(
            await db.scalars(select(PizzaContribution).where(PizzaContribution.campaign_id == c.id))
        )
        mine = next((r for r in contributions if own and r.student_id == own.id), None)
        record = dict(
            id=str(c.id),
            title=c.title,
            description=c.description,
            kind=c.kind,
            group_name=c.group_name,
            share=c.share,
            target=c.target,
            collected=c.collected,
            status="funded"
            if customer_view and c.status in ("funded", "paid", "ordered", "delivered")
            else c.status,
            finished=c.status in ("delivered", "cancelled", "expired"),
            deadline=utc(c.deadline).isoformat(),
            members=len(c.roster),
            joined=len(contributions),
            contributed=mine is not None,
            refunded=mine is not None and mine.refunded_at is not None,
            can_manage=staff,
            is_teacher=staff and c.teacher_id == actor.account.id,
            # No public names, unpaid list or balances of other children.
            can_pay=actor.director and staff,
            can_contribute=bool(
                member
                and mine is None
                and c.status == "open"
                and await get_effective_customer_access_link(
                    db,
                    tenant_id=actor.tenant.id,
                    account_id=actor.account.id,
                    student_id=own.id,
                    required_role=StudentAccessRole.STUDENT,
                )
            ),
        )
        if mine is not None:
            history.append(
                {
                    **record,
                    "contributed_at": utc(mine.created_at).isoformat(),
                    "refunded_at": utc(mine.refunded_at).isoformat() if mine.refunded_at else None,
                }
            )
        # Customers see the collection in the shop only while contributions are open.
        if not customer_view or c.status == "open":
            output.append(record)
    offers = (
        list(
            await db.scalars(
                select(PizzaOffer)
                .where(PizzaOffer.tenant_id == actor.tenant.id, PizzaOffer.active.is_(True))
                .order_by(PizzaOffer.created_at)
            )
        )
        if actor.roles and not customer_view
        else []
    )
    notices = list(
        await db.scalars(
            select(PizzaNotice)
            .join(PizzaCampaign, PizzaCampaign.id == PizzaNotice.campaign_id)
            .where(
                PizzaNotice.account_id == actor.account.id,
                PizzaCampaign.tenant_id == actor.tenant.id,
            )
            .order_by(PizzaNotice.created_at.desc())
            .limit(20)
        )
    )
    balance = (
        await db.scalar(select(Wallet.balance).where(Wallet.student_id == own.id)) if own else None
    )
    entries = (
        list(
            await db.scalars(
                select(AstrocoinLedgerEntry)
                .where(
                    AstrocoinLedgerEntry.tenant_id == actor.tenant.id,
                    AstrocoinLedgerEntry.student_id == own.id,
                    AstrocoinLedgerEntry.idempotency_key.like("pizza:%"),
                )
                .order_by(AstrocoinLedgerEntry.created_at.desc())
            )
        )
        if own
        else []
    )
    return dict(
        campaigns=output,
        history=history,
        ledger=[
            dict(
                id=str(e.id),
                student_id=str(e.student_id),
                reason=e.reason,
                comment=e.comment,
                amount=e.amount,
                direction=e.direction.value,
                created_at=utc(e.created_at).isoformat(),
            )
            for e in entries
        ],
        director=actor.director and not customer_view,
        teacher=StaffRole.TEACHER in actor.roles and not customer_view,
        balance=balance,
        groups=[
            dict(name=g, count=sum(s.group_name == g for s in visible_students))
            for g in sorted({s.group_name for s in visible_students if s.group_name})
        ],
        offers=[
            dict(
                id=str(o.id),
                title=o.title,
                description=o.description,
                share=o.share,
                kind=o.kind,
                revision=o.revision,
            )
            for o in offers
        ],
        notices=[
            dict(
                id=str(n.id),
                message=n.message,
                event=n.event,
                created_at=utc(n.created_at).isoformat(),
            )
            for n in notices
            if not customer_view or n.event == "refund"
        ],
        server_time=datetime.now(UTC).isoformat(),
    )
