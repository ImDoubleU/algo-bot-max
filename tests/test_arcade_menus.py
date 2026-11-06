"""The four entry points stay readable and navigation cannot create game results."""

import pytest

from app.services.arcade import GAMES
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.mark.parametrize("size", [(320, 568), (390, 844), (1440, 900)])
def test_all_sixteen_games_have_four_large_visible_mode_buttons(arcade, size):
    page, store = arcade
    page.set_viewport_size(dict(width=size[0], height=size[1]))
    for game in GAMES:
        page.locator(f'.game-card[data-game="{game}"]').click()
        if game == 'react':
            page.locator('[data-benchmark-react]').click()
        buttons = page.locator(".arcade-menu-actions > button")
        assert buttons.all_text_contents() == [
            "Соревнование›",
            "Тренировка›",
            "Обучение›",
            "Мой огород›" if game == "kopatych" else "Мой гараж›" if game == "hill" else "Уровни›",
        ]
        for button in buttons.all():
            rect = button.bounding_box()
            assert rect["height"] >= 64
            assert rect["y"] >= 0 and rect["y"] + rect["height"] <= size[1]
            assert button.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= 20
        assert page.locator("[data-input], .game-intro, .journey-chapters").count() == 0
        assert page.locator("#gameDialog").evaluate("e=>e.scrollWidth<=e.clientWidth")
        page.locator(".game-close").click()
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 0


def test_back_from_levels_and_learning_does_not_start_a_game_or_lose_progress(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="2048"]').click()
    for _ in range(2):
        page.locator("[data-menu-levels]").click()
        assert page.locator(".arcade-level-grid button").count() == 24
        assert page.locator(".arcade-level-grid button:not(:disabled)").count() == 1
        page.locator(".game-menu-back").click()
        page.locator("[data-menu-learning]").click()
        assert page.locator(".arcade-learning-tip").is_visible()
        assert (
            page.locator(".arcade-learning-tip").evaluate(
                "e=>parseFloat(getComputedStyle(e).fontSize)"
            )
            >= 16
        )
        page.locator(".game-menu-back").click()
        assert page.locator(".arcade-menu-action").count() == 4
    assert store.profile("p1")["mastery"]["xp"] == 0
    assert store.profile("p1")["runs"] == []
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 0


@pytest.mark.parametrize("arcade", [None, "touch"], indirect=True)
def test_practice_starts_immediately_with_automatic_controls(arcade):
    page, store = arcade
    expected = page.evaluate("matchMedia('(pointer:coarse)').matches?'touch':'keyboard'")
    page.locator('.game-card[data-game="2048"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.locator(".number-grid").wait_for()
    with store.db() as db:
        session = db.execute("SELECT mode,device FROM arcade_sessions").fetchone()
    assert session["mode"] == "practice" and session["device"] == expected


def test_farm_progress_opens_from_levels_without_starting_a_tournament(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    assert page.locator("#gameDialog").count() == 0
    page.locator("[data-farm-sprint]").first.click()
    assert page.locator("#kopatychFarm").count() == 0
    assert page.locator(".arcade-menu-action").count() == 4
    assert store.profile("p1")["runs"] == []
