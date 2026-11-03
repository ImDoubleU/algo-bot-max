"""Readable standings explain qualification and the source of points without changing scores."""

import pytest

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import verified


def seed_standings(store):
    # Two goals for the current pupil, four different goals for the other pupil.
    for game, score in (("tower", 25), ("blocks", 1200)):
        verified(store, "p1", game, score)
    for game, score in (("debug", 8), ("typing", 240), ("memory", 28), ("react", 12)):
        verified(store, "p2", game, score)


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_overall_standings_show_large_scores_and_clear_qualification(arcade, width):
    page, store = arcade
    seed_standings(store)
    before = store.board()["rows"]
    page.reload()
    page.set_viewport_size(dict(width=width, height=1000))
    page.locator('.games-tabs [data-tab="leaders"]').click()
    page.locator(".ranking-player").first.wait_for()
    assert page.locator(".ranking-player").count() == 2
    assert "Ещё 1 игра до призов" in page.locator(".ranking-qualification").inner_text()
    assert page.locator(".ranking-game-steps .is-complete").count() == 2
    assert page.locator(".ranking-mine-numbers strong").all_text_contents() == ["#2", "200"]
    for selector, minimum in (
        (".ranking-person h4", 19),
        (".ranking-person p", 15),
        (".ranking-points strong", 26),
        (".ranking-prize>strong", 26),
    ):
        assert (
            page.locator(selector).first.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)")
            >= minimum
        )
    assert page.locator(".arcade-ranking").evaluate("e=>e.scrollWidth<=e.clientWidth")
    for prize in page.locator(".ranking-prize").all():
        assert prize.evaluate("e=>e.scrollWidth<=e.clientWidth")
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    own = page.locator(".ranking-player.is-me")
    own.locator("summary").click()
    assert own.locator(".ranking-breakdown li").count() == 2
    assert own.locator(".ranking-breakdown strong").all_text_contents() == ["+100", "+100"]
    page.locator('[data-period="all"]').click()
    page.locator(".ranking-heading p").filter(has_text="всё время").wait_for()
    assert page.locator(".ranking-prizes, .ranking-qualification").count() == 0
    page.locator('[data-period="week"]').click()
    page.locator(".ranking-prizes").wait_for()
    assert store.board()["rows"] == before


def test_each_game_board_remains_readable_inside_the_cup_and_filters_work(arcade):
    page, store = arcade
    verified(store, "p1", "typing", 240, device="keyboard")
    page.locator('[data-leader="typing"]').click()
    page.locator(".ranking-player").wait_for()
    assert page.locator(".ranking-player").count() == 1
    assert page.locator(".ranking-prizes").count() == 0
    page.locator('[data-board-device="touch"]').click()
    page.locator(".ranking-empty").wait_for()
    assert page.locator(".ranking-player").count() == 0
    page.locator('[data-board-device="keyboard"]').click()
    page.locator(".ranking-player").wait_for()
    assert page.locator(".arcade-ranking").evaluate("e=>e.scrollWidth<=e.clientWidth")


def test_garden_label_opens_the_saved_farm_and_other_games_keep_levels(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="kopatych"]').click()
    page.get_by_role("button", name="Мой огород", exact=True).click()
    page.locator(".farm-bear").wait_for()
    page.locator("[data-farm-close]").click()
    page.locator('.game-card[data-game="2048"]').click()
    assert page.get_by_role("button", name="Уровни", exact=True).is_visible()
