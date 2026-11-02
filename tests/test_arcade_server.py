"""Server arcade: replay verification, accounting, ownership and browser integration."""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.api.routes.arcade_preview import make_router
from app.cli.games_preview import inject_games
from app.services import arcade_runtime
from app.services.arcade import GAMES, ArcadeError, ArcadeStore, maintenance_worker, week_key

pytest.importorskip("py_mini_racer", reason="Install requirements-games.txt for arcade tests")

STATIC = Path(__file__).parents[1] / "app/web/static/miniapp"


class Clock:
    def __init__(self):
        self.now = 1793448000.0  # Saturday before a Moscow week boundary.

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


@pytest.fixture
def store(tmp_path):
    clock = Clock()
    store = ArcadeStore(tmp_path / "isolated.sqlite3", clock)
    store.register([{"id": f"p{i}", "name": f"Игрок {i}", "group": "Демо"} for i in range(1, 6)])
    return store


# Generate input traces through the shared rules, never inject a submitted score.
def trace(setup, script):
    with arcade_runtime.context() as vm:
        vm.eval(
            "function play(setup){const W=ArcadeWorld,w=W.create(setup),events=[];"
            "const send=a=>{const e={...a,t:w.tick,source:w.device};events.push(e);W.input(w,e);};"
            + script
            + ";return {events,ticks:w.tick,report:W.report(w)};}"
        )
        return vm.call("play", setup)


def finish_debug(store, player="p1", mode="ranked"):
    session = store.session(player, "debug", mode, "keyboard")
    result = trace(
        session["setup"],
        """
      for(let i=0;i<8;i++){W.advance(w,12);send({type:'line',i:w.tasks[i].line});
        W.advance(w,12);send({type:'answer',i:w.tasks[i].answer});
        W.advance(w,12);send({type:'next'});}
    """,
    )
    store.clock_action(player, session["id"], "start")
    store.clock.advance(result["ticks"] / 60 + 0.5)
    return store.finish(player, session["id"], result["events"], result["ticks"]), session, result


@pytest.mark.parametrize("game", list(GAMES))
def test_shared_world_replays_exactly_independent_of_frame_batches(game):
    setup = {"game": game, "seed": 12345, "mode": "ranked", "device": "keyboard"}
    actions = {
        "orbit": "send({type:'tap'})",
        "evolve": "send({type:'cell',i:0});send({type:'cell',i:1})",
        "bugs": "if(w.targets[0])send({type:'tap',x:w.targets[0].x,y:w.targets[0].y})",
        "tower": "send({type:'tap'})",
        "typing": "send({type:'text',value:w.text[0]})",
        "debug": (
            "send({type:'line',i:w.tasks[0].line});send({type:'answer',i:w.tasks[0].answer})"
        ),
        "2048": "send({type:'move',dir:'left'})",
        "drop": "send({type:'tap',x:180})",
        "memory": "send({type:'cell',i:0})",
        "react": "send({type:'tap'})",
    }
    result = trace(setup, "W.advance(w,10);" + actions[game] + ";W.advance(w,120)")
    assert arcade_runtime.verify(setup, result["events"], result["ticks"]) == result["report"]
    with arcade_runtime.context() as vm:
        vm.eval(
            """function batched(s,n){const w=ArcadeWorld.create(s);
              for(let i=0;i<120;i+=n){Math.random();
                ArcadeWorld.advance(w,Math.min(n,120-i));}return JSON.stringify(w)}"""
        )
        assert vm.call("batched", setup, 1) == vm.call("batched", setup, 12)


