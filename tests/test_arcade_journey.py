"""Active adventures: server ownership, saved stages, real tools and no idle gains."""

import json

import pytest

from app.services import arcade_journey, arcade_runtime
from app.services.arcade import ArcadeError, ArcadeStore
from tests.test_arcade_farm import Clock
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


@pytest.fixture
def store(tmp_path):
    s = ArcadeStore(tmp_path / "adventures.sqlite3", Clock())
    s.register([dict(id="p1", name="Марк"), dict(id="p2", name="Соня")])
    return s


def solve_debug(setup, wrong=0):
    with arcade_runtime.context() as vm:
        vm.eval("""function solve(setup,wrong){const W=ArcadeWorld,w=W.create(setup),events=[];
          function send(a){const e={...a,source:w.device,t:w.tick};events.push(e);W.input(w,e);}
          while(!w.ended){const task=w.tasks[w.index];W.advance(w,20);
            send({type:'line',i:task.line});
            W.advance(w,20);send({type:'answer',i:wrong-->0?(task.answer+1)%3:task.answer});
            if(!w.ended){W.advance(w,20);send({type:'next'});}}
          return {events,ticks:w.tick,report:W.report(w)};}""")
        return vm.call("solve", setup, wrong)


def finish(store, session, trace, player="p1"):
    store.clock_action(player, session["id"], "start")
    store.clock.advance(trace["ticks"] / 60 + 0.5)
    return store.finish(player, session["id"], trace["events"], trace["ticks"])


@pytest.mark.parametrize("game", list(arcade_journey.catalogue()))
def test_all_adventures_have_twenty_four_stages_and_never_progress_by_waiting(game):
    stages = arcade_journey.catalogue()[game]["stages"]
    assert [m["stage"] for m in stages] == list(range(1, 25))
    assert len({m["title"] for m in stages}) == 6
    for stage in (1, 12, 24):
        report = arcade_runtime.verify(
            dict(
                game=game,
                seed=17,
                mode="journey",
                device="keyboard",
                journey=dict(stage=stage, charges=3),
            ),
            [],
            216000,
        )
        assert report["score"] == 0 and report["journey"]["stars"] == 0
        assert not report["journey"]["success"] and report["journey"]["inputs"] == 0


def test_unlocked_stages_belong_to_owner_and_duplicate_result_does_not_pay_again(store):
    with pytest.raises(ArcadeError):
        store.session("p1", "debug", "journey", "keyboard", 24)
    with pytest.raises(ArcadeError):
        store.session("p1", "kopatych", "journey", "keyboard")
    with pytest.raises(ArcadeError):
        store.session("p1", "debug", "ranked", "keyboard", 1)
    session = store.session("p1", "debug", "journey", "keyboard", 1)
    trace = solve_debug(session["setup"])
    result = finish(store, session, trace)
    assert result["run"]["report"]["journey"]["success"]
    assert not result["run"]["accepted"]
    assert store.finish("p1", session["id"], trace["events"], trace["ticks"])["duplicate"]
    profile = store.profile("p1")
    assert profile["journeys"]["debug"]["unlocked"] == 2
    assert profile["journeys"]["debug"]["stars"] == 3
    assert store.profile("p2")["journeys"]["debug"]["unlocked"] == 1
    assert not store.board("debug")["rows"]
    # Reading and waiting cannot open stages or generate awards.
    before = profile["journeys"]
    store.clock.advance(14 * 86400)
    assert store.profile("p1")["journeys"] == before
    assert not store.profile("p1")["awards"]
    restarted = ArcadeStore(store.path, store.clock)
    assert restarted.profile("p1")["journeys"] == before


def test_chapters_unlock_active_tools_and_weekly_award_is_shared_with_ranked(store):
    for stage in range(1, 9):
        session = store.session("p1", "debug", "journey", "keyboard", stage)
        finish(store, session, solve_debug(session["setup"]))
    profile = store.profile("p1")
    assert profile["journeys"]["debug"]["charges"] == 2
    assert profile["journeys"]["debug"]["keepsakes"] == [1, 2]
    assert store.session("p1", "debug", "journey", "keyboard")["setup"]["journey"] == dict(
        stage=9, charges=2
    )
    # The first two chapters have goals under the weekly target, so no passive award exists.
    assert not profile["awards"]


