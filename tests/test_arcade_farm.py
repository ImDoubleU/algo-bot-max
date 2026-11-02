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


def test_old_farm_migrates_without_changing_money_items_or_progress(farm):
    original = act(farm, "buy", "beds")["farm"]
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
        for key in (
            "compost",
            "windmill",
            "pond",
            "tractor",
            "nursery",
            "railway",
            "workshop",
            "logistics",
            "seedlab",
        ):
            del state["items"][key]
        for key in ("chapters", "order", "deliveries", "best_streak"):
            del state[key]
        del state["daily"]["deliveries"]
        state["version"] = 1
        farm._save(db, "p1", state)
    upgraded = farm.get("p1")
    assert upgraded["balance"] == original["balance"] == 30
    assert upgraded["stats"] == original["stats"]
    assert upgraded["version"] == 2 and upgraded["deliveries"] == 0
    assert len(upgraded["items"]) == 21 and len(upgraded["roadmap"]) == 30
    assert farm.board("p1")["me"]["per_hour"] == 210


def test_upgrade_projection_matches_actual_purchase_and_income_breakdown(farm):
    seed(farm, balance=10000000, earned=3000000)
    for key in (
        "beds",
        "gloves",
        "irrigation",
        "well",
        "silo",
        "tractor",
        "compost",
        "windmill",
        "workshop",
        "logistics",
        "seedlab",
    ):
        before = farm.get("p1")
        offer = next(i for i in before["items"] if i["id"] == key)
        after = act(farm, "buy", key)["farm"]
        assert after["stats"]["per_hour"] - before["stats"]["per_hour"] == offer["per_hour_gain"]
        actual = next(i for i in after["items"] if i["id"] == key)
        assert offer["effect"]["next"] == actual["effect"]["current"]
        production = after["production"]
        assert (
            production["base"]
            + sum(r["amount"] for r in production["sources"])
            + production["bonus"]
            == after["stats"]["per_hour"]
        )
    assert next(i for i in after["items"] if i["id"] == "railway")["locked"] is False


def test_manual_tools_grow_with_the_farm_and_breakdown_matches_real_harvest(farm):
    state = farm.get("p1")
    items = {i["id"]: 0 for i in state["items"]}
    items.update(shovel=10, gloves=5, tractor=4, workshop=2, beds=15, orchard=10)
    seed(farm, balance=10000000, earned=3000000, items=items)
    before = farm.get("p1")
    v = before["stats"]
    assert v["base_tap"] > 1000
    assert v["tap_flat"] + v["tap_income"] + v["tap_gloves"] + v["tap_workshop"] == v["base_tap"]
    assert act(farm, "tap")["result"]["amount"] == v["base_tap"]
    offer = next(i for i in before["items"] if i["id"] == "irrigation")
    after = act(farm, "buy", "irrigation")["farm"]
    assert after["stats"]["base_tap"] > v["base_tap"]
    assert after["stats"]["base_tap"] - v["base_tap"] == offer["manual_gain_from_income"]
    act(farm, "boost")
    assert act(farm, "tap")["result"]["amount"] == 2 * after["stats"]["base_tap"]
    assert farm.arcade.profile("p1")["balance"] == 0


def test_energy_upgrade_capacity_and_regeneration_use_the_advertised_rate(farm):
    seed(farm, balance=1000000, earned=8000)
    act(farm, "buy", "battery")
    upgraded = act(farm, "buy", "well")["farm"]
    assert upgraded["stats"]["energy_max"] == 1250
    assert upgraded["stats"]["energy_per_second"] == 1.5
    seed(farm, energy_milli=0, energy_carry=0)
    farm.arcade.clock.advance(2)
    assert farm.get("p1")["energy"] == 3
    farm.arcade.clock.advance(10000)
    assert farm.get("p1")["energy"] == 1250


def test_business_income_multipliers_stack_and_seedlab_improves_existing_buildings(farm):
    state = farm.get("p1")
    items = {i["id"]: 0 for i in state["items"]}
    items.update(irrigation=1, market=1, compost=1)
    seed(farm, balance=1000000, earned=3000000, items=items)
    before = farm.get("p1")
    assert before["stats"]["per_hour"] == 182  # 120 × 1.15 × 1.10 × 1.20, rounded down.
    act(farm, "buy", "beds")
    act(farm, "buy", "beds")
    before = farm.get("p1")
    offer = next(i for i in before["items"] if i["id"] == "seedlab")
    after = act(farm, "buy", "seedlab")["farm"]
    assert after["stats"]["growth_percent"] == 12.5
    assert after["stats"]["per_hour"] > before["stats"]["per_hour"]
    assert after["stats"]["per_hour"] - before["stats"]["per_hour"] == offer["per_hour_gain"]


