from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.db.base  # noqa: F401
from app.api.dependencies import get_miniapp_identity
from app.api.routes.pizza import router
from app.core.config import get_settings
from app.core.miniapp_auth import MiniAppIdentity
from app.db.session import get_db_session
from app.models.account import MaxAccount, StaffRoleAssignment
from app.models.base import Base
from app.models.enums import (
    AssignmentStatus,
    LedgerDirection,
    StaffRole,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
)
from app.models.pizza import PizzaContribution, PizzaNotice
from app.models.student import AstrocoinLedgerEntry, Student, StudentAccessLink, Wallet
from app.models.tenant import City, Partner, Tenant
from app.schemas.pizza import PizzaCampaignCreate, PizzaOfferCreate
from app.services import pizza


@pytest.fixture
async def context():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        city = City(slug="test", name="Test")
        partner = Partner(slug="test", name="Test")
        db.add_all([city, partner])
        await db.flush()
        tenant = Tenant(slug="test", name="Test", city_id=city.id, partner_id=partner.id)
        teacher = MaxAccount(max_user_id=910001, display_name="Орлов Алексей")
        director = MaxAccount(max_user_id=910002, display_name="Смирнова Мария")
        parent = MaxAccount(max_user_id=910003, display_name="Родитель")
        other = MaxAccount(max_user_id=910004, display_name="Другой Преподаватель")
        db.add_all([tenant, teacher, director, parent, other])
        await db.flush()
        for account, role in [
            (teacher, StaffRole.TEACHER),
            (director, StaffRole.PARTNER_DIRECTOR),
            (other, StaffRole.TEACHER),
        ]:
            db.add(
                StaffRoleAssignment(
                    tenant_id=tenant.id,
                    account_id=account.id,
                    role=role,
                    status=AssignmentStatus.ACTIVE,
                )
            )
        pupils = []
        accounts = []
        for i in range(4):
            pupil = Student(
                tenant_id=tenant.id,
                student_access_code=f"PIZZA-{i}",
                first_name=f"Ученик{i}",
                last_name="Тестовый",
                group_name="Группа" if i < 3 else "Чужая",
                teacher_name=teacher.display_name if i < 3 else other.display_name,
            )
            account = MaxAccount(max_user_id=920000 + i, display_name=f"Ученик{i}")
            db.add_all([pupil, account])
            await db.flush()
            db.add(Wallet(tenant_id=tenant.id, student_id=pupil.id, balance=1240))
            for owner, role in [
                (account, StudentAccessRole.STUDENT),
                (parent, StudentAccessRole.PARENT),
            ]:
                db.add(
                    StudentAccessLink(
                        tenant_id=tenant.id,
                        account_id=owner.id,
                        student_id=pupil.id,
                        role=role,
                        status=StudentAccessStatus.ACTIVE,
                        source=StudentAccessSource.ADMIN,
                    )
                )
            pupils.append(pupil)
            accounts.append(account)
        await db.commit()
        director_actor = await pizza.actor_for(db, director.max_user_id, "test")
        teacher_actor = await pizza.actor_for(db, teacher.max_user_id, "test")
        offer = await pizza.create_offer(
            db, director_actor, PizzaOfferCreate(title="Пицца", description="Ассорти", share=200)
        )
        campaign = await pizza.create_campaign(
            db,
            teacher_actor,
            PizzaCampaignCreate(
                offer_id=offer.id,
                group_name="Группа",
                deadline=datetime.now(UTC) + timedelta(days=3),
            ),
        )
        await db.commit()
        yield dict(
            db=db,
            tenant=tenant,
            teacher=teacher_actor,
            director=director_actor,
            parent=await pizza.actor_for(db, parent.max_user_id, "test"),
            other=await pizza.actor_for(db, other.max_user_id, "test"),
            pupils=pupils,
            accounts=accounts,
            offer=offer,
            campaign=campaign,
            factory=factory,
        )
    await engine.dispose()


async def pay(c, index=0):
    actor = await pizza.actor_for(c["db"], c["accounts"][index].max_user_id, "test")
    return await pizza.contribute(c["db"], actor, c["campaign"].id, c["pupils"][index].id)


async def balance(c, index=0):
    return await c["db"].scalar(
        select(Wallet.balance).where(Wallet.student_id == c["pupils"][index].id)
    )


