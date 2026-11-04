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
    assert "Осталась 1 игра" in page.locator(".ranking-qualification").inner_text()
    assert page.locator(".ranking-qualification progress").get_attribute("value") == "2"
    assert page.locator(".ranking-player.is-me .ranking-place").inner_text() == "2"
    assert page.locator(".ranking-player.is-me .ranking-points strong").inner_text() == "200"
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
    assert own.locator(".ranking-breakdown li strong").all_text_contents() == ["+100", "+100"]
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
    page.locator("#gameDialog").get_by_role("button", name="Мой огород", exact=True).click()
    page.locator(".farm-bear").wait_for()
    page.locator("[data-farm-close]").click()
    page.locator('.game-card[data-game="2048"]').click()
    assert page.get_by_role("button", name="Уровни", exact=True).is_visible()


def test_first_reward_hard_medals_and_fortnightly_season_are_explained_consistently(arcade):
    page, store = arcade
    assert "5 AC" in page.locator('.game-card[data-game="typing"] .game-reward').inner_text()
    page.locator('.games-tabs [data-tab="achievements"]').click()
    medal = page.locator(".game-achievement").filter(has_text="Клавиатурный спринт · золото")
    assert "400" in medal.inner_text() and "99%" in medal.inner_text()
    assert medal.locator("button").inner_text() == "+10 AC"
    page.locator('.games-tabs [data-tab="rewards"]').click()
    assert "один раз за всё время" in page.locator(".games-reward-summary").inner_text()
    page.locator('.games-tabs [data-tab="leaders"]').click()
    page.get_by_role("button", name="За сезон", exact=True).wait_for()
    assert "Сезон с" in page.locator(".ranking-heading p").inner_text()
    assert store.profile("p1")["season"]["days"] == 14


def test_projected_prizes_skip_ineligible_players_and_keyboard_opens_the_breakdown(arcade):
    page, store = arcade
    seed_standings(store)
    store.register([dict(id=f"p{i}", name=f"Игрок {i}", group="Демо") for i in range(3, 7)])
    for player, game, score in (("p4", "debug", 7), ("p5", "typing", 180), ("p6", "memory", 20)):
        verified(store, player, game, score)
    for game, score in (("debug", 5), ("typing", 120), ("memory", 8)):
        verified(store, "p3", game, score)
    page.reload()
    page.locator('.games-tabs [data-tab="leaders"]').click()
    page.locator(".ranking-player").first.wait_for()
    first, own, third = page.locator(".ranking-player").all()[:3]
    assert first.locator(".ranking-row-prize").inner_text() == "100 AC"
    assert own.locator(".ranking-place").inner_text() == "2"
    assert own.locator(".ranking-row-prize").count() == 0
    assert third.locator(".ranking-place").inner_text() == "3"
    assert third.locator(".ranking-row-prize").inner_text() == "75 AC"
    own.locator("summary").focus()
    page.keyboard.press("Enter")
    assert own.locator("details").get_attribute("open") is not None
    assert sum(int(v.lstrip("+")) for v in own.locator("li strong").all_text_contents()) == 200
    assert page.locator(".arcade-lobby-status").count() == 0


def test_rank_outside_the_top_twenty_stays_visible_with_an_explicit_gap(arcade):
    page, store = arcade
    store.register([dict(id=f"player{i}", name=f"Игрок {i}", group="Демо") for i in range(30)])
    for i in range(30):
        verified(store, f"player{i}", "blocks", 10000 - i * 100)
    verified(store, "p1", "blocks", 300)
    page.reload()
    page.locator('.games-tabs [data-tab="leaders"]').click()
    page.locator(".ranking-player.is-me").wait_for()
    assert page.locator(".ranking-player.is-me .ranking-place").inner_text() == "31"
    assert page.locator(".ranking-gap").count() == 1
    assert page.locator(".ranking-player").count() == 23
