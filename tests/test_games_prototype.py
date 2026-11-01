"""Local game rules and UI. Uses static files, no database or outgoing MAX requests."""

import os
from pathlib import Path

import pytest

from app.cli.games_preview import inject_games

STATIC = Path(__file__).parents[1] / "app/web/static/miniapp"


@pytest.fixture(scope="module")
def games_browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as runtime:
        try:
            browser = runtime.chromium.launch(channel="msedge" if os.name == "nt" else None)
        except pw.Error as error:
            if "Executable doesn't exist" in str(error) or "distribution 'msedge'" in str(error):
                pytest.skip("Install Playwright Chromium for game UI checks")
            raise
        yield browser
        browser.close()


@pytest.fixture
def engine(games_browser):
    page = games_browser.new_page()
    page.add_script_tag(path=str(STATIC / "games-engine.js"))
    yield page
    page.close()


@pytest.mark.parametrize(
    ("row", "expected", "score"),
    [
        ([2, 2, 2, 2], [4, 4, 0, 0], 8),
        ([2, 2, 4, 0], [4, 4, 0, 0], 4),
        ([4, 0, 4, 4], [8, 4, 0, 0], 8),
        ([2, 4, 8, 16], [2, 4, 8, 16], 0),
    ],
)
def test_2048_merges_once_per_move(engine, row, expected, score):
    result = engine.evaluate("r=>AlgoGameEngine.slide([...r,...Array(12).fill(0)],'left')", row)
    assert result["board"][:4] == expected
    assert result["score"] == score


def test_2048_vertical_reverse_and_game_over(engine):
    assert (
        engine.evaluate(
            "AlgoGameEngine.slide([2,0,0,0,2,0,0,0,...Array(8).fill(0)],'down').board[12]"
        )
        == 4
    )
    assert engine.evaluate(
        "AlgoGameEngine.slide([2,2,4,0,...Array(12).fill(0)],'right').board.slice(0,4)"
    ) == [0, 0, 4, 4]
    assert engine.evaluate("AlgoGameEngine.canMove([2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,2])") is False
    assert engine.evaluate("AlgoGameEngine.canMove([2,4,2,4,4,2,4,2,2,4,2,4,4,2,4,4])") is True


@pytest.mark.parametrize(
    ("stamp", "week"),
    [
        ("2026-11-01T20:59:59Z", "2026-10-26"),
        ("2026-11-01T21:00:00Z", "2026-11-02"),
        ("2027-01-01T00:00:00Z", "2026-12-28"),
    ],
)
def test_week_starts_on_monday_in_moscow(engine, stamp, week):
    assert engine.evaluate("s=>AlgoGameEngine.weekKey(new Date(s))", stamp) == week


def test_weekly_rewards_cannot_repeat_or_use_old_best(engine):
    result = engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank(),now=new Date('2026-10-31T12:00:00Z');
      e.finish(s,'orbit',7,now);
      const below=e.claim(s,'week','orbit',now);
      e.finish(s,'orbit',8,now);
      const first=e.claim(s,'week','orbit',now),duplicate=e.claim(s,'week','orbit',now);
      const next=new Date('2026-11-02T00:00:00Z');
      const oldBest=e.claim(s,'week','orbit',next);
      e.finish(s,'orbit',8,next);
      return [below,first,duplicate,oldBest,e.claim(s,'week','orbit',next),s.transactions.length];
    }""")
    assert result == [0, 10, 0, 0, 10, 2]


def test_achievements_one_time_and_restore(engine):
    assert (
        engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank();
      if(e.claim(s,'achievement','first')!==0)return false;
      e.finish(s,'debug',8);
      if(e.claim(s,'achievement','master2_debug')!==35)return false;
      const restored=e.normalize(JSON.parse(JSON.stringify(s)));
      if(e.claim(restored,'achievement','master2_debug')!==0)return false;
      return restored.best.debug===8 && e.balance(restored)===35 &&
        e.claim(restored,'achievement','first')===0;
    }""")
        is True
    )


