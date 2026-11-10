"""Exercise every Ball Sort adventure and retain progression on the server."""

import json

from app.services import arcade_runtime
from tests.test_arcade_server import store as store
from tests.test_arcade_server import trace

SOLVE = """
  for(let round=0;round<w.journey.goal;round++){
    for(const a of w.sortSolution.slice()){W.advance(w,60);send(a);}
    if(!w.ended){W.advance(w,60);send({type:'next'});}
  }
"""


def test_all_twenty_four_levels_are_solvable_on_twenty_seeds_without_losing_balls():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld;let checked=0,puzzles=0;
          for(let stage=1;stage<=24;stage++)for(let seed=0;seed<20;seed++){
            const w=W.create({game:'sort',mode:'journey',seed,sortRules:3,clockRules:2,
              journey:{stage,charges:3}});
            if(w.sortCompetition)throw Error('Ranked rules leaked into levels');
            for(let round=0;round<w.journey.goal;round++){
              const colors=w.tubes.length-2,counts=Array(colors).fill(0);
              if(colors<3||colors>7||w.tubes.filter(t=>!t.length).length!==2)
                throw Error('Invalid tube count');
              for(const c of w.tubes.flat())counts[c]++;
              if(counts.some(n=>n!==4))throw Error('Lost balls');
              for(const a of w.sortSolution.slice()){
                W.advance(w,60);if(!W.input(w,a))throw Error('Illegal solution');
              }
              puzzles++;
              if(!w.ended){
                if(!w.sortWon)throw Error('Missing transition');
                const before=ArcadeClock.time(w),snapshot=JSON.stringify(w.tubes);
                W.advance(w,60*120);
                if(ArcadeClock.time(w)!==before||JSON.stringify(w.tubes)!==snapshot)
                  throw Error('Transition changed board or clock');
                if(W.input(w,{type:'tube',i:0}))throw Error('Transition input');
                W.input(w,{type:'next'});
              }
            }
            const report=W.report(w);
            if(!w.ended||!report.journey.success||report.score!==w.journey.goal)
              throw Error('Incomplete stage '+stage+':'+seed);
            checked++;
          }
          return {checked,puzzles};
        })())""")
        )
    assert result["checked"] == 480
    assert result["puzzles"] > 1000


def test_all_levels_unlock_and_keep_stars_when_reopened_without_entering_rankings(store):
    for stage in range(1, 25):
        session = store.session("p1", "sort", "journey", "keyboard", stage)
        replay = trace(session["setup"], SOLVE)
        assert replay["report"]["journey"]["success"]
        store.clock_action("p1", session["id"], "start")
        store.clock.advance(replay["ticks"] / 60 + 1)
        result = store.finish("p1", session["id"], replay["events"], replay["ticks"])
        assert not result["run"]["accepted"]  # Levels never populate the ranked board.
    progress = store.profile("p1")["journeys"]["sort"]
    assert progress["cleared"] == 24 and progress["unlocked"] == 24
    assert progress["stars"] == 72 and progress["keepsakes"] == list(range(1, 7))
    assert not store.board("sort", viewer="p1")["rows"]
    restarted = type(store)(store.path, store.clock)
    assert restarted.profile("p1")["journeys"]["sort"] == progress
