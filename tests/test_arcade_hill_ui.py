"""Real pedal input, learning and garage controls work on narrow screens."""

import json

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (1440, 900)])
def test_pedals_fit_and_releasing_a_key_during_pause_does_not_leave_the_accelerator_on(
    arcade, size
):
    page, store = arcade
    page.set_viewport_size(dict(width=size[0], height=size[1]))
    assert page.locator('[data-game="runner"]').count() == 0
    page.locator('.game-card[data-game="hill"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.wait_for_function('document.querySelector("#gameClock").textContent.length>0')
    for pedal in page.locator("[data-pedal]").all():
        rect = pedal.bounding_box()
        assert rect["height"] >= 60
        assert 0 <= rect["y"] and rect["y"] + rect["height"] <= size[1]
    page.keyboard.down("ArrowRight")
    page.wait_for_function('Number(document.querySelector("#gameScore").textContent)>20')
    page.locator(".arcade-pause").click()
    page.keyboard.up("ArrowRight")
    page.locator("[data-resume]").click()
    page.wait_for_function(
        '!document.querySelector("[data-pedal=gas]").classList.contains("is-pressed")'
    )
    page.locator("#gameFinish").click()
    page.locator("[data-back-garage]").wait_for()
    with store.db() as db:
        row = db.execute("SELECT actions,report FROM arcade_runs WHERE game='hill'").fetchone()
    events = json.loads(row["actions"])
    assert [e["value"] for e in events if e.get("pedal") == "gas"] == [1, 0]
    assert json.loads(row["report"])["score"] > 20
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")


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
