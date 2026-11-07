"""The rebuilt Cosmodrop uses its visible soft boundary for contacts and replay."""

import json
from pathlib import Path

import pytest

from app.services import arcade_runtime
from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import trace
from tests.test_arcade_webkit import browser as browser


def inspect(script):
    with arcade_runtime.context() as vm:
        vm.eval("""function ball(id,level,x,y){return {id,level,x,y,r:ArcadeWorld.rad[level],
          vx:0,vy:0,spin:0,angle:0,age:0};}""")
        return json.loads(vm.eval("JSON.stringify((()=>{" + script + "})())"))


def test_floor_contact_keeps_area_and_settles_without_persistent_motion():
    value = inspect("""
      const W=ArcadeWorld,w=W.create({game:'drop',seed:5,mode:'practice',dropPhysics:6});
      w.balls=[ball(1,5,180,100)];w.nextId=1;W.advance(w,1800);
      const b=w.balls[0],first=b.nodes.map(p=>[p.x,p.y]);W.advance(w,600);
      return {sleep:b.sleep,area:b.nodes.reduce((s,p,i)=>{const n=b.nodes[(i+1)%12];
        return s+(p.x*n.y-p.y*n.x)/2},0)/(ArcadeDropLab.unitArea*b.r*b.r),
        bottom:Math.max(...b.nodes.map(p=>p.y)),
        drift:Math.max(...b.nodes.map((p,i)=>Math.hypot(p.x-first[i][0],p.y-first[i][1])))};""")
    assert value["sleep"] and value["drift"] < 0.01
    assert 0.94 < value["area"] < 1.04
    assert value["bottom"] == pytest.approx(416, abs=0.01)


def test_merge_counts_once_and_final_creatures_do_not_merge_again():
    result = inspect("""
      const W=ArcadeWorld,w=W.create({game:'drop',seed:5,mode:'practice',dropPhysics:6});
      w.balls=[ball(1,2,160,370),ball(2,2,200,370)];w.nextId=2;
      W.advance(w,600);const first={count:w.balls.length,level:w.balls[0].level,score:w.score};
      w.balls=[ball(3,7,95,335),ball(4,7,235,335)];w.nextId=4;W.advance(w,600);
      return {first,count:w.balls.length,levels:w.balls.map(b=>b.level)};""")
    assert result["first"] == dict(count=1, level=3, score=16)
    assert result["count"] == 2 and result["levels"] == [7, 7]


@pytest.mark.parametrize(
    "arena", ["classic", "bowl", "slopes", "pins", "arch", "saddle", "tilt", "wave"]
)
def test_long_drop_trace_stays_finite_bounded_and_verifiable(arena):
    setup = dict(
        game="drop",
        seed=71,
        mode="practice",
        device="keyboard",
        dropPhysics=6,
        clockRules=2,
        arena=arena,
    )
    replay = trace(
        setup,
        """for(let i=0;i<130&&!w.ended;i++){
      send({type:'tap',x:25+(i*83)%310});W.advance(w,45);
      for(const b of w.balls){
        if(![b.x,b.y,b.vx,b.vy,...b.nodes.flatMap(p=>[p.x,p.y])].every(Number.isFinite))
          throw Error('Non-finite soft body');
        if(b.nodes.some(p=>p.x<11.99||p.x>348.01||
          p.y>ArcadeDropLab.get(w.arena).height(p.x)+.01))throw Error('Outside capsule');
        const area=b.nodes.reduce((s,p,i)=>{const n=b.nodes[(i+1)%12];
          return s+(p.x*n.y-p.y*n.x)/2},0)/(ArcadeDropLab.unitArea*b.r*b.r);
        if(area<.70||area>1.15)throw Error('Lost volume '+area);
      }
    }""",
    )
    assert replay["report"]["details"]["physics"] == "lab6"
    assert arcade_runtime.verify(setup, replay["events"], replay["ticks"]) == replay["report"]