def test_server_records_claims_survive_restart_and_duplicate_submits(store):
    result, session, replay = finish_debug(store)
    assert result["run"]["score"] == 8 and result["run"]["accepted"]
    duplicate = store.finish("p1", session["id"], [], 0)
    assert duplicate["duplicate"] and duplicate["run"] == result["run"]
    profile = store.profile("p1")
    assert sum(a["unlocked"] for a in profile["achievements"]) == 3
    award = profile["goals"]["debug"]["id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: store.claim("p1", award), range(4)))
    restarted = ArcadeStore(store.path, store.clock)
    assert restarted.profile("p1")["balance"] == 10
    assert restarted.replay("p1", result["run"]["id"])["actions"] == replay["events"]
    with pytest.raises(ArcadeError):
        restarted.replay("p2", result["run"]["id"])
    with pytest.raises(ArcadeError):
        restarted.claim("p2", award)


def test_practice_incomplete_and_abandoned_runs_cannot_win_coins(store):
    result, _, _ = finish_debug(store, mode="practice")
    assert not result["run"]["accepted"]
    assert not store.profile("p1")["awards"]
    session = store.session("p1", "typing", "ranked", "keyboard")
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(1)
    partial = store.finish("p1", session["id"], [{"type": "text", "value": "x", "t": 0}], 30)
    assert not partial["run"]["accepted"]
    session = store.session("p1", "2048", "ranked", "keyboard")
    store.clock_action("p1", session["id"], "start")
    abandoned = store.finish("p1", session["id"], [], 0, True)
    assert not abandoned["run"]["accepted"]
    assert not store.board()["rows"]


def test_server_rejects_clock_owner_cohort_and_event_order(store):
    session = store.session("p1", "tower", "ranked", "keyboard")
    with pytest.raises(ArcadeError):
        store.clock_action("p2", session["id"], "start")
    store.clock_action("p1", session["id"], "start")
    with pytest.raises(ArcadeError):
        store.finish("p1", session["id"], [], 600)
    store.clock.advance(3)
    for actions in (
        [{"t": 0, "type": "tap", "source": "touch"}],
        [{"t": 100, "type": "tap"}, {"t": 20, "type": "tap"}],
        [{"t": 0, "type": "tap"}] * 51,
    ):
        with pytest.raises(ArcadeError):
            store.finish("p1", session["id"], actions, 120)
    store.clock_action("p1", session["id"], "pause")
    store.clock.advance(60)
    with pytest.raises(ArcadeError):
        store.finish("p1", session["id"], [], 600)
    store.clock_action("p1", session["id"], "resume")
    store.clock.advance(1)
    assert store.finish("p1", session["id"], [], 120)["run"]["accepted"]


def test_typing_needs_accuracy_and_practice_adapts_to_missed_letters(store):
    def run(correct):
        session = store.session("p1", "typing", "ranked", "keyboard")
        replay = trace(
            session["setup"],
            f"""
          for(let i=0;i<160;i++){{W.advance(w,6);
            send({{type:'text',value:i<{correct}?w.text[i]:'~'}});}}
          W.advance(w,3601);
        """,
        )
        store.clock_action("p1", session["id"], "start")
        store.clock.advance(80)
        return store.finish("p1", session["id"], replay["events"], replay["ticks"])

    assert run(140)["run"]["report"]["details"]["accuracy"] == 87
    assert not store.profile("p1")["goals"]["typing"]["eligible"]
    practice = store.session("p1", "typing", "practice", "keyboard")
    assert practice["setup"]["weak"]
    assert run(150)["run"]["report"]["details"]["accuracy"] == 93
    assert store.profile("p1")["goals"]["typing"]["eligible"]
    assert store.session("p1", "typing", "ranked", "keyboard")["setup"]["weak"] == ""


def test_practice_undo_only_and_generated_tasks_are_varied():
    with arcade_runtime.context() as vm:
        vm.eval("""function check(mode){let w=ArcadeWorld.create({game:'2048',seed:8,mode});
          const before=w.board.slice();ArcadeWorld.input(w,{type:'move',dir:'left'});
          const undone=ArcadeWorld.input(w,{type:'undo'});return {undone,before,after:w.board};}
          function tasks(seed){return ArcadeWorld.create({game:'debug',seed}).tasks;}""")
        practice = vm.call("check", "practice")
        assert practice["undone"] and practice["before"] == practice["after"]
        assert not vm.call("check", "ranked")["undone"]
        assert vm.call("tasks", 1) != vm.call("tasks", 2)
        tasks = vm.call("tasks", 1)
        assert all(tasks[i]["why"] != tasks[i + 1]["why"] for i in range(0, 8, 2))


# Ledger/ranking fixtures model already-verified rows to isolate settlement rules.
def verified(store, player, game, score, device="keyboard", detail=None):
    import secrets

    key = secrets.token_hex(8)
    report = {
        "game": game,
        "score": score,
        "rankScore": score,
        "level": 3,
        "timeMs": 60000,
        "details": {"accuracy": 100, "reactionMs": 300, "mistakes": 0, **(detail or {})},
    }
    with store.db() as db:
        db.execute(
            "INSERT INTO arcade_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                key,
                key,
                player,
                game,
                "ranked",
                device,
                week_key(store.clock()),
                store.clock(),
                score,
                score,
                json.dumps(report),
                "[]",
                3600,
                1,
            ),
        )