def test_repeating_a_stage_keeps_best_stars_and_cannot_unlock_next_stage_on_exit(store):
    first = store.session("p1", "debug", "journey", "keyboard", 1)
    finish(store, first, solve_debug(first["setup"]))
    second = store.session("p1", "debug", "journey", "keyboard", 1)
    finish(store, second, solve_debug(second["setup"], wrong=3))
    assert store.profile("p1")["journeys"]["debug"]["records"][0]["stars"] == 3
    next_session = store.session("p1", "debug", "journey", "keyboard", 2)
    trace = solve_debug(next_session["setup"])
    trace["events"] = trace["events"][:2]
    trace["ticks"] = trace["events"][-1]["t"]
    store.clock_action("p1", next_session["id"], "start")
    store.clock.advance(trace["ticks"] / 60 + 0.5)
    store.finish("p1", next_session["id"], trace["events"], trace["ticks"], abandoned=True)
    assert store.profile("p1")["journeys"]["debug"]["unlocked"] == 2


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_every_game_has_a_playable_route_on_mobile_and_desktop(arcade, width):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=900))
    for game in arcade_journey.catalogue():
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator("[data-menu-levels]").click()
        if game == "hill":
            page.locator('[data-garage-tab="missions"]').click()
            assert page.locator(".hill-missions button").count() == 24
            assert page.locator(".hill-missions button:not(:disabled)").count() == 1
            assert page.locator(".hill-garage-dialog").evaluate("(n)=>n.scrollWidth<=n.clientWidth")
            page.locator("[data-close]").click()
            continue
        hub = page.locator(".journey-hub")
        assert hub.is_visible()
        assert page.locator(".journey-stop").count() == 24
        assert page.locator(".journey-stop:not(:disabled)").count() == 1
        assert hub.evaluate("(n)=>n.scrollWidth<=n.clientWidth"), game
        assert page.locator("#gameDialog").evaluate("(n)=>n.scrollWidth<=n.clientWidth"), game
        page.locator(".game-close").click()
    assert all(g["cleared"] == 0 for g in store.profile("p1")["journeys"].values())


def test_adventure_starts_real_game_and_saves_result_across_reentry(arcade):
    page, store = arcade
    store.clock = Clock()
    page.locator('.game-card[data-game="debug"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-journey-play="1"]').click()
    page.wait_for_function("document.querySelector('#gameLevel')?.textContent==='Уровень 1'")
    page.locator(".arcade-countdown").wait_for(state="detached")
    assert page.locator(".journey-tools").is_visible()
    # Read the stored trusted setup to drive correct, actual UI answers.
    with store.db() as db:
        setup = json.loads(
            db.execute(
                "SELECT setup FROM arcade_sessions ORDER BY created DESC LIMIT 1"
            ).fetchone()[0]
        )
    tasks = page.evaluate("setup=>ArcadeWorld.create(setup).tasks", setup)
    page.wait_for_function("!document.querySelector('.journey-tools button').disabled")
    store.clock.advance(60)
    page.locator(".journey-tools button").click()
    assert page.locator(".journey-tools button").is_disabled()
    for i in range(2):
        page.locator(".debug-code button").nth(tasks[i]["line"]).click()
        page.locator("[data-option]").nth(tasks[i]["answer"]).click()
        if i == 0:
            page.locator("[data-next]").click()
    page.locator(".journey-result").wait_for()
    assert "Уровень пройден!" in page.locator(".journey-result").inner_text()
    xp = store.profile("p1")["mastery"]["xp"]
    assert xp >= 100
    assert f"+{xp} XP" in page.locator(".arcade-mastery-gain").inner_text()
    assert store.profile("p1")["journeys"]["debug"]["unlocked"] == 2
    page.locator("[data-journey-map]").click()
    assert page.locator('[data-journey-play="2"]').is_visible()
    page.locator(".game-close").click()
    assert "1 из 24 пройдено" in page.locator('.game-card[data-game="debug"]').inner_text()
    page.locator('.game-card[data-game="debug"]').click()
    page.locator("[data-menu-levels]").click()
    assert page.locator('[data-journey-play="2"]').is_visible()
    assert page.locator(".journey-stop.is-complete").count() == 1


