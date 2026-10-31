"""Run a loopback-only, persistent pizza preview with fictional pupils.

    .venv/Scripts/python.exe -m app.cli.pizza_preview

No production database, bindings, MAX delivery or payment integrations are used.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREVIEW_DB = ROOT / ".deploy_tmp/pizza-preview.sqlite3"
PREVIEW_DB.parent.mkdir(exist_ok=True)
os.environ.update(
    {
        "APP_ENV": "test",
        "APP_SECRET_KEY": "pizza-preview-local-only-key-not-for-production",
        "DATABASE_URL": f"sqlite+aiosqlite:///{PREVIEW_DB.as_posix()}",
        "DATABASE_SYNC_URL": f"sqlite:///{PREVIEW_DB.as_posix()}",
        "MAX_BOT_TOKEN": "",
        "GROUP_COLLECTIONS_ENABLED": "true",
    }
)

import uvicorn  # noqa: E402
from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from sqlalchemy import delete, select  # noqa: E402

import app.db.base  # noqa: E402, F401
from app.api.routes.pizza import router  # noqa: E402
from app.core.miniapp_auth import issue_miniapp_token  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.models.account import MaxAccount, StaffRoleAssignment  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.models.enums import (  # noqa: E402
    AssignmentStatus,
    StaffRole,
    StudentAccessRole,
    StudentAccessSource,
    StudentAccessStatus,
)
from app.models.pizza import PizzaCampaign, PizzaContribution, PizzaNotice, PizzaOffer  # noqa: E402
from app.models.student import (  # noqa: E402
    AstrocoinLedgerEntry,
    Student,
    StudentAccessLink,
    Wallet,
)
from app.models.tenant import City, Partner, Tenant  # noqa: E402
from app.schemas.pizza import PizzaCampaignCreate, PizzaOfferCreate  # noqa: E402
from app.services import pizza  # noqa: E402

GROUP = "ПС1 · Союзный 45, сб 14:00"
SLUG = "pizza-preview"
ROLES = {
    "student": (900001, "Ученик"),
    "teacher": (900100, "Преподаватель"),
    "partner_director": (900200, "Директор"),
    "parent": (900300, "Родитель"),
}
gate = asyncio.Lock()


async def seed_collection(db):
    director = await pizza.actor_for(db, 900200, SLUG)
    teacher = await pizza.actor_for(db, 900100, SLUG)
    offer = await pizza.create_offer(
        db,
        director,
        PizzaOfferCreate(
            title="Пицца-вечеринка",
            description="Ассорти пицц и напитки на общем занятии",
            share=200,
        ),
    )
    await pizza.create_offer(
        db,
        director,
        PizzaOfferCreate(
            title="Большая компания", description="Больше пиццы, больше вкусов", share=300
        ),
    )
    await db.flush()
    campaign = await pizza.create_campaign(
        db,
        teacher,
        PizzaCampaignCreate(
            offer_id=offer.id,
            group_name=GROUP,
            deadline=datetime.now(UTC) + timedelta(days=3, hours=5),
        ),
    )
    for number in range(2, 8):
        pupil = await db.scalar(select(Student).where(Student.lms_student_id == f"DEMO-{number}"))
        actor = await pizza.actor_for(db, 900000 + number, SLUG)
        await pizza.contribute(db, actor, campaign.id, pupil.id)


async def initialize():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        if await db.scalar(select(Tenant.id).where(Tenant.slug == SLUG)):
            return
        city = City(slug="pizza-demo-city", name="Демо-город")
        partner = Partner(slug="pizza-demo-partner", name="Algo MAX · демо")
        db.add_all([city, partner])
        await db.flush()
        tenant = Tenant(city_id=city.id, partner_id=partner.id, slug=SLUG, name="Локальная демка")
        teacher = MaxAccount(max_user_id=900100, display_name="Орлов Алексей")
        director = MaxAccount(max_user_id=900200, display_name="Смирнова Мария")
        parent = MaxAccount(max_user_id=900300, display_name="Петрова Анна")
        db.add_all([tenant, teacher, director, parent])
        await db.flush()
        for account, role in [(teacher, StaffRole.TEACHER), (director, StaffRole.PARTNER_DIRECTOR)]:
            db.add(
                StaffRoleAssignment(
                    tenant_id=tenant.id,
                    account_id=account.id,
                    role=role,
                    status=AssignmentStatus.ACTIVE,
                )
            )
        names = [
            ("Петров", "Артём"),
            ("Васильева", "Алиса"),
            ("Соколов", "Марк"),
            ("Иванова", "Соня"),
            ("Морозов", "Илья"),
            ("Орлова", "Даша"),
            ("Кузьмин", "Миша"),
            ("Белова", "Маша"),
        ]
        for number, (last, first) in enumerate(names, 1):
            pupil = Student(
                tenant_id=tenant.id,
                lms_student_id=f"DEMO-{number}",
                student_access_code=f"PIZZA-DEMO-{number}",
                first_name=first,
                last_name=last,
                group_name=GROUP,
                teacher_name=teacher.display_name,
                course_name="Питон Start 1-й год",
            )
            account = MaxAccount(max_user_id=900000 + number, display_name=f"{last} {first}")
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
        await db.flush()
        await seed_collection(db)
        await db.commit()


async def expiry_worker():
    while True:
        await asyncio.sleep(5)
        async with gate, AsyncSessionLocal() as db:
            await pizza.expire_campaigns(db)
            await db.commit()


@asynccontextmanager
async def lifespan(app):
    await initialize()
    worker = asyncio.create_task(expiry_worker())
    yield
    worker.cancel()
    with suppress(asyncio.CancelledError):
        await worker
    await engine.dispose()


preview = FastAPI(lifespan=lifespan)
preview.include_router(router, prefix="/api/v1/miniapp/pizza")
static = ROOT / "app/web/static/miniapp"
preview.mount("/miniapp/static", StaticFiles(directory=static), name="static")


@preview.middleware("http")
async def local_requests(request: Request, call_next):
    if request.headers.get("host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
        return Response(status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return Response(status_code=403)
    # SQLite does not implement SELECT FOR UPDATE. Serialize preview transactions;
    # the production service uses row locks and conditional wallet debits.
    if request.url.path.startswith(("/api/", "/preview/")):
        async with gate:
            response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@preview.get("/")
async def home():
    return RedirectResponse("/miniapp?demo=1&demo_role=student&view=store")


@preview.get("/miniapp", response_class=HTMLResponse)
async def index(request: Request):
    role = request.query_params.get("demo_role", "student")
    if role not in ROLES:
        raise HTTPException(400, "Unknown preview role")
    source = (static / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        '<script src="/miniapp/static/app-core.js?v=0.91.64"></script>',
        '<script src="/miniapp/static/app-core.js?v=0.91.64"></script>'
        f'<script src="/preview/bootstrap.js?role={role}"></script>',
    )
    source = source.replace("</body>", '<script src="/preview/controls.js"></script></body>')
    return source


@preview.get("/preview/bootstrap.js")
async def bootstrap(role: str = "student"):
    if role not in ROLES:
        raise HTTPException(400)
    max_id, label = ROLES[role]
    async with AsyncSessionLocal() as db:
        pupils = list(await db.scalars(select(Student).order_by(Student.lms_student_id)))
        first = pupils[0]
        if role in ("student", "parent"):
            pupils = [first]
        records = []
        for s in pupils:
            balance = await db.scalar(select(Wallet.balance).where(Wallet.student_id == s.id))
            records.append(
                dict(
                    id=str(s.id),
                    name=s.display_name,
                    lmsId=s.lms_student_id,
                    group=s.group_name,
                    course=s.course_name,
                    teacher=s.teacher_name,
                    venue="Союзный 45",
                    status="active",
                    balance=balance,
                    parentConnected=True,
                    teacherVisible=True,
                    staffVisible=True,
                    role="parent" if role == "parent" else "student",
                )
            )
        account = await db.scalar(select(MaxAccount).where(MaxAccount.max_user_id == max_id))
    context = dict(
        token=issue_miniapp_token(max_user_id=max_id, tenant_slug=SLUG),
        tenant=SLUG,
        role=role,
        label=label,
    )
    source = f"""window.pizzaPreview={json.dumps(context, ensure_ascii=False)};
