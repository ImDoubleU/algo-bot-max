"""Real pedal input, learning and garage controls work on narrow screens."""

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import finish_naturally


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (1440, 900)])
def test_pedals_fit_and_losing_focus_releases_the_accelerator_without_a_pause(arcade, size):
    page, store = arcade
    page.set_viewport_size(dict(width=size[0], height=size[1]))
    page.locator('.game-card[data-game="hill"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    for b in page.locator("[data-pedal]").all():
        assert b.bounding_box()["height"] >= 64
    page.keyboard.down("ArrowRight")
    page.wait_for_function("Number(document.querySelector('#gameScore').textContent)>15")
    page.evaluate("window.dispatchEvent(new Event('blur'))")
    page.keyboard.up("ArrowRight")
    page.wait_for_function(
        "!document.querySelector('[data-pedal=gas]').classList.contains('is-pressed')"
    )
    assert page.locator("[data-resume],.arcade-pause").count() == 0
    finish_naturally(page, store, 601)
    page.locator("[data-back-garage]").click()
    page.locator(".hill-route-hero").wait_for()


def test_garage_purchase_displays_actual_next_effect_and_survives_reentry(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="upgrades"]').click()
    engine = page.locator(".hill-upgrades article").filter(
        has=page.get_by_role("heading", name="Двигатель", exact=True)
    )
    assert "19.0 → 20.6" in engine.inner_text()
    engine.locator("button").click()
    page.wait_for_function(
        'document.querySelector(".hill-upgrade-heading>span")?.textContent==="1 / 10"'
    )
    assert "20.6 → 22.2" in engine.inner_text()
    page.locator("[data-close]").click()
    page.reload()
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="upgrades"]').click()
    assert "1 / 10" in page.locator(".hill-upgrades article").first.inner_text()
    assert "120" in page.locator(".hill-garage-wallet").inner_text()


def test_learning_requires_acceleration_and_braking_without_starting_a_paid_attempt(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-learning]").click()
    page.keyboard.down("ArrowRight")
    page.wait_for_function(
        'document.querySelector(".arcade-learning-tip").textContent.startsWith("Отпусти")'
    )
    page.keyboard.up("ArrowRight")
    page.keyboard.down("ArrowLeft")
    page.locator("[data-learning-play]").wait_for()
    page.keyboard.up("ArrowLeft")
    assert "Получилось!" in page.locator(".game-result").inner_text()
    with store.db() as db:
        assert db.execute("SELECT count(*) FROM arcade_sessions").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM hill_results").fetchone()[0] == 0