def test_soft_drop_compresses_bounces_and_settles_without_leaking_or_duplicate_merges():
    with arcade_runtime.context() as vm:
        vm.eval("""function soft(){const W=ArcadeWorld,
          w=W.create({game:'drop',seed:17,mode:'ranked',dropPhysics:2});
          W.input(w,{type:'tap',x:180});let peak=0,negative=false,finite=true;
          for(let i=0;i<720;i++){W.advance(w,1);for(const b of w.balls){
            peak=Math.max(peak,b.squash);
            negative ||= b.squash<0;
            finite &&= [b.x,b.y,b.vx,b.vy,b.squash,b.squashV].every(Number.isFinite);}}
          return {peak,negative,finite,body:w.balls[0],score:w.score,report:W.report(w)};}""")
        result = vm.call("soft")
        assert result["peak"] > 0.10 and result["peak"] <= 0.24
        assert result["finite"] and result["score"] == 0
        assert 0 < result["body"]["squash"] < 0.1
        assert 12 < result["body"]["x"] < 348
        assert result["report"]["details"]["physics"] == "soft2"
    # A current server session chooses soft physics itself; old replay setups remain rigid.


@pytest.mark.parametrize("game", list(arcade_journey.catalogue()))
def test_active_tools_have_finite_charges_and_do_not_create_idle_progress(game):
    with arcade_runtime.context() as vm:
        vm.eval("""function tool(game){const W=ArcadeWorld,
          w=W.create({game,seed:17,mode:'journey',journey:{stage:1,charges:1}});
          if(game==='bugs')while(!w.targets.some(t=>!t.good)&&!w.ended)W.advance(w,6);
          if(game==='blocks')for(let i=0;i<3;i++){W.input(w,{type:'piece',i});
            if(ArcadeJourney.rotatable(w))break;}
          if(game==='hill')w.hill.fuel=50;
          const before=w.score,first=W.input(w,{type:'power'});
          if(game==='2048'){W.input(w,{type:'swap_cell',i:0});
            const k=w.board.findIndex(v=>v!==w.board[0]);W.input(w,{type:'swap_cell',i:k});}
          const second=W.input(w,{type:'power'}),used=w.journey.used;W.advance(w,120);
          return {first,second,used,score:w.score,before,stars:w.journey.stars};}""")
        result = vm.call("tool", game)
        assert result["first"] and not result["second"], game
        assert result["used"] == 1 and result["stars"] == 0, game
        if game != "bugs":
            assert result["score"] == result["before"], game