def test_logistics_shortens_future_deliveries_with_full_profit_and_keeps_current_timer(farm):
    seed(farm, balance=100000000, earned=3000000)
    order = act(farm, "start_order", "basket")["farm"]["order"]
    upgraded = act(farm, "buy", "logistics")["farm"]
    assert upgraded["order"] == order
    offer = next(o for o in upgraded["orders"] if o["id"] == "basket")
    assert offer["seconds"] == 288 and offer["reward"] == order["reward"]
    act(farm, "cancel_order", order["delivery_id"])
    new = act(farm, "start_order", "basket")["farm"]["order"]
    assert new["finish_at"] - new["started_at"] == 288000
    for _ in range(9):
        upgraded = act(farm, "buy", "logistics")["farm"]
    assert upgraded["stats"]["delivery_speed"] == 40
    assert next(o for o in upgraded["orders"] if o["id"] == "basket")["seconds"] == 180
    assert upgraded["order"] == new


def test_orders_use_server_time_and_one_delivery_slot_and_receipts(farm):
    farm.get("p1")
    with pytest.raises(ArcadeError):
        act(farm, "start_order", "fair")
    key = str(uuid.uuid4())
    started = act(farm, "start_order", "basket", key=key)
    assert started["farm"]["balance"] == 110
    assert act(farm, "start_order", "basket", key=key)["duplicate"]
    with pytest.raises(ArcadeError):
        act(farm, "start_order", "basket")
    with pytest.raises(ArcadeError):
        act(farm, "claim_order", "basket")
    farm.arcade.clock.advance(299)
    with pytest.raises(ArcadeError):
        act(farm, "claim_order", "basket")
    farm.arcade.clock.advance(1)
    restarted = FarmStore(ArcadeStore(farm.arcade.path, farm.arcade.clock))
    key = str(uuid.uuid4())
    result = act(restarted, "claim_order", "basket", key=key)
    assert result["result"]["amount"] == 180
    assert result["farm"]["deliveries"] == 1 and result["farm"]["order"] is None
    assert act(restarted, "claim_order", "basket", key=key)["duplicate"]
    with pytest.raises(ArcadeError):
        act(restarted, "claim_order", "basket")
    assert farm.get("p2")["deliveries"] == 0


def test_order_profit_grows_with_income_and_trust_but_started_reward_is_fixed(farm):
    start = farm.get("p1")
    offers = {o["id"]: o for o in start["orders"]}
    assert offers["basket"]["profit"] == 140
    assert offers["basket"]["reward"] == offers["basket"]["cost"] + 140
    act(farm, "start_order", "basket")
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
        state["earned"] = 100000
        state["items"].update(beds=10, orchard=5, market=3)
        state["deliveries"] = 15
        farm._save(db, "p1", state)
    grown = farm.get("p1")
    assert grown["neighbors"]["bonus"] == 10
    for offer in grown["orders"]:
        old = offers[offer["id"]]
        assert offer["profit"] > old["profit"]
        assert offer["cost"] == old["cost"]  # No hidden increase in the required supplies.
    assert grown["order"]["reward"] == 180
    farm.arcade.clock.advance(300)
    assert act(farm, "claim_order", "basket")["result"]["amount"] == 180


@pytest.mark.parametrize("elapsed", [0, 600])
def test_cancel_delivery_refunds_supplies_once_without_profit_or_delivery_progress(farm, elapsed):
    order = act(farm, "start_order", "basket")["farm"]["order"]
    farm.arcade.clock.advance(elapsed)
    before = farm.get("p1")
    key = str(uuid.uuid4())
    result = act(farm, "cancel_order", order["delivery_id"], key=key)
    after = result["farm"]
    assert result["result"]["amount"] == order["cost"] == 40
    assert after["balance"] == before["balance"] + 40
    assert after["earned"] == before["earned"] and after["deliveries"] == 0
    assert not next(q for q in after["quests"] if q["id"] == "delivery")["ready"]
    assert not next(b for b in after["badges"] if b["id"] == "orders_1")["ready"]
    assert after["order"] is None
    assert act(farm, "cancel_order", order["delivery_id"], key=key)["duplicate"]
    with pytest.raises(ArcadeError):
        act(farm, "cancel_order", order["delivery_id"])
    new = act(farm, "start_order", "basket")["farm"]
    assert new["order"]["delivery_id"] != order["delivery_id"]
    # A late acknowledgement or an old confirmation must never cancel the next delivery.
    duplicate = act(farm, "cancel_order", order["delivery_id"], key=key)
    assert duplicate["farm"]["order"] == new["order"]
    assert duplicate["farm"]["balance"] == new["balance"]
    with pytest.raises(ArcadeError):
        act(farm, "cancel_order", order["delivery_id"])
    assert farm.get("p1")["order"] == new["order"]
    assert farm.arcade.profile("p1")["balance"] == 0


def test_existing_delivery_can_be_cancelled_after_restart_at_its_original_cost(farm):
    order = act(farm, "start_order", "basket")["farm"]["order"]
    del order["delivery_id"]
    order["cost"] = 27
    seed(farm, balance=123, order=order)
    restarted = FarmStore(ArcadeStore(farm.arcade.path, farm.arcade.clock))
    token = restarted.get("p1")["order"]["delivery_id"]
    assert token == restarted.get("p1")["order"]["delivery_id"]
    other = act(farm, "start_order", "basket", player="p2")["farm"]
    with pytest.raises(ArcadeError):
        act(restarted, "cancel_order", token, player="p2")
    assert farm.get("p2")["balance"] == other["balance"]
    result = act(restarted, "cancel_order", token)
    assert result["result"]["amount"] == 27 and result["farm"]["balance"] == 150


