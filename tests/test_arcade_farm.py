"""Persistent carrots: trusted time, exactly-once credits, ownership and offline storage."""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.api.routes.arcade_preview import make_router
from app.services.arcade import MOSCOW, ArcadeError, ArcadeStore
from app.services.arcade_farm import FarmStore


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 2, 12, tzinfo=MOSCOW).timestamp()

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def farm(tmp_path):
    store = ArcadeStore(tmp_path / "farm.sqlite3", Clock())
    store.register(
        [
            {"id": "p1", "name": "Марк", "group": "Демо"},
            {"id": "p2", "name": "Даша", "group": "Демо"},
        ]
    )
    return FarmStore(store)


def act(farm, action, item=None, count=1, player="p1", key=None):
    return farm.act(player, key or str(uuid.uuid4()), action, item, count)


def seed(farm, **fields):
    farm.get("p1")
    with farm.arcade.db() as db:
        state = json.loads(
            db.execute("SELECT state FROM kopatych_farms WHERE player='p1'").fetchone()[0]
        )
        state.update(fields)
        farm._save(db, "p1", state)


def test_first_farm_starts_production_without_a_purchase_and_uses_no_ac(farm):
    before = farm.arcade.profile("p1")
    state = farm.get("p1")
    assert state["balance"] == 150 and state["stats"]["per_hour"] == 120
    assert state["stats"]["offline_hours"] == 4 and state["energy"] == 500
    assert len(state["items"]) == 12 and len(state["quests"]) == 3
    act(farm, "tap", count=8)
    assert farm.arcade.profile("p1")["balance"] == before["balance"] == 0
    assert not farm.arcade.profile("p1")["awards"]
    with pytest.raises(ArcadeError):
        farm.get("not-a-player")


def test_offline_two_hours_credited_once_and_survives_server_restart(farm):
    farm.get("p1")
    farm.arcade.clock.advance(7200)
    result = farm.get("p1")
    assert result["offline"]["amount"] == 240 and result["balance"] == 390
    assert result["offline"]["seconds"] == 7200 and not result["offline"]["capped"]
    assert farm.get("p1")["offline"]["amount"] == 0
    restarted = FarmStore(ArcadeStore(farm.arcade.path, farm.arcade.clock))
    assert restarted.get("p1")["balance"] == 390
    assert restarted.get("p2")["balance"] == 150


def test_storage_caps_absence_and_barn_extends_it_only_after_purchase(farm):
    farm.get("p1")
    farm.arcade.clock.advance(12 * 3600)
    result = farm.get("p1")
    assert result["offline"]["amount"] == 480 and result["offline"]["capped"]
    assert result["offline"]["credited_seconds"] == 4 * 3600
    bought = act(farm, "buy", "silo")["farm"]
    assert bought["stats"]["offline_hours"] == 6
    farm.arcade.clock.advance(12 * 3600)
    assert farm.get("p1")["offline"]["amount"] == 720
    seed(farm, balance=1000000)
    for _ in range(9):
        act(farm, "buy", "silo")
    assert farm.get("p1")["stats"]["offline_hours"] == 24


def test_upgrade_settles_old_rate_and_duplicate_purchase_never_charges_twice(farm):
    farm.get("p1")
    farm.arcade.clock.advance(3600)
    key = str(uuid.uuid4())
    response = act(farm, "buy", "beds", key=key)
    assert response["farm"]["balance"] == 150
    assert response["farm"]["stats"]["per_hour"] == 210
    farm.arcade.clock.advance(3600)
    duplicate = act(farm, "buy", "beds", key=key)
    assert duplicate["duplicate"] and duplicate["farm"]["balance"] == 360
    assert next(i for i in duplicate["farm"]["items"] if i["id"] == "beds")["level"] == 1
    with pytest.raises(ArcadeError):
        act(farm, "buy", "shovel", key=key)