def test_invalid_results_and_corrupted_storage(engine):
    assert (
        engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank();
      e.finish(s,'unknown',100);e.finish(s,'orbit',NaN);e.finish(s,'orbit',-1);
      const clean=e.normalize({version:1,best:{orbit:'hello'},
        weeks:{'bad':{scores:{}}},transactions:'bad'});
      return s.runs===0 && !Object.keys(clean.best).length && !Object.keys(clean.weeks).length;
    }""")
        is True
    )


@pytest.fixture
def arcade(games_browser):
    context = games_browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    errors = []
    writes = []
    source = inject_games((STATIC / "index.html").read_text(encoding="utf-8"))

    def route(request):
        path = request.request.url.split("?", 1)[0].removeprefix("http://127.0.0.1:8779")
        if request.request.method not in ("GET", "HEAD"):
            writes.append(path)
            request.fulfill(status=403)
        elif path == "/miniapp":
            request.fulfill(body=source, content_type="text/html")
        elif path.startswith("/miniapp/static/"):
            target = (STATIC / path.removeprefix("/miniapp/static/")).resolve()
            if target.is_relative_to(STATIC.resolve()) and target.is_file():
                request.fulfill(path=str(target))
            else:
                request.fulfill(status=404)
        else:
            request.fulfill(status=404)

    page.route("http://127.0.0.1:8779/**", route)
    page.route("https://st.max.ru/**", lambda r: r.abort())
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(
        "http://127.0.0.1:8779/miniapp?demo=1&demo_role=student&view=games",
        wait_until="networkidle",
    )
    yield page
    context.close()
    assert not errors, errors
    assert not writes, writes


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_every_game_opens_starts_and_exits_without_overflow(arcade, width):
    page = arcade
    page.set_viewport_size({"width": width, "height": 900})
    assert page.locator(".game-card").count() == 10
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    for game in [
        "orbit",
        "evolve",
        "bugs",
        "tower",
        "typing",
        "debug",
        "2048",
        "drop",
        "memory",
        "react",
    ]:
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator("#gameStart").click()
        page.wait_for_timeout(50)
        assert page.locator("#gameDialog[open]").count() == 1
        assert page.evaluate(
            "document.querySelector('#gameDialog').scrollWidth<=document.querySelector('#gameDialog').clientWidth"
        )
        page.locator("#gameFinish").click()
        assert page.locator(".game-result").is_visible()
        page.locator(".game-back").click()
    page.locator('[data-games-tab="achievements"]').first.click()
    assert page.locator(".game-achievement").count() == 10
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary").is_visible()


def test_python_real_completion_claim_and_reload(arcade):
    page = arcade
    original = page.evaluate("students.map(s=>s.balance)")
    page.locator('.game-card[data-game="debug"]').click()
    page.locator("#gameStart").click()
    for _ in range(8):
        intro = page.locator(".debug-game h3").inner_text()
        task = page.evaluate("intro=>AlgoGameEngine.tasks.find(t=>t.intro===intro)", intro)
        page.locator(f'[data-line="{task["line"]}"]').click()
        page.locator(f'[data-option="{task["answer"]}"]').click()
        assert page.locator(".debug-feedback").inner_text().startswith("✓ Верно!")
        page.locator("[data-next]").click()
    assert "8 задач" in page.locator(".game-result h3").inner_text()
    page.locator(".game-claim-result").click()
    assert page.locator(".game-claim-result").is_disabled()
    page.locator(".game-back").click()
    page.locator('[data-games-tab="achievements"]').first.click()
    page.locator('[data-claim="achievement"][data-id="master2_debug"]').click()
    page.reload(wait_until="networkidle")
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary strong").inner_text() == "45 AC"
    assert page.locator('[data-claim="week"][data-id="debug"]').is_disabled()
    assert page.evaluate("students.map(s=>s.balance)") == original


def test_typing_input_and_memory_match_are_real(arcade):
    page = arcade
    page.locator('.game-card[data-game="typing"]').click()
    page.locator("#gameStart").click()
    passage = page.locator(".typing-passage").inner_text()
    page.locator(".typing-input").press_sequentially(passage[:20])
    assert page.locator("#gameScore").inner_text() == "20"
    page.locator(".typing-input").press("Backspace")
    assert page.locator("#gameScore").inner_text() == "19"
    page.locator(".game-close").click()
    assert page.locator('.game-card[data-game="typing"]').inner_text().find("19") >= 0
    page.locator('.game-card[data-game="memory"]').click()
    page.locator("#gameStart").click()
    page.locator('[data-card="0"]').click()
    assert page.locator(".memory-grid .flipped").count() == 1
    page.locator('[data-card="1"]').click()
    assert page.locator(".memory-grid .flipped,.memory-grid .matched").count() == 2
    page.locator(".game-close").click()


def test_dropping_identical_objects_really_merges_with_physics(arcade):
    page = arcade
    page.evaluate("Math.random=()=>0.1")
    page.locator('.game-card[data-game="drop"]').click()
    page.locator("#gameStart").click()
    canvas = page.locator("#gameDialog canvas")
    canvas.click(position={"x": canvas.bounding_box()["width"] / 2, "y": 50})
    page.wait_for_timeout(1400)
    canvas.click(position={"x": canvas.bounding_box()["width"] / 2, "y": 50})
    page.wait_for_function("Number(document.querySelector('#gameScore').textContent)>=4")
    assert page.locator(".game-result").count() == 0
    page.locator(".game-close").click()
    assert "Рекорд" in page.locator('.game-card[data-game="drop"]').inner_text()


def test_merging_creatures_and_keyboard_2048(arcade):
    page = arcade
    page.evaluate("Math.random=()=>0.1")
    page.locator('.game-card[data-game="evolve"]').click()
    page.locator("#gameStart").click()
    page.locator('[data-cell="0"]').click()
    page.locator('[data-cell="1"]').click()
    assert page.locator("#gameScore").inner_text() == "8"
    page.locator(".game-close").click()
    page.locator('.game-card[data-game="2048"]').click()
    page.locator("#gameStart").click()
    assert page.locator(".number-cell.n2").count() == 2
    page.keyboard.press("ArrowLeft")
    assert page.locator(".number-cell.n4").count() == 1
    assert page.locator("#gameScore").inner_text() == "4"
    page.locator(".game-close").click()


def test_reaction_false_start_then_green_signal(arcade):
    page = arcade
    page.locator('.game-card[data-game="react"]').click()
    page.locator("#gameStart").click()
    page.locator(".reaction-pad").click()
    assert "Рановато" in page.locator(".reaction-pad").inner_text()
    assert page.locator("#gameScore").inner_text() == "0"
    page.wait_for_selector(".reaction-pad.go")
    page.keyboard.press("Space")
    assert page.locator("#gameScore").inner_text() == "1"
    assert page.locator(".reaction-attempts .done").count() == 1
    page.locator(".game-close").click()


def test_arcade_requires_explicit_local_preview_flag(arcade):
    assert arcade.evaluate("roleViews(state.role).includes('games')")
    arcade.evaluate("window.ALGO_GAMES_PROTOTYPE=false;setView('games')")
    assert arcade.evaluate("state.view") == "dashboard"


@pytest.mark.parametrize(
    ("game", "progress"),
    [
        ("orbit", 15),
        ("evolve", 24),
        ("bugs", 30),
        ("tower", 15),
        ("typing", 240),
        ("debug", 6),
        ("2048", 256),
        ("drop", 300),
        ("memory", 18),
        ("react", 10),
    ],
)
def test_every_game_has_progressive_playable_difficulty(engine, game, progress):
    first, later = engine.evaluate(
        "([g,p])=>[AlgoGameEngine.difficulty(g,0),AlgoGameEngine.difficulty(g,p)]",
        [game, progress],
    )
    assert later["level"] > first["level"]
    assert later["orbitWindow"] >= 0.16
    assert later["pairSeconds"] >= 7
    assert later["reactionWindow"] >= 0.45
    assert later["towerSpeed"] > first["towerSpeed"]


def test_rankings_best_per_player_ties_and_week_reset(engine):
    assert engine.evaluate("""() => {
      const e=AlgoGameEngine,b=e.blankBoard(),d=new Date('2026-10-31T12:00:00Z');
      const p=n=>({id:n,name:n,group:'Тестовая группа'});
      e.recordBoard(b,'tower',p('one'),20,4,d);
      e.recordBoard(b,'tower',p('one'),10,2,d);
      e.recordBoard(b,'tower',p('two'),20,4,d);
      e.recordBoard(b,'tower',p('three'),15,3,d);
      const rows=e.leaders(b,'tower','week',d);
      if(rows.length!==3||rows[0].score!==20||rows.map(r=>r.rank).join()!=='1,1,3')return false;
      const next=new Date('2026-11-02T12:00:00Z');
      if(e.leaders(b,'tower','week',next).length!==0)return false;
      e.recordBoard(b,'tower',p('one'),5,1,next);
      const restored=e.normalizeBoard(JSON.parse(JSON.stringify(b)));
      return e.leaders(restored,'tower','week',next)[0].score===5 &&
        e.leaders(restored,'tower','all',next)[0].score===20 &&
        e.recordBoard(restored,'debug',p('one'),999,1,next)===false;
    }""")


def test_2048_animation_paths_conserve_every_source_tile(engine):
    assert engine.evaluate("""() => {
      const e=AlgoGameEngine,input=[2,2,4,4,0,4,4,0,...Array(8).fill(0)];
      return ['left','right','up','down'].every(dir=>{
        const r=e.slide(input,dir),sources=r.moves.map(m=>m.from);
        return new Set(sources).size===input.filter(Boolean).length &&
          r.board.every((v,i)=>r.moves.filter(m=>m.to===i).reduce((n,m)=>n+m.value,0)===v);
      });
    }""")


def test_leaderboard_changes_player_and_keeps_rewards_separate(arcade):
    page = arcade
    page.evaluate("Math.random=()=>0.1")
    who = page.locator("#gamesPlayer").input_value()
    page.locator('.game-card[data-game="evolve"]').click()
    page.locator("#gameStart").click()
    page.locator('[data-cell="0"]').click()
    page.locator('[data-cell="1"]').click()
    page.locator("#gameFinish").click()
    page.locator(".game-result-leaders").click()
    assert page.locator("#gamesLeaderDialog .games-my-rank").inner_text().find("#1") >= 0
    assert page.locator("#gamesLeaderDialog tr.is-me strong").inner_text() == "8"
    page.locator(".games-leader-close").click()
    page.locator(".game-back").click()
    options = page.locator("#gamesPlayer option").evaluate_all("els=>els.map(e=>e.value)")
    other = next(v for v in options if v != who)
    page.locator("#gamesPlayer").select_option(other)
    assert "Рекорд" not in page.locator('.game-card[data-game="evolve"]').inner_text()
    page.locator('[data-games-tab="leaders"]').click()
    assert page.locator(".games-my-rank").count() == 0
    assert page.locator(".games-leaders tbody tr").count() == 0
    assert page.locator(".league-prize-podium").is_visible()
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary strong").inner_text() == "0 AC"
    page.locator("#gamesPlayer").select_option(who)
    page.locator('[data-games-tab="games"]').click()
    assert "Рекорд" in page.locator('.game-card[data-game="evolve"]').inner_text()


def test_memory_next_level_actually_adds_pairs(arcade):
    page = arcade
    page.evaluate("Math.random=()=>.999")  # Fisher-Yates keeps a deterministic paired deck.
    page.locator('.game-card[data-game="memory"]').click()
    page.locator("#gameStart").click()
    assert page.locator(".memory-grid button").count() == 8
    for i in range(4):
        page.locator(f'[data-card="{i}"]').click()
        page.locator(f'[data-card="{i + 4}"]').click()
    assert page.locator("#gameScore").inner_text() == "4"
    page.locator("[data-memory-next]").click()
    assert page.locator(".memory-grid button").count() == 12
    assert page.locator("#gameLevel").inner_text() == "Ур. 2"
    page.locator(".game-close").click()


def test_orbit_jump_and_leaderboard_pause_do_not_lose_run(arcade):
    page = arcade
    page.evaluate("Math.random=()=>.5")
    page.locator('.game-card[data-game="orbit"]').click()
    page.locator("#gameStart").click()
    page.keyboard.press("Space")
    page.wait_for_function("document.querySelector('#gameScore').textContent==='1'")
    page.locator(".game-leaders-button").click()
    assert page.locator(".game-pause").count() == 1
    page.locator(".games-leader-close").click()
    before = page.locator("#gameClock").inner_text()
    page.wait_for_timeout(1100)
    assert page.locator("#gameClock").inner_text() == before
    page.locator(".game-pause button").click()
    page.locator("#gameFinish").click()
    page.locator(".game-result-leaders").click()
    assert page.locator("#gamesLeaderDialog tr.is-me strong").inner_text() == "1"
    page.locator(".games-leader-close").click()
    page.locator(".game-back").click()


def test_reduced_motion_keeps_gameplay_and_disables_decorative_particles(arcade):
    page = arcade
    page.emulate_media(reduced_motion="reduce")
    assert page.evaluate("""() => {
      const sparks=new AlgoGameMotion.Sparks();sparks.burst(100,100);
      return sparks.items.length===0;
    }""")
    page.locator('.game-card[data-game="2048"]').click()
    page.locator("#gameStart").click()
    page.keyboard.press("ArrowLeft")
    assert page.locator(".number-moving").count() == 0
    assert page.locator(".number-cell").count() == 16
    page.locator(".game-close").click()


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_leaderboard_layout_and_short_screen_results(arcade, width):
    page = arcade
    page.set_viewport_size({"width": width, "height": 568})
    page.locator('[data-games-tab="leaders"]').click()
    assert page.locator(".games-leaders").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    page.locator('[data-games-tab="games"]').click()
    page.locator('.game-card[data-game="orbit"]').click()
    page.locator("#gameStart").click()
    page.locator("#gameFinish").click()
    page.locator(".game-back").click()
    assert page.locator("#gameDialog").count() == 0


def test_participation_never_unlocks_mastery(engine):
    assert engine.evaluate("""() => {
      const e=AlgoGameEngine,s=e.blank();
      for(const g of e.games)e.finish(s,g.id,0);
      return Object.keys(s.unlocked).length===0 && e.balance(s)===0;
    }""")


@pytest.mark.parametrize(
    ("game", "below", "target"),
    [
        ("orbit", 24, 25),
        ("evolve", 2047, 2048),
        ("bugs", 49, 50),
        ("tower", 24, 25),
        ("debug", 7, 8),
        ("2048", 512, 1024),
        ("drop", 999, 1000),
        ("memory", 39, 40),
    ],
)
def test_achievement_requires_a_good_single_run(engine, game, below, target):
    assert engine.evaluate(
        """([game,below,target])=>{
      const e=AlgoGameEngine,s=e.blank(),id='master2_'+game;
      e.finish(s,game,below);e.finish(s,game,1);
      if(s.unlocked[id])return false;
      e.finish(s,game,target);
      return Boolean(s.unlocked[id]);
    }""",
        [game, below, target],
    )


def test_typing_and_reaction_mastery_require_quality_of_the_same_run(engine):
    assert engine.evaluate("""()=>{
      const e=AlgoGameEngine,s=e.blank(),now=new Date();
      e.finish(s,'typing',300,now,{accuracy:94});
      e.finish(s,'typing',10,now,{accuracy:100});
      if(s.unlocked.master2_typing)return false;
      e.finish(s,'typing',240,now,{accuracy:95});
      e.finish(s,'react',15,now,{mistakes:0,reactionMs:351});
      e.finish(s,'react',15,now,{mistakes:1,reactionMs:250});
      if(s.unlocked.master2_react)return false;
      e.finish(s,'react',15,now,{mistakes:0,reactionMs:350});
      const restored=e.normalize(JSON.parse(JSON.stringify(s)));
      return Boolean(restored.unlocked.master2_typing&&restored.unlocked.master2_react);
    }""")


def test_overall_combines_places_from_all_ten_games_not_raw_points(engine):
    result = engine.evaluate("""()=>{
      const e=AlgoGameEngine,b=e.blankBoard(),now=new Date('2026-11-01T12:00:00Z');
      const a={id:'all',name:'All'},one={id:'one',name:'One'},low={id:'low',name:'Low'};
      for(const g of e.games){
        e.recordBoard(b,g.id,a,g.goal,3,now,{result:g.goal,accuracy:98,mistakes:0,
          reactionMs:300,moves:10,timeMs:20000});
      }
      e.recordBoard(b,'drop',one,10000000,10,now);
      e.recordBoard(b,'orbit',low,1,1,now);
      return e.overall(b,'week',now).map(r=>[r.player,r.games,r.score]);
    }""")
    assert result == [["all", 10, 980], ["one", 1, 100]]


def test_closed_week_top_three_prizes_are_final_and_idempotent(engine):
    result = engine.evaluate("""()=>{
      const e=AlgoGameEngine,b=e.blankBoard(),sun=new Date('2026-11-01T20:59:59Z');
      for(let i=0;i<4;i++)e.recordBoard(b,'tower',{id:'p'+i,name:'Player '+i},30-i,5,sun);
      const early=e.settleBoard(b,sun).length;
      const before=e.collectPrizes(e.blank(),b,'p0',sun);
      const mon=new Date('2026-11-01T21:00:00Z');
      const closed=e.settleBoard(b,mon).length;
      const payouts=[];
      for(let i=0;i<4;i++){
        const s=e.blank();const paid=e.collectPrizes(s,b,'p'+i,mon);
        const restored=e.normalize(JSON.parse(JSON.stringify(s)));
        const board=e.normalizeBoard(JSON.parse(JSON.stringify(b)));
        payouts.push([paid,e.collectPrizes(restored,board,'p'+i,mon),e.balance(restored)]);
      }
      const late=e.recordBoard(b,'tower',{id:'p3',name:'Player 3'},999,10,sun);
      return {early,before,closed,payouts,late,again:e.settleBoard(b,mon).length};
    }""")
    assert result == {
        "early": 0,
        "before": 0,
        "closed": 1,
        "payouts": [[100, 0, 100], [75, 0, 75], [50, 0, 50], [0, 0, 0]],
        "late": False,
        "again": 0,
    }


def test_overall_ties_have_a_deterministic_top_three(engine):
    assert engine.evaluate("""()=>{
      const e=AlgoGameEngine,b=e.blankBoard(),now=new Date('2026-11-01T12:00:00Z');
      for(const id of ['d','c','b','a'])e.recordBoard(b,'orbit',{id,name:id},25,5,now);
      const rows=e.overall(b,'week',now);
      e.settleBoard(b,new Date('2026-11-02T12:00:00Z'));
      return rows.map(r=>r.player).join()==='a,b,c,d' &&
        b.settled['2026-10-26'].winners.map(r=>r.amount).join()==='100,75,50';
    }""")


def test_every_game_has_the_same_individual_leaderboard_entry(arcade):
    page = arcade
    assert page.locator(".game-card-leader").count() == 10
    for game in ["typing", "debug", "memory", "react", "orbit"]:
        page.locator(f'[data-game-board="{game}"]').click()
        assert page.locator("#gamesLeaderDialog .games-leader-period").is_visible()
        assert page.locator("#gamesLeaderDialog .league-prize-podium").count() == 0
        assert page.locator("#gamesLeaderDialog [data-leader-game]").count() == 0
        page.locator(".games-leader-close").click()


def test_weekly_winner_credit_survives_reload_without_duplicate(arcade):
    page = arcade
    original = page.evaluate("students.map(s=>s.balance)")
    page.evaluate("""()=>{
      const e=AlgoGameEngine,b=e.blankBoard(),id=document.querySelector('#gamesPlayer').value;
      const prev=new Date(e.weekKey()+'T00:00:00+03:00');prev.setTime(prev.getTime()-1000);
      e.recordBoard(b,'orbit',{id,name:'Победитель'},25,5,prev);
      localStorage.setItem('algo-games-leaderboards:v2',JSON.stringify(b));
      algoGames.render();
    }""")
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary strong").inner_text() == "100 AC"
    assert (
        page.locator(".games-reward-list").last.inner_text().count("Общий рейтинг · 1-е место") == 1
    )
    page.reload(wait_until="networkidle")
    page.locator('[data-games-tab="rewards"]').first.click()
    assert page.locator(".games-reward-summary strong").inner_text() == "100 AC"
    assert page.evaluate("students.map(s=>s.balance)") == original
