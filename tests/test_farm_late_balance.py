"""Early farming is exact; late factory scaling cannot multiply clicks indefinitely."""

import copy
import math

import pytest

from app.services.arcade_farm import stats, tap_income_basis
from tests.test_arcade_farm import act, seed
from tests.test_arcade_farm import farm as farm


def legacy_tap(v, items):
    production = v["per_hour"]
    raw = (
        v["tap_flat"]
        + production * items["shovel"] // 400000
        + production * items["tractor"] // 160000
    )
    gloves = max(items["gloves"], raw * 12 * items["gloves"] // 100)
    return (raw + gloves) * (100 + 6 * items["workshop"]) // 100


def test_small_farms_keep_the_existing_click_rewards_and_late_income_still_grows(farm):
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
    for count in [0, 1, 3, 5]:
        state["items"].update(shovel=count, tractor=count, gloves=count, workshop=count, beds=count)
        value = stats(state, state["last_ms"])
        assert value["per_hour"] < 100000
        assert value["base_tap"] == legacy_tap(value, state["items"])
    assert tap_income_basis(99999) == 99999 and tap_income_basis(100000) == 100000
    assert tap_income_basis(100001) == 100000
    assert tap_income_basis(100000000) > tap_income_basis(1000000) > 100000
    assert tap_income_basis(100000000) < 1000000


@pytest.mark.parametrize("sorting", [0, 1, 2, 3])
def test_later_seed_varieties_have_better_hourly_yield_at_every_research_level(farm, sorting):
    seed(farm, earned=1000000000)
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
        state["research"]["seed_sorting"] = sorting
        farm._save(db, "p1", state)
    crops = farm.get("p1")["activities"]["crops"]
    assert [c["seeds"] for c in crops] == [1 * (1 + sorting), 6 * (1 + sorting), 30 * (1 + sorting)]
    assert [c["seeds_per_hour"] for c in crops] == [
        6 * (1 + sorting),
        8 * (1 + sorting),
        10 * (1 + sorting),
    ]


def test_existing_plot_reward_timer_and_all_progress_are_preserved(farm):
    seed(farm, earned=1000000000, balance=100000, energy_milli=500000)
    snapshot = act(farm, "start_plot", "moon")["farm"]
    with farm.arcade.db() as db:
        state = farm._load(db, "p1")
        # Simulate a project planted under the previous balance rules.
        state["projects"]["plot"]["reward_seeds"] = 11
        before = copy.deepcopy(state)
        farm._save(db, "p1", state)
    after = farm.get("p1")
    assert after["activities"]["projects"]["plot"] == before["projects"]["plot"]
    assert after["balance"] == before["balance"]
    assert after["earned"] == before["earned"]
    farm.arcade.clock.advance(math.ceil(snapshot["activities"]["projects"]["plot"]["seconds"]))
    result = act(farm, "claim_project", before["projects"]["plot"]["project_id"])
    assert result["result"]["rewards"][0]["seeds"] == 11