def test_taps_are_rate_limited_and_energy_is_shared_across_clients(farm):
    farm.get("p1")
    first = act(farm, "tap", count=20)
    assert first["result"]["accepted"] == 8
    assert act(farm, "tap", count=20)["result"]["accepted"] == 0
    for _ in range(90):
        farm.arcade.clock.advance(1)
        act(farm, "tap", count=8)
    state = farm.get("p1")
    assert state["energy"] == 0 and state["taps"] <= 590
    farm.arcade.clock.advance(3)
    assert act(farm, "tap", count=8)["result"]["accepted"] == 3
    refill = act(farm, "refill")["farm"]
    assert refill["energy"] == 500 and refill["daily"]["refills_left"] == 1
    farm.arcade.clock.advance(1)
    act(farm, "tap", count=8)
    with pytest.raises(ArcadeError):
        act(farm, "refill")


def test_tap_boost_expires_and_does_not_double_offline_production(farm):
    farm.get("p1")
    act(farm, "boost")
    assert act(farm, "tap", count=1)["result"]["amount"] == 2
    with pytest.raises(ArcadeError):
        act(farm, "boost")
    farm.arcade.clock.advance(31)
    assert act(farm, "tap", count=1)["result"]["amount"] == 1
    farm.arcade.clock.advance(3600)
    assert farm.get("p1")["offline"]["amount"] == 120


def test_daily_streak_seven_days_and_missed_day_reset(farm):
    farm.get("p1")
    for day, reward in enumerate([100, 150, 200, 300, 400, 600, 1000], 1):
        response = act(farm, "claim_daily")
        assert response["result"]["amount"] == reward
        assert response["farm"]["daily"]["streak"] == day
        with pytest.raises(ArcadeError):
            act(farm, "claim_daily")
        farm.arcade.clock.advance(86400)
    farm.arcade.clock.advance(86400)
    assert act(farm, "claim_daily")["farm"]["daily"]["streak"] == 1


def test_daily_quests_require_real_actions_and_each_reward_is_once(farm):
    farm.get("p1")
    with pytest.raises(ArcadeError):
        act(farm, "claim_quest", "tap")
    for _ in range(10):
        act(farm, "tap", count=8)
        farm.arcade.clock.advance(1)
    assert act(farm, "claim_quest", "tap")["result"]["amount"] == 120
    with pytest.raises(ArcadeError):
        act(farm, "claim_quest", "tap")
    act(farm, "buy", "shovel")
    act(farm, "buy", "beds")
    assert act(farm, "claim_quest", "upgrade")["result"]["amount"] == 250
    farm.arcade.clock.advance(3600)
    farm.get("p1")
    assert act(farm, "claim_quest", "passive")["result"]["amount"] == 180


def test_daily_combo_is_fixed_and_milestones_do_not_unlock_from_gifts(farm):
    state = farm.get("p1")
    combo = state["daily"]["combo"]
    assert len(combo) == 3 and set(combo) == {"shovel", "battery", "beds"}
    seed(farm, balance=100000)
    with pytest.raises(ArcadeError):
        act(farm, "claim_badge", "first_harvest")
    with pytest.raises(ArcadeError):
        act(farm, "claim_quest", "combo")
    for item in combo:
        act(farm, "buy", item)
    assert farm.get("p1")["daily"]["combo"] == combo
    assert act(farm, "claim_quest", "combo")["result"]["amount"] == 600
    with pytest.raises(ArcadeError):
        act(farm, "claim_quest", "combo")
    farm.arcade.clock.advance(4 * 3600)
    # Income and real tapping, rather than the seeded spending balance, open levels.
    state = farm.get("p1")
    farm.arcade.clock.advance(3600)
    state = farm.get("p1")
    assert state["earned"] >= 1000
    assert act(farm, "claim_badge", "first_harvest")["result"]["amount"] == 300
    with pytest.raises(ArcadeError):
        act(farm, "claim_badge", "first_harvest")


def test_concurrent_offline_reads_and_daily_claims_do_not_multiply_rewards(farm):
    farm.get("p1")
    farm.arcade.clock.advance(4 * 3600)
    with ThreadPoolExecutor(max_workers=6) as pool:
        snapshots = list(pool.map(lambda _: farm.get("p1"), range(6)))
    assert sum(s["offline"]["amount"] for s in snapshots) == 480
    assert farm.get("p1")["balance"] == 630

    def claim(_):
        try:
            return act(farm, "claim_daily")["result"]["amount"]
        except ArcadeError:
            return 0

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(claim, range(6))) == 100
    assert farm.get("p1")["balance"] == 730


