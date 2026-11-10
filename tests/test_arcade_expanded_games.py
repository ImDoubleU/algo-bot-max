"""Curricula, dictionaries, rescue decisions and stable contacts use real verifiers."""

import contextlib
import io
import json
from pathlib import Path

import pytest

from app.services import arcade_journey, arcade_runtime, arcade_words
from app.services.arcade import ArcadeStore
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import store as store


@pytest.mark.parametrize("filename", ["arcade_legacy_sort_words.json", "arcade_legacy_drop.json"])
def test_frozen_old_replays_are_unchanged(filename):
    rows = json.loads((Path(__file__).parent / "fixtures" / filename).read_text(encoding="utf8"))
    for row in rows:
        assert arcade_runtime.verify(row["setup"], row["actions"], row["ticks"]) == row["report"]


def test_word_deck_uses_entire_catalogue_before_repeating_and_survives_restart(store):
    size = len(arcade_words.roots())
    assert size >= 150
    selected = []
    for _ in range(size // 5 + 2):
        setup = store.session("p1", "words", "practice", "keyboard")["setup"]
        assert len(set(setup["wordRoots"])) == 5
        selected.extend(setup["wordRoots"])
        store.clock.advance(3)
    assert len(set(selected[:size])) == size
    restarted = ArcadeStore(store.path, store.clock)
    with restarted.db() as db:
        before = json.loads(
            db.execute("SELECT state FROM arcade_word_decks WHERE player='p1'").fetchone()[0]
        )
    next_roots = restarted.session("p1", "words", "journey", "keyboard", 1)["setup"]["wordRoots"]
    assert next_roots == before["remaining"][:5]
    assert store.profile("p1")["balance"] == 0


def test_expanded_dictionary_accepts_real_nouns_and_explains_letter_shortages():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const w=ArcadeWorld.create({game:'words',seed:17,mode:'practice',wordDictionary:2,
            wordRoots:['ПРОГРАММИРОВАНИЕ','КОСМОНАВТИКА','ЭЛЕКТРОСТАНЦИЯ','КОНСТРУКТОР','МАТЕМАТИКА']});
          ArcadeWorld.input(w,{type:'word',value:' ГРАММ '});const accepted=w.score;
          ArcadeWorld.input(w,{type:'word',value:'грамм'});const duplicate=w.score;
          ArcadeWorld.input(w,{type:'word',value:'граммм'});const shortage=w.wordFeedback;
          const total=new Set(ArcadeExtras.packsV2.flatMap(p=>p.answers)).size;
          return {accepted,duplicate,shortage,total};
        })())""")
        )
    assert result["accepted"] == result["duplicate"] == 1
    assert "не хватает букв" in result["shortage"]
    assert result["total"] >= 9000


def test_all_ninety_six_python_patterns_have_executable_corrected_examples():
    with arcade_runtime.context() as vm:
        groups = json.loads(vm.eval("JSON.stringify(ArcadeLessons.cases)"))
    assert [len(g) for g in groups] == [12] * 8
    for group in groups:
        for task in group:
            lines = task["lines"].copy()
            lines[task["line"]] = task["options"][task["answer"]]
            assert "\n".join(lines) == task["correctCode"]
            with contextlib.redirect_stdout(io.StringIO()):
                exec(
                    compile(task["correctCode"], "<original-lesson>", "exec"),
                    {"__name__": "lesson"},
                )


def test_advanced_fixes_cannot_be_answered_by_option_number_and_ignore_only_safe_formatting():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'debug',mode:'journey',seed:17,lessonVersion:2,
            journey:{stage:85,charges:1}}),t=w.tasks[0];
          W.input(w,{type:'line',i:t.line});const bypass=W.input(w,{type:'answer',i:t.answer});
          const typed=W.input(w,{type:'fix',value:'  '+t.options[t.answer]+'  '});
          return {free:t.freeAnswer,bypass,typed,score:w.score,
            equivalent:ArcadeLessons.sameFix('print( "кот" )',"print('кот')"),
            altered:ArcadeLessons.sameFix('print("ко т")','print("кот")')};
        })())""")
        )
    assert result == dict(
        free=True, bypass=False, typed=True, score=1, equivalent=True, altered=False
    )


def test_long_curricula_keep_old_stars_chapter_rewards_and_tool_charges(store):
    with store.db() as db:
        for stage in range(1, 25):
            db.execute(
                "INSERT INTO arcade_journeys VALUES(?,?,?,?,?,?,?)",
                ("p1", "typing", stage, 3, 200, store.clock(), "{}"),
            )
    saved = store.profile("p1")["journeys"]["typing"]
    assert saved["maximum"] == 96 and saved["unlocked"] == 25
    assert saved["stars"] == 72 and saved["keepsakes"] == [1, 2, 3, 4, 5, 6]
    assert saved["charges"] == 3
    assert len(arcade_journey.catalogue()["debug"]["stages"]) == 96