def test_device_cohorts_contribute_once_and_three_games_required(store):
    verified(store, "p1", "tower", 20)
    verified(store, "p1", "tower", 18, "touch")
    verified(store, "p2", "tower", 10)
    assert store.board("tower", device="touch")["rows"][0]["player"] == "p1"
    overall = store.board()["rows"]
    assert overall[0]["score"] == 100 and overall[0]["games"] == 1
    assert not overall[0]["prizeEligible"]
    verified(store, "p1", "debug", 8)
    verified(store, "p1", "memory", 20)
    assert store.board()["rows"][0]["prizeEligible"]


def test_week_closes_automatically_once_with_100_75_50_and_frozen_winners(store):
    for i in range(1, 5):
        for game in ("tower", "debug", "memory"):
            verified(store, f"p{i}", game, 30 - i if game != "debug" else 9 - i)
    # A one-game specialist is excluded from prize selection.
    verified(store, "p5", "tower", 200)
    store.clock.advance(8 * 86400)

    async def run():
        worker = asyncio.create_task(maintenance_worker(store, 0.01))
        await asyncio.sleep(0.15)
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

    asyncio.run(run())
    for i, amount in ((1, 100), (2, 75), (3, 50), (4, 0), (5, 0)):
        assert store.profile(f"p{i}")["balance"] == amount
    first = store.board()["history"]
    ArcadeStore(store.path, store.clock).maintain()
    assert store.board()["history"] == first
    assert sum(len(store.profile(f"p{i}")["credits"]) for i in range(1, 6)) == 3


def test_cap_defers_earned_awards_without_loss_and_settings_are_persistent(store):
    with store.db() as db:
        for i in range(5):
            store._award(db, "p1", "test", "all", f"m:{i}", 50, "Тест", True)
    store.maintain()
    assert store.profile("p1")["balance"] == 200
    assert len([a for a in store.profile("p1")["awards"] if a["credited"] is None]) == 1
    assert store.policy(150)["cap"] == 150
    assert store.profile("p1")["cap"]["limit"] == 200
    store.clock.advance(8 * 86400)
    store.maintain()
    assert store.profile("p1")["balance"] == 250
    assert store.profile("p1")["cap"]["limit"] == 150
    with pytest.raises(ArcadeError):
        store.settings("p1", {"skin": "nebula"})
    prefs = {"ui": {"tab": "progress", "filter": "puzzle", "scroll": 42}, "quality": "low"}
    store.settings("p1", prefs)
    assert ArcadeStore(store.path, store.clock).profile("p1")["settings"]["ui"] == prefs["ui"]


def make_client(store):
    app = FastAPI()

    async def auth(request: Request):
        token = request.headers.get("x-miniapp-token")
        if token not in ("p1", "p2", "director"):
            raise HTTPException(401, "Нет доступа")
        return {"player": "p1" if token == "director" else token, "director": token == "director"}

    app.include_router(make_router(store, auth), prefix="/preview/arcade")
    return TestClient(app)