async def test_one_fixed_share_even_on_network_retry_and_after_funding(context):
    c = context
    await pay(c)
    await pay(c)
    assert await balance(c) == 1040 and c["campaign"].collected == 200
    await pay(c, 1)
    await pay(c, 2)
    await pay(c)
    await c["db"].commit()
    assert c["campaign"].status == "funded" and c["campaign"].collected == 600
    assert await balance(c) == 1040
    assert await c["db"].scalar(select(func.count()).select_from(PizzaContribution)) == 3
    assert await c["db"].scalar(select(func.count()).select_from(AstrocoinLedgerEntry)) == 3
    notices = list(await c["db"].scalars(select(PizzaNotice)))
    assert len(notices) == 2
    assert {n.account_id for n in notices} == {c["teacher"].account.id, c["director"].account.id}


@pytest.mark.parametrize("reason", ["cancel", "expire"])
async def test_partial_collection_returns_exact_shares_once_and_survives_new_session(
    context, reason
):
    c = context
    await pay(c)
    await pay(c, 1)
    await c["db"].commit()
    if reason == "cancel":
        await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "cancel")
        await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "cancel")
    else:
        after = pizza.utc(c["campaign"].deadline) + timedelta(seconds=1)
        assert await pizza.expire_campaigns(c["db"], now=after) == 1
        assert await pizza.expire_campaigns(c["db"], now=after) == 0
    await c["db"].commit()
    async with c["factory"]() as fresh:
        balances = list(await fresh.scalars(select(Wallet.balance)))
        assert balances == [1240] * 4
        entries = list(await fresh.scalars(select(AstrocoinLedgerEntry)))
        assert len(entries) == 4
        net = sum(e.amount if e.direction == LedgerDirection.CREDIT else -e.amount for e in entries)
        assert net == 0
        assert all(
            r.refunded_at is not None for r in await fresh.scalars(select(PizzaContribution))
        )


async def test_insufficient_funds_leave_collection_and_ledger_untouched(context):
    c = context
    wallet = await c["db"].scalar(select(Wallet).where(Wallet.student_id == c["pupils"][0].id))
    wallet.balance = 199
    await c["db"].commit()
    with pytest.raises(pizza.PizzaError, match="не хватает"):
        await pay(c)
    assert c["campaign"].collected == 0 and await balance(c) == 199
    assert await c["db"].scalar(select(func.count()).select_from(AstrocoinLedgerEntry)) == 0


@pytest.mark.parametrize("actor", ["parent", "teacher", "director"])
async def test_only_child_account_can_spend_own_coins(context, actor):
    c = context
    with pytest.raises(pizza.PizzaError, match="только ученик"):
        await pizza.contribute(c["db"], c[actor], c["campaign"].id, c["pupils"][0].id)
    assert await balance(c) == 1240


async def test_foreign_group_and_foreign_child_are_rejected(context):
    c = context
    with pytest.raises(pizza.PizzaError, match="другой группы"):
        await pay(c, 3)
    actor = await pizza.actor_for(c["db"], c["accounts"][0].max_user_id, "test")
    with pytest.raises(pizza.PizzaError):
        await pizza.contribute(c["db"], actor, c["campaign"].id, c["pupils"][1].id)
    assert [await balance(c, i) for i in range(4)] == [1240] * 4


async def test_expired_request_does_not_charge_and_background_returns_existing_funds(context):
    c = context
    await pay(c)
    actor = await pizza.actor_for(c["db"], c["accounts"][1].max_user_id, "test")
    after = pizza.utc(c["campaign"].deadline) + timedelta(seconds=1)
    with pytest.raises(pizza.PizzaError, match="уже закрыт"):
        await pizza.contribute(c["db"], actor, c["campaign"].id, c["pupils"][1].id, now=after)
    assert await balance(c, 1) == 1240
    await pizza.expire_campaigns(c["db"], now=after)
    await c["db"].commit()
    assert await balance(c) == 1240


