"""Authenticated arcade routes mounted exclusively by the loopback demo CLI."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.arcade import GAMES, ArcadeError, ArcadeStore
from app.services.arcade_farm import FarmStore
from app.services.arcade_hill import HillStore


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NewSession(StrictPayload):
    arena: str | None = Field(default=None, max_length=20)
    stage: int | None = Field(default=None, ge=1, le=24, strict=True)
    game: str = Field(max_length=20)
    mode: str = Field(pattern="^(ranked|practice|journey)$")
    device: str = Field(pattern="^(keyboard|touch)$")


class Finish(StrictPayload):
    actions: list[dict[str, Any]] = Field(max_length=20000)
    ticks: int = Field(ge=0, le=216000, strict=True)
    abandoned: bool = False


class Claim(StrictPayload):
    id: str = Field(max_length=160)


class Preferences(StrictPayload):
    values: dict[str, Any]


class Policy(StrictPayload):
    cap: int = Field(ge=100, le=1000, strict=True)


class FarmAction(StrictPayload):
    id: str = Field(min_length=12, max_length=80)
    action: str = Field(max_length=20)
    item: str | None = Field(default=None, max_length=40)
    count: int = Field(default=1, ge=1, le=20, strict=True)


class GarageAction(StrictPayload):
    id: str = Field(min_length=12, max_length=80)
    action: str = Field(max_length=20)
    item: str | None = Field(default=None, max_length=40)


def make_router(store: ArcadeStore, authenticate: Callable[[Request], Awaitable[dict]]):
    router = APIRouter()
    farm = FarmStore(store)
    garage = HillStore(store)

    async def call(method, *args):
        try:
            return await asyncio.to_thread(method, *args)
        except ArcadeError as error:
            raise HTTPException(400, str(error)) from error

    @router.get("/profile")
    async def profile(request: Request):
        actor = await authenticate(request)
        return await call(store.profile, actor["player"])

    @router.get("/farm")
    async def get_farm(request: Request):
        actor = await authenticate(request)
        return await call(farm.get, actor["player"])

    @router.get("/garage")
    async def get_garage(request: Request):
        actor = await authenticate(request)
        return await call(garage.get, actor["player"])

    @router.post("/garage/actions")
    async def garage_action(request: Request, payload: GarageAction):
        actor = await authenticate(request)
        return await call(garage.act, actor["player"], payload.id, payload.action, payload.item)

    @router.post("/farm/actions")
    async def farm_action(request: Request, payload: FarmAction):
        actor = await authenticate(request)
        return await call(
            farm.act, actor["player"], payload.id, payload.action, payload.item, payload.count
        )

    @router.get("/farm/board")
    async def farm_board(request: Request):
        actor = await authenticate(request)
        return await call(farm.board, actor["player"])

    @router.get("/boards")
    async def boards(
        request: Request, game: str = "overall", period: str = "week", device: str = "keyboard"
    ):
        await authenticate(request)
        if (
            game not in {"overall", *GAMES}
            or period not in ("week", "all")
            or device not in ("keyboard", "touch")
        ):
            raise HTTPException(400, "Неизвестный рейтинг.")
        return await call(store.board, game, period, device)

    @router.post("/sessions")
    async def create(request: Request, payload: NewSession):
        actor = await authenticate(request)
        return await call(
            store.session,
            actor["player"],
            payload.game,
            payload.mode,
            payload.device,
            payload.stage,
            payload.arena,
        )

    @router.post("/sessions/{session}/clock/{action}")
    async def clock(request: Request, session: str, action: str):
        actor = await authenticate(request)
        return await call(store.clock_action, actor["player"], session, action)

    @router.post("/sessions/{session}/finish")
    async def finish(request: Request, session: str, payload: Finish):
        actor = await authenticate(request)
        return await call(
            store.finish,
            actor["player"],
            session,
            payload.actions,
            payload.ticks,
            payload.abandoned,
        )

    @router.post("/claims")
    async def claim(request: Request, payload: Claim):
        actor = await authenticate(request)
        return await call(store.claim, actor["player"], payload.id)

    @router.patch("/settings")
    async def settings(request: Request, payload: Preferences):
        actor = await authenticate(request)
        return await call(store.settings, actor["player"], payload.values)

    @router.patch("/policy")
    async def policy(request: Request, payload: Policy):
        actor = await authenticate(request)
        if not actor.get("director"):
            raise HTTPException(403, "Лимит настраивает директор.")
        return await call(store.policy, payload.cap)

    @router.get("/replay/{run}")
    async def replay(request: Request, run: str):
        actor = await authenticate(request)
        return await call(store.replay, actor["player"], run)

    return router
