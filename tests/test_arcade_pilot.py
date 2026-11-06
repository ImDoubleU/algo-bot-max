"""The real signed account owns the private pilot; child links and wallets are untouched."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update

import app.api.routes.arcade as pilot
from app.core.config import get_settings
from app.core.miniapp_auth import issue_miniapp_token
from app.models.account import StaffRoleAssignment
from app.models.enums import AssignmentStatus
from app.models.student import StudentAccessLink, Wallet
from app.web.arcade_pilot import inject_pilot
from tests.test_pizza import context as context


@pytest.fixture
async def private_arcade(context, monkeypatch, tmp_path):
    monkeypatch.setenv("ARCADE_PILOT_ENABLED", "true")
    monkeypatch.setenv("ARCADE_PILOT_MAX_IDS", "[910001,910002]")
    monkeypatch.setenv("ARCADE_PILOT_DB_PATH", str(tmp_path / "staff-pilot.sqlite3"))
    monkeypatch.setenv("APP_SECRET_KEY", "test-only-pilot-key")
    get_settings.cache_clear()
    pilot.pilot_store.cache_clear()
    monkeypatch.setattr(pilot, "AsyncSessionLocal", context["factory"])
    app = FastAPI()
    app.include_router(pilot.make_pilot_router(), prefix="/arcade")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c, context, pilot.pilot_store()
    finally:
        pilot.pilot_store.cache_clear()
        get_settings.cache_clear()


def auth(max_id, tenant="test"):
    return {"X-Miniapp-Token": issue_miniapp_token(max_user_id=max_id, tenant_slug=tenant)}


async def test_only_allowed_signed_staff_can_access_and_identity_cannot_be_selected(private_arcade):
    c, ctx, store = private_arcade
    async with ctx["factory"]() as db:
        links_before = await db.scalar(select(func.count()).select_from(StudentAccessLink))
        balance_before = await db.scalar(select(func.sum(Wallet.balance)))
    assert (await c.get("/arcade/profile")).status_code == 401
    assert (
        await c.get("/arcade/profile?max_user_id=910001", headers=auth(910003))
    ).status_code == 403
    assert (await c.get("/arcade/profile", headers=auth(910004))).status_code == 403
    assert (await c.get("/arcade/profile", headers=auth(910001, "wrong-school"))).status_code == 403
    first = (await c.get("/arcade/profile?player=pilot:910002", headers=auth(910001))).json()
    second = (await c.get("/arcade/profile", headers=auth(910002))).json()
    assert first["player"]["id"] == "pilot:910001"
    assert second["player"]["id"] == "pilot:910002"
    payload = dict(game="drop", mode="practice", device="keyboard")
    session = (await c.post("/arcade/sessions", headers=auth(910001), json=payload)).json()
    denied = await c.post(f"/arcade/sessions/{session['id']}/clock/start", headers=auth(910002))
    assert denied.status_code == 400
    assert (
        await c.post(
            "/arcade/sessions", headers=auth(910002), json={**payload, "player": "pilot:910001"}
        )
    ).status_code == 422
    async with ctx["factory"]() as db:
        assert await db.scalar(select(func.count()).select_from(StudentAccessLink)) == links_before
        assert await db.scalar(select(func.sum(Wallet.balance))) == balance_before
    with store.db() as db:
        assert {r[0] for r in db.execute("SELECT id FROM arcade_players")} == {
            "pilot:910001",
            "pilot:910002",
        }


async def test_revoking_staff_access_also_revokes_games(private_arcade):
    c, ctx, _ = private_arcade
    assert (await c.get("/arcade/profile", headers=auth(910001))).status_code == 200
    async with ctx["factory"]() as db:
        await db.execute(update(StaffRoleAssignment).values(status=AssignmentStatus.REVOKED))
        await db.commit()
    assert (await c.get("/arcade/profile", headers=auth(910001))).status_code == 403


def test_pilot_is_disabled_by_default_and_template_preserves_other_content():
    assert not get_settings().arcade_pilot_enabled
    path = Path(__file__).parents[1] / "app/web/static/miniapp/index.html"
    before = path.read_text(encoding="utf8")
    after = inject_pilot(before, [53364725, 472128157])
    assert after.count('id="gamesRoot"') == 1
    assert after.count("app-arcade-pilot.js") == 1
    assert "app-connections-export.js" in after
    assert "app-help-media-catalog.js" in after
    assert (
        after.index("app-core.js")
        < after.index("app-arcade-pilot.js")
        < after.index("app-shell.js")
    )
    assert "53364725" in after and "472128157" in after
    manifest = json.loads((path.parent / "arcade-assets.json").read_text())
    for url in manifest["styles"] + manifest["scripts"]:
        assert (path.parent / url.split("/")[-1].split("?")[0]).is_file()
