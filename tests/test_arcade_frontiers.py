"""New games are replayed, time transitions pause, exploration rewards deliveries only."""

# ruff: noqa: E501 -- embedded JavaScript replay traces.
import json

import pytest

from app.services import arcade_runtime
from app.services.arcade import ArcadeError
from tests.test_arcade_server import store as store
from tests.test_arcade_server import trace


@pytest.mark.parametrize("game", ["ocean", "slap", "plane", "menagerie", "evolve"])
def test_new_rules_replay_and_finish_without_client_scores(store, game):
    session = store.session("p1", game, "ranked", "touch")
    result = trace(
        session["setup"],
        """
      if(w.id==='plane'){send({type:'launch'});send({type:'flight',tilt:0,boost:true});}
      else if(w.id==='evolve'){send({type:'cell',i:24});W.advance(w,15);send({type:'cell',i:30});}
      else {send({type:'steer',x:0,y:-1});W.advance(w,30);send({type:'ability'});send({type:'steer',x:0,y:0});}
      while(!w.ended&&w.tick<16000){
        if(w.frontier.phase==='mutation')send({type:'mutate',trait:'armor'});
        W.advance(w,60);
      }
    """,
    )
    assert result["report"]["complete"]
    assert (
        arcade_runtime.verify(session["setup"], result["events"], result["ticks"])
        == result["report"]
    )
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(result["ticks"] / 60 + 1)
    saved = store.finish("p1", session["id"], result["events"], result["ticks"])
    assert saved["run"]["report"]["details"]["frontierRules"] == 1
    assert store.finish("p1", session["id"], [], 0)["duplicate"]
    with pytest.raises(ArcadeError):
        store.replay("p2", saved["run"]["id"])


def test_build_has_budget_and_freezes_active_clock():
    with arcade_runtime.context() as vm:
        data = vm.eval("""(()=>{
          const W=ArcadeWorld,w=W.create({game:'plane',seed:2,clockRules:2});
          W.advance(w,600);const before=ArcadeClock.time(w);
          const rejected=W.input(w,{type:'build',part:'wing',value:8});
          W.input(w,{type:'build',part:'tank',value:1});
          const accepted=W.input(w,{type:'build',part:'wing',value:7});
          W.input(w,{type:'launch'});W.advance(w,60);
          return JSON.stringify({before,after:ArcadeClock.time(w),rejected,accepted,
            total:w.frontier.wing+w.frontier.engine+w.frontier.tank});})()""")
    data = json.loads(data)
    assert data == dict(before=0, after=1, rejected=False, accepted=True, total=12)


def test_evolution_choices_pause_clock_and_only_active_play_grows():
    with arcade_runtime.context() as vm:
        data = json.loads(
            vm.eval("""(()=>{
          const W=ArcadeWorld,w=W.create({game:'menagerie',seed:3,clockRules:2});
          w.frontier.xp=100;W.advance(w,1);const at=ArcadeClock.time(w);
          W.advance(w,600);const frozen=ArcadeClock.time(w)===at;
          const valid=W.input(w,{type:'mutate',trait:'magnet'});
          const invalid=W.input(w,{type:'mutate',trait:'magnet'});
          return JSON.stringify({frozen,valid,invalid,magnet:w.frontier.magnet,level:w.frontier.level});})()""")
        )
    assert data == dict(frozen=True, valid=True, invalid=False, magnet=1, level=2)


def test_rescue_requires_adjacent_movement_and_returning_with_cargo():
    with arcade_runtime.context() as vm:
        data = json.loads(
            vm.eval("""(()=>{
          const W=ArcadeWorld,w=W.create({game:'evolve',evolveRules:3,seed:4,clockRules:2});
          const f=w.frontier;f.map[24]={kind:'beast',level:8};
          const teleport=W.input(w,{type:'cell',i:0});
          W.input(w,{type:'cell',i:24});const unbanked=w.score;
          W.advance(w,12);W.input(w,{type:'cell',i:30});
          return JSON.stringify({teleport,unbanked,score:w.score,saved:f.saved,team:f.team,cargo:f.cargo});})()""")
        )
    assert data == dict(teleport=False, unbanked=0, score=96, saved=1, team=[8], cargo=[])


