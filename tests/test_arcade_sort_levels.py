"""Exercise every Ball Sort adventure and retain progression on the server."""

import json

import pytest

from app.services import arcade_runtime
from tests.test_arcade_server import store as store
from tests.test_arcade_server import trace

SOLVE = """
  for(let round=0;round<w.journey.goal;round++){
    for(const a of w.sortSolution.slice()){W.advance(w,60);send(a);}
    if(!w.ended){W.advance(w,60);send({type:'next'});}
  }
"""


@pytest.mark.parametrize("rules,maximum", [(3, 24), (4, 48)])
def test_all_levels_are_solvable_on_twenty_seeds_without_losing_balls(rules, maximum):
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval(
                """JSON.stringify((()=>{
          const W=ArcadeWorld;let checked=0,puzzles=0;
          for(let stage=1;stage<=MAXIMUM;stage++)for(let seed=0;seed<20;seed++){
            const w=W.create({game:'sort',mode:'journey',seed,sortRules:RULES,clockRules:2,
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
                if(w.tubes.some((t,i)=>t.length>ArcadeSortLevels.capacity(w,i)))
                  throw Error('Capacity overflow');
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
        })())""".replace("MAXIMUM", str(maximum)).replace("RULES", str(rules))
            )
        )
    assert result["checked"] == maximum * 20
    assert result["puzzles"] >= maximum * 20


def test_all_levels_unlock_and_keep_stars_when_reopened_without_entering_rankings(store):
    for stage in range(1, 49):
        session = store.session("p1", "sort", "journey", "keyboard", stage)
        replay = trace(session["setup"], SOLVE)
        assert replay["report"]["journey"]["success"]
        store.clock_action("p1", session["id"], "start")
        store.clock.advance(replay["ticks"] / 60 + 1)
        result = store.finish("p1", session["id"], replay["events"], replay["ticks"])
        assert not result["run"]["accepted"]  # Levels never populate the ranked board.
    progress = store.profile("p1")["journeys"]["sort"]
    assert progress["cleared"] == 48 and progress["unlocked"] == 48
    assert progress["stars"] == 144 and progress["keepsakes"] == list(range(1, 7))
    assert not store.board("sort", viewer="p1")["rows"]
    assert len(store.profile("p1")["awards"]) == 1
    assert store.profile("p1")["awards"][0]["amount"] == 5
    restarted = type(store)(store.path, store.clock)
    assert restarted.profile("p1")["journeys"]["sort"] == progress


def test_old_stars_tools_and_collections_survive_the_expanded_route(store):
    with store.db() as db:
        for stage in range(1, 25):
            db.execute(
                "INSERT INTO arcade_journeys VALUES(?,?,?,?,?,?,?)",
                ("p1", "sort", stage, 3, 4, store.clock(), "{}"),
            )
    saved = store.profile("p1")["journeys"]["sort"]
    assert saved["maximum"] == 48 and saved["unlocked"] == 25
    assert saved["stars"] == 72 and saved["cleared"] == 24
    assert saved["charges"] == 3 and saved["keepsakes"] == list(range(1, 7))
    assert store.session("p1", "sort", "journey", "keyboard")["setup"]["sortRules"] == 4