async def test_roster_price_and_title_are_frozen_and_unpaid_names_are_private(context):
    c = context
    c["offer"].share = 500
    c["offer"].title = "Изменённый вариант"
    c["pupils"][3].group_name = "Группа"
    await c["db"].commit()
    await pay(c)
    actor = await pizza.actor_for(c["db"], c["accounts"][0].max_user_id, "test")
    data = await pizza.board(c["db"], actor, student_id=c["pupils"][0].id)
    campaign = data["campaigns"][0]
    assert campaign["share"] == 200 and campaign["target"] == 600 and campaign["members"] == 3
    assert campaign["title"] == "Пицца" and campaign["joined"] == 1
    assert "roster" not in campaign and "contributions" not in campaign
    assert data["groups"] == [] and data["offers"] == []


async def test_stage_permissions_no_skipping_and_cancel_after_transfer_rejected(context):
    c = context
    for i in range(3):
        await pay(c, i)
    with pytest.raises(pizza.PizzaError, match="директор"):
        await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "paid")
    with pytest.raises(pizza.PizzaError, match="предыдущий этап"):
        await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "ordered")
    await pizza.campaign_action(c["db"], c["director"], c["campaign"].id, "paid")
    with pytest.raises(pizza.PizzaError, match="отмена"):
        await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "cancel")
    with pytest.raises(pizza.PizzaError, match="преподаватель"):
        await pizza.campaign_action(c["db"], c["director"], c["campaign"].id, "ordered")
    await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "ordered")
    await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "delivered")
    await c["db"].commit()
    assert c["campaign"].status == "delivered"
    child = await pizza.actor_for(c["db"], c["accounts"][0].max_user_id, "test")
    public = await pizza.board(c["db"], child, student_id=c["pupils"][0].id)
    assert public["campaigns"] == []
    assert public["history"][0]["status"] == "funded"
    assert public["history"][0]["finished"] is True
    assert public["notices"] == []


async def test_child_view_never_exposes_internal_stages_even_for_staff_account(context):
    c = context
    for i in range(3):
        await pay(c, i)
    child = await pizza.actor_for(c["db"], c["accounts"][0].max_user_id, "test")
    child.roles.add(StaffRole.PARTNER_DIRECTOR)
    for stage in ("funded", "paid", "ordered", "delivered"):
        c["campaign"].status = stage
        await c["db"].flush()
        public = await pizza.board(c["db"], child, student_id=c["pupils"][0].id)
        assert public["campaigns"] == []
        assert public["history"][0]["status"] == "funded"
        assert not public["history"][0]["can_manage"]
        assert not public["history"][0]["can_pay"]
        assert not public["director"] and not public["teacher"]
        assert public["offers"] == [] and public["groups"] == []


async def test_cancelled_collection_leaves_shop_but_keeps_exact_personal_history(context):
    c = context
    await pay(c)
    await pizza.campaign_action(c["db"], c["teacher"], c["campaign"].id, "cancel")
    await c["db"].commit()
    child = await pizza.actor_for(c["db"], c["accounts"][0].max_user_id, "test")
    data = await pizza.board(c["db"], child, student_id=c["pupils"][0].id)
    assert data["campaigns"] == [] and len(data["history"]) == 1
    assert data["history"][0]["refunded"]
    assert data["history"][0]["refunded_at"]
    assert data["balance"] == 1240
    assert len(data["ledger"]) == 2
    assert (
        sum(-e["amount"] if e["direction"] == "debit" else e["amount"] for e in data["ledger"]) == 0
    )
    unpaid = await pizza.actor_for(c["db"], c["accounts"][1].max_user_id, "test")
    other = await pizza.board(c["db"], unpaid, student_id=c["pupils"][1].id)
    assert other["campaigns"] == [] and other["history"] == [] and other["ledger"] == []


async def test_offers_director_only_campaigns_own_teacher_only_and_one_live_collection(context):
    c = context
    with pytest.raises(pizza.PizzaError, match="директор"):
        await pizza.create_offer(c["db"], c["teacher"], PizzaOfferCreate(title="Пицца", share=200))
    payload = PizzaCampaignCreate(
        offer_id=c["offer"].id, group_name="Группа", deadline=datetime.now(UTC) + timedelta(days=2)
    )
    with pytest.raises(pizza.PizzaError, match="преподаватель"):
        await pizza.create_campaign(c["db"], c["director"], payload)
    with pytest.raises(pizza.PizzaError, match="свою группу"):
        await pizza.create_campaign(c["db"], c["other"], payload)
    with pytest.raises(pizza.PizzaError, match="незавершённый"):
        await pizza.create_campaign(c["db"], c["teacher"], payload)
    with pytest.raises(pizza.PizzaError, match="Нет доступа"):
        await pizza.campaign_action(c["db"], c["other"], c["campaign"].id, "cancel")
    assert not (await pizza.board(c["db"], c["other"]))["campaigns"]


