"""Regression cases found while walking through complete game windows."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.arcade import GAMES, ArcadeError, ArcadeStore
from tests.test_arcade_journey import solve_debug
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import store as store


@pytest.mark.parametrize("game", list(GAMES))
def test_an_unfinished_competition_never_enters_ranking_or_pays_rewards(store, game):
    session = store.session("p1", game, "ranked", "keyboard")
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(1)
    result = store.finish("p1", session["id"], [], 30)
    assert not result["run"]["accepted"]
    assert result["garage_coins"] == 0
    assert result["rewards"] == dict(awards=[], credited=0, pending=0)
    assert not store.board()["rows"]


def test_goal_score_before_last_answer_is_not_a_completed_competition(store):
    session = store.session("p1", "debug", "ranked", "keyboard")
    replay = solve_debug(session["setup"])
    events = replay["events"][:-1]
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(10)
    result = store.finish("p1", session["id"], events, events[-1]["t"])
    assert result["run"]["score"] == 8 and not result["run"]["report"]["complete"]
    assert not result["run"]["accepted"] and not result["rewards"]["awards"]


def test_saved_reward_receipt_survives_a_lost_response_and_restart_without_double_credit(store):
    session = store.session("p1", "debug", "ranked", "keyboard")
    replay = solve_debug(session["setup"])
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(10)
    first = store.finish("p1", session["id"], replay["events"], replay["ticks"])
    restarted = ArcadeStore(store.path, store.clock)
    retry = restarted.finish("p1", session["id"], [], 0)
    assert retry["duplicate"] and retry["receipt"] == first["receipt"]
    assert retry["receipt"]["credited"] == restarted.profile("p1")["balance"] == 23
    assert not retry["rewards"]["awards"]


def test_policy_cannot_set_a_weekly_limit_that_would_trap_a_podium_prize_forever(store):
    with pytest.raises(ArcadeError):
        store.policy(50)
    assert store.policy(100)["cap"] == 100


def test_reward_notice_survives_a_lost_finish_response_in_the_actual_window(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="debug"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    with store.db() as db:
        session = dict(db.execute("SELECT * FROM arcade_sessions").fetchone())
    tasks = page.evaluate("s=>ArcadeWorld.create(s).tasks", json.loads(session["setup"]))

    def lose_response(route):
        payload = route.request.post_data_json
        with ThreadPoolExecutor() as pool:
            pool.submit(
                store.finish,
                "p1",
                session["id"],
                payload["actions"],
                payload["ticks"],
                payload["abandoned"],
            ).result()
        route.abort("failed")

    page.route("**/sessions/*/finish", lose_response, times=1)
    for task in tasks:
        page.locator(".debug-code button").nth(task["line"]).click()
        page.locator("[data-option]").nth(task["answer"]).click()
        page.locator("[data-next]").click()
    page.locator("[data-retry]").click()
    page.locator(".arcade-reward-receipt").wait_for()
    assert "Ваша награда — 23 AC" in page.locator(".arcade-reward-receipt").inner_text()
    assert store.profile("p1")["balance"] == 23


def test_leaving_typing_before_first_character_does_not_submit_an_unstarted_run(arcade):
    page, store = arcade
    finishes = []
    page.on("request", lambda r: finishes.append(r.url) if r.url.endswith("/finish") else None)
    page.locator('.game-card[data-game="typing"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.get_by_text("Начни печатать", exact=True).wait_for()
    page.locator(".game-close").click()
    page.locator("#gameDialog").wait_for(state="detached")
    assert not finishes
    assert not store.profile("p1")["runs"]


def test_keyboard_training_cannot_be_marked_complete_by_entering_wrong_characters(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="typing"]').click()
    page.locator("[data-menu-learning]").click()
    page.locator(".typing-input").press_sequentially("abc")
    assert page.locator("[data-learning-play]").count() == 0


def test_failed_leaderboard_has_retry_without_reopening_the_whole_game(arcade):
    page, _ = arcade
    page.route(
        "**/preview/arcade/boards?*",
        lambda r: r.fulfill(status=503, json={"detail": "Рейтинг временно недоступен"}),
        times=1,
    )
    page.locator('.game-card-leader[data-leader="2048"]').click()
    page.locator("[data-board-retry]").click()
    page.locator("#gamesLeaderDialog .ranking-heading").wait_for()


def test_achievement_hint_checks_quality_and_training_never_promises_a_medal(arcade):
    page, _ = arcade
    hints = page.evaluate("""() => {
      const game=AlgoGameEngine.games.find(g=>g.id==='typing'),
        world={id:'typing',score:250,time:50,details:{accuracy:92}},
        goal={claimed:true}, medal={target:240,requirements:{accuracy:95}};
      return {ranked:ArcadeResults.liveGoal(world,game,goal,medal,false),
        training:ArcadeResults.liveGoal(world,game,goal,medal,true),
        finished:ArcadeResults.liveGoal(world,game,goal,null,false)};
    }""")
    assert hints["ranked"]["text"] == "Точность 92% · нужно 95%"
    assert hints["training"] == dict(target=120, text="Цель тренировки выполнена")
    assert hints["finished"]["text"] == "Все награды этой игры получены"


def test_moving_to_another_window_never_freezes_a_timed_competition(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator('[data-mode="ranked"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent==='90 с'")
    assert page.locator(".arcade-pause,#gameFinish").count() == 0
    assert page.locator(".game-leaders-button").is_hidden()
    page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
    page.wait_for_function("document.querySelector('#gameClock')?.textContent==='89 с'")
    assert page.locator("[data-resume],.game-pause:not(.arcade-countdown)").count() == 0


def test_abandoned_scores_do_not_appear_as_completed_games_in_progress(arcade):
    page, store = arcade
    session = store.session("p1", "debug", "journey", "keyboard", 1)
    with ThreadPoolExecutor() as pool:
        replay = pool.submit(solve_debug, session["setup"]).result()
    store.clock_action("p1", session["id"], "start")
    previous_clock = store.clock
    store.clock = lambda: previous_clock() + 10
    with ThreadPoolExecutor() as pool:
        pool.submit(store.finish, "p1", session["id"], replay["events"], replay["ticks"]).result()
    partial = store.session("p1", "debug", "ranked", "keyboard")
    store.clock_action("p1", partial["id"], "start")
    with ThreadPoolExecutor() as pool:
        pool.submit(store.finish, "p1", partial["id"], [], 0, True).result()
    page.reload()
    page.locator(".games-tabs [data-tab=progress]").click()
    page.locator("#arcadeStatsGame").select_option("debug")
    assert page.locator(".games-reward-list>div").count() == 1
    assert "Задание 1" in page.locator(".games-reward-list").inner_text()
    assert "Незавершённая попытка" not in page.locator(".games-reward-list").inner_text()
