"""Vehicle illustrations stay readable and follow the selected model and paint."""

import pytest

from app.services.arcade_hill import save, state_for
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_all_four_vehicle_cards_have_large_finite_art_and_no_overflow(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="cars"]').click()
    cards = page.locator(".hill-car-list article")
    assert cards.count() == 4
    assert cards.locator("svg").evaluate_all("nodes=>nodes.map(n=>n.dataset.hillModel)") == [
        "scout",
        "buggy",
        "truck",
        "rover",
    ]
    for card in cards.all():
        art = card.locator("svg")
        assert art.bounding_box()["width"] >= 190
        assert "NaN" not in art.inner_html()
        assert card.evaluate("n=>n.scrollWidth<=n.clientWidth")
        assert card.locator("button").bounding_box()["height"] >= 44
    for button in page.locator(".hill-car-colors button").all():
        assert button.bounding_box()["width"] >= 44
        assert button.bounding_box()["height"] >= 44
        bounds = page.locator(".hill-garage-car").bounding_box()
        rect = button.bounding_box()
        assert rect["x"] >= bounds["x"]
        assert rect["x"] + rect["width"] <= bounds["x"] + bounds["width"]
    assert page.locator(".hill-garage-dialog").evaluate("n=>n.scrollWidth<=n.clientWidth")


def test_paint_and_car_selection_update_both_hero_and_catalogue_without_changing_stats(arcade):
    page, store = arcade
    with store.db() as db:
        state = state_for(db, "p1")
        state["xp"] = 100000
        state["owned"] = ["scout", "buggy", "truck", "rover"]
        save(db, "p1", state)
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="cars"]').click()
    stats = page.locator(".hill-car-stats").inner_text()
    page.locator('[data-action="paint"][data-item="#66a99c"]').click()
    page.wait_for_function(
        "document.querySelector('.hill-car-colors [data-item=\"#66a99c\"]')"
        "?.getAttribute('aria-pressed')==='true'"
    )
    for selector in (".hill-garage-car>svg", '.hill-car-list [data-car-model="scout"] svg'):
        assert page.locator(selector).locator('[fill="#66a99c"]').count() > 0
    assert page.locator(".hill-car-stats").inner_text() == stats
    page.locator('[data-action="select"][data-item="buggy"]').click()
    page.locator('.hill-car-list [data-car-model="buggy"].is-selected').wait_for()
    assert page.locator(".hill-garage-car>svg").get_attribute("data-hill-model") == "buggy"
    assert page.locator(".hill-car-hero-heading h3").inner_text() == "Багги"
    page.locator("[data-close]").click()
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="cars"]').click()
    assert page.locator(".hill-garage-car>svg").get_attribute("data-hill-model") == "buggy"
