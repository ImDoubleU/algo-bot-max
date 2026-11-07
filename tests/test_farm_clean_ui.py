"""Farm purchases show the actual before/after parameter and the full price only."""

from pathlib import Path

import pytest

from app.services.arcade_farm import FarmStore
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("width", [320, 1440])
def test_upgrade_cards_are_readable_and_daily_combo_is_absent(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=850))
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        s = farm._load(db, "p1")
        s["earned"] = 1000000000
        s["balance"] = 1000000
        s["research"]["seed_sorting"] = 1
        farm._save(db, "p1", s)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-tab="upgrades"]').first.click()
    page.locator(".farm-shop-grid .farm-upgrade").first.wait_for()
    assert (
        page.locator(
            ".farm-upgrade-note,.farm-extra-effect,.farm-production,.farm-shop-summary"
        ).count()
        == 0
    )
    assert page.locator(".farm-shop-grid .farm-upgrade-info small").count() == 0
    assert (
        page.locator(".farm-shop-grid .farm-effect-values").first.evaluate(
            "n=>parseFloat(getComputedStyle(n).fontSize)"
        )
        >= 18
    )
    assert "→" in page.locator(".farm-shop-grid").inner_text()
    assert "Доход этой постройки" not in page.locator(".farm-shop-grid").inner_text()
    assert page.locator("#kopatychFarm").evaluate("n=>n.scrollWidth<=n.clientWidth")
    captures = Path(__file__).parents[1] / ".deploy_tmp/farm-clean-ui"
    captures.mkdir(exist_ok=True)
    page.locator("#kopatychFarm").screenshot(path=str(captures / f"upgrades-{width}.png"))
    page.locator('[data-farm-tab="tasks"]').click()
    assert "Комбо" not in page.locator("#kopatychFarm").inner_text()
    page.locator('[data-farm-tab="activities"]').click()
    page.locator(".farm-seed-rate").first.wait_for()
    assert page.locator(".farm-seed-rate").all_inner_texts() == [
        "12 семян/ч",
        "16 семян/ч",
        "20 семян/ч",
    ]
    page.locator("[data-farm-close]").click()
