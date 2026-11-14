"""Actual gameplay art: decoded actors, graceful fallback, and matching flight icons."""

from tests.test_arcade_server import arcade as arcade
from tests.test_arcade_server import browser as browser


def test_all_actors_decode_and_draw_with_transparent_surroundings(arcade):
    page, _ = arcade
    results = page.evaluate("""async()=>{
      const A=ArcadeWorldArt,out=[];
      for(const id of A.actors){
        const ready=await A.ready(id),canvas=document.createElement('canvas');
        canvas.width=160;canvas.height=160;const c=canvas.getContext('2d');
        const drawn=A.drawActor(c,id,80,80,80),pixels=c.getImageData(0,0,160,160).data;
        let count=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i])count++;
        out.push({id,ready,drawn,count,corner:pixels[3]});
      }
      return out;
    }""")
    assert len(results) == 19
    for result in results:
        assert result["ready"] and result["drawn"], result
        assert result["count"] > 1000, result
        assert result["corner"] == 0, result


def test_failed_illustration_requests_do_not_stop_gameplay(arcade):
    page, _ = arcade
    page.route("**/worlds/**", lambda route: route.abort())
    page.locator('.game-card[data-game="orbit"]').click()
    page.locator('[data-mode="practice"]').click()
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
    canvas = page.locator(".frame-orbit canvas")
    assert canvas.evaluate("n=>n.width>0&&n.height>0")
    page.wait_for_function("document.querySelector('#gameClock b')?.textContent!=='0:00'")
    assert canvas.is_visible()
    page.locator(".game-close").click()


def test_tall_phone_keeps_fields_compact_and_driving_fills_the_available_space(arcade):
    page, _ = arcade
    page.set_viewport_size(dict(width=390, height=844))
    for game in ("orbit", "bugs", "hill"):
        page.locator(f'.game-card[data-game="{game}"]').click()
        page.locator('[data-mode="practice"]').click()
        if page.locator("[data-practice-start]").count():
            page.locator("[data-practice-start]").first.click()
        page.wait_for_function("document.querySelector('#gameClock b')?.textContent.length>0")
        page.wait_for_timeout(100)
        gap = page.locator(".game-stage").evaluate("""n=>{
          const child=n.querySelector('.hill-drive,.arcade-canvas-frame');
          const css=getComputedStyle(n);
          // Floating instruments now live inside the illustrated stage's safe area.
          return n.clientHeight-child.getBoundingClientRect().height
            -parseFloat(css.paddingTop)-parseFloat(css.paddingBottom);
        }""")
        assert 0 <= gap <= 12, (game, gap)
        box = page.locator("#gameDialog").bounding_box()
        assert box["y"] >= 0 and box["y"] + box["height"] <= 844
        page.locator(".game-close").click()


def test_all_eight_marble_illustrations_decode(arcade):
    page, _ = arcade
    sizes = page.evaluate("""async()=>{
      const out=[];for(let i=0;i<8;i++){
        const image=new Image();image.src='/miniapp/static/worlds/marble-'+i+'.svg';
        await image.decode();out.push([image.naturalWidth,image.naturalHeight]);
      }return out;
    }""")
    assert sizes == [[100, 100]] * 8


def test_missing_marble_images_preserve_visible_playable_balls(arcade):
    page, _ = arcade
    page.route("**/worlds/marble-*.svg*", lambda route: route.abort())
    page.locator('.game-card[data-game="sort"]').click()
    with page.expect_request("**/worlds/marble-*.svg*"):
        page.locator('[data-mode="practice"]').click()
    ball = page.locator(".sort-ball").first
    ball.wait_for()
    assert ball.evaluate("n=>getComputedStyle(n).backgroundColor") != "rgba(0, 0, 0, 0)"
    assert ball.locator("small,svg").count() == 0
    page.locator(".game-close").click()


def test_four_vehicle_bodies_load_repaint_and_preserve_the_simulation(arcade):
    page, _ = arcade
    page.evaluate("""()=>{
      window.vehicleArtProbe=()=>{
        const results=[];
        for(const id of ['scout','buggy','truck','rover']){
          const h=ArcadeWorld.create({game:'hill',mode:'practice',seed:17,hill:{car:id}}).hill,
            before=JSON.stringify(h),canvas=document.createElement('canvas');
          canvas.width=320;canvas.height=240;const c=canvas.getContext('2d');
          c.translate(160,140);c.scale(45,-45);
          if(!ArcadeWorldArt.vehicle(c,h))return null;
          const first=c.getImageData(0,0,320,240).data;
          c.save();c.resetTransform();c.clearRect(0,0,320,240);c.restore();
          const painted={...h,paint:'#315fc8'};
          if(!ArcadeWorldArt.vehicle(c,painted))return null;
          const second=c.getImageData(0,0,320,240).data;
          let difference=0;for(let i=0;i<first.length;i+=4)
            difference+=Math.abs(first[i]-second[i])+Math.abs(first[i+2]-second[i+2]);
          results.push({id,difference,corner:second[3],unchanged:before===JSON.stringify(h)});
        }return results;
      };
    }""")
    page.wait_for_function("vehicleArtProbe()!==null")
    for result in page.evaluate("vehicleArtProbe()"):
        assert result["difference"] > 1000, result
        assert result["corner"] == 0 and result["unchanged"], result