def test_duplicate_tap_receipt_is_idempotent_even_with_a_new_server(farm):
    farm.get("p1")
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(lambda _: act(farm, "tap", count=8, key=key), range(6)))
    assert len([r for r in rows if not r["duplicate"]]) == 1
    assert farm.get("p1")["taps"] == 8 and farm.get("p1")["balance"] == 158
    restarted = FarmStore(ArcadeStore(farm.arcade.path, farm.arcade.clock))
    assert act(restarted, "tap", count=8, key=key)["duplicate"]
    assert restarted.get("p1")["taps"] == 8


def test_viewing_somebody_elses_leaderboard_never_extends_their_offline_cap(farm):
    farm.get("p1")
    farm.get("p2")
    for _ in range(12):
        farm.arcade.clock.advance(3600)
        board = farm.board("p2")
        assert next(r for r in board["rows"] if r["player"] == "p1")["earned"] <= 480
    with farm.arcade.db() as db:
        assert (
            db.execute("SELECT COUNT(*) FROM kopatych_events WHERE player='p1'").fetchone()[0] == 1
        )
    assert farm.get("p1")["offline"]["amount"] == 480


def test_fractional_production_is_not_lost_by_frequent_polls(farm):
    farm.get("p1")
    farm.get("p2")
    for _ in range(360):
        farm.arcade.clock.advance(10)
        farm.get("p1")
    assert farm.get("p1")["earned"] == farm.get("p2")["earned"] == 120


def test_backwards_clock_cannot_repeat_income_or_daily_gifts(farm):
    farm.get("p1")
    act(farm, "claim_daily")
    farm.arcade.clock.advance(3600)
    assert farm.get("p1")["offline"]["amount"] == 120
    farm.arcade.clock.advance(-7200)
    assert farm.get("p1")["offline"]["amount"] == 0
    with pytest.raises(ArcadeError):
        act(farm, "claim_daily")
    farm.arcade.clock.advance(7200)
    assert farm.get("p1")["offline"]["amount"] == 0


def test_locked_and_unaffordable_upgrades_do_not_spend_anything(farm):
    state = farm.get("p1")
    for item in ("orchard", "battery", "no-item"):
        with pytest.raises(ArcadeError):
            act(farm, "buy", item)
    assert farm.get("p1")["balance"] == state["balance"]
    with pytest.raises(ArcadeError):
        act(farm, "tap", count=True)


def test_farm_api_uses_authenticated_owner_and_rejects_client_balances(farm):
    app = FastAPI()

    async def auth(request: Request):
        player = request.headers.get("x-player")
        if player not in ("p1", "p2"):
            raise HTTPException(401, "Нет доступа")
        return {"player": player}

    app.include_router(make_router(farm.arcade, auth), prefix="/arcade")
    client = TestClient(app)
    assert client.get("/arcade/farm").status_code == 401
    assert client.get("/arcade/farm", headers={"x-player": "p1"}).json()["player"] == "p1"
    assert (
        client.post(
            "/arcade/farm/actions",
            headers={"x-player": "p1"},
            json={
                "id": str(uuid.uuid4()),
                "action": "tap",
                "count": 5,
                "balance": 999999,
                "player": "p2",
            },
        ).status_code
        == 422
    )
    response = client.post(
        "/arcade/farm/actions",
        headers={"x-player": "p1"},
        json={"id": str(uuid.uuid4()), "action": "tap", "count": 5},
    )
    assert response.status_code == 200 and response.json()["farm"]["taps"] == 5
    assert client.get("/arcade/farm", headers={"x-player": "p2"}).json()["taps"] == 0


def test_offline_production_is_calculated_after_server_was_stopped(farm):
    farm.get("p1")
    farm.arcade.clock.advance(7200)
    restarted = FarmStore(ArcadeStore(farm.arcade.path, farm.arcade.clock))
    state = restarted.get("p1")
    assert state["offline"]["amount"] == 240
    assert state["balance"] == 390
    assert farm.get("p1")["offline"]["amount"] == 0
