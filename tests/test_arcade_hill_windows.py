"""Window transitions, interrupted delivery and landscape controls preserve driving progress."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from app.services.arcade_hill import HillStore, save, state_for
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import finish_naturally


def clickable(locator):
    return locator.evaluate("""n=>{
      const r=n.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2;
      return x>=0&&y>=0&&x<innerWidth&&y<innerHeight&&
        n.contains(document.elementFromPoint(x,y));}""")


def start(page):
    page.locator('.game-card[data-game="hill"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.wait_for_function('document.querySelector("#gameClock").textContent.length>0')


def short_drive(page):
    page.keyboard.down("ArrowRight")
    page.wait_for_function('Number(document.querySelector("#gameScore").textContent)>25')
    page.keyboard.up("ArrowRight")


@pytest.mark.parametrize("size", [(844, 390), (568, 320)])
def test_landscape_menu_pedals_results_and_replay_are_accessible(arcade, size):
    page, store = arcade
    page.set_viewport_size(dict(width=size[0], height=size[1]))
    page.locator('.game-card[data-game="hill"]').click()
    assert all(clickable(b) for b in page.locator(".arcade-menu-actions>button").all())
    page.locator('[data-mode="practice"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    assert all(clickable(b) for b in page.locator("[data-pedal]").all())
    assert page.locator(".hill-canvas").bounding_box()["height"] >= 70
    short_drive(page)
    finish_naturally(page, store, 601)
    page.locator(".hill-run-coins").wait_for()
    assert HillStore(store).get("p1")["balance"] > 250
    page.locator(".arcade-result-details>summary").click()
    page.locator("[data-analysis]").click()
    assert page.locator(".arcade-replay [data-pedal]").count() == 0
    assert (
        page.locator(".arcade-replay .hill-instruments>div")
        .first.inner_text()
        .startswith("Дистанция")
    )
    page.evaluate(
        "(()=>{window.replayInputs=0;const original=ArcadeWorld.input;"
        "ArcadeWorld.input=(...a)=>{window.replayInputs++;return original(...a);};})()"
    )
    page.keyboard.press("ArrowRight")
    assert page.evaluate("window.replayInputs") == 0


def test_garage_loading_can_be_closed_and_failed_load_can_be_retried(arcade):
    page, _ = arcade
    pending = []
    page.route("**/preview/arcade/garage", lambda r: pending.append(r), times=1)
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    assert page.get_by_role("button", name="Закрыть гараж").is_visible()
    page.get_by_role("button", name="Закрыть гараж").click()
    assert page.locator(".hill-garage-dialog").count() == 0
    for request in pending:
        request.abort()
    page.route(
        "**/preview/arcade/garage",
        lambda r: r.fulfill(
            status=503, json={"detail": "Гараж временно недоступен. Попробуй ещё раз."}
        ),
        times=1,
    )
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator("[data-reload]").wait_for()
    assert "временно недоступен" in page.locator(".hill-garage-loading").inner_text()
    page.locator("[data-reload]").click()
    page.locator(".hill-route-hero").wait_for()


def test_ready_claimed_and_maximum_states_show_amounts_and_keep_the_close_button_visible(arcade):
    page, store = arcade
    with store.db() as db:
        state = state_for(db, "p1")
        state.update(xp=100000, balance=10000, distance=1000, best=300, coins=100, jumps=8)
        state["upgrades"]["scout"] = dict(engine=10, tires=10, suspension=10, tank=10)
        day = datetime.fromtimestamp(store.clock(), timezone(timedelta(hours=3))).date().isoformat()
        state["daily"] = dict(day=day, distance=1000, coins=100, jumps=8)
        save(db, "p1", state)
    before = HillStore(store).get("p1")
    amount = sum(t["reward"] for t in before["tasks"] if t["ready"] and not t["claimed"])
    page.set_viewport_size(dict(width=320, height=568))
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="tasks"]').click()
    assert "Готово монет" not in page.locator(".hill-garage-dialog").inner_text()
    assert all(
        b.inner_text().startswith("+") for b in page.locator(".hill-task-list .is-ready>b").all()
    )
    assert page.locator('[data-action="claim_all"]').inner_text().endswith("монет")
    page.locator('[data-action="claim_all"]').click()
    page.locator(".hill-claim-line").wait_for(state="detached")
    assert HillStore(store).get("p1")["balance"] == 10000 + amount
    assert page.locator(".hill-task-list .is-claimed").count() == 3
    assert "До уровня 25" not in page.locator(".hill-garage-wallet").inner_text()
    page.locator('[data-garage-tab="upgrades"]').click()
    assert all(
        b.is_disabled() and b.inner_text() == "Максимум"
        for b in page.locator(".hill-upgrades button").all()
    )
    assert "→" not in page.locator(".hill-upgrades").inner_text()
    page.locator(".hill-garage-dialog").evaluate("n=>n.scrollTop=n.scrollHeight")
    assert clickable(page.locator("[data-close]"))


def test_expedition_returns_to_the_updated_garage_mission_list(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-garage-tab="missions"]').click()
    page.locator(".hill-mission-rules>summary").click()
    assert "Сохрани 40" in page.locator(".hill-mission-rules").inner_text()
    page.locator('[data-mission="1"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.wait_for_function('document.querySelector("#gameClock").textContent.length>0')
    page.keyboard.down("ArrowRight")
    page.locator(".journey-result").wait_for(timeout=12000)
    page.keyboard.up("ArrowRight")
    assert "Заезд пройден!" in page.locator(".journey-result").inner_text()
    page.locator("[data-journey-map]").click()
    page.locator(".hill-missions").wait_for()
    assert page.locator('[data-garage-tab="missions"]').get_attribute("aria-pressed") == "true"
    assert page.locator('[data-stage="2"]').get_attribute("aria-pressed") == "true"
    assert store.profile("p1")["journeys"]["hill"]["unlocked"] == 2


def test_lost_finish_response_can_be_retried_without_losing_or_duplicating_coins(arcade):
    page, store = arcade
    attempts = []

    def lose_response(route):
        attempts.append(1)
        payload = route.request.post_data_json
        session = route.request.url.split("/sessions/")[1].split("/")[0]
        with ThreadPoolExecutor() as pool:
            pool.submit(
                store.finish,
                "p1",
                session,
                payload["actions"],
                payload["ticks"],
                payload["abandoned"],
            ).result()
        route.abort("failed")

    page.route("**/sessions/*/finish", lose_response, times=1)
    start(page)
    short_drive(page)
    finish_naturally(page, store)
    page.locator("[data-retry]").wait_for()
    page.locator("[data-retry]").click()
    page.locator(".hill-run-coins").wait_for()
    with store.db() as db:
        rows = db.execute("SELECT reward FROM hill_results").fetchall()
    assert len(attempts) == 1 and len(rows) == 1 and rows[0][0] > 0
    assert page.locator(".hill-run-coins").inner_text() == f"+{rows[0][0]} монет в гараж"
    assert HillStore(store).get("p1")["balance"] == 250 + rows[0][0]


def test_profile_refresh_failure_reuses_the_saved_result_instead_of_sending_it_again(arcade):
    page, store = arcade
    start(page)
    short_drive(page)
    finishes = []
    page.on(
        "request", lambda request: finishes.append(1) if request.url.endswith("/finish") else None
    )
    page.route(
        "**/preview/arcade/profile",
        lambda route: route.fulfill(status=503, json={"detail": "Временно недоступно"}),
        times=1,
    )
    finish_naturally(page, store)
    page.get_by_role("heading", name="Результат сохранён", exact=True).wait_for()
    page.get_by_role("button", name="Обновить результат", exact=True).click()
    page.locator(".hill-run-coins").wait_for()
    assert len(finishes) == 1
    assert HillStore(store).get("p1")["balance"] > 250


def test_return_from_free_drive_keeps_the_selected_track(arcade):
    page, store = arcade
    with store.db() as db:
        state = state_for(db, "p1")
        state["xp"] = 480
        save(db, "p1", state)
    page.locator('.game-card[data-game="hill"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-route="dunes"]').click()
    page.locator("[data-drive]").click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    page.wait_for_function('document.querySelector("#gameClock").textContent.length>0')
    short_drive(page)
    finish_naturally(page, store)
    page.locator("[data-back-garage]").click()
    page.locator(".hill-route-hero").wait_for()
    assert page.locator('[data-route="dunes"]').get_attribute("aria-pressed") == "true"