@pytest.mark.parametrize("width,height", [(320, 568), (390, 600), (1440, 900)])
def test_touch_aim_release_cancel_and_new_board_fit_on_webkit(arcade, width, height):
    page, store = arcade
    page.set_viewport_size(dict(width=width, height=height))
    page.evaluate("""()=>{
      window.dropInputs=[];
      const mount=ArcadeDropLabView.mount;
      ArcadeDropLabView.mount=(stage,send,options)=>mount(stage,a=>{
        dropInputs.push(a);send(a);
      },options);
    }""")
    page.locator('.game-card[data-game="drop"]').click()
    assert page.locator(".arcade-menu-art canvas").is_visible()
    page.locator('[data-mode="practice"]').click()
    assert page.locator("[data-arena]").count() == 8
    arena = {320: "arch", 390: "wave", 1440: "saddle"}[width]
    page.locator(f'[data-arena="{arena}"]').click()
    page.locator("[data-practice-start]").click()
    page.locator("#gameClock b").wait_for()
    canvas = page.locator(".drop-lab-canvas")
    page.wait_for_timeout(150)
    box = canvas.bounding_box()
    assert box["y"] >= 0 and box["y"] + box["height"] <= height
    # Holding and cancelling must not record a throw.
    page.mouse.move(box["x"] + box["width"] * 0.2, box["y"] + box["height"] * 0.5)
    canvas.evaluate("c=>c.addEventListener('pointerdown',e=>window.lastDropPointer=e.pointerId)")
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 0.75, box["y"] + box["height"] * 0.5)
    page.wait_for_timeout(100)
    assert page.evaluate("dropInputs.length") == 0
    canvas.evaluate("""c=>c.dispatchEvent(new PointerEvent('pointercancel',{
      pointerId:lastDropPointer,bubbles:true}))""")
    page.mouse.up()
    assert page.evaluate("dropInputs.length") == 0
    page.mouse.down()
    page.mouse.up()
    assert page.evaluate("dropInputs.length") == 1
    assert page.evaluate("dropInputs[0].x") == pytest.approx(270, abs=1)
    page.wait_for_timeout(800)
    captures = Path(__file__).parents[1] / ".deploy_tmp/drop-rebuild"
    captures.mkdir(exist_ok=True)
    page.locator(".game-dialog").screenshot(path=str(captures / f"live-{width}.png"))
    page.on("dialog", lambda d: d.accept())
    page.locator(".game-close").click()
    page.locator(".game-dialog").wait_for(state="detached")
    with store.db() as db:
        row = db.execute(
            "SELECT setup FROM arcade_sessions ORDER BY created DESC LIMIT 1"
        ).fetchone()
        assert json.loads(row["setup"])["dropPhysics"] == 6
        assert json.loads(row["setup"])["arena"] == arena


def test_compact_pile_uses_particle_outline_and_keeps_creatures_readable(arcade):
    page, _ = arcade
    page.set_viewport_size(dict(width=390, height=650))
    page.evaluate("""()=>{
      const W=ArcadeWorld,w=W.create({game:'drop',seed:41,mode:'practice',dropPhysics:6});
      w.balls=[[1,2,42,380],[2,3,105,375],[3,4,193,365],[4,2,299,382],
        [5,5,260,290],[6,1,140,295]].map(([id,level,x,y])=>({id,level,x,y,
          r:W.rad[level],vx:0,vy:0,angle:0,spin:0,age:0}));
      w.nextId=6;W.advance(w,1200);
      const d=document.createElement('dialog');d.id='dropPile';d.className='game-dialog';
      d.dataset.game='drop';
      d.innerHTML='<header><h2>Космодроп</h2></header><div class="game-stage"></div>';
      document.body.append(d);d.showModal();const abort=new AbortController();
      const view=ArcadeView.mount('drop',d.lastElementChild,()=>{},
        {signal:abort.signal,dropPhysics:6,readOnly:true,paused:()=>true,quality:()=> 'high'});
      view.update(w,0);ArcadePersonality.decorate({dialog:d,g:{id:'drop'},view});
      window.dropPileCheck={abort,w};
    }""")
    captures = Path(__file__).parents[1] / ".deploy_tmp/drop-rebuild"
    captures.mkdir(exist_ok=True)
    page.wait_for_timeout(150)
    page.locator("#dropPile").screenshot(path=str(captures / "pile.png"))
    page.evaluate('dropPileCheck.abort.abort();document.querySelector("#dropPile").remove()')