def test_rescue_missions_require_real_rescues_and_abilities_spend_charges():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'evolve',seed:17,mode:'journey',evolveRules:2,
            journey:{stage:1,charges:1}});
          for(let n=0;n<8&&!w.ended;n++){
            let pair=null;for(let i=0;i<16&&!pair;i++)for(let j=i+1;j<16;j++)
              if(w.cells[i]===w.cells[j]){pair=[i,j];break;}
            W.input(w,{type:'cell',i:pair[0]});W.input(w,{type:'cell',i:pair[1]});
          }
          const blocked=!w.journey.complete&&w.score>=w.journey.goal;
          const slot=w.expedition.orders.findIndex(v=>w.cells.includes(v));
          W.input(w,{type:'cell',i:w.cells.indexOf(w.expedition.orders[slot])});
          W.input(w,{type:'rescue',slot});
          const p=W.create({game:'evolve',seed:17,mode:'practice',evolveRules:2});
          const i=p.cells.indexOf(0);
          W.input(p,{type:'cell',i});const grown=W.input(p,{type:'ability',kind:'grow'});
          return {blocked,rescued:w.expedition.rescued,complete:w.journey.complete,
            grown,charges:p.expedition.charges};
        })())""")
        )
    assert result == dict(blocked=True, rescued=1, complete=True, grown=True, charges=0)


def test_drop_v4_piles_sleep_maximum_bodies_do_not_merge_again_and_values_stay_finite():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'drop',seed:17,mode:'practice',
            dropPhysics:4,arena:'classic'});
          w.balls=[0,1,2,3].map((level,i)=>({id:i+1,level,r:W.rad[level],x:70+i*65,y:100,
            vx:.5,vy:0,spin:0,angle:0,age:0,squash:0}));w.nextId=4;
          W.advance(w,1800);const before=w.balls.map(b=>[b.x,b.y]);W.advance(w,600);
          const movement=Math.max(...w.balls.map((b,i)=>
            Math.hypot(b.x-before[i][0],b.y-before[i][1])));
          const max=W.create({game:'drop',seed:17,mode:'practice',dropPhysics:4});
          max.balls=[120,230].map((x,i)=>({id:i+1,level:7,r:W.rad[7],x,y:300,
            vx:0,vy:0,spin:0,angle:0,age:0,squash:0}));max.nextId=2;W.advance(max,600);
          return {movement,sleep:w.balls.every(b=>b.sleep),
            maxCount:max.balls.length,maxScore:max.score,
            finite:w.balls.every(b=>[b.x,b.y,b.vx,b.vy,b.spin,b.squash].every(Number.isFinite))};
        })())""")
        )
    assert result["movement"] < 0.1, result
    assert result["sleep"] and result["finite"], result
    assert result["maxCount"] == 2 and result["maxScore"] == 0, result


