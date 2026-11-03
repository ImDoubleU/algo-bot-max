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
        "kopatych": "send({type:'tap'})",
        "blocks": "send({type:'piece',i:0});send({type:'place',piece:0,x:0,y:0})",
        "runner": "send({type:'tap'})",
        "hill": "send({type:'pedal',pedal:'gas',value:1})",
        "bubbles": "send({type:'shoot',x:180,y:50})",
        "sort": "send(w.sortSolution[0])",
        "words": "send({type:'word',value:w.wordPack.answers[0]})",
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
    assert restarted.profile("p1")["balance"] == 40
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


def test_season_closes_automatically_once_with_100_75_50_and_frozen_winners(store):
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
def arcade(browser, tmp_path, request):
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
    touch = getattr(request, "param", None) == "touch"
    context = browser.new_context(
        viewport={"width": 390, "height": 844}, has_touch=touch, is_mobile=touch
    )
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
    assert page.locator(".game-card").count() == len(GAMES)
    for game in GAMES:
        page.locator(f'.game-card[data-game="{game}"]').click()
        if game == "kopatych":
            page.locator("[data-menu-levels]").click()
            page.locator("[data-farm-sprint]").first.click()
        page.locator('[data-mode="ranked"]').click()
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
            page.get_by_role("button", name="Продолжить").wait_for()
        except Exception:
            print("PAUSE", game, page.locator("body").inner_text()[-800:])
            raise
        ticks = page.locator("#gameClock").inner_text()
        page.wait_for_timeout(50)
        assert page.locator("#gameClock").inner_text() == ticks
        page.get_by_role("button", name="Продолжить").click()
        page.wait_for_timeout(50)
        page.locator("#gameFinish").click()
        page.locator("[data-again]").wait_for()
        assert "Не удалось" not in page.locator(".game-result").inner_text()
        assert page.locator("dialog[open]").evaluate("(d)=>d.scrollWidth<=d.clientWidth")
        page.locator("[data-back]").click()
    assert len(store.profile("p1")["runs"]) == len(GAMES)
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")


