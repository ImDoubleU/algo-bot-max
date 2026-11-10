"""Finite, replay-verified Ball Sort races and compatibility with earlier runs."""

import json

from app.services import arcade_runtime
from tests.test_arcade_server import store as store
from tests.test_arcade_server import trace

SOLVE = """
  for(let level=0;level<5;level++){
    for(const a of w.sortSolution.slice()){W.advance(w,54);send(a);}
    if(level<4){W.advance(w,54);send({type:'next'});}
  }
"""


def test_same_ranked_series_for_both_devices_and_all_players(store):
    sessions = [
        store.session(player, "sort", "ranked", device)
        for player, device in [("p1", "keyboard"), ("p2", "touch"), ("p3", "keyboard")]
    ]
    assert len({s["setup"]["seed"] for s in sessions}) == 1
    for session in sessions:
        setup = session["setup"]
        assert setup["sortCompetition"] == 1 and setup["sortRules"] == 3
        assert setup["roundSeconds"] == 600
    assert "sortCompetition" not in store.session("p1", "sort", "practice", "touch")["setup"]
    assert "sortCompetition" not in store.session("p1", "memory", "ranked", "touch")["setup"]


def test_five_hundred_puzzles_are_solvable_with_legal_grouped_pours():
    with arcade_runtime.context() as vm:
        value = json.loads(
            vm.eval("""JSON.stringify((()=>{
          const W=ArcadeWorld;let boards=0;
          for(let seed=0;seed<100;seed++){
            const w=W.create({game:'sort',seed,mode:'ranked',sortRules:3,
              sortCompetition:1,clockRules:2,roundSeconds:600});
            for(let level=0;level<5;level++){
              const colors=level+3,counts=Array(colors).fill(0);
              w.tubes.flat().forEach(c=>counts[c]++);
              if(counts.some(n=>n!==4)||w.tubes.filter(t=>!t.length).length!==2)
                throw Error('Invalid starting board '+seed+':'+level);
              for(const a of w.sortSolution.slice()){
                W.advance(w,54);if(!W.input(w,a))throw Error('Illegal solution');
              }
              if(!w.sortWon||w.score!==level+1)throw Error('Unsolved '+seed+':'+level);
              boards++;
              if(level<4){W.advance(w,54);W.input(w,{type:'next'});}
            }
            if(!w.ended||w.details.sortSplits.length!==5)throw Error('No final result');
          }
          return boards;
        })())""")
        )
    assert value == 500


def test_transition_rejects_every_board_action_and_clock_stays_frozen(store):
    session = store.session("p1", "sort", "ranked", "keyboard")
    result = trace(
        session["setup"],
        """
      for(const a of w.sortSolution.slice()){W.advance(w,54);send(a);}
      W.advance(w,54);
      const snapshot=JSON.stringify(w.tubes),before=ArcadeClock.time(w),moves=w.details.moves;
      for(const a of [{type:'tube',i:0},{type:'restart'},{type:'undo'},
        {type:'pour',from:0,to:3}]){
        if(W.input(w,a))throw Error('Input leaked through transition');
      }
      W.advance(w,7200);
      if(ArcadeClock.time(w)!==before||w.details.moves!==moves||
        w.selectedTube!==-1||JSON.stringify(w.tubes)!==snapshot)throw Error('Board mutated');
      send({type:'next'});
      if(W.input(w,{type:'next'}))throw Error('Double next');
      W.advance(w,60);
      if(ArcadeClock.time(w)!==before+1)throw Error('Clock did not resume');
    """,
    )
    assert result["report"]["score"] == 1
    assert (
        arcade_runtime.verify(session["setup"], result["events"], result["ticks"])
        == result["report"]
    )


def test_ranked_pacing_cannot_be_bypassed_by_reduced_animation_or_single_flag(store):
    setup = store.session("p1", "sort", "ranked", "keyboard")["setup"]
    with arcade_runtime.context() as vm:
        vm.eval("""function check(setup){
          const W=ArcadeWorld,w=W.create(setup),moves=w.sortSolution.slice();
          const first=moves[0],color=w.tubes[first.from].at(-1),space=4-w.tubes[first.to].length;
          let count=0;for(const c of w.tubes[first.from].slice().reverse()){
            if(c!==color)break;count++;
          }
          if(!W.input(w,{...first,single:true}))throw Error('Initial pour');
          const moved=w.cues.filter(c=>c.type==='pour').at(-1).count;
          if(moved!==Math.min(count,space))throw Error('Single flag');
          if(W.input(w,moves[1]))throw Error('Same-tick pacing');
          W.advance(w,53);if(W.input(w,moves[1]))throw Error('Early pacing');
          W.advance(w,1);if(!W.input(w,moves[1]))throw Error('Pacing never releases');
          return w.details.moves;
        }""")
        assert vm.call("check", setup) == 2