def test_small_tubes_clip_grouped_pours_and_cannot_be_overfilled():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'sort',mode:'journey',seed:17,sortRules:4,
            clockRules:2,journey:{stage:12,charges:1}});
          // Isolated input fixture: same color group, deliberately smaller receiver.
          w.tubes=[[0,0,0,0],[],[1,1,1,1],[]];w.sortCaps=[4,2,4,4];
          w.sortSeals=[false,false,false,false];w.sortSeen=w.tubes.map(t=>t.map(()=>true));
          const first=W.input(w,{type:'pour',from:0,to:1}),sizes=w.tubes.map(t=>t.length),
            second=W.input(w,{type:'pour',from:0,to:1});
          return {first,second,sizes,moves:w.details.moves};
        })())""")
        )
    assert result == {"first": True, "second": False, "sizes": [2, 2, 4, 0], "moves": 1}


def test_seal_rejects_input_then_opens_permanently_even_if_a_color_is_dismantled():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,L=ArcadeSortLevels,w=W.create({game:'sort',mode:'journey',
            seed:17,sortRules:4,clockRules:2,journey:{stage:21,charges:1}}),
            lock=w.sortSeals.indexOf(true),source=w.tubes.findIndex(t=>t.length);
          if(!L.sealed(w,lock)||W.input(w,{type:'pour',from:source,to:lock}))
            throw Error('Seal accepts input');
          for(const a of w.sortSolution.slice()){
            W.advance(w,60);W.input(w,a);if(w.sortSealUnlocked)break;
          }
          if(w.ended||!w.sortSealUnlocked)throw Error('No intermediate unlock');
          const small=w.sortCaps.findIndex(c=>c===2);
          if(w.tubes[small].length){
            const empty=w.tubes.findIndex((t,i)=>i!==small&&!t.length&&w.sortCaps[i]===4);
            if(!W.input(w,{type:'pour',from:small,to:empty}))throw Error('Cannot empty buffer');
          }
          const full=w.tubes.findIndex(t=>t.length===4&&t.every(c=>c===t[0]));
          if(!W.input(w,{type:'pour',from:full,to:small}))throw Error('Cannot dismantle');
          return {sealed:L.sealed(w,lock),moves:w.details.moves};
        })())""")
        )
    assert not result["sealed"] and result["moves"] > 1


def test_hidden_layers_reveal_top_balls_and_move_their_knowledge_with_the_pour():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'sort',mode:'journey',seed:17,sortRules:4,
            clockRules:2,journey:{stage:29,charges:1}}),
            hidden=()=>w.sortSeen.flat().filter(v=>!v).length,before=hidden();
          if(!before)throw Error('No hidden layers');
          for(const a of w.sortSolution.slice()){
            W.advance(w,60);W.input(w,a);
            w.tubes.forEach((t,i)=>{
              if(w.sortSeen[i].length!==t.length||(t.length&&!w.sortSeen[i].at(-1)))
                throw Error('Knowledge detached from balls');
            });
          }
          return {before,after:hidden(),success:w.journey.complete};
        })())""")
        )
    assert result["before"] > result["after"] and result["success"]


def test_help_is_once_per_puzzle_and_prevents_three_stars_without_adding_coins():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'sort',mode:'journey',seed:17,sortRules:4,
            clockRules:2,journey:{stage:8,charges:3}});
          if(!W.input(w,{type:'power'})||W.input(w,{type:'power'}))throw Error('Stacked help');
          W.input(w,{type:'restart'});
          if(W.input(w,{type:'power'}))throw Error('Restart stacks help');
          for(let round=0;round<w.journey.goal;round++){
            for(const a of w.sortSolution.slice()){W.advance(w,60);W.input(w,a);}
            if(!w.ended){W.input(w,{type:'next'});if(!W.input(w,{type:'power'}))
              throw Error('Next puzzle loses help');}
          }
          return {stars:w.journey.stars,used:w.journey.used,tubes:w.tubes.length};
        })())""")
        )
    assert result["stars"] == 2 and result["used"] == 2 and result["tubes"] <= 10


def test_restart_keeps_spent_moves_and_exceeding_the_budget_fails_the_level():
    with arcade_runtime.context() as vm:
        result = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld,w=W.create({game:'sort',mode:'journey',seed:17,sortRules:4,
            clockRules:2,journey:{stage:33,charges:1}}),limit=w.journey.moves;
          while(!w.ended){
            W.advance(w,60);W.input(w,w.sortSolution[0]);
            W.advance(w,60);W.input(w,{type:'restart'});
          }
          return {score:w.score,moves:w.journey.movesUsed,limit,stars:w.journey.stars,
            reason:w.reason,elapsed:ArcadeClock.time(w)};
        })())""")
        )
    assert result["moves"] == result["limit"] and result["elapsed"] > 0
    assert result["stars"] == 0 and result["score"] == 0
    assert result["reason"] == "Ходы закончились"
