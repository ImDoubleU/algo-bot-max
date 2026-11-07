"""Verify research progression and missing-resource navigation in the real miniapp."""

from pathlib import Path

import pytest

from app.services.arcade_farm import FarmStore
from tests.test_arcade_server import Clock
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_research_has_visible_caps_and_unlocks_without_any_greenhouse(arcade, width):
    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(earned=10**15, balance=10**12, resources=dict(seeds=1000, materials=1000))
        state["research"]["garden_notes"] = 2
        state["items"]["beds"] = 2
        farm._save(db, "p1", state)
    page.set_viewport_size(dict(width=width, height=850))
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-activity-view="research"]').click()
    notes = page.locator('[data-research="garden_notes"]')
    assert notes.locator(".farm-upgrade-level").inner_text() == "2/3"
    notes.locator("button").click()
    page.wait_for_function(
        "document.querySelector('[data-research=garden_notes] .farm-upgrade-level')"
        ".textContent==='3/3'"
    )
    assert notes.locator("button").is_disabled()
    assert notes.locator("button").inner_text() == "Изучено"
    assert notes.locator(".farm-research-cost").count() == 0
    sorting = page.locator('[data-research="seed_sorting"]')
    assert sorting.locator("button").is_enabled()
    maps = page.locator('[data-research="trail_maps"]')
    assert "Отбор семян 1/3" in maps.inner_text()
    assert maps.locator("button").is_disabled()
    sorting.locator("button").click()
    maps.locator("button").click()
    page.wait_for_function(
        "document.querySelector('[data-research=trail_maps] .farm-upgrade-level')"
        ".textContent==='1/3'"
    )
    assert "−3 мин" in maps.locator(".farm-effect-gain").inner_text()
    captures = Path(__file__).parents[1] / ".deploy_tmp/farm-feedback"
    captures.mkdir(exist_ok=True)
    assert page.locator(".farm-content").evaluate("n=>n.scrollWidth<=n.clientWidth")
    page.locator("#kopatychFarm").screenshot(path=str(captures / f"research-{width}.png"))
    page.locator('.farm-tabs [data-farm-tab="upgrades"]').click()
    page.locator('[data-farm-category="business"]').click()
    seedlab = page.locator('[data-farm-action="buy"][data-item="seedlab"]')
    assert seedlab.locator(".farm-upgrade-level").inner_text() == "0/10"
    assert seedlab.locator(".farm-effect-gain").is_visible()
    assert "%" not in seedlab.locator(".farm-effect").inner_text()
    page.locator("#kopatychFarm").screenshot(path=str(captures / f"upgrades-{width}.png"))
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-activity-view="expedition"]').click()
    assert page.locator(".farm-route-cards .farm-activity-option").count() == 5
    assert "Нужно построить: Горная ферма" in page.locator(".variety-highland").inner_text()
    page.locator("#kopatychFarm").screenshot(path=str(captures / f"expeditions-{width}.png"))
    assert not any(i["level"] for i in farm.get("p1")["items"] if i["id"] == "greenhouse")
    page.locator("[data-farm-close]").click()
