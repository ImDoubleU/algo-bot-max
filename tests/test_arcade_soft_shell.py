"""Soft bodies stay deformed under pressure and recover without spring oscillation."""

import json
from pathlib import Path

import pytest

from app.services import arcade_runtime
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser
from tests.test_arcade_server import trace


def evaluate(script):
    with arcade_runtime.context() as vm:
        vm.eval("""function softBall(id,level,x,y){const r=ArcadeWorld.rad[level];
          return {id,level,r,x,y,vx:0,vy:0,spin:0,angle:0,age:0,squash:0};} """)
        return json.loads(vm.eval("JSON.stringify((()=>{" + script + "})())"))


def test_soft_floor_contact_is_local_flattening_with_no_bounce_and_stays_asleep():
    result = evaluate("""
      const W=ArcadeWorld,w=W.create({game:'drop',seed:17,mode:'practice',dropPhysics:5});
      w.balls=[softBall(1,4,180,90)];w.nextId=1;
      let upwards=0;for(let i=0;i<600;i++){W.advance(w,1);if(w.balls[0].vy<-.1)upwards++;}
      const b=w.balls[0],y=b.y;W.advance(w,600);
      return {upwards,sleep:b.sleep,movement:Math.abs(b.y-y),bottom:b.softShape[6],
        top:b.softShape[18],side:b.softShape[0],q:b.squash,velocity:b.squashV};
    """)
    assert result["upwards"] == 0
    assert result["sleep"] and result["movement"] < 0.001
    assert result["bottom"] < 0.91 and result["top"] > 1 and result["side"] > 1
    assert result["q"] == result["velocity"] == 0


def test_weight_compresses_lower_body_more_and_releasing_it_recovers_monotonically():
    result = evaluate("""
      const W=ArcadeWorld,w=W.create({game:'drop',seed:17,mode:'practice',dropPhysics:5});
      w.balls=[softBall(1,3,180,385),softBall(2,5,180,310)];w.nextId=2;
      W.advance(w,1200);const lower=w.balls.find(b=>b.id===1),upper=w.balls.find(b=>b.id===2);
      const loaded={compression:lower.compression,top:lower.softShape[18],
        bottom:lower.softShape[6],side:lower.softShape[0],upper:upper.compression};
      w.balls=[lower];lower.y=180;lower.vy=0;lower.sleep=true;
      const values=[];for(let i=0;i<60;i++){
        // Hold the released body clear of all contacts to inspect its material recovery.
        lower.y=180;lower.vy=0;lower.sleep=true;
        W.advance(w,1);values.push(lower.softShape[18]);
      }
      return {loaded,values};
    """)
    loaded = result["loaded"]
    assert loaded["compression"] > loaded["upper"] + 0.05
    assert loaded["top"] < 0.9 and loaded["bottom"] < 0.9 and loaded["side"] > 1.02
    values = result["values"]
    assert all(a <= b + 1e-9 for a, b in zip(values, values[1:], strict=False))
    assert values[-1] > 0.99 and max(values) <= 1.001


@pytest.mark.parametrize("arena", ["classic", "bowl", "slopes", "pins"])
def test_new_soft_shells_remain_finite_bounded_and_server_replay_matches(arena):
    setup = dict(
        game="drop", seed=71, mode="practice", device="keyboard", dropPhysics=5, arena=arena
    )
    run = trace(
        setup,
        """
      for(let i=0;i<180&&!w.ended;i++){
        send({type:'tap',x:25+(i*83)%310});W.advance(w,42);
        for(const b of w.balls){
          if(![b.x,b.y,b.vx,b.vy,b.compression,...b.softShape].every(Number.isFinite))
            throw Error('Invalid soft body');
          if(b.x<10||b.x>350||b.y>417)throw Error('Escaped arena');
          if(b.softShape.some(v=>v<.5||v>1.221))throw Error('Unbounded deformation');
        }
      }
    """,
    )
    assert run["report"]["details"]["physics"] == "soft5"
    assert arcade_runtime.verify(setup, run["events"], run["ticks"]) == run["report"]


@pytest.mark.parametrize("width", [320, 1440])
def test_soft_contact_outline_renders_inside_the_board_at_phone_and_desktop_sizes(arcade, width):
    page, _ = arcade
    page.set_viewport_size(dict(width=width, height=900))
    result = page.evaluate("""()=>{
      const W=ArcadeWorld,w=W.create({game:'drop',seed:17,mode:'practice',dropPhysics:5});
      w.balls=[[1,5,70,368],[2,6,180,357],[3,4,300,377],[4,7,180,235]].map(
        ([id,level,x,y])=>({id,level,x,y,r:W.rad[level],vx:0,vy:0,
          spin:0,angle:0,age:0,squash:0}));w.nextId=4;W.advance(w,1800);
      const d=document.createElement('dialog');d.id='softShellCheck';d.className='game-dialog';
      d.dataset.game='drop';
      d.innerHTML='<header><h2>Космо-дроп</h2></header><div class="game-stage"></div>';
      document.body.append(d);d.showModal();const abort=new AbortController();
      const view=ArcadeView.mount('drop',d.lastElementChild,()=>{},
        {signal:abort.signal,readOnly:true,paused:()=>true,quality:()=> 'high',skin:'base'});
      view.update(w,0);window.softShellCheck={abort,view,w};
      return w.balls.every(b=>b.softShape.every((r,i)=>{
        const angle=i*Math.PI*2/b.softShape.length,x=b.x+Math.cos(angle)*r*b.r,
          y=b.y+Math.sin(angle)*r*b.r;
        return x>=11.99&&x<=348.01&&y<=416.01;
      }));
    }""")
    assert result
    page.wait_for_timeout(150)
    assert page.locator("#softShellCheck").evaluate("n=>n.scrollWidth<=n.clientWidth")
    captures = Path(__file__).parents[1] / ".deploy_tmp/soft-shell-screens"
    captures.mkdir(exist_ok=True)
    page.locator("#softShellCheck").screenshot(path=str(captures / f"pile-{width}.png"))
    page.evaluate('softShellCheck.abort.abort();document.querySelector("#softShellCheck").remove()')
