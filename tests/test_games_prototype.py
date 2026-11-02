"""Local game rules and UI. Uses static files, no database or outgoing MAX requests."""

import os
from pathlib import Path

import pytest

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