async def test_funded_collection_does_not_expire_and_can_be_refunded_before_transfer(context):
    c = context
    for i in range(3):
        await pay(c, i)
    assert await pizza.expire_campaigns(c["db"], now=datetime.now(UTC) + timedelta(days=30)) == 0
    await pizza.campaign_action(c["db"], c["director"], c["campaign"].id, "cancel")
    await c["db"].commit()
    assert [await balance(c, i) for i in range(4)] == [1240] * 4


async def test_http_missing_identity_cross_tenant_and_parent_spend_are_denied(context, monkeypatch):
    c = context
    monkeypatch.setattr(get_settings(), "group_collections_enabled", True)
    app = FastAPI()
    app.include_router(router, prefix="/pizza")

    async def db():
        yield c["db"]

    async def anonymous():
        return None

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_miniapp_identity] = anonymous
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/pizza?tenant_slug=test")).status_code == 401

        async def parent():
            return MiniAppIdentity(c["parent"].account.max_user_id, "test", 9999999999)

        app.dependency_overrides[get_miniapp_identity] = parent
        assert (await client.get("/pizza?tenant_slug=other")).status_code == 403
        result = await client.post(
            f"/pizza/campaigns/{c['campaign'].id}/contribute?tenant_slug=test",
            json={"student_id": str(c["pupils"][0].id)},
        )
        assert result.status_code == 403


async def test_closed_feature_does_not_expose_or_query_new_tables(context, monkeypatch):
    c = context
    monkeypatch.setattr(get_settings(), "group_collections_enabled", False)
    app = FastAPI()
    app.include_router(router, prefix="/pizza")

    async def db():
        yield c["db"]

    async def identity():
        return MiniAppIdentity(910001, "test", 9999999999)

    app.dependency_overrides[get_db_session] = db
    app.dependency_overrides[get_miniapp_identity] = identity
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/pizza?tenant_slug=test")).status_code == 404


async def test_director_can_still_refund_after_pupil_leaves_group(context):
    from app.models.enums import StudentStatus

    c = context
    await pay(c)
    c["pupils"][0].status = StudentStatus.DEPARTED
    await c["db"].commit()
    visible = await pizza.board(c["db"], c["director"])
    assert visible["campaigns"][0]["can_manage"]
    await pizza.campaign_action(c["db"], c["director"], c["campaign"].id, "cancel")
    await c["db"].commit()
    assert await balance(c) == 1240


async def test_director_scope_prevents_reading_other_venue_collection(context):
    from app.models.account import StaffVenueScope
    from app.models.tenant import Venue

    c = context
    venue = Venue(tenant_id=c["tenant"].id, slug="other", name="Другая площадка")
    c["db"].add(venue)
    await c["db"].flush()
    assignment = await c["db"].scalar(
        select(StaffRoleAssignment).where(
            StaffRoleAssignment.account_id == c["director"].account.id
        )
    )
    c["db"].add(StaffVenueScope(assignment_id=assignment.id, venue_id=venue.id))
    await c["db"].commit()
    assert not (await pizza.board(c["db"], c["director"]))["campaigns"]
    with pytest.raises(pizza.PizzaError, match="Нет доступа"):
        await pizza.campaign_action(c["db"], c["director"], c["campaign"].id, "cancel")


def test_new_migration_only_creates_collection_tables_and_indexes():
    import importlib.util
    from io import StringIO
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).parents[1] / "alembic/versions/20261031_0040_group_pizza.py"
    spec = importlib.util.spec_from_file_location("pizza_migration_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        module.upgrade()
    sql = output.getvalue().upper()
    assert sql.count("CREATE TABLE") == 4
    assert "UQ_PIZZA_LIVE_GROUP" in sql and "WHERE STATUS IN" in sql
    assert all(word not in sql for word in ("ALTER TABLE", "UPDATE ", "DELETE FROM", "DROP "))
