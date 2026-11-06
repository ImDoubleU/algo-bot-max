"""Only play time counts; deterministic intermissions cannot consume a deadline."""

import json

import pytest

from app.services import arcade_runtime
from tests.test_arcade_server import store as store


@pytest.mark.parametrize("game", ["sort", "memory", "debug"])
def test_explicit_intermission_freezes_attempt_time_and_server_replays_it(store, game):
    session = store.session("p1", game, "ranked", "keyboard")
    with arcade_runtime.context() as vm:
        vm.eval("""function playClock(setup){
          const W=ArcadeWorld,C=ArcadeClock,w=W.create(setup),events=[];
          const send=a=>{const e={...a,t:w.tick,source:'keyboard'};events.push(e);W.input(w,e);};
          W.advance(w,12);
          if(w.id==='sort')for(const move of w.sortSolution.slice()){
            W.advance(w,6);send(move);
          }
          if(w.id==='memory'){
            const groups=new Map();w.cards.forEach((v,i)=>{if(!groups.has(v))groups.set(v,[]);
              groups.get(v).push(i);});
            for(const pair of groups.values())for(const i of pair)send({type:'cell',i});
          }
          if(w.id==='debug'){
            const t=w.tasks[0];send({type:'line',i:t.line});
            send(t.freeAnswer?{type:'fix',value:t.options[t.answer]}:{type:'answer',i:t.answer});
          }
          const before=C.time(w),clock=C.view(w),paused=C.intermission(w);
          W.advance(w,60*120);const after=C.time(w),during=C.view(w),ended=w.ended;
          send({type:'next'});W.advance(w,60);
          return {events,ticks:w.tick,report:W.report(w),before,after,
            resumed:C.time(w),clock,during,paused,ended};
        }""")
        run = vm.call("playClock", session["setup"])
    assert session["setup"]["clockRules"] == 2
    assert run["paused"] and not run["ended"]
    assert run["after"] == run["before"]
    assert run["resumed"] == pytest.approx(run["before"] + 1)
    assert run["clock"]["value"] == run["during"]["value"]
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(run["ticks"] / 60 + 1)
    result = store.finish("p1", session["id"], run["events"], run["ticks"])
    assert result["run"]["report"]["timeMs"] == run["report"]["timeMs"]
    assert result["run"]["report"]["details"]["elapsedTimeMs"] >= 120000
    assert not result["run"]["accepted"]  # An unfinished attempt cannot get rewards.


def test_sort_competition_ends_after_ten_minutes_of_play_not_intermission_wall_time():
    with arcade_runtime.context() as vm:
        value = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,C=ArcadeClock,w=W.create({game:'sort',seed:17,mode:'ranked',
            clockRules:2,sortRules:2,roundSeconds:600});
          W.advance(w,60);for(const a of w.sortSolution.slice())W.input(w,a);
          W.advance(w,600*60);const paused=!w.ended&&C.time(w)===1;
          W.input(w,{type:'next'});W.advance(w,600*60);
          return {paused,report:W.report(w)};
        })())""")
        )
    assert value["paused"]
    assert value["report"]["complete"] and value["report"]["timeMs"] == 600000
    assert value["report"]["details"]["elapsedTimeMs"] >= 1200000


def test_reaction_feedback_does_not_count_but_automatic_transition_still_completes():
    with arcade_runtime.context() as vm:
        value = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,C=ArcadeClock,w=W.create({game:'react',seed:17,
            mode:'ranked',clockRules:2});
          while(w.signal!=='go')W.advance(w,1);
          W.advance(w,12);W.input(w,{type:'tap'});const before=C.time(w);
          W.advance(w,60);return {elapsed:C.time(w)-before,signal:w.signal,score:w.score};
        })())""")
        )
    assert value["score"] == 1 and value["signal"] == "wait"
    assert 0 <= value["elapsed"] < 0.1


def test_clock_policy_distinguishes_deadlines_from_attempt_stopwatches():
    with arcade_runtime.context() as vm:
        views = json.loads(
            vm.eval("""JSON.stringify(Object.fromEntries(
          AlgoGameEngine.games.map(g=>{const w=ArcadeWorld.create({game:g.id,seed:17,
            mode:'ranked',clockRules:2,evolveRules:2,roundSeconds:g.id==='sort'?600:0});
            return [g.id,ArcadeClock.view(w)];})))""")
        )
    countdown = {"typing", "kopatych", "words", "evolve", "sort", "memory"}
    assert {g for g, v in views.items() if v["kind"] == "countdown"} == countdown
    assert all(v["value"] >= 0 for v in views.values())
