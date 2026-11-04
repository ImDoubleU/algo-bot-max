"""Rewards are settled with a verified result, exactly once, including retries and caps."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.arcade import ArcadeStore, week_key
from tests.test_arcade_journey import solve_debug
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import store as store


def ready(store, mode="ranked", game="debug"):
    session = store.session("p1", game, mode, "keyboard")
    replay = solve_debug(session["setup"])
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(replay["ticks"] / 60 + 0.5)
    return session, replay


def test_all_awards_are_auto_collected_once_even_with_concurrent_duplicate_finishes(store):
    session, replay = ready(store)

    def finish():
        return store.finish("p1", session["id"], replay["events"], replay["ticks"])

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: finish(), range(3)))
    assert sum(not r["duplicate"] for r in results) == 1
    assert sum(r["rewards"]["credited"] for r in results) == 40
    assert sum(len(r["rewards"]["awards"]) for r in results) == 4
    profile = ArcadeStore(store.path, store.clock).profile("p1")
    assert profile["balance"] == 40
    assert profile["goals"]["debug"]["credited"]
    assert all(a["claimed"] and a["credited"] is not None for a in profile["awards"])
    assert store.profile("p2")["balance"] == 0


def test_zero_practice_and_repeat_do_not_create_a_fake_reward_receipt(store):
    session, replay = ready(store)
    store.finish("p1", session["id"], replay["events"], replay["ticks"])
    for mode in ("ranked", "practice"):
        session, replay = ready(store, mode)
        result = store.finish("p1", session["id"], replay["events"], replay["ticks"])
        assert result["rewards"] == dict(awards=[], credited=0, pending=0)
    session = store.session("p1", "drop", "ranked", "keyboard")
    store.clock_action("p1", session["id"], "start")
    result = store.finish("p1", session["id"], [], 0, abandoned=True)
    assert not result["rewards"]["awards"] and store.profile("p1")["balance"] == 40


def test_capped_reward_is_saved_and_credited_on_the_next_week_without_a_claim(store):
    with store.db() as db:
        store._award(db, "p1", "test", "all", "earlier", 190, "Earlier", claimed=True)
        store._credit(db, "p1")
    session, replay = ready(store)
    result = store.finish("p1", session["id"], replay["events"], replay["ticks"])
    assert result["rewards"]["credited"] == 10 and result["rewards"]["pending"] == 30
    assert store.profile("p1")["balance"] == 200
    store.clock.advance(8 * 86400)
    assert ArcadeStore(store.path, store.clock).profile("p1")["balance"] == 230


def test_legacy_unclaimed_award_is_collected_on_a_new_qualifying_result(store):
    with store.db() as db:
        store._award(
            db,
            "p1",
            "weekly",
            week_key(store.clock()),
            f"weekly:{week_key(store.clock())}:p1:debug",
            10,
            "Earlier goal",
        )
    session, replay = ready(store)
    result = store.finish("p1", session["id"], replay["events"], replay["ticks"])
    assert result["rewards"]["credited"] == 45
    assert len(result["rewards"]["awards"]) == 4


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_natural_results_have_large_controls_and_aligned_header_buttons(arcade, width):
    from tests.test_arcade_server import finish_naturally

    page, store = arcade
    page.set_viewport_size(dict(width=width, height=844))
    page.locator('.game-card[data-game="2048"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    assert page.locator(".arcade-pause,#gameFinish").count() == 0
    finish_naturally(page, store)
    cup = page.locator(".game-leaders-button").bounding_box()
    close = page.locator(".game-close").bounding_box()
    assert abs(cup["y"] - close["y"]) < 1 and cup["height"] == close["height"] == 44
    assert page.locator(".game-hud").is_hidden()
    assert page.locator(".arcade-live-goal").is_hidden()
    assert page.locator(".arcade-reward-receipt").count() == 0
    for selector in ("[data-again]", "[data-back]"):
        b = page.locator(selector)
        assert b.bounding_box()["height"] >= 50
        assert b.evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= 18
    assert store.profile("p1")["balance"] == 0
    page.locator("[data-again]").click()
    page.locator(".number-grid").wait_for()
    with store.db() as db:
        assert db.execute("SELECT COUNT(*) FROM arcade_sessions").fetchone()[0] == 2


def test_escape_during_typing_clock_start_closes_without_an_unstarted_result(arcade):
    page, _ = arcade
    pending = []
    page.route("**/clock/start", lambda r: pending.append(r))
    page.locator('.game-card[data-game="typing"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.get_by_text("Начни печатать", exact=True).wait_for()
    with page.expect_request("**/clock/start"):
        page.locator(".typing-input").press_sequentially("кот")
    page.keyboard.press("Escape")
    assert page.locator("#gameDialog").count() == 0
    pending[0].fallback()
    assert page.locator("[data-resume],.game-result").count() == 0


@pytest.mark.parametrize("game", ["2048", "blocks", "drop"])
def test_level_timer_is_visible_even_when_free_play_has_no_time_limit(arcade, game):
    page, _ = arcade
    page.locator(f'.game-card[data-game="{game}"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-journey-play="1"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    assert page.locator("#gameClock").is_visible()


def test_cup_is_available_after_completion_and_cannot_interrupt_a_competition(arcade):
    from tests.test_arcade_server import finish_naturally

    page, store = arcade
    page.locator('.game-card[data-game="blocks"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    assert page.locator(".game-leaders-button").is_hidden()
    finish_naturally(page, store)
    page.locator(".game-leaders-button").click()
    page.locator(".games-leader-close").click()
    assert page.locator("[data-again]").is_visible()
    assert page.locator("[data-resume]").count() == 0
