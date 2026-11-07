"""Research unlocks, honest stat previews and later resource progression."""

import copy
import math

import pytest

from app.services.arcade import ArcadeError
from tests.test_arcade_farm import act, seed
from tests.test_arcade_farm import farm as farm


def test_research_has_a_real_cap_unlocks_next_nodes_and_never_needs_greenhouses(farm):
    seed(farm, earned=10**15, balance=10**12, resources=dict(seeds=10000, materials=10000))
    for key in (
        "garden_notes",
        "seed_sorting",
        "trail_maps",
        "soil_calendar",
        "challenge_training",
    ):
        for n in range(3):
            before = farm.get("p1")
            offer = next(r for r in before["activities"]["research"] if r["id"] == key)
            assert offer["level"] == n and not offer["locked"] and not offer["maxed"]
            after = act(farm, "research", key)["farm"]
            bought = next(r for r in after["activities"]["research"] if r["id"] == key)
            assert bought["level"] == n + 1
            assert bought["effect"]["current"] == offer["effect"]["next"]
            for resource in ("seeds", "materials"):
                assert (
                    after["activities"]["resources"][resource]
                    == before["activities"]["resources"][resource] - offer[resource]
                )
        assert bought["maxed"] and bought["effect"]["gain"] == 0
        resources = after["activities"]["resources"]
        with pytest.raises(ArcadeError, match="3/3"):
            act(farm, "research", key)
        assert farm.get("p1")["activities"]["resources"] == resources
    assert not any(i["level"] for i in farm.get("p1")["items"])


def test_research_explains_missing_prerequisite_and_level(farm):
    before = farm.get("p1")
    offer = next(r for r in before["activities"]["research"] if r["id"] == "seed_sorting")
    assert offer["lock_reasons"] == ["С 12 уровня", "Нужно: Записки садовода 1/3"]
    with pytest.raises(ArcadeError, match="Записки садовода 1/3"):
        act(farm, "research", "seed_sorting")


def test_percent_upgrades_preview_actual_income_and_delivery_time(farm):
    seed(farm, earned=10**15, balance=10**12)
    act(farm, "buy", "beds")
    act(farm, "buy", "beds")
    for key in ("gloves", "workshop", "irrigation", "market", "compost", "seedlab", "logistics"):
        before = farm.get("p1")
        offer = next(i for i in before["items"] if i["id"] == key)
        after = act(farm, "buy", key)["farm"]
        actual = next(i for i in after["items"] if i["id"] == key)
        assert offer["effect"]["next"] == actual["effect"]["current"]
        assert offer["effect"]["unit"] != "%"
        if key == "logistics":
            order = next(o for o in after["orders"] if o["id"] == "fair")
            assert offer["effect"]["next"] == order["seconds"]
        elif key == "seedlab":
            assert (
                offer["effect"]["gain"]
                == after["stats"]["per_hour"] - before["stats"]["per_hour"]
                > 0
            )


@pytest.mark.parametrize("maps,lighthouse", [(0, 0), (3, 0), (0, 10), (3, 10)])
def test_later_routes_always_have_better_material_yield(farm, maps, lighthouse):
    seed(farm, earned=10**15)
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
        state["research"]["trail_maps"] = maps
        state["items"].update(lighthouse=lighthouse, balloon=1, highland=1)
        farm._save(db, "p1", state)
    routes = farm.get("p1")["activities"]["routes"]
    rates = [r["materials_per_hour"] for r in routes]
    assert len(rates) == 5 and all(b > a for a, b in zip(rates, rates[1:], strict=False))
    if maps == lighthouse == 0:
        assert rates == [9, 18, 24, 45, 60]


def test_new_routes_enforce_buildings_and_pay_the_advertised_reward_once(farm):
    seed(farm, earned=10**15, balance=10**12, resources=dict(seeds=10000, materials=10000))
    with pytest.raises(ArcadeError, match="Горная ферма"):
        act(farm, "start_expedition", "highland")
    act(farm, "buy", "highland")
    act(farm, "buy", "lighthouse")
    for key in ("highland", "summit"):
        farm.arcade.clock.advance(1000)
        before = farm.get("p1")
        offer = next(r for r in before["activities"]["routes"] if r["id"] == key)
        p = act(farm, "start_expedition", key)["farm"]["activities"]["projects"]["expedition"]
        assert p["reward_materials"] == offer["materials"]
        farm.arcade.clock.advance(p["seconds"])
        result = act(farm, "claim_project", p["project_id"], key=f"collect-{key}")
        assert (
            result["farm"]["activities"]["resources"]["materials"]
            == before["activities"]["resources"]["materials"] + offer["materials"]
        )
        assert act(farm, "claim_project", p["project_id"], key=f"collect-{key}")["duplicate"]


def test_rebalance_preserves_previously_dispatched_reward_and_timer(farm):
    seed(farm, earned=10**15, balance=10**12, resources=dict(seeds=100, materials=100))
    act(farm, "buy", "balloon")
    act(farm, "start_expedition", "sky")
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
        state["projects"]["expedition"]["reward_materials"] = 36
        before = copy.deepcopy(state)
        farm._save(db, "p1", state)
    after = farm.get("p1")
    assert after["activities"]["projects"]["expedition"] == before["projects"]["expedition"]
    farm.arcade.clock.advance(math.ceil(before["projects"]["expedition"]["seconds"]))
    result = act(farm, "claim_project", before["projects"]["expedition"]["project_id"])
    assert result["result"]["rewards"][0]["materials"] == 36


def test_trust_percentage_shows_exact_extra_carrots_without_changing_order_profit(farm):
    seed(farm, earned=10**15, deliveries=0)
    baseline = {o["id"]: o for o in farm.get("p1")["orders"]}
    seed(farm, deliveries=30)
    for offer in farm.get("p1")["orders"]:
        assert offer["bonus"] == 15
        assert offer["bonus_amount"] == offer["profit"] - baseline[offer["id"]]["profit"]