def test_api_rejects_scores_without_trace_extra_fields_and_director_only_policy(store):
    client = make_client(store)
    assert client.get("/preview/arcade/profile").status_code == 401
    h = {"x-miniapp-token": "p1"}
    session = client.post(
        "/preview/arcade/sessions",
        headers=h,
        json={"game": "2048", "mode": "ranked", "device": "keyboard"},
    ).json()
    assert (
        client.post(
            f"/preview/arcade/sessions/{session['id']}/finish",
            headers=h,
            json={"actions": [], "ticks": 0, "score": 9999},
        ).status_code
        == 422
    )
    assert client.patch("/preview/arcade/policy", headers=h, json={"cap": 500}).status_code == 403
    assert (
        client.patch(
            "/preview/arcade/policy", headers={"x-miniapp-token": "director"}, json={"cap": 500}
        ).status_code
        == 200
    )


@pytest.fixture
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge" if os.name == "nt" else None)
        except pw.Error as error:
            if "Executable doesn't exist" in str(error) or "distribution 'msedge'" in str(error):
                pytest.skip("Install Playwright Chromium for arcade browser checks")
            raise
        yield b
        b.close()


@pytest.fixture
def arcade(browser, tmp_path):
    store = ArcadeStore(tmp_path / "ui.sqlite3")
    store.register(
        [
            {"id": "p1", "name": "Марк", "group": "Демо"},
            {"id": "p2", "name": "Соня", "group": "Демо"},
        ]
    )
    client = make_client(store)
    source = inject_games((STATIC / "index.html").read_text(encoding="utf-8"))
    source = source.replace(
        "</head>",
        '<script>window.ALGO_ARCADE_API="/preview/arcade";window.ALGO_GAME_PLAYERS=[{id:"p1",name:"Марк",token:"p1"},{id:"p2",name:"Соня",token:"p2"}];</script></head>',
    )
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    page.set_default_timeout(5000)
    errors = []

    def route(r):
        path = r.request.url.split("?", 1)[0].removeprefix("http://127.0.0.1:8779")
        if path.startswith("/preview/arcade"):
            result = client.request(
                r.request.method,
                r.request.url.removeprefix("http://127.0.0.1:8779"),
                headers={
                    "x-miniapp-token": r.request.headers.get("x-miniapp-token", ""),
                    "content-type": "application/json",
                },
                content=r.request.post_data,
            )
            if result.status_code >= 400:
                print("API", r.request.method, path, r.request.post_data, result.text)
            r.fulfill(
                status=result.status_code, body=result.content, content_type="application/json"
            )
        elif path == "/miniapp":
            r.fulfill(body=source, content_type="text/html")
        elif path.startswith("/miniapp/static/"):
            target = STATIC / path.removeprefix("/miniapp/static/")
            if target.is_file():
                r.fulfill(path=str(target))
            else:
                r.fulfill(status=404)
        else:
            r.fulfill(status=404)

    context.route("http://127.0.0.1:8779/**", route)
    context.route("https://st.max.ru/**", lambda r: r.abort())
    context.add_init_script(
        "const st=window.setTimeout;window.setTimeout=(f,t,...a)=>st(f,t===650?1:t,...a)"
    )
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:8779/miniapp?demo=1&demo_role=student&view=games")
    page.locator(".game-card").first.wait_for()
    yield page, store
    context.close()
    client.close()
    assert not errors, errors


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_all_ten_games_start_pause_finish_and_fit(arcade, width):
    page, store = arcade
    page.set_viewport_size({"width": width, "height": 900})
    assert page.locator(".game-card").count() == 10
    for game in GAMES:
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator("[data-skip-guide]").click()
        try:
            page.locator(".arcade-pause").wait_for(state="visible")
        except Exception:
            print(
                game,
                page.locator("dialog[open]").inner_text(),
                page.locator("body").inner_text()[-400:],
            )
            raise
        page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
        if game == "typing":
            field = page.locator(".typing-input")
            field.press_sequentially("Кос")
            page.wait_for_function(
                "/^\\d+ с$/.test(document.querySelector('#gameClock').textContent)"
            )
        elif game == "2048":
            page.keyboard.press("ArrowLeft")
        page.keyboard.press("Escape")
        try:
            page.get_by_role("button", name="Продолжить →").wait_for()
        except Exception:
            print("PAUSE", game, page.locator("body").inner_text()[-800:])
            raise
        ticks = page.locator("#gameClock").inner_text()
        page.wait_for_timeout(50)
        assert page.locator("#gameClock").inner_text() == ticks
        page.get_by_role("button", name="Продолжить →").click()
        page.wait_for_timeout(50)
        page.locator("#gameFinish").click()
        page.locator("[data-again]").wait_for()
        assert "Не удалось" not in page.locator(".game-result").inner_text()
        assert page.locator("dialog[open]").evaluate("(d)=>d.scrollWidth<=d.clientWidth")
        page.locator("[data-back]").click()
    assert len(store.profile("p1")["runs"]) == 10
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")