def test_tutorial_then_real_2048_has_one_handler_and_practice_undo(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="2048"]').click()
    page.locator("[data-menu-learning]").click()
    page.keyboard.press("ArrowLeft")
    page.locator("[data-learning-play]").click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Escape")
    page.get_by_role("button", name="Продолжить").click()
    page.locator("#gameFinish").click()
    page.locator("[data-back]").click()
    page.locator('.game-card[data-game="2048"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    before = page.locator(".number-grid").inner_text()
    page.keyboard.press("ArrowLeft")
    page.locator("[data-undo]").click()
    assert page.locator(".number-grid").inner_text() == before


def test_sections_mastery_and_server_saved_selection_survive_reload(arcade):
    page, store = arcade
    page.locator('[data-tab="achievements"]').click()
    assert page.locator(".game-achievement").count() == len(GAMES) * 3
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
    if game == "kopatych":
        page.locator("[data-menu-levels]").click()
        page.locator("[data-farm-sprint]").first.click()
    page.locator("[data-menu-learning]").click()
    if game in ("orbit", "tower", "react", "runner"):
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
    elif game == "kopatych":
        page.locator(".kopatych-tap").click()
    elif game == "blocks":
        page.locator('[data-block-cell="63"]').click()
    elif game == "bubbles":
        canvas = page.locator(".game-stage canvas")
        box = canvas.bounding_box()
        page.mouse.click(box["x"] + box["width"] * 145 / 360, box["y"] + box["height"] * 46 / 430)
    elif game == "sort":
        page.locator('[data-tube="0"]').click()
        page.locator('[data-tube="1"]').click()
    elif game == "words":
        page.locator("#arcadeWordInput").fill("сом")
        page.get_by_role("button", name="Проверить", exact=True).click()
    elif game == "hill":
        page.keyboard.down("ArrowRight")
        page.wait_for_function(
            'document.querySelector(".arcade-learning-tip").textContent.startsWith("Отпусти")'
        )
        page.keyboard.up("ArrowRight")
        page.keyboard.down("ArrowLeft")
    page.locator("[data-learning-play]").wait_for()
    if game == "hill":
        page.keyboard.up("ArrowLeft")
    assert not store.profile("p1")["awards"]
    assert not store.profile("p1")["runs"]
    page.wait_for_timeout(150)
    assert game in store.profile("p1")["settings"]["tutorials"]


def test_ui_generated_python_completion_award_and_replay(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="debug"]').click()
    page.locator('[data-mode="ranked"]').click()
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
    assert page.locator(".arcade-reward-receipt").is_visible()
    assert page.locator("[data-claim-result]").count() == 0
    assert store.profile("p1")["balance"] == 40
    page.locator(".arcade-result-details summary").click()
    page.locator("[data-analysis]").click()
    assert page.locator(".arcade-replay[open]").count() == 1


def test_first_character_starts_typing_timer_and_new_page_restores_results(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="typing"]').click()
    page.locator('[data-mode="ranked"]').click()
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


def test_season_challenge_seed_is_shared_but_practice_is_variable(store):
    first = store.session("p1", "drop", "ranked", "keyboard")["setup"]
    assert first["seed"] == store.session("p2", "drop", "ranked", "keyboard")["setup"]["seed"]
    assert first["seed"] != store.session("p1", "drop", "practice", "keyboard")["setup"]["seed"]
    store.clock.advance(8 * 86400)
    assert first["seed"] != store.session("p1", "drop", "ranked", "keyboard")["setup"]["seed"]


def test_three_mastery_tiers_require_quality_and_unlock_cosmetics_without_game_advantage(store):
    assert not store._master("typing", 240, {"accuracy": 94}, 2)
    assert store._master("typing", 400, {"accuracy": 99}, 2)
    assert not store._master("react", 15, {"reactionMs": 351, "mistakes": 0}, 2)
    assert not store._master("react", 15, {"reactionMs": 300, "mistakes": 1}, 2)
    finish_debug(store)
    settings = store.settings("p1", {"skin": "nebula", "theme": "nebula"})
    assert settings["skin"] == "nebula"
    setup = store.session("p1", "2048", "ranked", "keyboard")["setup"]
    assert "skin" not in setup and "theme" not in setup
    assert len(store.profile("p1")["achievements"]) == len(GAMES) * 3
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


def play_extra(store, game, script, mode="ranked"):
    session = store.session("p1", game, mode, "keyboard")
    run = trace(session["setup"], script)
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(run["ticks"] / 60 + 1)
    result = store.finish("p1", session["id"], run["events"], run["ticks"])
    assert result["run"]["score"] == run["report"]["score"]
    return result, run


def test_kopatych_upgrades_and_full_harvest_are_replayed_before_reward(store):
    result, run = play_extra(
        store,
        "kopatych",
        """
      while(!w.ended&&w.tick<5500){
        if(w.tick%8===0)send({type:'tap'});
        if(w.tick%60===0)for(let i=0;i<3;i++)if(w.upgrades[i]<6&&
          w.harvest-w.spent>=ArcadeExtras.cost(w,i))send({type:'buy',i});
        W.advance(w,1);
      }
    """,
    )
    assert result["run"]["accepted"] and result["run"]["score"] >= 1800
    assert run["report"]["timeMs"] >= 90000
    profile = store.profile("p1")
    assert profile["goals"]["kopatych"]["eligible"]
    assert (
        len([a for a in profile["achievements"] if a["game"] == "kopatych" and a["unlocked"]]) >= 2
    )
    assert store.claim("p1", profile["goals"]["kopatych"]["id"])["balance"] == (
        5
        + sum(
            a["reward"]
            for a in profile["achievements"]
            if a["game"] == "kopatych" and a["unlocked"]
        )
    )
    with arcade_runtime.context() as vm:
        report = vm.call(
            "ArcadeWorld.verify",
            {"game": "kopatych", "seed": 4, "mode": "ranked"},
            [{"t": 0, "type": "tap"}] * 10,
            0,
        )
        assert report["score"] == 1  # Holding/autoclicking cannot add ten taps at the same instant.


def test_blocks_clear_crossing_lines_once_and_reject_overlap():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,X=ArcadeExtras,w=W.create({game:'blocks',seed:3});
          for(let i=0;i<7;i++){w.blockBoard[56+i]=1;w.blockBoard[i*8+7]=2;}
          w.pieces=[[[0,0]],[[0,0]],[[0,0]]];
          W.input(w,{type:'place',piece:0,x:7,y:7});const cleared=w.blockBoard.every(v=>v===0);
          W.input(w,{type:'place',piece:1,x:0,y:0});const before=w.score;
          const overlap=W.input(w,{type:'place',piece:2,x:0,y:0});
          const outside=W.input(w,{type:'place',piece:2,x:8,y:0});
          w.blockBoard.fill(1);
          return {score:before,lines:w.lines,cleared,overlap,outside,
            available:X.blocksAvailable(w)};
        })())""")
        )
        assert result == {
            "score": 82,
            "lines": 2,
            "cleared": True,
            "overlap": False,
            "outside": False,
            "available": False,
        }


def test_retired_runner_replays_still_clear_their_original_obstacles():
    setup = dict(game="runner", seed=17, mode="ranked", device="keyboard")
    run = trace(
        setup,
        """
      while(!w.ended&&w.score<28&&w.tick<18000){
        const next=w.obstacles.find(o=>!o.passed);
        if(w.runnerGround&&next&&next.x<128&&next.x+next.width>65)send({type:'tap'});
        W.advance(w,1);
      }
    """,
    )
    assert arcade_runtime.verify(setup, run["events"], run["ticks"]) == run["report"]
    assert run["report"]["score"] >= 25
    assert run["report"]["level"] >= 4
    assert run["report"]["details"]["jumps"] >= 25


def test_bubble_shooter_physics_pops_groups_and_server_accepts_goal(store):
    result, run = play_extra(
        store,
        "bubbles",
        """
      for(let shot=0;shot<12&&!w.ended&&w.score<250;shot++){
        let best=null;
        for(let x=-100;x<=460;x+=16){
          const copy=JSON.parse(JSON.stringify(w));
          W.input(copy,{type:'shoot',x,y:40});let n=0;
          while(copy.projectile&&!copy.ended&&n++<140)W.advance(copy,1);
          const quality=copy.ended?-10000:copy.score-w.score;
          if(!best||quality>best.quality)best={x,quality};
        }
        send({type:'shoot',x:best.x,y:40});
        while(w.projectile&&!w.ended)W.advance(w,1);
        W.advance(w,6);
      }
    """,
    )
    assert result["run"]["accepted"] and result["run"]["score"] >= 200
    assert run["report"]["details"]["moves"] > 0
    assert store.profile("p1")["goals"]["bubbles"]["eligible"]


def test_every_sort_scramble_is_reversible_and_more_colors_are_added(store):
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,results=[];
          for(let seed=0;seed<24;seed++){
            const w=W.create({game:'sort',seed});
            for(let level=0;level<5;level++){
              const colors=w.tubes.length-2,counts=Array(colors).fill(0);
              w.tubes.flat().forEach(c=>counts[c]++);
              if(counts.some(n=>n!==4))return false;
              for(const a of w.sortSolution.slice())W.input(w,a);
              if(!w.sortWon||w.score!==level+1)return false;
              results.push(colors);W.input(w,{type:'next'});
            }
          }
          return results.length===120&&results.slice(0,5).join()==='3,4,5,6,7';
        })())""")
        )
        assert result is True
    result, _ = play_extra(
        store,
        "sort",
        """
      for(let level=0;level<3;level++){
        for(const a of w.sortSolution.slice()){send(a);W.advance(w,4);}
        if(level<2){send({type:'next'});W.advance(w,4);}
      }
    """,
    )
    assert result["run"]["score"] == 3 and result["run"]["accepted"]
    assert store.profile("p1")["goals"]["sort"]["eligible"]