def test_full_race_is_verified_and_rewards_are_not_duplicated(store):
    session = store.session("p1", "sort", "ranked", "keyboard")
    replay = trace(session["setup"], SOLVE)
    assert replay["report"]["complete"] and replay["report"]["score"] == 5
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(replay["ticks"] / 60 + 1)
    result = store.finish("p1", session["id"], replay["events"], replay["ticks"])
    assert result["run"]["accepted"]
    assert store.profile("p1")["goals"]["sort"]["eligible"]
    assert store.finish("p1", session["id"], [], 0)["duplicate"]
    assert len(store.profile("p1")["awards"]) == 4
    board = store.board("sort", viewer="p1")
    assert board["rows"][0]["result"] == 5
    splits = result["run"]["report"]["details"]["sortSplits"]
    assert [s["solved"] for s in splits] == [1, 2, 3, 4, 5]
    assert store._master("sort", 5, {"sortCompetition": 1, "sortSplits": splits}, 0)


def test_timeout_ranks_by_last_completed_puzzle_not_later_wasted_moves(store):
    setup = store.session("p1", "sort", "ranked", "keyboard")["setup"]
    replay = trace(
        setup,
        """
      for(const a of w.sortSolution.slice()){W.advance(w,54);send(a);}
      W.advance(w,54);send({type:'next'});
      W.advance(w,54);send(w.sortSolution[0]);
      W.advance(w,600*60);
    """,
    )
    report = replay["report"]
    assert report["complete"] and report["timeMs"] == 600000
    assert report["score"] == 1
    assert report["details"]["sortSolvedTimeMs"] < report["timeMs"]
    assert report["details"]["sortSolvedMoves"] < report["details"]["moves"]
    assert arcade_runtime.verify(setup, replay["events"], replay["ticks"]) == report


def test_board_orders_solutions_then_time_then_moves_and_keeps_legacy_rows_untouched(store):
    def row(player, score, time_ms, moves, version=1):
        return {
            "player": player,
            "game": "sort",
            "device": "keyboard",
            "score": score,
            "rank_score": score,
            "name": player,
            "group_name": "Demo",
            "created": 1,
            "report": json.dumps(
                {
                    "level": 1,
                    "timeMs": 600000,
                    "details": {
                        "sortCompetition": version,
                        "sortSolvedTimeMs": time_ms,
                        "sortSolvedMoves": moves,
                    },
                }
            ),
        }

    rows = [
        row("p1", 4, 50000, 10),
        row("p2", 5, 100000, 90),
        row("p3", 5, 90000, 95),
        row("p4", 5, 90000, 80),
        row("old", 20, 1, 1, 0),
    ]
    before = json.dumps(rows)
    assert [r["player"] for r in store._game_board(rows, "sort")] == ["p4", "p3", "p2", "p1"]
    assert json.dumps(rows) == before


def test_medals_require_more_than_the_basic_goal_and_gold_requires_better_quality(store):
    assert not store._master(
        "sort",
        3,
        {"sortCompetition": 1, "sortSplits": [{"solved": 3, "timeMs": 30000, "moves": 20}]},
        0,
    )
    details = {
        "sortCompetition": 1,
        "sortSplits": [
            {"solved": 4, "timeMs": 170000, "moves": 79},
            {"solved": 5, "timeMs": 250000, "moves": 110},
        ],
    }
    assert store._master("sort", 5, details, 0)
    assert store._master("sort", 5, details, 1)
    assert not store._master("sort", 5, details, 2)
    details["sortSplits"][1].update(timeMs=179000, moves=90)
    assert store._master("sort", 5, details, 2)
    details["sortSplits"][1]["moves"] = 91
    assert not store._master("sort", 5, details, 2)