students.splice(0,students.length,...{json.dumps(records, ensure_ascii=False)});
state.activeStudentId=students[0].id;
state.account={{display_name:{json.dumps(account.display_name, ensure_ascii=False)}}};
orders.splice(0,orders.length);
ledger.splice(0,ledger.length);
"""
    return Response(source, media_type="application/javascript")


@preview.get("/preview/controls.js")
async def controls():
    source = Path(__file__).with_name("pizza_preview_controls.js").read_text(encoding="utf-8")
    return Response(source, media_type="application/javascript")


@preview.post("/preview/scenario/{scenario}")
async def scenario(scenario: str, request: Request):
    from app.core.miniapp_auth import verify_miniapp_token

    identity = verify_miniapp_token(request.headers.get("X-Miniapp-Token", ""))
    if identity.tenant_slug != SLUG:
        raise HTTPException(403)
    async with AsyncSessionLocal() as db:
        if scenario == "reset":
            for model in (
                PizzaNotice,
                PizzaContribution,
                PizzaCampaign,
                PizzaOffer,
                AstrocoinLedgerEntry,
            ):
                await db.execute(delete(model))
            wallets = list(await db.scalars(select(Wallet)))
            for w in wallets:
                w.balance = 1240
            await db.flush()
            await seed_collection(db)
        elif scenario in ("fill", "expire"):
            campaign = await db.scalar(select(PizzaCampaign).where(PizzaCampaign.status == "open"))
            if campaign is None:
                return {"ok": True}
            if scenario == "expire":
                campaign.deadline = datetime.now(UTC) - timedelta(seconds=1)
                await db.flush()
                await pizza.expire_campaigns(db)
            else:
                for row in campaign.roster:
                    from uuid import UUID

                    pupil_id = UUID(row["id"])
                    link = await db.scalar(
                        select(StudentAccessLink).where(
                            StudentAccessLink.student_id == pupil_id,
                            StudentAccessLink.role == StudentAccessRole.STUDENT,
                        )
                    )
                    account = await db.get(MaxAccount, link.account_id)
                    actor = await pizza.actor_for(db, account.max_user_id, SLUG)
                    await pizza.contribute(db, actor, campaign.id, pupil_id)
        else:
            raise HTTPException(404)
        await db.commit()
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(preview, host="127.0.0.1", port=8770, log_level="warning")