def test_tutorial_then_real_2048_has_one_handler_and_practice_undo(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="2048"]').click()
    page.locator("#gameStart").click()
    page.keyboard.press("ArrowLeft")
    page.get_by_role("button", name="Играть →", exact=True).click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Продолжить →").click()
    page.locator("#gameFinish").click()
    page.locator("[data-back]").click()
    page.locator('.game-card[data-game="2048"]').click()
    page.locator('[data-mode="practice"]').click()
    page.locator("#gameStart").click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    before = page.locator(".number-grid").inner_text()
    page.keyboard.press("ArrowLeft")
    page.locator("[data-undo]").click()
    assert page.locator(".number-grid").inner_text() == before


def test_sections_mastery_and_server_saved_selection_survive_reload(arcade):
    page, store = arcade
    page.locator('[data-tab="achievements"]').click()
    assert page.locator(".game-achievement").count() == 30
    page.locator('[data-tab="looks"]').click()
    assert page.locator(".arcade-look").count() == 4
    page.locator('[data-tab="progress"]').click()
    page.wait_for_timeout(300)
    page.reload()
    page.locator(".arcade-progress-heading").wait_for()
    assert store.profile("p1")["settings"]["ui"]["tab"] == "progress"
    assert page.locator("dialog[open]").count() == 0
    page.select_option("#arcadeStatsGame", "typing")
    page.wait_for_timeout(300)
    page.reload()
    page.locator(".arcade-progress-heading").wait_for()
    assert page.locator("#arcadeStatsGame").input_value() == "typing"


@pytest.mark.parametrize("game", list(GAMES))
def test_first_time_tutorial_requires_a_successful_action(arcade, game):
    page, store = arcade
    page.locator(f'.game-card[data-game="{game}"]').click()
    page.locator("#gameStart").click()
    if game in ("orbit", "tower", "react"):
        page.keyboard.press("Space")
    elif game == "bugs":
        canvas = page.locator(".game-stage canvas")
        box = canvas.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] * 220 / 430)
    elif game == "evolve":
        page.locator('[data-cell="0"]').click()
        page.locator('[data-cell="1"]').click()
    elif game == "typing":
        page.locator(".typing-input").press_sequentially("кот")
    elif game == "debug":
        task = page.evaluate("ArcadeWorld.create({game:'debug',seed:41,mode:'practice'}).tasks[0]")
        page.locator(f'[data-line="{task["line"]}"]').click()
        page.locator(f'[data-option="{task["answer"]}"]').click()
    elif game == "2048":
        page.keyboard.press("ArrowLeft")
    elif game == "drop":
        canvas = page.locator(".game-stage canvas")
        box = canvas.bounding_box()
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    elif game == "memory":
        page.locator('[data-card="0"]').click()
        page.locator('[data-card="2"]').click()
    page.get_by_role("button", name="Играть →", exact=True).wait_for()
    assert not store.profile("p1")["awards"]
    assert not store.profile("p1")["runs"]
    page.wait_for_timeout(150)
    assert game in store.profile("p1")["settings"]["tutorials"]


def test_ui_generated_python_completion_award_and_replay(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="debug"]').click()
    page.locator("[data-skip-guide]").click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    with store.db() as db:
        session = dict(db.execute("SELECT * FROM arcade_sessions").fetchone())
    tasks = page.evaluate("s=>ArcadeWorld.create(s).tasks", json.loads(session["setup"]))
    for task in tasks:
        page.locator(f'[data-line="{task["line"]}"]').click()
        page.locator(f'[data-option="{task["answer"]}"]').click()
        page.locator("[data-next]").click()
    page.locator("[data-again]").wait_for()
    assert store.profile("p1")["best"]["debug"] == 8
    page.locator("[data-claim-result]").click()
    page.wait_for_timeout(250)
    assert store.profile("p1")["balance"] == 10
    page.locator("[data-analysis]").click()
    assert page.locator(".arcade-replay[open]").count() == 1