def test_2048_exchange_is_a_real_two_cell_choice_and_spends_only_after_selection(arcade):
    page, store = arcade
    page.locator('.game-card[data-game="2048"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-journey-play="1"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    with store.db() as db:
        setup = json.loads(
            db.execute(
                "SELECT setup FROM arcade_sessions ORDER BY created DESC LIMIT 1"
            ).fetchone()[0]
        )
    board = page.evaluate("setup=>ArcadeWorld.create(setup).board", setup)
    second = next(i for i, v in enumerate(board) if v != board[0])
    page.locator(".journey-tools button").click()
    assert page.locator(".number-cell.can-swap").count() == 16
    page.locator('[data-number-cell="0"]').click()
    assert page.locator('[data-number-cell="0"]').get_attribute("class").find("swap-selected") >= 0
    page.locator(f'[data-number-cell="{second}"]').click()
    assert page.locator('[data-number-cell="0"]').inner_text() == (
        str(board[second]) if board[second] else ""
    )
    assert page.locator(".journey-tools button").is_disabled()


def test_soft_drop_is_selected_by_server_and_bad_session_parameters_are_rejected(store):
    session = store.session("p1", "drop", "ranked", "keyboard")
    assert session["setup"]["dropPhysics"] == 3
    assert arcade_runtime.verify(session["setup"], [], 1)["details"]["physics"] == "soft3"
    for stage in (True, 0, 25, -1):
        with pytest.raises(ArcadeError):
            store.session("p1", "debug", "journey", "keyboard", stage)


def test_evolution_star_targets_can_be_built_before_the_score_goal_ends_the_mission():
    for stage in arcade_journey.catalogue()["evolve"]["stages"]:
        species = stage["species"]
        assert species * 2 ** (species + 1) <= stage["goal"]


def test_verified_adventure_win_survives_pagehide_marked_as_abandoned(store):
    session = store.session("p1", "debug", "journey", "keyboard", 1)
    trace = solve_debug(session["setup"])
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(trace["ticks"] / 60 + 0.5)
    result = store.finish("p1", session["id"], trace["events"], trace["ticks"], abandoned=True)
    assert result["run"]["report"]["journey"]["success"]
    assert store.profile("p1")["journeys"]["debug"]["unlocked"] == 2
    assert store.finish("p1", session["id"], trace["events"], trace["ticks"])["duplicate"]


def test_adventure_weekly_reward_and_ranked_reward_share_the_same_once_only_credit(store):
    for stage in range(1, 11):
        session = store.session("p1", "debug", "journey", "keyboard", stage)
        finish(store, session, solve_debug(session["setup"]))
    profile = store.profile("p1")
    reward = profile["goals"]["debug"]
    assert reward["eligible"] and reward["score"] >= 5
    assert store.claim("p1", reward["id"])["balance"] == 5
    ranked = store.session("p1", "debug", "ranked", "keyboard")
    assert finish(store, ranked, solve_debug(ranked["setup"]))["run"]["accepted"]
    assert len([a for a in store.profile("p1")["awards"] if a["kind"] == "first"]) == 1
    assert store.claim("p1", reward["id"])["balance"] == 40


def test_adventure_result_collects_weekly_ac_automatically_through_the_real_interface(arcade):
    page, store = arcade
    store.clock = Clock()
    with store.db() as db:
        for stage in range(1, 10):
            db.execute(
                "INSERT INTO arcade_journeys VALUES(?,?,?,?,?,?,?)",
                ("p1", "debug", stage, 3, 10, store.clock(), "{}"),
            )
    page.reload()
    page.locator('.game-card[data-game="debug"]').click()
    page.locator("[data-menu-levels]").click()
    page.locator('[data-journey-play="10"]').click()
    page.locator(".arcade-countdown").wait_for(state="detached")
    with store.db() as db:
        setup = json.loads(
            db.execute(
                "SELECT setup FROM arcade_sessions ORDER BY created DESC LIMIT 1"
            ).fetchone()[0]
        )
    tasks = page.evaluate("setup=>ArcadeWorld.create(setup).tasks", setup)
    page.wait_for_function("!document.querySelector('.journey-tools button').disabled")
    store.clock.advance(60)
    for i in range(5):
        page.locator(".debug-code button").nth(tasks[i]["line"]).click()
        page.locator("[data-option]").nth(tasks[i]["answer"]).click()
        if i < 4:
            page.locator("[data-next]").click()
    page.locator(".arcade-reward-receipt").wait_for()
    assert "Ваша награда — 5 AC" in page.locator(".arcade-reward-receipt").inner_text()
    assert page.locator("[data-journey-claim]").count() == 0
    assert store.profile("p1")["balance"] == 5


def test_soft_drop_many_real_drops_remain_bounded_and_replay_identically():
    setup = dict(game="drop", seed=42, mode="practice", device="keyboard", dropPhysics=2)
    with arcade_runtime.context() as vm:
        vm.eval("""function pile(setup){const W=ArcadeWorld,w=W.create(setup),events=[];
          let finite=true,maxBodies=0;
          for(let i=0;i<300&&!w.ended;i++){
            const e={type:'tap',x:25+(i*83)%310,t:w.tick,source:'keyboard'};
            events.push(e);W.input(w,e);W.advance(w,40);maxBodies=Math.max(maxBodies,w.balls.length);
            finite &&= w.balls.every(b=>[b.x,b.y,b.vx,b.vy,b.squash].every(Number.isFinite));
            finite &&= new Set(w.balls.map(b=>b.id)).size===w.balls.length;
          }return {events,ticks:w.tick,report:W.report(w),finite,maxBodies};}""")
        trace = vm.call("pile", setup, timeout_sec=8)
    assert trace["finite"] and trace["maxBodies"] < 100
    assert arcade_runtime.verify(setup, trace["events"], trace["ticks"]) == trace["report"]


def test_sort_moves_count_actual_tube_controls_and_direct_pours_equally():
    with arcade_runtime.context() as vm:
        vm.eval("""function controls(){const W=ArcadeWorld,
          setup={game:'sort',seed:17,mode:'journey',journey:{stage:1,charges:1}},
          a=W.create(setup),b=W.create(setup),move=a.sortSolution[0];
          W.input(a,{type:'tube',i:move.from});W.input(a,{type:'tube',i:move.to});
          W.input(b,move);
          return {a:W.report(a).journey.moves,b:W.report(b).journey.moves};}""")
        assert vm.call("controls") == dict(a=1, b=1)