def test_words_dictionary_rounds_duplicates_and_timed_reward(store):
    result, run = play_extra(
        store,
        "words",
        """
      for(let i=0;i<24;i++){
        const answer=w.wordPack.answers.find(a=>!w.roundWords.includes(a));
        send({type:'word',value:answer});W.advance(w,15);
      }
      W.advance(w,10801-w.tick);
    """,
    )
    assert result["run"]["accepted"] and result["run"]["score"] == 24
    assert run["report"]["level"] >= 3
    assert store.profile("p1")["goals"]["words"]["eligible"]
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'words',seed:3});
          const good=w.wordPack.answers[0];W.input(w,{type:'word',value:good});
          W.input(w,{type:'word',value:good});W.input(w,{type:'word',value:'несуществующееслово'});
          W.input(w,{type:'hint'});return {score:w.score,hint:w.wordHint,
            packs:ArcadeExtras.packs.every(p=>p.answers.length>=8)};
        })())""")
        )
        assert result == {"score": 1, "hint": "", "packs": True}


def test_added_game_boards_are_visible_and_practice_still_has_no_rewards(store):
    client = make_client(store)
    headers = {"x-miniapp-token": "p1"}
    for game in ("kopatych", "blocks", "hill", "bubbles", "sort", "words"):
        response = client.get("/preview/arcade/boards", params={"game": game}, headers=headers)
        assert response.status_code == 200
    result, _ = play_extra(
        store, "kopatych", "send({type:'tap'});W.advance(w,5500)", mode="practice"
    )
    assert not result["run"]["accepted"] and not store.profile("p1")["awards"]


def test_sort_and_words_render_real_controls_and_accept_actions(arcade):
    page, _ = arcade
    page.locator('.game-card[data-game="sort"]').click()
    page.locator("[data-menu-learning]").click()
    assert page.locator(".sort-ball").count() == 8
    assert "< i" not in page.locator(".sort-game").inner_text()
    page.locator('[data-tube="0"]').click()
    page.locator('[data-tube="1"]').click()
    page.locator("[data-learning-play]").wait_for()
    page.locator(".game-close").click()
    page.locator('.game-card[data-game="words"]').click()
    page.locator("[data-menu-learning]").click()
    assert page.locator("#arcadeWordInput").bounding_box()["width"] > 200
    page.locator("#arcadeWordInput").fill("сом")
    page.locator(".words-form").evaluate("(f)=>f.requestSubmit()")
    page.locator("[data-learning-play]").wait_for()


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
def test_expansion_accepts_real_touch_input_and_onscreen_letters(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="kopatych"]').tap()
    page.locator("[data-menu-levels]").tap()
    page.locator("[data-farm-sprint]").first.tap()
    page.locator('[data-mode="ranked"]').tap()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent==='90 с'")
    for _ in range(3):
        page.locator(".kopatych-tap").tap()
        page.wait_for_timeout(100)
    page.locator("#gameFinish").tap()
    page.locator("[data-back]").tap()
    run = store.profile("p1")["runs"][0]
    assert run["score"] == 3
    assert run["device"] == "touch"
    assert all(a["source"] == "touch" for a in store.replay("p1", run["id"])["actions"])
    page.locator('.game-card[data-game="blocks"]').tap()
    page.locator('[data-mode="ranked"]').tap()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent.length>0")
    page.locator('[data-piece="0"]').tap()
    page.locator('[data-block-cell="0"]').tap()
    assert page.locator(".block-cell.is-filled").count() > 0
    page.locator("#gameFinish").tap()
    page.locator("[data-back]").tap()
    page.locator('.game-card[data-game="words"]').tap()
    page.locator("[data-menu-learning]").tap()
    for i in (2, 1, 3):
        page.locator(f'[data-letter="{i}"]').tap()
    assert page.locator("#arcadeWordInput").input_value() == "сом"
    page.get_by_role("button", name="Проверить", exact=True).tap()
    page.locator("[data-learning-play]").wait_for()


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_persistent_farm_tabs_fit_mobile_and_desktop(arcade, width):
    page, store = arcade
    page.set_viewport_size({"width": width, "height": 900})
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    assert page.locator("#gameDialog").count() == 0
    for tab in ("home", "upgrades", "tasks", "valley"):
        page.locator(f'.farm-tabs [data-farm-tab="{tab}"]').click()
        assert page.locator("#kopatychFarm").evaluate("(d)=>d.scrollWidth<=d.clientWidth")
        assert page.locator(".farm-content").evaluate("(d)=>d.scrollWidth<=d.clientWidth")
        if tab == "tasks":
            for view in ("daily", "story", "orders", "badges"):
                page.locator(f'.farm-task-filters [data-task-view="{view}"]').click()
                assert page.locator(".farm-content").evaluate("(d)=>d.scrollWidth<=d.clientWidth")
    assert not store.profile("p1")["awards"]


def test_farm_gifts_purchases_and_keyboard_taps_survive_reentry(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    for _ in range(5):
        page.keyboard.press("Space")
        page.wait_for_timeout(160)
    page.wait_for_function("document.querySelector('#kopatychFarm')?.dataset.saveState==='saved'")
    assert FarmStore(store).get("p1")["taps"] == 5
    page.locator('.farm-tabs [data-farm-tab="tasks"]').click()
    page.locator('[data-farm-action="claim_daily"]').click()
    page.wait_for_function("document.querySelector('[data-farm-action=claim_daily]')?.disabled")
    page.locator('.farm-tabs [data-farm-tab="upgrades"]').click()
    page.locator('[data-farm-action="buy"][data-item="beds"]').click()
    page.wait_for_function("document.querySelector('[data-farm-income]')?.textContent==='+210'")
    page.locator("[data-farm-close]").click()
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-shop-grid").wait_for()
    assert (
        page.locator('.farm-tabs [data-farm-tab="upgrades"]').get_attribute("aria-pressed")
        == "true"
    )
    state = FarmStore(store).get("p1")
    assert state["balance"] == 135 and state["daily"]["claimed"]
    assert next(i for i in state["items"] if i["id"] == "beds")["level"] == 1
    page.locator("[data-farm-close]").click()
    page.select_option("#gamesPlayer", "p2")
    page.locator(".game-card").first.wait_for()
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    assert page.locator("[data-farm-bank]").inner_text() == "150"
    assert FarmStore(store).get("p2")["taps"] == 0


def test_farm_return_shows_one_offline_receipt_without_manual_claim(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    page.locator("[data-farm-close]").click()
    store.clock.advance(7200)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-offline").wait_for()
    assert "+240" in page.locator(".farm-offline").inner_text()
    assert FarmStore(store).get("p1")["balance"] == 390
    page.locator("[data-dismiss-offline]").click()
    assert page.locator(".farm-offline").is_hidden()
    page.locator("[data-farm-close]").click()
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    assert page.locator(".farm-offline").is_hidden()
    assert page.locator("[data-farm-bank]").inner_text() == "390"


def test_lost_farm_purchase_ack_retries_same_receipt_without_second_debit(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    farm = FarmStore(store)
    lost = [False]

    def interrupt(r):
        payload = json.loads(r.request.post_data)
        if payload["action"] == "buy" and not lost[0]:
            lost[0] = True
            farm.act(
                "p1", payload["id"], payload["action"], payload.get("item"), payload.get("count", 1)
            )
            r.abort("failed")
        else:
            r.fallback()

    page.route("http://127.0.0.1:8779/preview/arcade/farm/actions", interrupt)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    page.locator('.farm-tabs [data-farm-tab="upgrades"]').click()
    page.locator('[data-item="beds"]').click()
    page.locator(".farm-retry").wait_for()
    assert farm.get("p1")["balance"] == 30
    page.locator(".farm-retry").click()
    page.wait_for_function("document.querySelector('#kopatychFarm')?.dataset.saveState==='saved'")
    state = farm.get("p1")
    assert (
        state["balance"] == 30
        and next(i for i in state["items"] if i["id"] == "beds")["level"] == 1
    )


def test_farm_tournament_remains_separate_from_passive_carrots(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    page.locator("[data-farm-sprint]").first.click()
    assert page.locator("#kopatychFarm").count() == 0
    page.locator('[data-mode="ranked"]').click()
    page.wait_for_function("document.querySelector('#gameClock')?.textContent==='90 с'")
    page.locator("#gameFinish").click()
    page.locator("[data-back]").click()
    assert not store.profile("p1")["goals"]["kopatych"]["eligible"]


@pytest.mark.parametrize("arcade", ["touch"], indirect=True)
def test_persistent_farm_accepts_touch_taps_and_closing_flushes_pending_input(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    page.locator('.game-card[data-game="kopatych"]').tap()
    page.locator("[data-menu-levels]").tap()
    page.locator(".farm-bear").wait_for()
    for _ in range(3):
        page.locator(".farm-bear").tap()
        page.wait_for_timeout(150)
    page.locator("[data-farm-close]").tap()
    page.wait_for_timeout(350)
    assert FarmStore(store).get("p1")["taps"] == 3
    page.locator('.game-card[data-game="kopatych"]').tap()
    page.locator("[data-menu-levels]").tap()
    page.locator(".farm-bear").wait_for()
    assert page.locator("[data-farm-bank]").inner_text() == "153"


def test_farm_explains_purchase_and_collects_delivery_and_its_rewards_together(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    page.locator('[data-farm-action="claim_all"]').click()
    page.wait_for_function("document.querySelector('[data-farm-bank]').textContent==='250'")
    page.locator('.farm-tabs [data-farm-tab="upgrades"]').click()
    bed = page.locator('[data-farm-action="buy"][data-item="beds"]')
    assert bed.locator(".farm-effect b").inner_text() == "0"
    assert bed.locator(".farm-effect strong").inner_text() == "90"
    bed.click()
    page.wait_for_function("document.querySelector('[data-farm-income]').textContent==='+210'")
    page.locator(".farm-production summary").click()
    assert "Грядки" in page.locator(".farm-production-rows").inner_text()
    page.locator('.farm-tabs [data-farm-tab="tasks"]').click()
    page.locator('.farm-task-filters [data-task-view="orders"]').click()
    page.locator('[data-farm-action="start_order"][data-item="basket"]').click()
    page.locator(".farm-active-order").wait_for()
    assert farm.get("p1")["balance"] == 90
    assert page.locator('[data-farm-action="claim_order"]').is_disabled()
    page.locator("[data-farm-close]").click()
    store.clock.advance(300)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-active-order").wait_for()
    before = farm.get("p1")
    assert before["claimable"]["amount"] == 450
    page.locator('[data-farm-action="claim_all"]').click()
    page.wait_for_function("!document.querySelector('.farm-active-order')")
    after = farm.get("p1")
    assert after["balance"] == before["balance"] + 450
    assert after["deliveries"] == 1 and not after["claimable"]["count"]
    assert page.locator('[data-farm-action="claim_all"]').is_disabled()
    assert page.locator(".farm-collect-bar").is_hidden()
    assert page.locator(".farm-status").is_hidden()
    page.locator('.farm-task-filters [data-task-view="badges"]').click()
    page.locator('[data-badge-category="all"]').click()
    assert page.locator(".farm-badge").count() == 105
    assert not store.profile("p1")["awards"]


def test_farm_outfit_and_environment_follow_saved_level_and_collected_notices_stay_gone(arcade):
    from app.services.arcade_farm import LEVELS, FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state["earned"] = 1200
        farm._save(db, "p1", state)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-action="claim_all"]').click()
    page.wait_for_function("document.querySelector('.farm-collect-bar').hidden")
    assert page.locator(".farm-status").is_hidden()
    assert page.locator(".farm-save-line").count() == 0
    page.locator('.farm-tabs [data-farm-tab="tasks"]').click()
    page.locator('.farm-task-filters [data-task-view="badges"]').click()
    assert page.locator(".farm-badge.is-ready").count() == 0
    page.locator('[data-badge-category="all"]').click()
    assert page.locator(".farm-badge.is-claimed").count() > 0
    page.locator("[data-farm-close]").click()
    for lv, stage in ((1, 0), (5, 1), (10, 2), (17, 3), (24, 4)):
        with store.db() as db:
            state = farm._load(db, "p1")
            state["earned"] = LEVELS[lv - 1]
            farm._save(db, "p1", state)
        page.locator('.game-card[data-game="kopatych"]').click()
        page.locator("[data-menu-levels]").click()
        page.locator('.farm-tabs [data-farm-tab="home"]').click()
        assert page.locator(".farm-scene").get_attribute("data-farm-stage") == str(stage)
        assert page.locator("[data-farm-level]").inner_text() == str(lv)
        assert page.locator(".farm-landscape svg").count() == 1
        assert page.locator(".farm-bear svg").count() == 1
        page.locator("[data-farm-close]").click()


def test_farm_cancel_delivery_requires_confirmation_and_lost_ack_refunds_once(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    lost = [False]

    def interrupt(r):
        payload = json.loads(r.request.post_data)
        if payload["action"] == "cancel_order" and not lost[0]:
            lost[0] = True
            farm.act("p1", payload["id"], payload["action"], payload["item"])
            r.abort("failed")
        else:
            r.fallback()

    page.route("http://127.0.0.1:8779/preview/arcade/farm/actions", interrupt)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="tasks"]').click()
    page.locator('.farm-task-filters [data-task-view="orders"]').click()
    page.locator('[data-farm-action="start_order"][data-item="basket"]').click()
    page.locator(".farm-active-order").wait_for()
    page.locator("[data-farm-cancel-delivery]").click()
    confirmation = page.get_by_role("alertdialog", name="Отменить доставку?")
    assert "Вернём 40 морковок" in confirmation.inner_text()
    page.locator("[data-farm-keep-delivery]").click()
    assert confirmation.count() == 0 and farm.get("p1")["balance"] == 110
    assert not lost[0]
    page.locator("[data-farm-cancel-delivery]").click()
    page.locator('[data-farm-action="cancel_order"]').click()
    page.locator(".farm-retry").wait_for()
    assert farm.get("p1")["balance"] == 150
    page.locator(".farm-retry").click()
    page.wait_for_function("!document.querySelector('.farm-active-order')")
    assert farm.get("p1")["balance"] == 150 and farm.get("p1")["deliveries"] == 0
    assert page.locator(".farm-cancel-confirm").count() == 0


def test_farm_progression_plot_and_achievement_categories_work_across_reentry(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(earned=4000, balance=10000)
        farm._save(db, "p1", state)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-farm-action="start_plot"][data-item="radish"]').click()
    page.locator(".farm-project").wait_for()
    page.locator('[data-farm-action="water_plot"]').click()
    page.wait_for_function(
        "document.querySelector('[data-farm-action=water_plot]').textContent==='Полито'"
    )
    assert page.locator('[data-farm-action="claim_project"]').is_disabled()
    page.locator("[data-farm-close]").click()
    store.clock.advance(480)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-action="claim_project"]').click()
    page.wait_for_function("!document.querySelector('.farm-project')")
    assert farm.get("p1")["activities"]["resources"]["seeds"] == 1
    page.locator('.farm-tabs [data-farm-tab="tasks"]').click()
    page.locator('[data-task-view="badges"]').click()
    assert page.locator(".farm-badge-categories>button").count() == 9
    page.locator('[data-badge-category="rare"]').click()
    assert page.locator(".farm-medal-card").count() == 12
    page.locator('.farm-medal-card.is-ready [data-farm-action="claim_badge"]').first.click()
    page.wait_for_function("!document.querySelector('.farm-medal-card.is-ready')")
    assert farm.get("p1")["activities"]["counts"]["plots"] == 1
    page.locator("[data-farm-close]").click()
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    assert page.locator('[data-badge-category="rare"]').get_attribute("aria-pressed") == "true"
    assert page.locator(".farm-medal-card.is-claimed").count() == 1


def test_farm_trial_uses_the_actual_harvest_and_collects_resource_prize(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(earned=4000000, resources={"seeds": 2, "materials": 0})
        farm._save(db, "p1", state)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-activity-view="trial"]').click()
    page.locator('[data-farm-action="start_trial"][data-item="harvest"]').click()
    page.locator("[data-trial-harvest]").click()
    page.wait_for_function("document.querySelector('[data-trial-progress]').textContent==='1'")
    for i in range(30):
        store.clock.advance(1)
        farm.act("p1", f"trial-ui-input-{i:04}", "tap", count=7 if i == 29 else 8)
    page.locator("[data-farm-close]").click()
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-action="claim_trial"]').click()
    page.wait_for_function("!document.querySelector('.farm-trial')")
    after = farm.get("p1")
    assert after["activities"]["counts"]["trials"] == 1
    assert after["activities"]["resources"] == {"seeds": 4, "materials": 4}
    assert not store.profile("p1")["awards"]


def test_farm_resource_wallet_is_visible_everywhere_and_updates_after_spending_and_harvest(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(earned=250000, balance=10000, resources={"seeds": 6, "materials": 8})
        farm._save(db, "p1", state)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    for tab in ("home", "upgrades", "activities", "tasks", "valley"):
        page.locator(f'.farm-tabs [data-farm-tab="{tab}"]').click()
        assert page.locator(".farm-resource-wallet").is_visible()
        assert page.locator('[data-resource="seeds"]').inner_text() == "6"
        assert page.locator('[data-resource="materials"]').inner_text() == "8"
        assert page.locator('[data-resource="seeds"]').count() == 1
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-activity-view="research"]').click()
    page.locator('[data-farm-action="research"][data-item="garden_notes"]').click()
    page.wait_for_function("document.querySelector('[data-resource=seeds]').textContent==='4'")
    assert page.locator('[data-resource="materials"]').inner_text() == "5"
    page.locator('[data-activity-view="expedition"]').click()
    page.locator('[data-farm-action="start_expedition"][data-item="forest"]').click()
    page.locator(".farm-project").wait_for()
    page.locator("[data-farm-close]").click()
    store.clock.advance(1200)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-action="claim_project"]').click()
    page.wait_for_function("document.querySelector('[data-resource=materials]').textContent==='8'")
    assert page.locator('[data-resource="seeds"]').inner_text() == "4"


@pytest.mark.parametrize(
    "width,seeds,materials,target",
    [(390, 0, 10, "plot"), (1440, 10, 0, "expedition"), (320, 0, 0, None)],
)
def test_farm_purchase_routes_missing_resources_to_source_and_returns_without_spending(
    arcade, width, seeds, materials, target
):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(
            earned=1000000000, balance=100000000, resources={"seeds": seeds, "materials": materials}
        )
        farm._save(db, "p1", state)
    before = farm.get("p1")
    actions = []
    page.on(
        "request",
        lambda r: (
            actions.append(r.post_data_json)
            if r.method == "POST" and r.url.endswith("/farm/actions")
            else None
        ),
    )
    page.set_viewport_size({"width": width, "height": 844})
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="upgrades"]').click()
    page.locator('[data-farm-category="garden"]').click()
    button = page.locator('[data-farm-action="buy"][data-item="vineyard"]')
    assert button.is_enabled()
    button.click()
    assert page.locator(".farm-resource-guide").is_visible()
    if target is None:
        assert page.locator("[data-resource-route]").count() == 2
        page.locator('[data-resource-route="materials"]').click()
        target = "expedition"
    assert page.locator(f'[data-activity-view="{target}"]').get_attribute("aria-pressed") == "true"
    assert not actions
    assert farm.get("p1")["balance"] == before["balance"]
    assert page.locator(".farm-content").evaluate("(n)=>n.scrollWidth<=n.clientWidth")
    # An expedition must not require the materials it is meant to produce.
    if target == "expedition":
        forest = page.locator('[data-farm-action="start_expedition"][data-item="forest"]')
        assert forest.is_enabled()
    page.locator("[data-resource-return]").click()
    assert page.locator('[data-farm-category="garden"]').get_attribute("aria-pressed") == "true"
    assert button.is_visible() and button.is_enabled()
    assert not actions


def test_farm_research_routes_both_resources_then_allows_purchase_after_harvest(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(earned=250000, balance=10000, resources={"seeds": 1, "materials": 0})
        farm._save(db, "p1", state)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-activity-view="research"]').click()
    research = page.locator('[data-farm-action="research"][data-item="garden_notes"]')
    research.click()
    page.locator('[data-resource-route="materials"]').click()
    page.locator('[data-farm-action="start_expedition"][data-item="forest"]').click()
    page.locator(".farm-project").wait_for()
    page.locator("[data-farm-close]").click()
    store.clock.advance(1200)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-action="claim_project"]').click()
    page.wait_for_function("document.querySelector('[data-resource=materials]').textContent==='3'")
    # Reopening restores the source section; only seeds are missing now.
    page.locator('[data-activity-view="research"]').click()
    research.click()
    assert page.locator('[data-activity-view="plot"]').get_attribute("aria-pressed") == "true"
    page.locator('[data-farm-action="start_plot"][data-item="radish"]').click()
    page.locator(".farm-project").wait_for()
    page.locator("[data-farm-close]").click()
    store.clock.advance(600)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-farm-action="claim_project"]').click()
    page.wait_for_function("document.querySelector('[data-resource=seeds]').textContent==='2'")
    page.locator('[data-activity-view="research"]').click()
    assert research.inner_text() == "Исследовать" and research.is_enabled()
    research.click()
    page.wait_for_function("document.querySelector('[data-resource=seeds]').textContent==='0'")
    assert farm.get("p1")["activities"]["resources"] == dict(seeds=0, materials=0)


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_farm_endgame_large_balances_rewards_and_completed_collection_fit_all_tabs(arcade, width):
    from app.services.arcade_farm import BY_ID, LEVELS, FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(
            earned=LEVELS[-1],
            balance=100_000_000_000_000,
            items={k: i["maximum"] for k, i in BY_ID.items()},
            daily=None,
        )
        farm._save(db, "p1", state)
    page.set_viewport_size(dict(width=width, height=900))
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator(".farm-bear").wait_for()
    assert "трлн" in page.locator("[data-farm-bank]").inner_text()
    for tab in ("home", "upgrades", "activities", "tasks", "valley"):
        page.locator(f'.farm-tabs [data-farm-tab="{tab}"]').click()
        assert page.locator(".farm-content").evaluate("(n)=>n.scrollWidth<=n.clientWidth"), tab
        assert page.locator(".farm-wallet").evaluate("(n)=>n.scrollWidth<=n.clientWidth"), tab
    page.locator('.farm-tabs [data-farm-tab="tasks"]').click()
    page.locator('[data-task-view="daily"]').click()
    assert page.locator(".farm-days").evaluate("(n)=>n.scrollWidth<=n.clientWidth")
    assert page.locator(".farm-content").evaluate("(n)=>n.scrollWidth<=n.clientWidth")
    assert page.locator(".farm-combo").inner_text() == "Сегодня без комбо."
    page.locator('[data-task-view="badges"]').click()
    assert page.locator('.farm-section-title [data-badge-category="all"]').inner_text() == "Все 105"
    page.locator('[data-badge-category="all"]').click()
    assert page.locator(".farm-medal-card").count() == 105
    assert page.locator(".farm-content").evaluate("(n)=>n.scrollWidth<=n.clientWidth")
    page.locator(".farm-medal-card").last.scroll_into_view_if_needed()
    assert page.locator(".farm-content").evaluate("n=>n.scrollTop") > 0
    page.locator('.farm-tabs [data-farm-tab="home"]').click()
    assert page.locator(".farm-content").evaluate("n=>n.scrollTop") == 0
    assert page.locator(".farm-bear").is_visible()


def test_farm_trial_warns_about_energy_before_spending_the_entry_fee(arcade):
    from app.services.arcade_farm import FarmStore

    page, store = arcade
    store.clock = Clock()
    farm = FarmStore(store)
    farm.get("p1")
    with store.db() as db:
        state = farm._load(db, "p1")
        state.update(earned=4000000, resources=dict(seeds=1, materials=0), energy_milli=0)
        farm._save(db, "p1", state)
    page.locator('.game-card[data-game="kopatych"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('.farm-tabs [data-farm-tab="activities"]').click()
    page.locator('[data-activity-view="trial"]').click()
    button = page.locator('[data-farm-action="start_trial"][data-item="harvest"]')
    assert button.is_disabled() and button.inner_text() == "Нужно больше энергии"
    assert farm.get("p1")["activities"]["resources"]["seeds"] == 1