def test_delivery_collection_and_cancellation_race_can_pay_only_one_result(farm):
    order = act(farm, "start_order", "basket")["farm"]["order"]
    farm.arcade.clock.advance(300)
    before = farm.get("p1")

    def attempt(action):
        try:
            return act(farm, action, order["delivery_id"] if action == "cancel_order" else "basket")
        except ArcadeError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, ["cancel_order", "claim_order"] * 2))
    successes = [r for r in results if r]
    assert len(successes) == 1
    amount = successes[0]["result"]["amount"]
    assert amount in (order["cost"], order["reward"])
    after = farm.get("p1")
    assert after["balance"] == before["balance"] + amount
    assert after["deliveries"] == (1 if amount == order["reward"] else 0)
    assert after["order"] is None


def test_collect_all_clears_ready_badges_and_keeps_them_in_the_collection(farm):
    seed(farm, earned=1200)
    assert next(b for b in farm.get("p1")["badges"] if b["id"] == "first_harvest")["ready"]
    after = act(farm, "claim_all")["farm"]
    badge = next(b for b in after["badges"] if b["id"] == "first_harvest")
    assert badge["claimed"] and not badge["ready"]
    assert not after["claimable"]["count"]
    restarted = FarmStore(ArcadeStore(farm.arcade.path, farm.arcade.clock))
    assert not restarted.get("p1")["claimable"]["count"]


def test_collect_all_includes_cascading_chapters_order_and_quests_exactly_once(farm):
    state = farm.get("p1")
    items = {i["id"]: 0 for i in state["items"]}
    items.update(shovel=2, beds=1)
    seed(farm, balance=1000, earned=1200, items=items)
    act(farm, "start_order", "basket")
    farm.arcade.clock.advance(300)
    before = farm.get("p1")
    expected = before["claimable"]
    key = str(uuid.uuid4())
    result = act(farm, "claim_all", key=key)
    after = result["farm"]
    assert result["result"]["amount"] == expected["amount"]
    assert result["result"]["count"] == expected["count"]
    assert after["balance"] == before["balance"] + expected["amount"]
    assert after["claimable"] == {"count": 0, "amount": 0}
    assert after["earned"] == before["earned"]  # No experience from gifts.
    assert after["deliveries"] == 1
    assert [c["id"] for c in after["chapters"] if c["claimed"]] == [
        "start",
        "build",
        "neighbour",
        "harvest",
    ]
    assert act(farm, "claim_all", key=key)["duplicate"]
    assert act(farm, "claim_all")["result"]["amount"] == 0
    with pytest.raises(ArcadeError):
        act(farm, "claim_quest", "delivery")


def test_collect_all_concurrent_clients_cannot_duplicate_rewards(farm):
    expected = farm.get("p1")["claimable"]["amount"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: act(farm, "claim_all"), range(4)))
    assert sum(r["result"]["amount"] for r in results) == expected == 100
    assert farm.get("p1")["balance"] == 250
    assert farm.arcade.profile("p1")["balance"] == 0


def test_chapters_require_the_previous_chapter_and_bonus_does_not_unlock_levels(farm):
    seed(farm, balance=100000, earned=1000)
    with pytest.raises(ArcadeError):
        act(farm, "claim_chapter", "harvest")
    after = act(farm, "claim_chapter", "start")["farm"]
    assert after["level"] == 3 and after["earned"] == 1000
    with pytest.raises(ArcadeError):
        act(farm, "claim_chapter", "start")
    with pytest.raises(ArcadeError):
        act(farm, "claim_chapter", "build")


def test_collect_all_seventh_gift_also_claims_new_streak_achievement(farm):
    farm.get("p1")
    yesterday = (datetime.fromtimestamp(farm.arcade.clock(), MOSCOW).date()).isoformat()
    seed(farm, daily_last=yesterday, streak=6, best_streak=6)
    farm.arcade.clock.advance(86400)
    before = farm.get("p1")
    after = act(farm, "claim_all")
    assert after["result"]["amount"] == before["claimable"]["amount"]
    assert next(b for b in after["farm"]["badges"] if b["id"] == "streak_7")["claimed"]
    assert after["farm"]["daily"]["streak"] == 7


def test_first_farm_starts_production_without_a_purchase_and_uses_no_ac(farm):
    before = farm.arcade.profile("p1")
    state = farm.get("p1")
    assert state["balance"] == 150 and state["stats"]["per_hour"] == 120
    assert state["stats"]["offline_hours"] == 4 and state["energy"] == 500
    assert len(state["items"]) == 21 and len(state["quests"]) == 7
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
    assert bought["stats"]["offline_hours"] == 8
    farm.arcade.clock.advance(12 * 3600)
    assert farm.get("p1")["offline"]["amount"] == 960
    seed(farm, balance=1000000)
    for _ in range(9):
        act(farm, "buy", "silo")
    assert farm.get("p1")["stats"]["offline_hours"] == 44


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