def test_first_character_starts_typing_timer_and_new_page_restores_results(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="typing"]').click()
    page.locator("[data-skip-guide]").click()
    page.locator(".typing-input").wait_for()
    page.wait_for_timeout(250)
    with store.db() as db:
        assert db.execute("SELECT started FROM arcade_sessions").fetchone()[0] is None
    sample = page.locator(".typing-passage").inner_text()[:3]
    page.locator(".typing-input").press_sequentially(sample)
    page.wait_for_function("/^\\d+ с$/.test(document.querySelector('#gameClock').textContent)")
    page.locator("#gameFinish").click()
    page.locator("[data-back]").click()
    other = page.context.new_page()
    other.goto(page.url)
    other.locator(".game-card").first.wait_for()
    other.locator('[data-tab="progress"]').click()
    other.select_option("#arcadeStatsGame", "typing")
    assert other.locator(".arcade-chart").is_visible()
    assert store.profile("p1")["runs"][0]["score"] == 3
    other.close()


def test_weekly_challenge_seed_is_shared_but_practice_is_variable(store):
    first = store.session("p1", "drop", "ranked", "keyboard")["setup"]
    assert first["seed"] == store.session("p2", "drop", "ranked", "keyboard")["setup"]["seed"]
    assert first["seed"] != store.session("p1", "drop", "practice", "keyboard")["setup"]["seed"]
    store.clock.advance(8 * 86400)
    assert first["seed"] != store.session("p1", "drop", "ranked", "keyboard")["setup"]["seed"]


def test_three_mastery_tiers_require_quality_and_unlock_cosmetics_without_game_advantage(store):
    assert not store._master("typing", 240, {"accuracy": 94}, 2)
    assert store._master("typing", 240, {"accuracy": 95}, 2)
    assert not store._master("react", 15, {"reactionMs": 351, "mistakes": 0}, 2)
    assert not store._master("react", 15, {"reactionMs": 300, "mistakes": 1}, 2)
    finish_debug(store)
    settings = store.settings("p1", {"skin": "nebula", "theme": "nebula"})
    assert settings["skin"] == "nebula"
    setup = store.session("p1", "2048", "ranked", "keyboard")["setup"]
    assert "skin" not in setup and "theme" not in setup
    assert len(store.profile("p1")["achievements"]) == 30
    with pytest.raises(ArcadeError):
        store.settings("p1", {"tutorials": [{}]})


def test_cross_week_attempt_keeps_history_but_not_new_week_rank(store):
    from datetime import datetime, timedelta

    from app.services.arcade import MOSCOW

    current = week_key(store.clock())
    monday = datetime.fromisoformat(current).replace(tzinfo=MOSCOW) + timedelta(days=7)
    store.clock.now = monday.timestamp() - 0.5
    session = store.session("p1", "2048", "ranked", "keyboard")
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(1)
    result = store.finish("p1", session["id"], [], 30)
    assert not result["run"]["accepted"]
    assert len(store.profile("p1")["runs"]) == 1


def test_tower_combo_and_drop_queue_are_physical_world_state():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,t=W.create({game:'tower',seed:4});
          t.left=t.blocks.at(-1).left;W.input(t,{type:'tap'});
          t.left=t.blocks.at(-1).left;W.input(t,{type:'tap'});
          const d=W.create({game:'drop',seed:5}),next=d.queue[1];
          W.input(d,{type:'tap',x:180});const before=d.balls[0].y;W.advance(d,30);
          return {combo:t.bestCombo,queue:d.queue.length,next:next===d.queue[0],
            falling:d.balls[0].y>before,velocity:d.balls[0].vy>0};})())""")
        )
        assert result == {"combo": 2, "queue": 3, "next": True, "falling": True, "velocity": True}
