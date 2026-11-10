"""Run a loopback-only, persistent pizza preview with fictional pupils.

    .venv/Scripts/python.exe -m app.cli.pizza_preview

No production database, bindings, MAX delivery or payment integrations are used.
"""

import argparse
import asyncio
import json
import os
import re
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description="Local group collection preview")
parser.add_argument("--port", type=int, default=8770)
parser.add_argument("--database-name", default="pizza-preview.sqlite3")
parser.add_argument("--games", action="store_true", help="Enable local games prototype")
options = parser.parse_args() if __name__ == "__main__" else parser.parse_args([])
if Path(options.database_name).name != options.database_name or not options.database_name.endswith(
    ".sqlite3"
):
    raise ValueError("Use a SQLite filename inside .deploy_tmp")
PREVIEW_DB = ROOT / ".deploy_tmp" / options.database_name
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

arcade_store = None
if options.games:
    from app.services.arcade import ArcadeStore

    arcade_store = ArcadeStore(PREVIEW_DB.with_name("arcade-" + options.database_name))

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
    await pizza.create_offer(
        db,
        director,
        PizzaOfferCreate(
            title="Общий подарок", description="Подарок для нашей группы", share=150, kind="other"
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
        # Only the isolated preview database is upgraded here, preserving its data.
        def upgrade_preview(conn):
            from sqlalchemy import inspect

            inspector = inspect(conn)
            definitions = {
                "pizza_offers": {
                    "kind": "VARCHAR(20) NOT NULL DEFAULT 'pizza'",
                    "revision": "INTEGER NOT NULL DEFAULT 1",
                },
                "pizza_campaigns": {"kind": "VARCHAR(20) NOT NULL DEFAULT 'pizza'"},
                "pizza_notices": {
                    "attempted_at": "DATETIME",
                    "next_attempt_at": "DATETIME",
                    "attempts": "INTEGER NOT NULL DEFAULT 0",
                    "cancelled_at": "DATETIME",
                    "last_error": "VARCHAR(120)",
                },
            }
            for table, fields in definitions.items():
                if table not in inspector.get_table_names():
                    continue
                existing = {c["name"] for c in inspector.get_columns(table)}
                for name, definition in fields.items():
                    if name not in existing:
                        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

        await connection.run_sync(upgrade_preview)
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
    arcade_worker = None
    if arcade_store:
        from app.services.arcade import maintenance_worker
        from app.services.arcade_runtime import catalogue

        await asyncio.to_thread(catalogue)
        async with AsyncSessionLocal() as db:
            game_students = list(await db.scalars(select(Student)))
        await asyncio.to_thread(
            arcade_store.register,
            [
                {"id": str(s.id), "name": s.display_name, "group": s.group_name}
                for s in game_students
            ],
        )
        arcade_worker = asyncio.create_task(maintenance_worker(arcade_store))
    worker = asyncio.create_task(expiry_worker())
    yield
    worker.cancel()
    with suppress(asyncio.CancelledError):
        await worker
    if arcade_worker:
        arcade_worker.cancel()
        with suppress(asyncio.CancelledError):
            await arcade_worker
    await engine.dispose()


preview = FastAPI(lifespan=lifespan)
preview.include_router(router, prefix="/api/v1/miniapp/pizza")
if arcade_store:
    from app.api.routes.arcade_preview import make_router
    from app.core.miniapp_auth import MiniAppAuthError, verify_miniapp_token

    async def arcade_actor(request: Request):
        try:
            identity = verify_miniapp_token(request.headers.get("X-Miniapp-Token", ""))
        except MiniAppAuthError as error:
            raise HTTPException(401, "Открой локальную демку заново.") from error
        if identity.tenant_slug != SLUG:
            raise HTTPException(403, "Эта ссылка не относится к демке.")
        async with AsyncSessionLocal() as db:
            if identity.max_user_id == 900200:
                pupil = await db.scalar(select(Student).order_by(Student.lms_student_id))
                return {"player": str(pupil.id), "director": True}
            pupil = await db.scalar(
                select(Student)
                .join(StudentAccessLink, StudentAccessLink.student_id == Student.id)
                .join(MaxAccount, MaxAccount.id == StudentAccessLink.account_id)
                .where(
                    MaxAccount.max_user_id == identity.max_user_id,
                    StudentAccessLink.role == StudentAccessRole.STUDENT,
                    StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                )
            )
        if not pupil:
            raise HTTPException(403, "Аккаунт игрока не найден в демке.")
        return {"player": str(pupil.id), "director": False}

    preview.include_router(make_router(arcade_store, arcade_actor), prefix="/preview/arcade")
static = ROOT / "app/web/static/miniapp"
preview.mount("/miniapp/static", StaticFiles(directory=static), name="static")


@preview.get("/preview/sort-levels")
async def sort_levels_preview():
    if not arcade_store:
        raise HTTPException(404)
    return Response(
        Path(__file__).with_name("sort_levels_preview.html").read_text(encoding="utf-8"),
        media_type="text/html",
    )


@preview.middleware("http")
async def local_requests(request: Request, call_next):
    if request.headers.get("host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
        return Response(status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        return Response(status_code=403)
    # SQLite does not implement SELECT FOR UPDATE. Serialize preview transactions;
    # the production service uses row locks and conditional wallet debits.
    if request.url.path.startswith("/preview/arcade") and (
        len(request.headers.get("content-length", "0")) > 10
        or (
            request.headers.get("content-length", "0").isdigit()
            and int(request.headers.get("content-length", "0")) > 2000000
        )
    ):
        return Response(status_code=413)
    if request.url.path.startswith(("/api/", "/preview/")) and not request.url.path.startswith(
        "/preview/arcade"
    ):
        async with gate:
            response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@preview.get("/")
async def home():
    return RedirectResponse(
        "/miniapp?demo=1&demo_role=student&view=" + ("games" if options.games else "store")
    )


@preview.get("/miniapp", response_class=HTMLResponse)
async def index(request: Request):
    role = request.query_params.get("demo_role", "student")
    if role not in ROLES:
        raise HTTPException(400, "Unknown preview role")
    source = (static / "index.html").read_text(encoding="utf-8")
    if options.games:
        from app.cli.games_preview import inject_games

        source = inject_games(source)
    source = re.sub(
        r'(<script src="/miniapp/static/app-core\.js[^\"]*"></script>)',
        lambda match: match.group(1) + f'<script src="/preview/bootstrap.js?role={role}"></script>',
        source,
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
        game_players = (
            [{"id": str(s.id), "name": s.display_name, "group": s.group_name} for s in pupils]
            if options.games
            else []
        )
        if options.games:
            for player in game_players:
                pupil = next(s for s in pupils if str(s.id) == player["id"])
                account_id = await db.scalar(
                    select(MaxAccount.max_user_id)
                    .join(StudentAccessLink, StudentAccessLink.account_id == MaxAccount.id)
                    .where(
                        StudentAccessLink.student_id == pupil.id,
                        StudentAccessLink.role == StudentAccessRole.STUDENT,
                        StudentAccessLink.status == StudentAccessStatus.ACTIVE,
                    )
                )
                player["token"] = issue_miniapp_token(max_user_id=account_id, tenant_slug=SLUG)
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
window.ALGO_GAMES_PROTOTYPE={json.dumps(options.games)};
window.ALGO_GAME_PLAYERS={json.dumps(game_players, ensure_ascii=False)};
window.ALGO_ARCADE_API={json.dumps("/preview/arcade" if options.games else None)};
if (window.ALGO_GAMES_PROTOTYPE && queryParam("view") === "games") state.view="games";
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
    uvicorn.run(preview, host="127.0.0.1", port=options.port, log_level="warning")
