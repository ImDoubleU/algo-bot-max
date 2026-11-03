"""Lobby navigation stays readable and never creates or resets game progress."""

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_lobby_has_readable_labels_large_controls_and_no_sideways_scroll(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=1000))
    assert page.locator(".game-card").count() == 16
    assert page.locator(".arcade-new, .game-card-body>small, .games-wordmark").count() == 0
    for selector, minimum in (
        (".games-tabs button", 16),
        (".games-filters button", 16),
        (".game-card h3", 22),
        (".game-card-bottom", 16),
        (".game-card-leader", 16),
        (".game-reward", 16),
        (".arcade-next-level", 16),
        (".arcade-passport-label", 16),
        ("#gamesPlayer", 16),
    ):
        for item in page.locator(selector).all():
            assert item.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= minimum
            assert item.evaluate("e=>e.scrollWidth<=e.clientWidth"), selector
    for item in page.locator(".games-tabs button,.games-filters button,.game-card-leader").all():
        assert item.bounding_box()["height"] >= 44
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    for selector in (".arcade-passport", ".arcade-reward-overview"):
        assert page.locator(selector).evaluate("e=>e.scrollWidth<=e.clientWidth")
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 0


def test_lobby_reward_rank_filters_and_player_switch_keep_the_saved_state(arcade):
    page, store = arcade
    before = store.profile("p1")
    page.locator(".arcade-reward-overview").click()
    page.locator(".games-reward-summary").wait_for()
    page.locator('.games-tabs [data-tab="games"]').click()
    page.locator('.games-filters [data-filter="puzzle"]').click()
    expected = page.evaluate("AlgoGameEngine.games.filter(g=>g.kind==='puzzle').map(g=>g.id)")
    shown = page.locator(".game-card").evaluate_all("cards=>cards.map(c=>c.dataset.game)")
    assert sorted(shown) == sorted(expected)
    page.locator('.arcade-passport-league[data-tab="leaders"]').click()
    page.locator(".ranking-heading").wait_for()
    page.locator('.games-tabs [data-tab="games"]').click()
    page.locator("#gamesPlayer").select_option("p2")
    page.wait_for_function("document.querySelector('#gamesPlayer')?.value==='p2'")
    page.locator(".game-card").first.wait_for()
    after = store.profile("p1")
    assert after["balance"] == before["balance"]
    assert after["journeys"] == before["journeys"]
    assert after["awards"] == before["awards"]
    assert after["mastery"] == before["mastery"]


def test_long_mastery_title_fits_small_phone_without_tiny_type(arcade):
    page, store = arcade
    with store.db() as db:
        for game in ("orbit", "tower", "memory"):
            for stage in range(1, 5):
                db.execute(
                    "INSERT INTO arcade_journeys VALUES(?,?,?,?,?,?,?)",
                    ("p1", game, stage, 3, 100, store.clock(), "{}"),
                )
    page.set_viewport_size(dict(width=320, height=900))
    page.reload()
    heading = page.locator(".arcade-passport h2")
    heading.wait_for()
    assert heading.inner_text() == "Исследователь"
    assert heading.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= 22
    assert heading.evaluate("e=>e.clientHeight<=parseFloat(getComputedStyle(e).lineHeight)+1")
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")


def test_featured_garden_and_competition_open_the_actual_modes(arcade):
    page, store = arcade
    page.locator(".arcade-garden-feature [data-garden]").click()
    page.locator(".farm-bear").wait_for()
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 0
    page.locator("[data-farm-close]").click()
    page.locator(".arcade-garden-feature [data-sprint]").click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    with store.db() as db:
        rows = db.execute("SELECT game,mode FROM arcade_sessions").fetchall()
        assert [(r["game"], r["mode"]) for r in rows] == [("kopatych", "ranked")]
    assert not store.profile("p1")["awards"]