@pytest.mark.parametrize("game", ["ocean", "slap", "plane", "menagerie", "evolve"])
def test_every_first_journey_has_reachable_goal_and_persistent_stars(store, game):
    session = store.session("p1", game, "journey", "keyboard", 1)
    common = """
      const f=w.frontier;
      for(let tick=0;tick<10000&&!w.ended;tick++){
        if(w.id==='plane'){
          if(f.phase==='build')send({type:'launch'});
          if(tick%15===0)send({type:'flight',tilt:f.y>190?-1:f.y<140?1:0,boost:true});
        }else if(w.id==='slap'){
          const e=f.enemies.reduce((a,b)=>!a||Math.hypot(b.x-f.x,b.y-f.y)<Math.hypot(a.x-f.x,a.y-f.y)?b:a,null);
          if(e&&tick%10===0){send({type:'aim',x:e.x,y:e.y});send({type:'ability'});}
        }else if(w.id==='ocean'){
          if(tick%10===0){const target=f.cargo.length>=2?{x:180,y:370}:f.items.filter(i=>!i.taken).sort((a,b)=>Math.hypot(a.x-f.x,a.y-f.y)-Math.hypot(b.x-f.x,b.y-f.y))[0];
            const dx=target.x-f.x,dy=target.y-f.y,l=Math.max(1,Math.hypot(dx,dy));send({type:'steer',x:dx/l,y:dy/l});}
        }else if(w.id==='menagerie'){
          if(f.phase==='mutation')send({type:'mutate',trait:'magnet'});
          if(tick%10===0){const target=f.fruit.filter(i=>(i.sleep||0)<=w.time).sort((a,b)=>Math.hypot(a.x-f.x,a.y-f.y)-Math.hypot(b.x-f.x,b.y-f.y))[0];
            if(target){const dx=target.x-f.x,dy=target.y-f.y,l=Math.max(1,Math.hypot(dx,dy));send({type:'steer',x:dx/l,y:dy/l});}}
        }else if(w.id==='evolve'&&!f.cool){
          const target=f.cargo.length?30:f.map.findIndex(t=>t.kind==='beast');
          const x=f.tile%6,y=Math.floor(f.tile/6),tx=target%6,ty=Math.floor(target/6);
          send({type:'cell',i:f.tile+(x!==tx?Math.sign(tx-x):Math.sign(ty-y)*6)});
        }
        W.advance(w,1);
      }
    """
    result = trace(session["setup"], common)
    assert result["report"].get("journey", {}).get("success"), result["report"]
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(result["ticks"] / 60 + 1)
    store.finish("p1", session["id"], result["events"], result["ticks"])
    assert store.profile("p1")["journeys"][game]["unlocked"] == 2


def test_legacy_evolution_replays_keep_the_old_grid():
    with arcade_runtime.context() as vm:
        assert vm.eval("!!ArcadeWorld.create({game:'evolve',seed:1,evolveRules:2}).expedition")
        assert vm.eval("!ArcadeWorld.create({game:'evolve',seed:1,evolveRules:2}).frontier")


def test_last_launched_plane_blueprint_survives_reentry_and_cancelled_build(store):
    session = store.session("p1", "plane", "practice", "keyboard")
    result = trace(
        session["setup"],
        """
      send({type:'build',part:'tank',value:1});
      send({type:'build',part:'wing',value:7});
      send({type:'launch'});W.advance(w,120);
    """,
    )
    store.clock_action("p1", session["id"], "start")
    store.clock.advance(3)
    store.finish("p1", session["id"], result["events"], result["ticks"], True)
    next_session = store.session("p1", "plane", "practice", "keyboard")
    assert next_session["setup"]["planeBuild"] == dict(wing=7, engine=4, tank=1)
    store.clock_action("p1", next_session["id"], "start")
    store.clock.advance(1)
    store.finish("p1", next_session["id"], [], 30, True)
    assert store.session("p1", "plane", "practice", "keyboard")["setup"]["planeBuild"] == dict(
        wing=7, engine=4, tank=1
    )


def test_touch_arena_attack_tracks_heading_and_keeps_it_after_stopping():
    with arcade_runtime.context() as vm:
        data = json.loads(
            vm.eval("""(()=>{
          const W=ArcadeWorld,w=W.create({game:'slap',seed:9,clockRules:2}),f=w.frontier;
          f.enemies=[{x:230,y:250,vx:0,vy:0,stun:0,cool:10,windup:0,health:1,id:0}];
          W.input(w,{type:'steer',x:1,y:0});W.advance(w,1);
          W.input(w,{type:'steer',x:0,y:0});W.advance(w,1);
          W.input(w,{type:'ability'});
          return JSON.stringify({vx:f.enemies[0].vx,vy:f.enemies[0].vy});})()""")
        )
    assert data["vx"] > 190 and abs(data["vy"]) < 1