def test_drop_impact_squashes_rebounds_and_settles_without_moving_the_collision_circle():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'drop',seed:17,mode:'practice',dropPhysics:4});
          w.balls=[{id:1,level:4,r:W.rad[4],x:180,y:90,vx:0,vy:0,
            spin:0,angle:0,age:0,squash:0}];w.nextId=1;
          const other=JSON.parse(JSON.stringify(w)),values=[];
          for(let i=0;i<240;i++){
            W.advance(w,1);W.advance(other,1);other.balls[0].squash=.3;
            const a=w.balls[0],b=other.balls[0];
            if(a.x!==b.x||a.y!==b.y||a.vx!==b.vx||a.vy!==b.vy)throw Error('Visual physics');
            values.push(a.squash);
          }
          return {peak:Math.max(...values),rebound:Math.min(...values),
            settled:values.at(-1),radius:w.balls[0].r,expected:W.rad[4]};
        })())""")
        )
    assert 0.20 < result["peak"] <= 0.30
    assert result["rebound"] < -0.01
    assert abs(result["settled"] - 0.025) < 0.001
    assert result["radius"] == result["expected"]


@pytest.mark.parametrize("width", [320, 1440])
def test_grouped_ball_flight_stays_in_the_board_and_rapid_click_does_not_double_move(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    page.evaluate("""()=>{
      const host=document.createElement('dialog');host.id='sortCheck';host.className='game-dialog';
      host.dataset.game='sort';host.style.cssText='width:'+Math.min(500,innerWidth-20)+'px';
      host.innerHTML='<div class="game-stage"></div>';document.body.append(host);host.showModal();
      const w=ArcadeWorld.create({game:'sort',seed:17,mode:'practice',sortRules:2});
      w.tubes=[[0,0,1,1],[1,1],[],[0,0],[]];w.sortStart=w.tubes.map(t=>t.slice());
      const abort=new AbortController(),events=[];let view;
      view=ArcadeView.mount('sort',host.firstElementChild,a=>{
        events.push(a);ArcadeWorld.input(w,a);view.update(w,0);},
        {signal:abort.signal,device:'keyboard',mode:'practice',
          quality:()=> 'high',paused:()=>false});
      view.update(w,0);window.sortCheck={w,view,abort,events};
    }""")
    page.locator('#sortCheck [data-tube="0"]').click()
    page.locator('#sortCheck [data-tube="1"]').click()
    assert page.locator("#sortCheck .sort-flight").count() == 2
    flight = page.locator("#sortCheck .sort-flight").first
    landing = page.locator('#sortCheck [data-tube="1"] .sort-ball').last
    assert flight.evaluate("n=>n.style.getPropertyValue('--marble')") == landing.evaluate(
        "n=>n.style.getPropertyValue('--marble')"
    )
    assert flight.locator("small,svg").count() == 0
    assert (
        page.locator("#sortCheck .sort-flight").first.evaluate("n=>getComputedStyle(n).position")
        == "absolute"
    )
    # Send the rapid physical click now; an ordinary Playwright click would wait
    # for the newly disabled button to become enabled after the flight.
    page.locator('#sortCheck [data-tube="3"]').click(force=True)
    assert page.evaluate("sortCheck.events.length") == 2
    assert page.evaluate("sortCheck.w.tubes[1].length") == 4
    page.wait_for_function(
        "!document.querySelector('#sortCheck .sort-tubes').hasAttribute('aria-busy')"
    )
    assert page.locator("#sortCheck .sort-flight").count() == 0
    assert page.locator("#sortCheck .sort-tubes button:disabled").count() == 0
    assert page.locator("#sortCheck").evaluate("n=>n.scrollWidth<=n.clientWidth")
    page.evaluate("sortCheck.abort.abort();document.querySelector('#sortCheck').remove()")


@pytest.mark.parametrize("width", [320, 390, 1440])
def test_changed_game_windows_fit_and_inline_typing_and_free_fix_are_operable(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    captures = Path(__file__).parents[1] / ".deploy_tmp/arcade-upgrade-screens"
    captures.mkdir(exist_ok=True)
    for game in ("typing", "debug", "evolve", "sort", "drop", "orbit", "tower"):
        page.evaluate(
            """game=>{
          const d=document.createElement('dialog');d.id='gameWindowCheck';d.className='game-dialog';
          d.dataset.game=game;
          d.innerHTML='<header><h2>'+AlgoGameEngine.games.find(g=>g.id===game).name+
            '</h2></header><div class="game-stage"></div>';
          document.body.append(d);d.showModal();
          const setup={game,seed:17,mode:'practice',device:'keyboard',lessonVersion:2,
            evolveRules:2,sortRules:2,dropPhysics:4,arena:'classic'};
          if(game==='debug')Object.assign(setup,{mode:'journey',journey:{stage:85,charges:1}});
          const w=ArcadeWorld.create(setup),abort=new AbortController();let view;
          view=ArcadeView.mount(game,d.querySelector('.game-stage'),a=>{
            ArcadeWorld.input(w,a);view.update(w,0);},
            {signal:abort.signal,mode:setup.mode,device:'keyboard',expedition:!!w.expedition,
              theme:'space',skin:'base',quality:()=> 'high',paused:()=>false});
          view.update(w,0);ArcadePersonality.decorate({g:{id:game},dialog:d,view});
          window.gameWindowCheck={w,view,abort};
        }""",
            game,
        )
        if game == "typing":
            field = page.locator("#gameWindowCheck textarea")
            first = page.evaluate("gameWindowCheck.w.text[0]")
            field.press_sequentially(first + "~")
            assert page.locator("#gameWindowCheck .typing-passage .correct").count() == 1
            assert page.locator("#gameWindowCheck .typing-passage .wrong").count() == 1
            field.press("Backspace")
            assert page.locator("#gameWindowCheck .typing-passage .wrong").count() == 0
            assert page.locator("#gameWindowCheck .typing-passage .cursor").count() == 1
        if game == "debug":
            line = page.evaluate("gameWindowCheck.w.tasks[0].line")
            page.locator(f'#gameWindowCheck [data-line="{line}"]').click()
            assert page.locator("#gameWindowCheck [data-option]").count() == 0
            answer = page.evaluate(
                "gameWindowCheck.w.tasks[0].options[gameWindowCheck.w.tasks[0].answer]"
            )
            page.locator("#debugFix").fill(answer)
            page.locator(".debug-fix-form button").click()
            assert page.locator(".debug-feedback.is-success").is_visible()
        if game == "evolve":
            cell = page.evaluate("gameWindowCheck.w.cells.indexOf(1)")
            page.locator(f'#gameWindowCheck [data-cell="{cell}"]').click()
            page.locator('#gameWindowCheck [data-rescue="0"]').click()
            assert page.evaluate("gameWindowCheck.w.expedition.rescued") == 1
        assert page.locator("#gameWindowCheck").evaluate("n=>n.scrollWidth<=n.clientWidth"), game
        page.locator("#gameWindowCheck").screenshot(path=str(captures / f"{game}-{width}.png"))
        page.evaluate(
            'gameWindowCheck.abort.abort();document.querySelector("#gameWindowCheck").remove()'
        )
